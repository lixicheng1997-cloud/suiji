"""里程碑/日记 creator_id 归属列；移除 family.readonly 只读开关

Revision ID: b8c4e9f2a16d
Revises: a3d7f1c62b58
Create Date: 2026-11-12 10:00:00.000000

背景：两角色模型（v1.3）下权限收敛为 创建者/成员：
  - 里程碑、日记补 creator_id 归属列：成员仅可处置本人记录，创建者任意；
    里程碑系统预置清单行为空（家庭共享，成员均可勾选）。
  - family.readonly 家庭只读开关整体废弃：模型/接口/响应均已摘除，本迁移 drop 残留列。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8c4e9f2a16d'
down_revision: Union[str, None] = 'a3d7f1c62b58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspect():
    return sa.inspect(op.get_bind())


def _columns(table: str) -> set:
    return {c["name"] for c in _inspect().get_columns(table)} if table in _inspect().get_table_names() else set()


def _add_column(table: str, name: str, col: sa.Column, index: bool) -> None:
    if table not in _inspect().get_table_names() or name in _columns(table):
        return
    op.add_column(table, col)
    if index:
        op.create_index(f"ix_{table}_{name}", table, [name])


def _drop_column(table: str, name: str, index: bool = False) -> None:
    if table not in _inspect().get_table_names() or name not in _columns(table):
        return
    if index:
        try:
            op.drop_index(f"ix_{table}_{name}", table_name=table)
        except Exception:
            pass
    op.drop_column(table, name)


def upgrade() -> None:
    _add_column("milestone_record", "creator_id",
                 sa.Column("creator_id", sa.String(length=32), nullable=False, server_default=""), True)
    _add_column("ai_journal", "creator_id",
                sa.Column("creator_id", sa.String(length=32), nullable=False, server_default=""), True)
    _drop_column("family", "readonly")


def downgrade() -> None:
    if "family" in _inspect().get_table_names() and "readonly" not in _columns("family"):
        op.add_column("family", sa.Column("readonly", sa.Integer, nullable=False, server_default="0"))
    _drop_column("ai_journal", "creator_id", index=True)
    _drop_column("milestone_record", "creator_id", index=True)
