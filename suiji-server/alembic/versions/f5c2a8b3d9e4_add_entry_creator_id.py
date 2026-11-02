"""entry.creator_id / entry.deleted_by_id：记录人与删除人的账号 ID

Revision ID: f5c2a8b3d9e4
Revises: e7a1c2f09b34
Create Date: 2026-10-30 18:30:00.000000

背景：记录人展示口径此前只有一串 creator 名字（客户端传的是注册昵称，服务端兜底
auth.name 同样是昵称），而成员表的 name 走 display_name（家长信息姓名优先）。
妈妈填了家长信息后两侧字符串对不上，主页 creatorLabel 解析不到关系就回退「家人」。
加 ID 列让客户端能按 user_id 直查成员表，名字串只留作历史数据兜底。

历史行按 (family_id, 名字串 == user.name 或 user.username) 回填；同家庭重名时取一条，
回填不上的留空，由客户端继续走名字匹配兜底。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f5c2a8b3d9e4'
down_revision: Union[str, None] = 'e7a1c2f09b34'
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


def _backfill(bind, table: str, src_col: str, dst_col: str) -> int:
    """把名字串解析成 user_id：先按昵称匹配，再按账号名匹配（不透出账号，仅落 ID）。"""
    if table not in _inspect().get_table_names() or dst_col not in _columns(table):
        return 0
    users = list(bind.execute(sa.text("SELECT id, family_id, name, username FROM \"user\"")))
    rows = list(bind.execute(sa.text(f"SELECT id, family_id, {src_col} FROM {table} WHERE {src_col} IS NOT NULL AND {src_col} <> ''")))
    updated = 0
    for rid, family_id, name in rows:
        if not name:
            continue
        hit = next((u for u in users if u[1] == family_id and u[2] and u[2] == name), None)
        if hit is None:
            hit = next((u for u in users if u[1] == family_id and u[3] and u[3] == name), None)
        if hit is None:
            continue
        bind.execute(sa.text(f"UPDATE {table} SET {dst_col} = :uid WHERE id = :rid"), {"uid": hit[0], "rid": rid})
        updated += 1
    return updated


def upgrade() -> None:
    _add_column("entry", "creator_id", sa.Column("creator_id", sa.String(length=32), nullable=False, server_default=""), True)
    _add_column("entry", "deleted_by_id", sa.Column("deleted_by_id", sa.String(length=32), nullable=True), False)
    bind = op.get_bind()
    _backfill(bind, "entry", "creator", "creator_id")
    _backfill(bind, "entry", "deleted_by", "deleted_by_id")


def downgrade() -> None:
    for name in ("deleted_by_id", "creator_id"):
        if name in _columns("entry"):
            if name == "creator_id":
                op.drop_index("ix_entry_creator_id", table_name="entry")
            op.drop_column("entry", name)
