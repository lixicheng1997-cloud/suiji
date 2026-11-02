"""岁记服务端入口：FastAPI + /api/v1 路由；启动时建表（Alembic 为正式迁移通道）与媒体目录。"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 日志配置放在业务导入之前：导入期的降级告警也能正常输出
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("suiji.startup")

if __package__ in (None, ""):
    # 支持 `python app/main.py` 直接启动：此时无父包，相对导入会报
    # "attempted relative import with no known parent package"，先把项目根目录
    # 加入 sys.path 并声明所属包，使下面的相对导入可正常解析。
    # （uvicorn --reload 的子进程通过 sys_path 继承，app.main 同样可被导入）
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "app"

# 内置 swagger-ui/redoc 静态资源，避免依赖公网 CDN（CDN 不可达时 /docs 会空白）；
# 依赖缺失时降级为原生 FastAPI，保证服务仍可启动。
try:
    from fastapi_offline import FastAPIOffline
except ImportError:  # pip install fastapi-offline
    FastAPIOffline = None
    logger.warning("未安装 fastapi-offline，/docs 将回退到 CDN 资源：pip install fastapi-offline")

from .api import api_router
from .core.config import BASE_DIR, settings
from .core.db import Base, engine
from .core.payload_crypto import PayloadCryptoMiddleware
from .core.startup_check import run_startup_checks
from .media.store import get_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 静态字段加密密钥：必须在 create_all / 任何 DB 写入之前初始化，
    # 否则首批落库的 Baby.name / Entry.note 会以明文落库，后续读出时无前缀按明文返回（兼容），
    # 但安全等级与加密数据不一致。密钥未配置时自动生成到 data/crypto/field_key.bin。
    from .core.field_crypto import field_crypto
    field_crypto.init(key_b64=settings.field_enc_key, key_file=settings.field_key_file)
    if field_crypto.enabled:
        logger.info("静态字段加密已启用（AES-256-GCM）")

    # 外部依赖（数据库 / 对象存储）不可用时只告警不中断启动：
    # 否则 /docs、/openapi.json 会随启动失败一起打不开，排查成本变高。
    try:
        Base.metadata.create_all(engine)  # create_all 兜底：开发/测试免迁移
    except Exception as exc:
        logger.warning("建表失败（数据库可能未就绪），服务已启动但数据接口会报错：%s", exc)
    # Alembic 迁移通道（RUN_MIGRATIONS=1 时启用）：先 create_all 建出缺失的**表**，
    # 再 upgrade head 补齐老库缺失的**列**并落版本号。迁移全部判存幂等，
    # 与 create_all 共存不冲突；失败只告警不中断启动，下次启动重试。
    if settings.run_migrations:
        try:
            from alembic import command
            from alembic.config import Config

            # script_location 锚定项目根：不受启动 cwd 影响（uvicorn 可从任意目录拉起）
            cfg = Config(str(BASE_DIR / "alembic.ini"))
            cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
            command.upgrade(cfg, "head")
            logger.info("数据库迁移已执行至最新版本（alembic upgrade head）")
        except Exception as exc:
            logger.warning("数据库迁移执行失败，服务已启动但表结构可能落后于模型：%s", exc)
    # 服务器地址配置（server_endpoint）：空表时按 static/config/servers.json 播种，
    # 否则客户端「选择服务器」下拉会是空的（暂无配置界面）。
    try:
        from .core.db import SessionLocal
        from .services.server_service import ensure_seed

        with SessionLocal() as db:
            ensure_seed(db)
    except Exception as exc:
        logger.warning("服务器地址配置播种失败，GET /servers 会在首次请求时重试：%s", exc)
    # 内置管理员账号：启动自动写入（幂等，已存在则只补标记不重置密码）。
    try:
        from .core.db import SessionLocal
        from .services.admin_service import ensure_admin

        with SessionLocal() as db:
            ensure_admin(db)
    except Exception as exc:
        logger.warning("内置管理员账号播种失败，下次启动重试：%s", exc)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    store = None
    try:
        store = get_store()  # 预热存储后端：MinIO 会在此自动建桶（失败则告警，后续读写重试）
    except Exception as exc:
        logger.warning("存储后端预热失败，后续读写会重试：%s", exc)
    # 外部依赖体检：PostgreSQL / Redis / MinIO / Nginx 等逐项探测并打日志
    # （失败只告警不中断启动，与上面各步骤的容错策略一致）
    run_startup_checks(store)
    # 到期数据清理：回收站/AI 日记草稿超 30 天、操作留痕超 180 天、注销冷静期到期账号
    # （失败不中断启动）
    sweep_task: asyncio.Task | None = None
    try:
        from .core.db import SessionLocal
        from .services.cleanup_service import SWEEP_INTERVAL_SECONDS, purge_expired, purge_old_notifications

        def _run_sweep_once() -> None:
            try:
                with SessionLocal() as db:
                    purge_expired(db)
                    purge_old_notifications(db)
            except Exception as exc:
                logger.warning("定时清理本轮失败，%d 秒后重试：%s", SWEEP_INTERVAL_SECONDS, exc)

        # 启动即先跑一次
        _run_sweep_once()

        async def _sweep_loop():
            while True:
                await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
                await asyncio.to_thread(_run_sweep_once)

        sweep_task = asyncio.create_task(_sweep_loop(), name="suiji-sweeper")
        logger.info("后台定时清理任务已启动（间隔 %d 秒）", SWEEP_INTERVAL_SECONDS)
    except Exception as exc:
        logger.warning("定时清理任务启动失败（仅启动时清理会跑一次）：%s", exc)

    try:
        yield
    finally:
        if sweep_task is not None:
            sweep_task.cancel()
            try:
                await sweep_task
            except (asyncio.CancelledError, Exception):
                pass


app = (FastAPIOffline or FastAPI)(title="岁记服务端", version="3.0.0", lifespan=lifespan)

# CORS：默认不开放。
#
# 客户端（App / 小程序）不走浏览器，请求不带 Origin，本来就不需要 CORS；
# 服务端与 H5 也通过 nginx 同源部署。开着 `allow_origins=["*"]` 等于允许任意站点
# 在浏览器里直接调本 API（allow_headers=["*"] 还放行 Authorization），
# 是纯粹多出来的攻击面。确实需要跨域（H5 独立域名）时用 CORS_ORIGINS 显式列出。
_cors_origins = settings.cors_origins
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,   # 含 "*" 时 Starlette 走 allow-all 分支
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        # X-Sj-Enc 是传输加密的密钥材料头（见 core/crypto.py）：H5 跨域调试时不放行它，
        # 浏览器会把自定义头判成非简单请求并拦掉，加密请求直接发不出去。
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Sj-Enc"],
    )
    logger.info("CORS 已启用，放行来源：%s", ", ".join(_cors_origins))
else:
    # 必须显式提示：CORS 关着的时候浏览器只报一句笼统的
    # "blocked by CORS policy"，排查时根本想不到是服务端没开。
    logger.info(
        "CORS 未启用（CORS_ORIGINS 为空）：浏览器从不同源（如 H5 开发服务器 "
        "http://localhost:5173）调用本接口会被拦截。需要跨域时设 CORS_ORIGINS。"
    )


# swagger / redoc 是真正的网页（要加载同域 JS/CSS 并跑内联脚本），
# 不能下发 API 用的 default-src 'none'——那会让页面整块白屏。
# 关键点：多份 CSP 是「与」的关系（必须全部满足），只要有一处仍是 'none' 就全盘拦死，
# 所以后端这一层必须自己给出宽松策略，不能指望网关覆盖。
_DOC_PATHS = ("/docs", "/redoc", "/static-offline-docs")
_DOC_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src 'self' data:; connect-src 'self'; frame-ancestors 'self'"
)
_API_CSP = "default-src 'none'; frame-ancestors 'none'"


@app.middleware("http")
async def security_headers(request, call_next):
    """基础安全响应头（nginx 侧同样配了一份，这里是纵深防御）。

    nosniff 尤其重要：下载端点返回用户上传的字节，禁止浏览器把它猜成
    HTML 去执行，是防存储型 XSS 的最后一道。

    用赋值而不是 setdefault：保证同一响应里每个头只有一份值，
    避免与网关追加的同名头叠加成多值策略。
    """
    resp = await call_next(request)
    path = request.url.path or ""
    is_doc = any(path == p or path.startswith(p + "/") for p in _DOC_PATHS)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN" if is_doc else "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    resp.headers["Content-Security-Policy"] = _DOC_CSP if is_doc else _API_CSP
    return resp


app.include_router(api_router, prefix="/api/v1")

# 传输加密中间件放在最后注册 = 最外层（Starlette 的 add_middleware 是往头部插）：
# 它必须先于业务与 CORS 处理拿到原始密文，响应加密的包才能在往外传的路上不被改动。
# 未启用加密（cryptography 缺失 / CRYPTO_MODE=off）时它自动退化成透明转发。
app.add_middleware(PayloadCryptoMiddleware)


@app.get("/")
def root():
    return {"app": "suiji-server", "api": "/api/v1"}


if __name__ == "__main__":
    # 直接运行入口：python app/main.py（也支持 python -m app.main）
    # 可用环境变量覆盖：HOST / PORT / RELOAD（RELOAD=0 关闭热重载）
    import os
    from pathlib import Path

    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload_enabled = os.getenv("RELOAD", "1").strip().lower() not in ("0", "false", "no", "off")

    logger.info("岁记服务端启动：http://127.0.0.1:%d  |  API: /api/v1  |  文档: /docs", port)
    if reload_enabled:
        # 只监听 app/ 源码：避免 data/ 写媒体、日志触发无谓重启
        source_dir = str(Path(__file__).resolve().parents[1] / "app")
        uvicorn.run("app.main:app", host=host, port=port, reload=True, reload_dirs=[source_dir])
    else:
        # 非重载模式直接传 app 对象，避免模块被重复导入（引擎/连接各建一份）
        uvicorn.run(app, host=host, port=port)
