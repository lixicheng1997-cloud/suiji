"""add family.events_version（家庭事件水位，感知删除/修改）

Revision ID: d4e9f2a1b6c7
Revises: c3f81b2a9d47
Create Date: 2026-10-30 10:00:00.000000

说明：客户端 /events/count 水位原来只比 entry.id，软删/恢复/修改不改 id，
家人轮询永远感知不到。family.events_version 在 entry 任何写操作后 +1，
客户端水位同时存 entry_id 与 version，任一变化就重拉 bootstrap。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4e9f2a1b6c7'
down_revision: Union[str, None] = 'b7d3f92e4a15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('family')}
    if 'events_version' in cols:
        return
    op.add_column('family',
                  sa.Column('events_version', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('family')}
    if 'events_version' not in cols:
        return
    op.drop_column('family', 'events_version')
