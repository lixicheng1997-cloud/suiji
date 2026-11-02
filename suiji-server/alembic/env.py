"""Alembic 迁移环境：连接串优先取环境变量 DATABASE_URL（与运行时同源）。"""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.core import settings as app_settings
from app.core.db import Base
import app.models  # noqa: F401  # 确保所有模型注册到 Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 运行时配置覆盖 alembic.ini 的空 url
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", app_settings.database_url))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：直连数据库执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
