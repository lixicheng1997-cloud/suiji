"""宝宝档案软删列：与 entry.deleted_at 同口径，回收站保留 30 天

Revision ID: c9d5f3a1b27e
Revises: b8c4e9f2a16d
Create Date: 2026-11-18 10:00:00.000000

背景：统一删除可恢复性口径（评审第 8 项）——
  - 记录（entry）：已有软删 + 回收站 + 30 天自动清理
  - 宝宝档案（baby）：补齐 deleted_at 列，支持软删 → 回收站 → 30 天清理
  - 关系解除（成员移除 / 退出家庭）：不进回收站，语义不同，本次不动
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d5f3a1b27e'
down_revision: Union[str, None] = 'b8c4e9f2a16d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspect():
    return sa.inspect(op.get_bind())


def _columns(table: str) -> set:
    return {c["name"] for c in _inspect().get_columns(table)} if table in _inspect().get_table_names() else set()


def upgrade() -> None:
    if "baby" in _inspect().get_table_names() and "deleted_at" not in _columns("baby"):
        op.add_column("baby", sa.Column("deleted_at", sa.String(length=32), nullable=True))


def downgrade() -> None:
    if "baby" in _inspect().get_table_names() and "deleted_at" in _columns("baby"):
        op.drop_column("baby", "deleted_at")
