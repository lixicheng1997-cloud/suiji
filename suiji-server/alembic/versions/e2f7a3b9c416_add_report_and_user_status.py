"""管理后台地基：report 举报表 + user.status 停用列

Revision ID: e2f7a3b9c416
Revises: c9d5f3a1b27e
Create Date: 2026-11-18 12:00:00.000000

说明：与既有迁移同风格——全部判存幂等，与 create_all 兜底共存不冲突：
    - 新库：main.py 启动时 Base.metadata.create_all 已建出 report 表与带 status 的 user 表，
      本迁移检测到已存在即跳过，只记录版本号；
    - 老库：补建表 / 补列。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2f7a3b9c416'
down_revision: Union[str, None] = 'c9d5f3a1b27e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspect():
    return sa.inspect(op.get_bind())


def _tables() -> set:
    return set(_inspect().get_table_names())


def _columns(table: str) -> set:
    return ({c["name"] for c in _inspect().get_columns(table)}
            if table in _tables() else set())


def upgrade() -> None:
    if "report" not in _tables():
        op.create_table(
            "report",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("family_id", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("reporter_id", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("reporter_name", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("target_type", sa.String(length=16), nullable=False, server_default="entry"),
            sa.Column("target_id", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("reason", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("detail", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
            sa.Column("handler_id", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("handler_name", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("handle_action", sa.String(length=16), nullable=False, server_default=""),
            sa.Column("handle_note", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("created_at", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("handled_at", sa.String(length=32), nullable=False, server_default=""),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_report_family_id", "report", ["family_id"])
        op.create_index("ix_report_reporter_id", "report", ["reporter_id"])
        op.create_index("ix_report_target_id", "report", ["target_id"])
        op.create_index("ix_report_status", "report", ["status"])
        op.create_index("ix_report_created_at", "report", ["created_at"])
    if "user" in _tables() and "status" not in _columns("user"):
        op.add_column(
            "user",
            sa.Column("status", sa.Integer(), nullable=False, server_default=sa.text("0")),
        )
        if op.get_bind().dialect.name == "postgresql":
            op.alter_column("user", "status", existing_type=sa.Integer(), server_default=None)


def downgrade() -> None:
    if "report" in _tables():
        op.drop_index("ix_report_created_at", table_name="report")
        op.drop_index("ix_report_status", table_name="report")
        op.drop_index("ix_report_target_id", table_name="report")
        op.drop_index("ix_report_reporter_id", table_name="report")
        op.drop_index("ix_report_family_id", table_name="report")
        op.drop_table("report")
    if "user" in _tables() and "status" in _columns("user"):
        op.drop_column("user", "status")
