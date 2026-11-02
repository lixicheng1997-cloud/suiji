"""add notification table（家人动态通知落库）

Revision ID: c3f81b2a9d47
Revises: a1c94f7d2be3
Create Date: 2026-10-29 10:00:00.000000

说明：家人动态通知从「客户端从 bootstrap feeds 本地合成」改为服务端按收件人
user_id 落库、读后即删（app/api/notifications.py）。本迁移必须与 create_all
共存——app/main.py 启动时 Base.metadata.create_all 会先建出该表（老库场景），
因此升级前判存：表已存在则只记录版本号，不重复建。

与模型的对应关系（app/models/models.py::Notification）：
    mapped_column(String, default=...) → 各列 NOT NULL，且无 server default
（default 是 Python 侧默认值，不落库）。索引与 create_all 命名一致：
ix_notification_family_id / ix_notification_user_id / ix_notification_created_at。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3f81b2a9d47'
down_revision: Union[str, None] = 'a1c94f7d2be3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = (
    ("ix_notification_family_id", "family_id"),
    ("ix_notification_user_id", "user_id"),
    ("ix_notification_created_at", "created_at"),
)


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "notification" in _tables():
        return
    op.create_table(
        "notification",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("family_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=64), nullable=False),
        sa.Column("content", sa.String(length=255), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("entry_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, col in _INDEXES:
        op.create_index(name, "notification", [col])


def downgrade() -> None:
    if "notification" not in _tables():
        return
    for name, _ in _INDEXES:
        op.drop_index(name, table_name="notification")
    op.drop_table("notification")
