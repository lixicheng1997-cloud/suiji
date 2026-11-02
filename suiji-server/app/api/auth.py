"""认证 /auth（契约 §2）：注册不再代建家庭；登录/注册返回 need_family，客户端据此强制引导。

令牌策略（core/security.py + core/session_store.py）：
  access 2 小时（业务）/ refresh 30 天（一次性轮换）/ media 7 天（仅下载）
  /auth/logout   精确撤销当前 access，并一并作废传入的 refresh
  refresh 重放   判定令牌已泄露 → 抬高该用户水位线，全部已签发令牌立即失效
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..core.deps import AuthContext, get_auth, session_valid
from ..core.rate_limit import limit as rate_limit
from ..core.security import (ACCESS, MEDIA, REFRESH, create_token, decode_token,
                             hash_password, verify_password)
from ..core.session_store import session_store
from ..domain.dates import utc_now_iso
from ..models import Family, FamilyMember, User
from ..schemas import DeactivateIn, LoginIn, LogoutIn, PasswordIn, RefreshIn, RegisterIn
from ..services import account_service
from ..services.ids import gen_id
from ..services.rows import user_row

router = APIRouter(prefix="/auth", tags=["auth"])


def _check_password_strength(password: str) -> None:
    """口令强度：只卡长度与字符构成，不强制复杂度组合（容易被写成弱口令的变形）。"""
    pwd = password or ""
    if len(pwd) < settings.password_min_length:
        raise HTTPException(
            status_code=422, detail=f"密码至少 {settings.password_min_length} 位")
    if len(pwd.strip()) < len(pwd):
        raise HTTPException(status_code=422, detail="密码不能以空格开头或结尾")
    if pwd.isdigit() or pwd.isalpha():
        raise HTTPException(status_code=422, detail="密码不能是纯数字或纯字母")


def _role_of(db: Session, family_id: str, user_id: str) -> str:
    m = db.query(FamilyMember).filter(FamilyMember.family_id == family_id, FamilyMember.user_id == user_id).first()
    return m.role if m else "member"


def _issue_tokens(user_id: str, family_id: str, role: str) -> dict:
    """一次性签发三件套；role 由调用方实时查出，避免沿用旧令牌里的过期角色。"""
    return {
        "access": create_token(user_id, family_id, role, ACCESS),
        "refresh": create_token(user_id, family_id, role, REFRESH),
        "media": create_token(user_id, family_id, role, MEDIA),
    }


def _issue(db: Session, user: User, family: Family) -> dict:
    role = _role_of(db, family.id, user.id)
    return dict(
        _issue_tokens(user.id, family.id, role),
        user=user_row(user),
        family={"id": family.id, "name": family.name, "readonly": int(family.readonly or 0), "role": role},
        need_family=False,
    )


def _issue_pending(user: User) -> dict:
    """无关联家庭（新注册 / 被创建者移除后回落为空）：照常签发 Token，
    family 置 null + need_family=true，客户端必须经「邀请码加入 / 创建家庭」二选一
    完成关联后才能进首页；服务端对业务接口同步返回 409 need_family 兜底。
    """
    return dict(
        _issue_tokens(user.id, "", "member"),
        user=user_row(user),
        family=None,
        need_family=True,
    )


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db),
             _rl=rate_limit("register", settings.rl_register, settings.rl_register_window)):
    """注册只建账号，不代建家庭：家庭由用户在引导页创建或凭邀请码加入。

    接口必然要回答「用户名是否已占用」（否则注册流程不可用），所以无法完全消除
    用户名枚举——改为用严格配额把它压到不可用：同一 IP 每小时 5 次。
    """
    username = (body.username or "").strip()
    if not username:
        raise HTTPException(status_code=422, detail="用户名不能为空")
    if len(username) < 3:
        raise HTTPException(status_code=422, detail="用户名至少 3 位")
    _check_password_strength(body.password)
    if db.query(User).filter(User.username == username).first():
        # 409 而非 422：detail 是给用户看的业务文案，客户端错误映射只回显 409/400/403/404
        raise HTTPException(status_code=409, detail=f"用户名「{username}」已被注册，请换一个")
    name = (body.name or "").strip() or username
    user = User(id=gen_id("usr"), username=username, name=name,
                password_hash=hash_password(body.password), family_id="", created_at=utc_now_iso())
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_pending(user)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db),
          _rl=rate_limit("login", settings.rl_login, settings.rl_login_window)):
    """登录失败按原因细分提示：空字段、用户名不存在、密码错误各给各的文案。

    注意：这会暴露「用户名是否存在」（可被枚举），属产品要求可用性优先的取舍；
    爆破与枚举由限流（rl_login 配额）压制。
    """
    username = (body.username or "").strip()
    if not username:
        raise HTTPException(status_code=422, detail="用户名不能为空")
    if not body.password:
        raise HTTPException(status_code=422, detail="密码不能为空")
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户名不存在，请检查或先注册")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="密码错误，请重新输入")
    family = db.get(Family, user.family_id) if user.family_id else None
    if family is None:
        return _issue_pending(user)
    return _issue(db, user, family)


@router.post("/refresh")
def refresh(body: RefreshIn, db: Session = Depends(get_db),
            _rl=rate_limit("refresh", settings.rl_refresh, settings.rl_refresh_window)):
    """用 refresh 换新三件套；refresh 一次性，用后即焚。

    同一 refresh 被第二次提交说明令牌可能已泄露：抬高用户水位线，
    让该用户此前签发的 access/refresh/media 全部失效，强制重新登录。
    """
    import jwt as pyjwt

    try:
        payload = decode_token(body.refresh)
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="刷新令牌无效或已过期")
    if payload.get("type") != REFRESH:
        raise HTTPException(status_code=401, detail="令牌类型错误")
    jti = payload.get("jti") or ""
    user_id = payload.get("user_id", "")
    if not session_valid(payload):
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    if jti and not session_store.consume_refresh(jti, payload.get("exp", 0)):
        # 重放：撤销该 refresh 并抬高水位线（含同一用户的其他设备会话）
        session_store.revoke(jti, payload.get("exp", 0))
        session_store.bump_epoch(user_id)
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    family = db.get(Family, user.family_id) if user.family_id else None
    role = _role_of(db, user.family_id, user.id) if family else "member"
    return dict(
        _issue_tokens(user.id, user.family_id, role),
        need_family=family is None,
    )


@router.post("/logout")
def logout(body: LogoutIn, auth: AuthContext = Depends(get_auth)):
    """登出：撤销当前 access，并作废传入的 refresh（不传入则它最多再活到自然过期）。

    撤销是服务端的——客户端仅清本地令牌不够，否则旧 access 在剩余寿命内仍可用。

    body.all=true 时额外抬高用户水位线：本账号在所有设备上已签发的 access/refresh/media
    立即失效（换设备后「退出登录」、或怀疑令牌泄露时用）。
    """
    import jwt as pyjwt

    session_store.revoke(auth.jti, auth.exp)
    if body.refresh:
        try:
            payload = decode_token(body.refresh)
        except pyjwt.PyJWTError:
            payload = None
        # 只作废同一用户的 refresh，避免被拿来撤销他人令牌
        if payload and payload.get("type") == REFRESH and payload.get("user_id") == auth.user_id:
            session_store.revoke_refresh(payload.get("jti") or "", payload.get("exp", 0))
    if body.all:
        session_store.bump_epoch(auth.user_id)
    return {"ok": True}


@router.post("/password")
def change_password(body: PasswordIn, db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)):
    """改密：校验旧密码 → 写新哈希 → 抬高用户水位线 → 重新签发当前设备的三件套。

    抬高水位线是必须的：JWT 无状态，不这么做的话旧令牌在剩余寿命（refresh 30 天）内
    依然能调用业务接口，等于改密没有实际收回任何已泄露的凭证。
    当前设备紧接着重签（iat 必然晚于水位线），所以不用重新登录，其他设备全部下线。
    """
    user = db.get(User, auth.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    _check_password_strength(body.new_password)
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    # 先抬水位线再签新令牌：新令牌的 iat 一定晚于水位线，不会被自己作废
    session_store.bump_epoch(auth.user_id)
    return dict(
        _issue_tokens(user.id, user.family_id or "", auth.role),
        user=user_row(user),
        need_family=not bool(user.family_id),
    )


@router.get("/me")
def me(auth=Depends(get_auth)):
    need = not bool(auth.family_id)
    return {
        "user": {"id": auth.user_id, "name": auth.name, "username": auth.username},
        "family": None if need else
                 {"id": auth.family_id, "name": auth.family_name, "readonly": 1 if auth.readonly else 0, "role": auth.role},
        "need_family": need,
    }


@router.post("/deactivate")
def deactivate(body: DeactivateIn, db: Session = Depends(get_db),
               auth: AuthContext = Depends(get_auth)):
    """申请注销：二次验证密码 → 进入 30 天冷静期。

    冷静期内账号仍可正常使用，登录/业务不被拦截；客户端拉到 scheduled=true 时
    展示「账号将于 X 日注销，撤销」banner。不抬高用户水位线：冷静期是软状态，
    不是安全事件，当前与其他设备会话保持有效，用户下次打开 App 即可看到状态并撤销。
    """
    user = db.get(User, auth.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="密码不正确")
    when = account_service.request_deletion(db, user)
    return {"ok": True, "scheduled": True, "execute_at": when}


@router.post("/deactivate/cancel")
def deactivate_cancel(db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)):
    """冷静期内撤销注销申请。"""
    user = db.get(User, auth.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    if not user.deletion_scheduled_at:
        return {"ok": True, "scheduled": False}
    account_service.cancel_deletion(db, user)
    return {"ok": True, "scheduled": False}


@router.get("/deactivate")
def deactivate_status(db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)):
    """查询当前注销状态。"""
    user = db.get(User, auth.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return account_service.status_of(user)
