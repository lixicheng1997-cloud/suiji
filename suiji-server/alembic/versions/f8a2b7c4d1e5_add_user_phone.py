"""号码认证登录：user 增加 phone（密文）与 phone_hash（确定性唯一键）

Revision ID: f8a2b7c4d1e5
Revises: e2f7a3b9c416
Create Date: 2026-11-19 12:00:00.000000

说明：与既有迁移同风格——全部判存幂等，与 create_all 兜底共存不冲突：
    - 新库：main.py 启动 create_all 已建出带 phone/phone_hash 与部分唯一索引的 user 表，
      本迁移检测到已存在即跳过，只记录版本号；
    - 老库：补列 + 补部分唯一索引。phone 为 AES-GCM 密文（EncryptedString 落库宽度
      明文 32 → 256），老用户两列均为空串，无需回填。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f8a2b7c4d1e5'
down_revision: Union[str, None] = 'e2f7a3b9c416'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspect():
    return sa.inspect(op.get_bind())


def _tables() -> set:
    return set(_inspect().get_table_names())


def _columns(table: str) -> set:
    return ({c["name"] for c in _inspect().get_columns(table)}
            if table in _tables() else set())


def _indexes(table: str) -> set:
    return ({ix["name"] for ix in _inspect().get_indexes(table)}
            if table in _tables() else set())


def upgrade() -> None:
    if "user" in _tables():
        cols = _columns("user")
        if "phone" not in cols:
            # 宽度对齐 EncryptedString 落库口径：明文 32 字符 → 32*1.4+64 ≈ 256
            op.add_column("user", sa.Column("phone", sa.String(length=256),
                                            nullable=False, server_default=""))
        if "phone_hash" not in cols:
            op.add_column("user", sa.Column("phone_hash", sa.String(length=64),
                                            nullable=False, server_default=""))
        if "uq_user_phone_hash" not in _indexes("user"):
            # 部分唯一索引：仅 phone_hash 非空的行参与唯一约束（老用户空串共存）
            op.create_index(
                "uq_user_phone_hash", "user", ["phone_hash"], unique=True,
                sqlite_where=sa.text("phone_hash != ''"),
                postgresql_where=sa.text("phone_hash != ''"),
            )


def downgrade() -> None:
    if "user" in _tables():
        if "uq_user_phone_hash" in _indexes("user"):
            op.drop_index("uq_user_phone_hash", table_name="user")
        cols = _columns("user")
        if "phone_hash" in cols:
            op.drop_column("user", "phone_hash")
        if "phone" in cols:
            op.drop_column("user", "phone")
