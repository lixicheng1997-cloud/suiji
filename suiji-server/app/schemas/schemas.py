"""请求体模型（Pydantic v2）：客户端整行提交的表用 extra=allow 透传。"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# 密码长度上限：bcrypt 只取前 72 字节，再长也没有额外强度，只会被静默截断
PASSWORD_MAX_LENGTH = 128


class RegisterIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    # 下限由 settings.password_min_length 在业务层校验（配置项，改了不用动 schema）；
    # 这里只挡空串，避免 422 文案与业务校验不一致
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    name: str = ""


class LoginIn(BaseModel):
    username: str
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class RefreshIn(BaseModel):
    refresh: str


class LogoutIn(BaseModel):
    """登出：refresh 可选，传入则一并作废（不传则它最多再活到自然过期）。"""
    refresh: str = ""
    # true = 同时抬高用户水位线，让本账号在所有设备上已签发的令牌全部失效
    all: bool = False


class PasswordIn(BaseModel):
    """改密：必须校验旧密码，否则被盗的 access 令牌就能直接改密接管账号。"""
    old_password: str = Field(max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class JoinIn(BaseModel):
    code: str


class FamilyCreateIn(BaseModel):
    name: str = ""


class FamilyReadonlyIn(BaseModel):
    readonly: bool


class MemberRoleIn(BaseModel):
    role: str  # creator / member


class BabyIn(BaseModel):
    """客户端 createBaby/updateBaby 提交整行；未知字段忽略但保留已知派生字段。"""
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str = "宝宝"
    birth_date: str = ""
    gestational_weeks: int = 40
    gender: str = "boy"
    birth_length: float = 0
    birth_weight: float = 0
    avatar: str = ""
    allergy: str = ""
    is_active: int = 0
    created_at: str = ""
    updated_at: str = ""


class EntryIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    id: str | None = None
    baby_id: str | None = None
    occurred_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    is_backfilled: Any = 0
    note: str = ""
    creator: str = ""
    title: str = ""
    meta: str = ""
    badge: str = ""
    photo: str = ""
    payload: dict = Field(default_factory=dict)


class VaccinePatch(BaseModel):
    model_config = ConfigDict(extra="allow")

    plan_date: str | None = None   # 用户自定义的预期接种日期（空串=恢复按出生日期排期）
    done: bool | None = None
    done_date: str | None = None
    org: str | None = None
    lot: str | None = None
    remind: bool | None = None
    remind_lead: int | None = None


class SyncRowsIn(BaseModel):
    rows: list[dict] = Field(default_factory=list)


class MilestonePatch(BaseModel):
    model_config = ConfigDict(extra="allow")

    done: bool | None = None
    achieved_at: str | None = None
    source_entry_id: str | None = None
    month: str | None = None
    creator: str | None = None


class SettingsIn(BaseModel):
    key: str
    value: Any


class JournalGenerateIn(BaseModel):
    baby_id: str = ""
    range_start: str = ""
    range_end: str = ""


class JournalUpdateIn(BaseModel):
    paras: list | None = None
    status: str | None = None


class ImportIn(BaseModel):
    snapshot: dict


class FilePatch(BaseModel):
    """非结构化文件局部更新：只能改挂载点与展示名，内容与 storage_key 不可变。"""
    business_type: str | None = None
    business_id: str | None = None
    baby_id: str | None = None
    original_name: str | None = None
    meta: dict | None = None


class DeactivateIn(BaseModel):
    """账号注销二次验证：必须输入当前密码。"""
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)
