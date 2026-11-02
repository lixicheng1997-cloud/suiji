"""鉴权依赖：Bearer access JWT → AuthContext；写端点只读门控（契约 §2/§4）。

令牌校验三段式：
  1. 签名与有效期（decode_token）
  2. 类型匹配（access 只能调业务接口；media 只能下载）
  3. 撤销账本（jti 黑名单 + 用户 epoch 水位线），见 core/session_store.py

第 3 段是无状态 JWT 能「主动失效」的关键：登出 / 改密 / 被移出家庭后，
已签发但尚未过期的令牌不再被接受。
"""
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..models import Family, FamilyMember, User
from .db import get_db
from .security import ACCESS, MEDIA, decode_token, issued_ms
from .session_store import session_store

bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user_id: str
    username: str
    name: str
    family_id: str
    role: str          # creator / member（实时查 family_member）
    readonly: bool     # 当前家庭只读开关
    family_name: str
    jti: str = ""      # 当前 access 令牌 ID，供 /auth/logout 精确撤销
    exp: int = 0       # 当前 access 过期时刻，撤销时用作账本 TTL


def _resolve(db: Session, payload: dict) -> AuthContext:
    user = db.get(User, payload.get("user_id", ""))
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    family = db.get(Family, user.family_id) if user.family_id else None
    role = "member"
    readonly = False
    family_name = ""
    if family:
        readonly = bool(family.readonly)
        family_name = family.name
        member = (
            db.query(FamilyMember)
            .filter(FamilyMember.family_id == family.id, FamilyMember.user_id == user.id)
            .first()
        )
        if member:
            role = member.role
        else:
            # 成员行缺失（异常数据）：创建者兜底
            role = "creator" if family.creator_id == user.id else "member"
    return AuthContext(
        user_id=user.id,
        username=user.username,
        name=user.name,
        family_id=family.id if family else "",
        role=role,
        readonly=readonly,
        family_name=family_name,
        jti=payload.get("jti") or "",
        exp=int(payload.get("exp") or 0),
    )


def session_valid(payload: dict) -> bool:
    """撤销账本校验：False 表示令牌已被主动收回（登出 / 轮换 / 用户级失效）。

    供 access 校验（get_auth）与 refresh 校验（/auth/refresh）共用。
    """
    jti = payload.get("jti") or ""
    if jti and session_store.is_revoked(jti):
        return False
    # 签发时刻早于用户水位线 → 改密、被移出家庭、refresh 重放等场景下全量失效
    if issued_ms(payload) < session_store.epoch_of(payload.get("user_id", "")):
        return False
    return True


_revoke_check = session_valid


def get_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    if payload.get("type") != ACCESS:
        raise HTTPException(status_code=401, detail="令牌类型错误")
    if not _revoke_check(payload):
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return _resolve(db, payload)


def require_family(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    """家庭门控：账号尚未关联家庭时，业务接口一律 409 need_family。

    放行范围是 /auth/* 与 GET|POST /family（含 /family/join、/family/invite），
    即「创建家庭」「凭邀请码加入」两条关联路径本身，避免门控自锁。
    前端收到 409 need_family 后强制回退到 pages/family-setup 引导页。
    """
    if not auth.family_id:
        raise HTTPException(status_code=409, detail="need_family")
    return auth


def require_family_write(auth: AuthContext = Depends(require_family)) -> AuthContext:
    """写端点：先过家庭门控（无家庭 409 need_family），再过只读门控。

    files/media 的下载端点为兼容 <img src> 直连而手写鉴权（无 token 需保持 403 语义），
    因此这两个模块的依赖在各自 endpoint 上施加，不套 router 级依赖。
    """
    return require_write(auth)


def require_write(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    """只读模式下非创建者禁止一切写操作（契约 §4）。"""
    if auth.readonly and auth.role != "creator":
        raise HTTPException(status_code=403, detail="只读模式")
    return auth


def require_creator(auth: AuthContext = Depends(require_family_write)) -> AuthContext:
    """仅家庭创建者：用于不可逆/家庭级的操作（清空数据、导入覆盖等）。

    普通成员（哪怕家庭未开只读）不应具备「一键清空整个家庭全部记录」的能力——
    那是创建者的管理动作，误触或被盗号时损失不可恢复。
    """
    if auth.role != "creator":
        raise HTTPException(status_code=403, detail="仅家庭创建者可执行该操作")
    return auth


def resolve_token(db: Session, token: str, types: tuple[str, ...] = (ACCESS,)) -> AuthContext | None:
    """手写鉴权入口：token 无效/过期/类型不对/已撤销/用户不存在时返回 None。

    供文件下载这类需要支持 query 传 token（<img src> 无法带 Header）的端点使用。
    下载端点应放行 media 类型：业务令牌不进 URL，媒体令牌也不能调业务接口。
    """
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return None
    if payload.get("type") not in types:
        return None
    if not _revoke_check(payload):
        return None
    try:
        return _resolve(db, payload)
    except HTTPException:
        return None
