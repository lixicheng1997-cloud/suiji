"""基础可观测性：进程内指标注册表 + 就绪探测（P0-B，不引入新依赖）。

指标以 Prometheus 文本格式从 `/metrics` 暴露；不依赖 prometheus-client，
用最小计数器/直方图实现，后续换正式客户端时保持端点与指标名不变。

端点分工：
  - `/healthz`  存活探针（liveness）：进程能响应即 200，不探测外部依赖；
  - `/readyz`   就绪探针（readiness）：探测数据库等硬依赖，失败返回 503；
  - `/metrics`  指标文本（受 METRICS_ENABLED 开关控制，生产应在反代层限制访问）。
"""
from __future__ import annotations

import os
import time
from typing import Optional

from .config import settings

APP_VERSION = "3.0.0"
_PROCESS_START_TS = time.time()

# 耗时分桶（秒）：覆盖快接口到慢 LLM 请求
_HIST_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)


def _escape_label(value: str) -> str:
    """转义 Prometheus 标签值中的反斜杠、引号、换行。"""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )


class _Registry:
    """最小内存注册表：计数器 + 简单直方图 + 静态 gauge。"""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._hist_buckets: dict[float, int] = {b: 0 for b in _HIST_BUCKETS}
        self._hist_count = 0
        self._hist_sum = 0.0
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}

    def inc_counter(self, name: str, labels: dict[str, str], value: float = 1) -> None:
        key = (name, tuple(sorted(labels.items())))
        self._counters[key] = self._counters.get(key, 0) + value

    def observe_duration(self, seconds: float) -> None:
        self._hist_count += 1
        self._hist_sum += seconds
        for b in _HIST_BUCKETS:
            if seconds <= b:
                self._hist_buckets[b] += 1

    def set_gauge(self, name: str, labels: dict[str, str], value: float) -> None:
        key = (name, tuple(sorted(labels.items())))
        self._gauges[key] = value

    @staticmethod
    def _labels_str(labels: tuple[tuple[str, str], ...]) -> str:
        if not labels:
            return ""
        inner = ",".join(f'{k}="{_escape_label(v)}"' for k, v in labels)
        return "{" + inner + "}"

    def render(self) -> str:
        lines: list[str] = []

        lines += [
            "# HELP suiji_http_requests_total 已处理 HTTP 请求数",
            "# TYPE suiji_http_requests_total counter",
        ]
        for (name, labels), val in sorted(self._counters.items()):
            if name != "suiji_http_requests_total":
                continue
            lines.append(f"suiji_http_requests_total{self._labels_str(labels)} {int(val)}")

        lines += [
            "# HELP suiji_http_request_duration_seconds 请求耗时（秒）",
            "# TYPE suiji_http_request_duration_seconds histogram",
        ]
        for b in _HIST_BUCKETS:
            lines.append(
                f"suiji_http_request_duration_seconds_bucket{{le=\"{b}\"}} {self._hist_buckets[b]}"
            )
        lines.append(f'suiji_http_request_duration_seconds_bucket{{le="+Inf"}} {self._hist_count}')
        lines.append(f"suiji_http_request_duration_seconds_sum {self._hist_sum:.6f}")
        lines.append(f"suiji_http_request_duration_seconds_count {self._hist_count}")

        for (name, labels), val in sorted(self._gauges.items()):
            lines.append(f"{name}{self._labels_str(labels)} {val}")

        lines.append(f"suiji_info{{version=\"{APP_VERSION}\"}} 1")
        lines.append(f"suiji_process_start_timestamp_seconds {_PROCESS_START_TS:.6f}")
        return "\n".join(lines) + "\n"


registry = _Registry()


def record_request(method: str, path: str, status: int, duration: float) -> None:
    registry.inc_counter(
        "suiji_http_requests_total",
        {"method": method, "path": path, "status": str(status)},
    )
    registry.observe_duration(duration)


def _backend_labels() -> dict[str, str]:
    """暴露各有状态后端当前实际走的后端（redis / memory），便于发现静默降级。"""
    labels: dict[str, str] = {}
    try:
        from .session_store import session_store
        labels["session"] = session_store.backend
    except Exception:
        labels["session"] = "unknown"
    try:
        from .rate_limit import rate_limiter
        labels["rate_limit"] = rate_limiter.backend
    except Exception:
        labels["rate_limit"] = "unknown"
    try:
        from .redis_client import idem_store
        labels["idempotency"] = idem_store.backend
    except Exception:
        labels["idempotency"] = "unknown"
    return labels


def check_readiness() -> tuple[bool, dict]:
    """探测硬依赖与关键后端；返回 (是否就绪, 明细)。

    数据库是硬依赖：不可用则 503。Redis / 存储异常记为 warning，不直接判失败
    （与启动容错策略一致：降级态仍可部分服务，但必须在明细里一眼可见）。
    """
    from . import startup_check
    from ..media.store import get_store

    details: dict[str, dict] = {}
    ready = True

    db_name, db_ok, db_detail = startup_check._check_database()
    details["database"] = {"ok": db_ok, "detail": db_detail}
    if db_ok is False:
        ready = False

    r_name, r_ok, r_detail = startup_check._check_redis()
    details["redis"] = {"ok": r_ok, "detail": r_detail}

    try:
        store = get_store()
        s_name, s_ok, s_detail = startup_check._check_storage(store)
    except Exception as exc:  # 存储初始化失败也记为 warning
        s_ok, s_detail = False, f"存储后端异常：{exc}"
    details["storage"] = {"ok": s_ok, "detail": s_detail}

    details["backends"] = _backend_labels()
    details["process"] = {"pid": os.getpid(), "uptime_seconds": round(time.time() - _PROCESS_START_TS, 3)}
    return ready, details
