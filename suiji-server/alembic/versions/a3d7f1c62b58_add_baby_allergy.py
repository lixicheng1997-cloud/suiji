"""baby.allergy：宝宝过敏史落库列

Revision ID: a3d7f1c62b58
Revises: f5c2a8b3d9e4
Create Date: 2026-10-31 09:10:00.000000

背景：家长档案页的「过敏史」输入框（baby.vue）一直在提交 allergy，但 baby 表没有这一列、
_UPDATABLE 也不认它，服务端静默丢弃、baby_row 也回不来——用户写完保存，重启应用就没了，
baby-list 页的过敏史展示行永远不出现。补一列，加密口径与 entry.note 一致（健康信息）。

列宽按 core/field_crypto.py 的 EncryptedString 公式 int(明文长度*1.4)+64 给出，
对应模型里的 EncryptedString(2048)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3d7f1c62b58'
down_revision: Union[str, None] = 'f5c2a8b3d9e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "baby" not in insp.get_table_names():
        return
    if "allergy" in {c["name"] for c in insp.get_columns("baby")}:
        return
    op.add_column("baby", sa.Column("allergy", sa.String(length=2931),
                                    nullable=False, server_default=""))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "baby" in insp.get_table_names() and "allergy" in {c["name"] for c in insp.get_columns("baby")}:
        op.drop_column("baby", "allergy")
