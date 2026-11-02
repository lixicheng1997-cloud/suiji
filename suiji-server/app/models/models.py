"""数据模型（SQLAlchemy 2.x）：行形状对齐契约 §1，时间字段统一存字符串。"""
from sqlalchemy import JSON, Boolean, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ..core.field_crypto import EncryptedString


class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    password_hash: Mapped[str] = mapped_column(String(128))
    family_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    created_at: Mapped[str] = mapped_column(String(32), default="")
    is_admin: Mapped[int] = mapped_column(Integer, default=0)  # 0/1 系统管理员（启动自动播种）
    # 账号注销冷静期（TDD §十）：空串=未申请注销；非空=计划于该 UTC 时刻删除账号。
    # 30 天内登录或主动调用 /auth/deactivate/cancel 即清空该字段撤销注销。
    deletion_scheduled_at: Mapped[str] = mapped_column(String(32), default="", index=True)


class Family(Base):
    __tablename__ = "family"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="家庭空间")
    creator_id: Mapped[str] = mapped_column(String(32), default="")
    readonly: Mapped[int] = mapped_column(Integer, default=0)  # 0/1
    events_version: Mapped[int] = mapped_column(Integer, default=0)  # 家庭事件水位：entry 任何写操作都 bump，客户端据此感知删除/修改
    created_at: Mapped[str] = mapped_column(String(32), default="")


class FamilyMember(Base):
    __tablename__ = "family_member"
    __table_args__ = (UniqueConstraint("family_id", "user_id", name="uq_family_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")  # creator/member
    color: Mapped[str] = mapped_column(String(16), default="#FF6B8B")
    joined_at: Mapped[str] = mapped_column(String(32), default="")


class InviteCode(Base):
    __tablename__ = "invite_code"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_by: Mapped[str] = mapped_column(String(32), default="")
    expires_at: Mapped[str] = mapped_column(String(32), default="")


class Baby(Base):
    __tablename__ = "baby"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    # 宝宝姓名属儿童身份信息，落库前 AES-256-GCM 加密（见 core/field_crypto.py）。
    name: Mapped[str] = mapped_column(EncryptedString(64), default="宝宝")
    birth_date: Mapped[str] = mapped_column(String(10), default="")
    gestational_weeks: Mapped[int] = mapped_column(Integer, default=40)
    gender: Mapped[str] = mapped_column(String(8), default="boy")
    birth_length: Mapped[float] = mapped_column(Float, default=0)
    birth_weight: Mapped[float] = mapped_column(Float, default=0)
    avatar: Mapped[str] = mapped_column(String(64), default="")  # 大值可为 base64 前缀，放宽
    # 过敏史属健康信息，与 entry.note 同口径加密；客户端限 500 字，明文预算见 field_crypto 列宽公式
    allergy: Mapped[str] = mapped_column(EncryptedString(2048), default="")
    is_active: Mapped[int] = mapped_column(Integer, default=0)   # 0/1
    created_at: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[str] = mapped_column(String(32), default="")


class Entry(Base):
    __tablename__ = "entry"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    baby_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    type: Mapped[str] = mapped_column(String(16))
    occurred_at: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[str] = mapped_column(String(32), default="")
    is_backfilled: Mapped[int] = mapped_column(Integer, default=0)  # 0/1
    # 自由文本备注属健康日志，落库前 AES-256-GCM 加密。
    note: Mapped[str] = mapped_column(EncryptedString(2048), default="")
    creator: Mapped[str] = mapped_column(String(64), default="")
    # 记录人账号 ID：展示口径的唯一可靠依据（creator 存的是历史名字串，改名即失配）
    creator_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    title: Mapped[str] = mapped_column(String, default="")
    meta: Mapped[str] = mapped_column(String, default="")
    badge: Mapped[str] = mapped_column(String(32), default="")
    photo: Mapped[str] = mapped_column(String, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    deleted_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deleted_by_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class EntryMedia(Base):
    __tablename__ = "entry_media"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    entry_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    baby_id: Mapped[str] = mapped_column(String(32), default="")
    storage_key: Mapped[str] = mapped_column(String(255), default="")
    sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)


class FileObject(Base):
    """非结构化文件台账：字节只存在 MinIO/对象存储，这里只存 storage_key（路径）与元信息。

    business_type/business_id 为业务挂载点（entry / entry_media / baby / other），
    未绑定业务的“待挂载文件” business_type 为空，后续通过 PATCH /files/{id} 挂到业务行。
    """
    __tablename__ = "file_object"
    __table_args__ = (
        UniqueConstraint("family_id", "sha256", "business_type", "business_id", name="uq_file_dedup"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    business_type: Mapped[str] = mapped_column(String(32), default="", index=True)
    business_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    baby_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    original_name: Mapped[str] = mapped_column(String(255), default="")
    content_type: Mapped[str] = mapped_column(String(128), default="")
    ext: Mapped[str] = mapped_column(String(16), default="")
    storage_key: Mapped[str] = mapped_column(String(255), default="", index=True)
    sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    uploader_id: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[str] = mapped_column(String(32), default="")
    deleted_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class Measurement(Base):
    __tablename__ = "measurement"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    entry_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    baby_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    metric: Mapped[str] = mapped_column(String(8))
    value: Mapped[float] = mapped_column(Float)
    occurred_at: Mapped[str] = mapped_column(String(32), default="")
    corrected_age_flag: Mapped[int] = mapped_column(Integer, default=0)  # 0/1


class GrowthPoint(Base):
    __tablename__ = "growth_point"

    measurement_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    percentile_p: Mapped[float] = mapped_column(Float, default=0)
    z_score: Mapped[float] = mapped_column(Float, default=0)
    standard_version: Mapped[str] = mapped_column(String(32), default="")


class MilestoneRecord(Base):
    __tablename__ = "milestone_record"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    baby_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    domain: Mapped[str] = mapped_column(String(32), default="")
    month: Mapped[str] = mapped_column(String(32), default="")
    ref: Mapped[str] = mapped_column(String(64), default="")
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    achieved_at: Mapped[str] = mapped_column(String(32), default="")
    source_entry_id: Mapped[str] = mapped_column(String(32), default="")
    creator: Mapped[str] = mapped_column(String(64), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Vaccine(Base):
    __tablename__ = "vaccine"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    code: Mapped[str] = mapped_column(String(32), index=True)
    baby_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    n: Mapped[str] = mapped_column(String(64), default="")
    dose: Mapped[str] = mapped_column(String(32), default="")
    age: Mapped[str] = mapped_column(String(32), default="")
    months: Mapped[int] = mapped_column(Integer, default=0)
    cls: Mapped[str] = mapped_column(String(16), default="一类")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    plan_date: Mapped[str] = mapped_column(String(10), default="")
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    done_date: Mapped[str] = mapped_column(String(10), default="")
    org: Mapped[str] = mapped_column(String(64), default="")
    lot: Mapped[str] = mapped_column(String(64), default="")
    remind: Mapped[bool] = mapped_column(Boolean, default=True)
    remind_lead: Mapped[int] = mapped_column(Integer, default=7)
    created_at: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[str] = mapped_column(String(32), default="")


class AiJournal(Base):
    __tablename__ = "ai_journal"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    baby_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    range: Mapped[str] = mapped_column(String(64), default="")
    range_start: Mapped[str] = mapped_column(String(10), default="")
    range_end: Mapped[str] = mapped_column(String(10), default="")
    paras: Mapped[list] = mapped_column(JSON, default=list)  # [{text, cites}]
    status: Mapped[str] = mapped_column(String(16), default="draft")
    model_version: Mapped[str] = mapped_column(String(64), default="template")
    prompt_version: Mapped[str] = mapped_column(String(16), default="v1")
    fact_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[str] = mapped_column(String(32), default="")


class AuditLog(Base):
    """操作留痕（FR-22）：加入/退出/角色变更/删除/导出等关键操作，保留 180 天，成员不可删除（无写接口）。"""
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(16), default="")                    # create/invite/join/leave/role/readonly/delete/purge/export/wipe
    actor_id: Mapped[str] = mapped_column(String(32), default="")
    actor_name: Mapped[str] = mapped_column(String(64), default="")
    target_type: Mapped[str] = mapped_column(String(16), default="")               # family/member/entry/trash/data
    target_id: Mapped[str] = mapped_column(String(32), default="")
    text: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String(32), default="", index=True)


class ServerEndpoint(Base):
    """客户端可选服务器地址（登录页 /「我的」页下拉选择的来源）。

    暂无配置界面：数据由 static/config/servers.json 播种（脚本 scripts/seed_servers.py
    可全量同步），页面只读不写。
    """
    __tablename__ = "server_endpoint"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="")           # 展示名，如「本机开发」
    url: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # 含 /api/v1 的完整基址
    env: Mapped[str] = mapped_column(String(16), default="dev")         # dev/test/prod
    remark: Mapped[str] = mapped_column(String(255), default="")
    enabled: Mapped[int] = mapped_column(Integer, default=1)            # 0/1：停用后不再出现在下拉里
    is_default: Mapped[int] = mapped_column(Integer, default=0)         # 0/1：客户端首次启动的选中项
    sort: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[str] = mapped_column(String(32), default="")


class Setting(Base):
    __tablename__ = "setting"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Notification(Base):
    """家人动态通知（落库版）：创建记录时按收件人 user_id 逐人写一行，读过即删。

    之前通知由客户端从 bootstrap feeds 本地合成，「是否本人」靠 creator 名字字符串
    匹配，昵称不同步/重名时自己的操作会给自己弹通知，且 feeds 取「最新 3 条」
    不筛时间，老记录在本地账本过期后会反复冒通知。改为服务端落库后：
    - 投递以 user_id 精确排除操作者本人，永不误弹；
    - 客户端已读即删行，未读的换设备/重装仍能拉到，不会凭空多出也不会凭空消失。
    """
    __tablename__ = "notification"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)   # 收件人
    type: Mapped[str] = mapped_column(String(16), default="feed")  # feed（家人动态）
    title: Mapped[str] = mapped_column(String(64), default="")
    content: Mapped[str] = mapped_column(String(255), default="")
    actor: Mapped[str] = mapped_column(String(64), default="")     # 操作人展示名
    entry_id: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[str] = mapped_column(String(32), default="", index=True)
