"""数据库引擎与会话：SQLAlchemy 2.x 同步；SQLite 兜底 / PostgreSQL 生产。

本地开发（直接 `python app/main.py`）时，若配置的数据库驱动缺失或连不上，
会降级到项目根 data/suiji.db 的 SQLite 并打印告警，保证服务能起来。
"""
import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings

logger = logging.getLogger("suiji.db")


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        else:
            # 文件库：确保父目录存在
            db_file = url.split("sqlite:///")[-1]
            Path(db_file).parent.mkdir(parents=True, exist_ok=True)
        return kwargs
    return {"pool_pre_ping": True}


def _create_engine_for(url: str):
    return create_engine(url, **_engine_kwargs(url))


def _make_engine():
    url = settings.database_url
    try:
        engine = _create_engine_for(url)
        with engine.connect() as conn:  # 启动即探测连通性，失败才能及时降级
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as exc:
        if not settings.allow_fallback:
            raise
        fallback = settings.sqlite_fallback_url
        if fallback == url:  # 本身就是 SQLite 且不可用：不再降级，交给请求期报错
            raise
        logger.warning("数据库不可用（%s）：%s；降级到本地 SQLite：%s", url, exc, fallback)
        settings.database_url = fallback  # 保持一致，便于日志/迁移看到真实库
        return _create_engine_for(fallback)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI 依赖：请求级会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
