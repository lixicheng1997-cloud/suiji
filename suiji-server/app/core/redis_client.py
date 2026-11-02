"""Idempotency-Key 去重存储（契约 §16）：优先 Redis（SETNX+TTL 24h），异常降级进程内存。"""
import json
import time
from typing import Optional

from .config import settings

TTL_SECONDS = 24 * 3600
# Redis 故障后重新探测的间隔（秒）：降级是临时的，到点必须重试
_REDIS_RETRY_INTERVAL = 30.0


class IdempotencyStore:
    """幂等去重存储；Redis 不可用时降级内存，但到点会重试恢复（不永久降级）。"""

    def __init__(self) -> None:
        self._redis = None
        self._redis_retry_at = 0.0
        # 内存兜底：key -> (json_str, 过期时间戳)
        self._mem: dict[str, tuple[str, float]] = {}
        self._connect()

    # ---------- 后端选择 ----------
    def _connect(self) -> None:
        self._redis_retry_at = time.time() + _REDIS_RETRY_INTERVAL
        if not settings.redis_url:
            return
        try:
            import redis  # 局部导入：未装/不可达时静默降级

            client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            client.ping()
            self._redis = client
        except Exception:
            self._redis = None

    def _ensure_backend(self) -> None:
        if self._redis is not None or time.time() < self._redis_retry_at:
            return
        self._connect()

    @staticmethod
    def _rkey(family_id: str, key: str) -> str:
        return f"idem:{family_id}:{key}"

    def _mem_get(self, rk: str) -> Optional[dict]:
        item = self._mem.get(rk)
        if not item:
            return None
        value, expire_at = item
        if time.time() >= expire_at:
            self._mem.pop(rk, None)
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    def get(self, family_id: str, key: str) -> Optional[dict]:
        rk = self._rkey(family_id, key)
        self._ensure_backend()
        if self._redis is not None:
            try:
                raw = self._redis.get(rk)
                return json.loads(raw) if raw else None
            except Exception:
                self._redis = None
                self._redis_retry_at = time.time() + _REDIS_RETRY_INTERVAL
        return self._mem_get(rk)

    def set(self, family_id: str, key: str, value: dict) -> None:
        rk = self._rkey(family_id, key)
        raw = json.dumps(value, ensure_ascii=False)
        self._ensure_backend()
        if self._redis is not None:
            try:
                self._redis.set(rk, raw, ex=TTL_SECONDS)
                return
            except Exception:
                self._redis = None
                self._redis_retry_at = time.time() + _REDIS_RETRY_INTERVAL
        # 顺带清理过期项，防止长跑进程内存膨胀
        now = time.time()
        for k in [k for k, (_, exp) in self._mem.items() if exp <= now]:
            self._mem.pop(k, None)
        self._mem[rk] = (raw, now + TTL_SECONDS)


idem_store = IdempotencyStore()
