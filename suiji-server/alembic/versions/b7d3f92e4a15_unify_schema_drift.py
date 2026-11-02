"""unify schema drift：补齐 file_object / audit_log 表与 entry 软删列的迁移记录

Revision ID: b7d3f92e4a15
Revises: c3f81b2a9d47
Create Date: 2026-10-29 12:00:00.000000

背景：本项目表结构一直由 app/main.py 启动时的 Base.metadata.create_all 兜底，
create_all 只能补建缺失的**表**，补不了老库上缺失的**列**；而此前部分结构变更
（file_object、audit_log 两张表，entry 的软删列）没有对应的 alembic 迁移记录，
导致从未跑过 alembic 的库（如开发 SQLite、早期部署的 PostgreSQL）无法通过
`alembic upgrade head` 一步到位。本迁移统一补齐这些缺口。

升级前判存：表/列已存在（create_all 已建出）时直接跳过，与既有迁移
（48da6530eef1 / a1c94f7d2be3 / c3f81b2a9d47）的防御式风格一致。

与模型的对应关系（app/models/models.py）：
    FileObject  →  file_object 表（含 uq_file_dedup 唯一约束与 5 个索引列）
    AuditLog    →  audit_log 表（family_id / created_at 带索引）
    Entry.deleted_at / deleted_by  →  可空字符串列（软删回收站）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7d3f92e4a15'
down_revision: Union[str, None] = 'c3f81b2a9d47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspect() -> sa.inspect:
    return sa.inspect(op.get_bind())


def _tables() -> set:
    return set(_inspect().get_table_names())


def _columns(table: str) -> set:
    return {c["name"] for c in _inspect().get_columns(table)}


def _add_entry_soft_delete_columns() -> None:
    """entry 软删列（回收站）：比 file_object/audit_log 更早存在，仅老库可能缺。"""
    if "entry" not in _tables():
        return
    cols = _columns("entry")
    if "deleted_at" not in cols:
        op.add_column("entry", sa.Column("deleted_at", sa.String(length=32), nullable=True))
    if "deleted_by" not in cols:
        op.add_column("entry", sa.Column("deleted_by", sa.String(length=64), nullable=True))


FILE_OBJECT_COLS = (
    sa.Column("id", sa.String(length=32), nullable=False),
    sa.Column("family_id", sa.String(length=32), nullable=True),
    sa.Column("business_type", sa.String(length=32), nullable=True),
    sa.Column("business_id", sa.String(length=32), nullable=True),
    sa.Column("baby_id", sa.String(length=32), nullable=True),
    sa.Column("original_name", sa.String(length=255), nullable=True),
    sa.Column("content_type", sa.String(length=128), nullable=True),
    sa.Column("ext", sa.String(length=16), nullable=True),
    sa.Column("storage_key", sa.String(length=255), nullable=True),
    sa.Column("sha256", sa.String(length=64), nullable=True),
    sa.Column("size", sa.Integer(), nullable=True),
    sa.Column("uploader_id", sa.String(length=32), nullable=True),
    sa.Column("created_at", sa.String(length=32), nullable=True),
    sa.Column("updated_at", sa.String(length=32), nullable=True),
    sa.Column("deleted_at", sa.String(length=32), nullable=True),
    sa.Column("meta", sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("family_id", "sha256", "business_type", "business_id", name="uq_file_dedup"),
)


def _add_file_object() -> None:
    """file_object：非结构化文件台账（/files、去重复用 storage_key）。"""
    if "file_object" in _tables():
        return
    op.create_table("file_object", *FILE_OBJECT_COLS)
    op.create_index(op.f("ix_file_object_family_id"), "file_object", ["family_id"])
    op.create_index(op.f("ix_file_object_business_type"), "file_object", ["business_type"])
    op.create_index(op.f("ix_file_object_baby_id"), "file_object", ["baby_id"])
    op.create_index(op.f("ix_file_object_storage_key"), "file_object", ["storage_key"])
    op.create_index(op.f("ix_file_object_sha256"), "file_object", ["sha256"])


AUDIT_LOG_COLS = (
    sa.Column("id", sa.String(length=32), nullable=False),
    sa.Column("family_id", sa.String(length=32), nullable=True),
    sa.Column("action", sa.String(length=16), nullable=True),
    sa.Column("actor_id", sa.String(length=32), nullable=True),
    sa.Column("actor_name", sa.String(length=64), nullable=True),
    sa.Column("target_type", sa.String(length=16), nullable=True),
    sa.Column("target_id", sa.String(length=32), nullable=True),
    sa.Column("text", sa.String(), nullable=True),
    sa.Column("created_at", sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint("id"),
)


def _add_audit_log() -> None:
    """audit_log：操作留痕（FR-22，保留 180 天）。"""
    if "audit_log" in _tables():
        return
    op.create_table("audit_log", *AUDIT_LOG_COLS)
    op.create_index(op.f("ix_audit_log_family_id"), "audit_log", ["family_id"])
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"])


def upgrade() -> None:
    _add_entry_soft_delete_columns()
    _add_file_object()
    _add_audit_log()


def downgrade() -> None:
    if "audit_log" in _tables():
        op.drop_index(op.f("ix_audit_log_created_at"), table_name="audit_log")
        op.drop_index(op.f("ix_audit_log_family_id"), table_name="audit_log")
        op.drop_table("audit_log")
    if "file_object" in _tables():
        op.drop_index(op.f("ix_file_object_sha256"), table_name="file_object")
        op.drop_index(op.f("ix_file_object_storage_key"), table_name="file_object")
        op.drop_index(op.f("ix_file_object_baby_id"), table_name="file_object")
        op.drop_index(op.f("ix_file_object_business_type"), table_name="file_object")
        op.drop_index(op.f("ix_file_object_family_id"), table_name="file_object")
        op.drop_table("file_object")
    if "entry" in _tables():
        cols = _columns("entry")
        if "deleted_by" in cols:
            op.drop_column("entry", "deleted_by")
        if "deleted_at" in cols:
            op.drop_column("entry", "deleted_at")
