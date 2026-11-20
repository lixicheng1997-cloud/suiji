"""认证 /auth（契约 §2）：注册不再代建家庭；登录/注册返回 need_family，客户端据此强制引导。

令牌策略（core/security.py + core/session_store.py）：
  access 2 小时（业务）/ refresh 30 天（一次性轮换）/ media 7 天（仅下载）
  /auth/logout   精确撤销当前 access，并一并作废传入的 refresh
  refresh 重放   判定令牌已泄露 → 抬高该用户水位线，全部已签发令牌立即失效

手机号登录（阿里云号码认证服务，/auth/phone/*）：
  一键登录（App/H5 原生 SDK 取号令牌 → GetMobile）与本机号码校验（输入号 + 令牌 →
  VerifyPhone PASS）共用同一套账号融合规则 _resolve_phone_login：
  手机号已绑定 → 登录该账号；未绑定 → 自动注册新账号（无密码，仅手机号通道）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..core.deps import AuthContext, get_auth, session_valid
from ..core.rate_limit import limit as rate_limit, rate_limiter
from ..core.security import (ACCESS, MEDIA, REFRESH, create_token, decode_token,
                             hash_password, verify_password)
from ..core.session_store import session_store
from ..domain.dates import utc_now_iso
from ..models import Family, FamilyMember, User
from ..schemas import (DeactivateIn, LoginIn, LogoutIn, PasswordIn, PhoneBindIn,
                       PhoneOneClickIn, PhonePrefetchIn, PhoneUnbindIn,
                       PhoneVerifyLoginIn, RefreshIn, RegisterIn)
from ..services import account_service
from ..services.alibaba_phone import (gen_auto_username, get_mobile, phone_hash_of,
                                      verify_phone)
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
        family={"id": family.id, "name": family.name, "role": role},
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
    # 停用拦截（第一层）：密码正确也拒登，业务接口由 deps._resolve 每请求实时兜底
    if int(user.status or 0) == 1:
        raise HTTPException(status_code=403, detail="账号已被停用，请联系管理员")
    family = db.get(Family, user.family_id) if user.family_id else None
    if family is None:
        return _issue_pending(user)
    return _issue(db, user, family)


# ---------- 手机号登录（阿里云号码认证） ----------

def _phone_service_ready() -> None:
    """号码认证服务可用性闸：AK 未配置或开关关闭时一律 503（前端按钮隐藏，端点兜底）。"""
    if not (settings.aliyun_phone_enabled and settings.aliyun_phone_ak_id
            and settings.aliyun_phone_ak_secret):
        raise HTTPException(status_code=503, detail="号码认证未开通，请使用账号密码登录")


def _check_phone_format(phone: str) -> str:
    """手机号格式闸：大陆 11 位号码（1 开头），只挡格式不挡归属地。"""
    phone = (phone or "").strip()
    if len(phone) != 11 or not phone.isdigit() or not phone.startswith("1"):
        raise HTTPException(status_code=422, detail="手机号格式不正确")
    return phone


def _phone_rate_guard(phone_hash: str, count: int, window: int) -> None:
    """按手机号哈希限流（防枚举）：同一手机号窗口内超过配额直接 429，不区分是否命中账号。"""
    if not rate_limiter.hit(f"rl:phonehash:{phone_hash}", count, window):
        raise HTTPException(
            status_code=429, detail="该手机号操作过于频繁，请稍后再试",
            headers={"Retry-After": str(window)},
        )


def _resolve_phone_login(db: Session, phone: str) -> dict:
    """手机号登录融合规则（一键登录与本机号码校验共用）：
    - 已绑定手机号 → 登录该账号（复刻 login 的停用拦截 + need_family 判定）；
    - 未绑定 → 自动注册新账号：username=sj+随机10位（不展示）、password_hash=""
      （不可密码登录，可在「我的」页设置密码后获得双通道）、name=手机用户。
    """
    ph = phone_hash_of(phone)
    user = db.query(User).filter(User.phone_hash == ph).first()
    if user is None:
        # 自动注册：username 撞库重掷（随机 10 位碰撞概率可忽略，兜底仍做幂等重试）
        for _ in range(3):
            candidate = gen_auto_username()
            if not db.query(User).filter(User.username == candidate).first():
                break
        else:
            raise HTTPException(status_code=503, detail="注册繁忙，请稍后再试")
        user = User(id=gen_id("usr"), username=candidate, name="手机用户",
                    password_hash="", family_id="", created_at=utc_now_iso(),
                    phone=phone, phone_hash=ph)
        db.add(user)
        db.commit()
        db.refresh(user)
        return _issue_pending(user)
    if int(user.status or 0) == 1:
        raise HTTPException(status_code=403, detail="账号已被停用，请联系管理员")
    family = db.get(Family, user.family_id) if user.family_id else None
    if family is None:
        return _issue_pending(user)
    return _issue(db, user, family)


@router.post("/phone/prefetch",
             dependencies=[rate_limit("phone_prefetch", 10, 300)])
def phone_prefetch(body: PhonePrefetchIn):
    """静默预取脱敏本机号码：客户端 SDK 静默令牌 → GetMobile 换号 → 返回脱敏号。

    仅供登录页顶部展示「138****8888」，不产生任何登录态；令牌一次性消费，
    预取用掉不影响后续一键登录（getLoginToken 另发新令牌）。
    换号失败（无 SIM / 令牌类型不符 / 服务异常）一律 503，前端静默回退手动输入。
    """
    _phone_service_ready()
    phone = get_mobile(body.token)
    return {"masked": phone[:3] + "****" + phone[7:]}


@router.post("/phone/oneclick",
             dependencies=[rate_limit("phone_login", settings.rl_phone_login, settings.rl_phone_login_window)])
def phone_oneclick(body: PhoneOneClickIn, db: Session = Depends(get_db)):
    """一键登录：客户端 SDK 取号令牌 → 服务端 GetMobile 换手机号 → 融合规则签发令牌。

    阿里云令牌一次性消费，天然防重放；IP 限流 + 手机号哈希限流双键防枚举。
    """
    _phone_service_ready()
    phone = get_mobile(body.token)
    _phone_rate_guard(phone_hash_of(phone), 5, 3600)
    return _resolve_phone_login(db, phone)


@router.post("/phone/verify-login",
             dependencies=[rate_limit("phone_login", settings.rl_phone_login, settings.rl_phone_login_window)])
def phone_verify_login(body: PhoneVerifyLoginIn, db: Session = Depends(get_db)):
    """本机号码校验登录：用户输入手机号 + SDK 校验令牌，VerifyPhone PASS 才放行。"""
    _phone_service_ready()
    phone = _check_phone_format(body.phone)
    verify_phone(phone, body.token)
    _phone_rate_guard(phone_hash_of(phone), 5, 3600)
    return _resolve_phone_login(db, phone)


@router.post("/phone/bind",
             dependencies=[rate_limit("phone_bind", settings.rl_phone_bind, settings.rl_phone_bind_window)])
def phone_bind(body: PhoneBindIn, db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)):
    """绑定手机号（登录态）：VerifyPhone 校验持机者本人后写入。

    冲突策略：手机号已归属其他账号 → 409 拒绝不自动合并（防误并家庭数据），
    提示先在原账号解绑；本账号已绑其他手机号 → 409 要求先解绑。
    """
    user = db.get(User, auth.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    phone = _check_phone_format(body.phone)
    verify_phone(phone, body.token)
    ph = phone_hash_of(phone)
    other = db.query(User).filter(User.phone_hash == ph, User.id != user.id).first()
    if other is not None:
        raise HTTPException(status_code=409, detail="该手机号已绑定其他账号，请先在原账号解绑后再绑定")
    if user.phone_hash and user.phone_hash != ph:
        raise HTTPException(status_code=409, detail="当前账号已绑定其他手机号，请先解绑")
    user.phone = phone
    user.phone_hash = ph
    db.commit()
    return {"ok": True, "user": user_row(user)}


@router.post("/phone/unbind")
def phone_unbind(body: PhoneUnbindIn, db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)):
    """解绑手机号（登录态）：无短信通道，用密码二次校验兜底。

    手机号账号（password_hash 为空）不允许解绑：解绑后将失去唯一登录通道。
    """
    user = db.get(User, auth.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    if not user.phone_hash:
        raise HTTPException(status_code=400, detail="当前账号未绑定手机号")
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="请先设置密码后再解绑手机号，否则将无法登录")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="密码不正确")
    user.phone = ""
    user.phone_hash = ""
    db.commit()
    return {"ok": True, "user": user_row(user)}


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
    # 停用拦截（第二层）：存量 refresh 也续不出新令牌（第一层在 login，第三层在 deps._resolve）
    if int(user.status or 0) == 1:
        raise HTTPException(status_code=403, detail="账号已被停用，请联系管理员")
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
    # 手机号注册的账号（password_hash 为空）首次设置密码：免验旧密码
    if user.password_hash and not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    _check_password_strength(body.new_password)
    if user.password_hash and verify_password(body.new_password, user.password_hash):
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
                 {"id": auth.family_id, "name": auth.family_name, "role": auth.role},
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
