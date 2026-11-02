"""add server_endpoint（客户端可选服务器地址配置表）

Revision ID: 48da6530eef1
Revises:
Create Date: 2026-10-25 15:54:43.683444

说明：这是本项目的首个迁移版本（此前 alembic/versions 为空，历史表由
app/main.py 启动时 Base.metadata.create_all 建成）。因此建表前先判存：
    - 新库：本迁移建表；
    - 既有库（create_all 已建）：跳过建表，仅记录版本。
既有库等价操作：`alembic stamp head`。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '48da6530eef1'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("server_endpoint"):
        return
    op.create_table(
        "server_endpoint",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=255), nullable=False),
        sa.Column("env", sa.String(length=16), nullable=False),
        sa.Column("remark", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Integer(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_server_endpoint_url"), "server_endpoint", ["url"], unique=True)


def downgrade() -> None:
    if not _has_table("server_endpoint"):
        return
    op.drop_index(op.f("ix_server_endpoint_url"), table_name="server_endpoint")
    op.drop_table("server_endpoint")
