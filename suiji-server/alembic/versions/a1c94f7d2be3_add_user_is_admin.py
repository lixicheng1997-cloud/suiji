"""add user.is_admin（系统管理员标记）

Revision ID: a1c94f7d2be3
Revises: 48da6530eef1
Create Date: 2026-10-28 10:30:00.000000

说明：is_admin 列此前由两条路径产生，本迁移必须与它们共存而不冲突：
    - 新库：app/main.py 启动时 Base.metadata.create_all 建表，模型里已含该列；
    - 老库：app/services/admin_service.py::_ensure_column 启动时手工 ALTER TABLE 补列。
因此升级前判存：表不存在或列已存在都直接跳过，只记录版本号。

与模型的对应关系（app/models/models.py::User.is_admin）：
    mapped_column(Integer, default=0)  →  INTEGER NOT NULL，且无 server default
（default 是 Python 侧默认值，不落库）。SQLite 不支持 DROP DEFAULT，
所以只在 PostgreSQL 上回收 server_default，SQLite 保留 DEFAULT 0 不影响读写。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1c94f7d2be3'
down_revision: Union[str, None] = '48da6530eef1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _user_columns() -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user")}


def upgrade() -> None:
    if "user" not in _tables():
        # 本项目的表结构主要由 create_all 兜底，纯迁移链里 user 可能尚未建立：
        # 此时无需补列，交给 create_all 建出带 is_admin 的完整表。
        return
    if "is_admin" in _user_columns():
        return
    op.add_column(
        "user",
        sa.Column("is_admin", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column("user", "is_admin", existing_type=sa.Integer(), server_default=None)


def downgrade() -> None:
    if "user" not in _tables() or "is_admin" not in _user_columns():
        return
    op.drop_column("user", "is_admin")
