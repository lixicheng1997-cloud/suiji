"""启动期外部依赖探测：PostgreSQL / Redis / MinIO / Nginx / 本地存储 / 传输加密 / LLM。

与 lifespan 的容错策略一致：探测失败只打日志、不中断启动——依赖缺失时服务会
降级运行（SQLite / 进程内存 / 本地磁盘），但运维必须一眼看清「哪些依赖没起来、
当前实际跑在什么后端上」，否则「上传成功却看不到文件」这类静默降级极难排查。

探测串行且带短超时：只在启动时跑一次，不在请求路径上。
"""
import logging

import httpx

from .config import settings

logger = logging.getLogger("suiji.startup.check")

_PROBE_TIMEOUT = 3.0  # 单项探测上限（秒）：依赖挂掉时不能把启动卡死

# Nginx 网关探测地址（NGINX_PROBE_URL 留空时按顺序尝试）：
# - http://nginx/healthz       ：docker compose 内网，api 与 nginx 同网络走服务名
# - http://127.0.0.1:30080/... ：本机直连运行（python app/main.py），
#                                nginx 映射到宿主默认端口（NGINX_PORT 改过请显式配 NGINX_PROBE_URL）
_NGINX_FALLBACK_URLS = ("http://nginx/healthz", "http://127.0.0.1:30080/healthz")


def _check_database() -> tuple[str, bool | None, str]:
    from sqlalchemy import text

    from .db import engine

    dialect = engine.dialect.name
    try:
        with engine.connect() as conn:
            if dialect == "postgresql":
                ver = conn.execute(text("SHOW server_version")).scalar()
                return "PostgreSQL", True, f"{engine.url.render_as_string(hide_password=True)}（server {ver}）"
            ver = conn.execute(text("SELECT sqlite_version()")).scalar()
            return "数据库", None, (
                f"当前为 SQLite {ver}（{engine.url.database}）："
                "开发默认或 PostgreSQL 降级态；正式部署请确认 DATABASE_URL 指向 PG"
            )
    except Exception as exc:
        return "数据库", False, f"连接失败：{exc}"


def _check_redis() -> tuple[str, bool | None, str]:
    if not settings.redis_url:
        return "Redis", None, "未配置 REDIS_URL：幂等去重 / 会话撤销 / 限流走进程内存"
    try:
        import redis  # 局部导入：依赖缺失只影响本项探测

        client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=_PROBE_TIMEOUT,
            socket_timeout=_PROBE_TIMEOUT,
        )
        client.ping()
        ver = client.info("server").get("redis_version", "?")
        return "Redis", True, f"version {ver}"
    except ImportError:
        return "Redis", False, "已配置但依赖缺失：pip install redis（相关功能降级进程内存）"
    except Exception as exc:
        return "Redis", False, f"不可用：{exc.__class__.__name__}（相关功能降级进程内存）"


def _check_storage(store) -> tuple[str, bool | None, str]:
    from ..media.store import LocalMediaStore, MinioMediaStore

    if settings.media_backend == "minio":
        if isinstance(store, MinioMediaStore):
            # 构造时已探测并建桶（_ensure_bucket probe），能拿到实例即就绪
            return "MinIO", True, f"endpoint={store.endpoint} bucket={store.bucket}（桶已就绪）"
        if isinstance(store, LocalMediaStore):
            return "MinIO", False, (
                f"对象存储不可用，已降级本地磁盘：{store.base_dir}"
                "（文件不会进 MinIO，接口仍返回成功，务必排查）")
        return "MinIO", False, "存储后端初始化失败（见上方告警），文件读写将在请求期重试"
    # local 后端：探测媒体目录可写
    probe = settings.media_dir / ".write_probe"
    try:
        settings.media_dir.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"")
        probe.unlink(missing_ok=True)
        return "本地存储", True, f"{settings.media_dir}（可写）"
    except Exception as exc:
        return "本地存储", False, f"{settings.media_dir} 不可写：{exc}"


def _check_nginx() -> tuple[str, bool | None, str]:
    urls = [settings.nginx_probe_url] if settings.nginx_probe_url else list(_NGINX_FALLBACK_URLS)
    last_err = ""
    for url in urls:
        try:
            resp = httpx.get(url, timeout=_PROBE_TIMEOUT)
            if resp.status_code == 200:
                return "Nginx", True, f"{url} → 200（对外入口已就绪）"
            last_err = f"{url} → HTTP {resp.status_code}"
        except Exception as exc:
            last_err = f"{url} → {exc.__class__.__name__}"
    return "Nginx", False, (
        f"网关不可达（{last_err}）：api 直连仍可用；"
        "本机开发未启动 nginx 属正常，容器部署请检查 nginx 服务状态")


def _check_crypto() -> tuple[str, bool | None, str]:
    from .crypto import crypto

    if crypto.enabled:
        return "传输加密", True, f"mode={settings.crypto_mode} kid={crypto.kid}"
    if settings.crypto_mode == "off":
        return "传输加密", None, "CRYPTO_MODE=off：敏感接口走明文"
    return "传输加密", False, f"未启用：{crypto.reason}"


def _check_llm() -> tuple[str, bool | None, str]:
    if settings.llm_configured:
        return "LLM", True, f"{settings.llm_api_base}（model={settings.llm_model}）"
    return "LLM", None, "未配置：日记生成走模板兜底"


def run_startup_checks(store) -> None:
    """逐项打印依赖状态，最后输出一行汇总，便于部署后 grep 排查。"""
    results = [
        _check_database(),
        _check_redis(),
        _check_storage(store),
        _check_nginx(),
        _check_crypto(),
        _check_llm(),
    ]
    marks = []
    for name, ok, detail in results:
        if ok is True:
            logger.info("[启动检测] %s 正常：%s", name, detail)
            marks.append(f"{name}=OK")
        elif ok is None:
            logger.info("[启动检测] %s 提示：%s", name, detail)
            marks.append(f"{name}=-")
        else:
            logger.warning("[启动检测] %s 异常：%s", name, detail)
            marks.append(f"{name}=FAIL")
    logger.info("[启动检测] 依赖汇总：%s", " | ".join(marks))
