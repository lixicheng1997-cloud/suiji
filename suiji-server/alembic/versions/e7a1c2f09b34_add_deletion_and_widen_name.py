"""add user.deletion_scheduled_at + widen baby.name for ciphertext

Revision ID: e7a1c2f09b34
Revises: d4e9f2a1b6c7
Create Date: 2026-10-30 10:10:00.000000

背景：
- 账号注销冷静期（TDD §十）：user.deletion_scheduled_at 记录计划删除时刻，
  空串=未申请；到期由 cleanup_service.purge_due_accounts 物理删除。
- 静态字段加密（TDD §十 P0）：baby.name 落库前 AES-256-GCM 加密，密文比明文
  长约 64 字节（nonce+tag+base64 膨胀），原 varchar(64) 装不下，扩到 varchar(256)。
  entry.note 本来就是 text 类型，无需扩容。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7a1c2f09b34'
down_revision: Union[str, None] = 'd4e9f2a1b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspect():
    return sa.inspect(op.get_bind())


def _columns(table: str) -> set:
    return {c["name"] for c in _inspect().get_columns(table)}


def upgrade() -> None:
    # 1. user.deletion_scheduled_at
    if "user" in _inspect().get_table_names() and "deletion_scheduled_at" not in _columns("user"):
        op.add_column(
            "user",
            sa.Column("deletion_scheduled_at", sa.String(length=32), nullable=False, server_default=""),
        )
        op.create_index("ix_user_deletion_scheduled_at", "user", ["deletion_scheduled_at"])

    # 2. baby.name 列宽扩容（密文需要）。PostgreSQL 下 alter column type 是元数据操作，很快。
    if "baby" in _inspect().get_table_names():
        op.execute("ALTER TABLE baby ALTER COLUMN name TYPE VARCHAR(256)")


def downgrade() -> None:
    if "user" in _inspect().get_table_names() and "deletion_scheduled_at" in _columns("user"):
        op.drop_index("ix_user_deletion_scheduled_at", table_name="user")
        op.drop_column("user", "deletion_scheduled_at")
    if "baby" in _inspect().get_table_names():
        op.execute("ALTER TABLE baby ALTER COLUMN name TYPE VARCHAR(64)")
