"""家庭 /family（契约 §4）：邀请/加入/只读/成员角色管理。

家庭归属唯一（§4.0）：一个用户同一时刻只能关联 1 个家庭——`user.family_id` 是唯一归属指针，
`family_member` 中同一 user 至多 1 行。换家庭的唯一路径是「凭其他家庭的邀请码加入」：
加入 = 与当前家庭解绑 + 归属到新家庭；账号/昵称/设置等个人资料不随家庭变动。
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..core.deps import AuthContext, get_auth, require_creator
from ..core.rate_limit import limit as rate_limit
from ..domain.dates import utc_now_iso
from ..models import Family, FamilyMember, InviteCode, Setting, User
from ..schemas import FamilyCreateIn, FamilyReadonlyIn, JoinIn, MemberRoleIn
from ..services import audit_service
from ..services.bootstrap_service import family_members
from ..services.ids import gen_id
from ..services.rows import display_name

router = APIRouter(prefix="/family", tags=["family"])

PALETTE = ["#FF6B8B", "#FF9E58", "#E86FA0", "#8FA8D8", "#7CC6A6"]
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_ROLE_TEXT = {"creator": "创建者", "member": "成员"}


def _name_of(db: Session, user_id: str) -> str:
    # 留痕文案显示口径：统一走 display_name，绝不透出登录账号
    u = db.get(User, user_id)
    if u is None:
        return "家人"
    st = db.get(Setting, user_id)
    parent = ((st.data or {}).get("parent") or {}) if st else {}
    return display_name(u, parent)


def _require_creator(auth: AuthContext) -> None:
    if auth.role != "creator":
        raise HTTPException(status_code=403, detail="仅创建者可操作")


def _family_dict(db: Session, auth: AuthContext) -> dict:
    fam = db.get(Family, auth.family_id) if auth.family_id else None
    return {
        "id": auth.family_id,
        "name": fam.name if fam else "",
        "readonly": 1 if auth.readonly else 0,
        "role": auth.role,
        "need_family": fam is None,
    }


def _memberships(db: Session, user_id: str) -> list[FamilyMember]:
    """某用户的全部家庭成员行（约束下正常只有 0/1 行）。"""
    return db.query(FamilyMember).filter(FamilyMember.user_id == user_id).all()


def _detach(db: Session, auth: AuthContext, family_id: str) -> dict | None:
    """与 family_id 解绑（唯一归属：换家庭前必须离开旧家庭）。

    删除成员行并向旧家庭写一条 leave 留痕；若离开者是创建者，则把创建者身份交给
    最早加入的成员（避免家庭无人管理），无人可交时家庭保留、创建者字段不动，
    使本人日后被移出其他家庭时仍可回落到自己创建的家庭。
    返回被解绑家庭 {id, name}，本来就不在该家庭则返回 None。
    """
    if not family_id:
        return None
    rows = db.query(FamilyMember).filter(FamilyMember.family_id == family_id,
                                         FamilyMember.user_id == auth.user_id).all()
    if not rows:
        return None
    fam = db.get(Family, family_id)
    heir = None
    if any(r.role == "creator" for r in rows):
        heir = (db.query(FamilyMember)
                .filter(FamilyMember.family_id == family_id, FamilyMember.user_id != auth.user_id)
                .order_by(FamilyMember.id).first())
    for r in rows:
        db.delete(r)
    if heir is not None:
        heir.role = "creator"
        if fam is not None:
            fam.creator_id = heir.user_id
        audit_service.record(db, family_id, auth, action="role", target_type="member", target_id=heir.user_id,
                             text=f"创建者加入其他家庭，「{_name_of(db, heir.user_id)}」自动接管家庭空间")
    left = {"id": family_id, "name": fam.name if fam else ""}
    audit_service.record(db, family_id, auth, action="leave", target_type="member", target_id=auth.user_id,
                         text=f"「{_name_of(db, auth.user_id)}」加入其他家庭，已与「{left['name']}」解绑")
    return left


def _bind(db: Session, auth: AuthContext, family_id: str, role: str, color: str) -> None:
    """把用户唯一绑定到 family_id：清掉其他家庭的成员行（历史异常兜底），再建本家庭成员行。"""
    for row in _memberships(db, auth.user_id):
        if row.family_id != family_id:
            db.delete(row)
    user = db.get(User, auth.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    user.family_id = family_id
    db.add(FamilyMember(family_id=family_id, user_id=auth.user_id, role=role, color=color, joined_at=utc_now_iso()))


@router.get("")
def get_family(db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)):
    return {"family": _family_dict(db, auth), "members": family_members(db, auth.family_id)}


@router.get("/audit")
def list_audit(limit: int = Query(200, ge=1, le=500), days: int = Query(audit_service.KEEP_DAYS, ge=1, le=365),
               offset: int = Query(0, ge=0),
               db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)):
    """家庭操作留痕（FR-22）：全员可读，按保留期内的时间倒序，服务端产出、成员不可删除。"""
    return {"items": audit_service.list_recent(db, auth.family_id, limit=limit, days=days, offset=offset)}


@router.post("/audit/export")
def audit_export(db: Session = Depends(get_db), auth: AuthContext = Depends(require_creator)):
    """客户端本机导出（备份包/成长档案）不可观测，由其主动上报一次「导出」留痕（FR-22）。

    写留痕即写库，属于写操作：必须过只读门控（家庭只读时不应产生新留痕），
    且不该让任意成员无限次灌日志——与「清空数据」同级，收拢到创建者。
    """
    audit_service.record(db, auth.family_id, auth, action="export", target_type="data",
                         text="导出家庭数据副本")
    db.commit()
    return {"ok": True}


@router.post("")
def create_family(body: FamilyCreateIn, db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)):
    """创建新家庭并归属为创建者（登录后无家庭的引导流程调用，契约 §4）。"""
    user = db.get(User, auth.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    # 归属唯一：已关联家庭的用户不能再自建家庭，换家庭只能凭邀请码加入（会与当前家庭解绑）
    if user.family_id:
        raise HTTPException(status_code=422, detail="已关联家庭，如需更换请用邀请码加入其他家庭")
    now = utc_now_iso()
    name = (body.name or "").strip() or (user.name + "的家庭")
    fid = gen_id("fam")
    fam = Family(id=fid, name=name, creator_id=user.id, readonly=0, created_at=now)
    db.add(fam)
    _bind(db, auth, fid, "creator", PALETTE[0])
    audit_service.record(db, fid, auth, action="create", target_type="family", target_id=fid,
                         text=f"创建家庭空间「{name}」", created_at=now)
    db.commit()
    return {
        "family": {"id": fid, "name": name, "readonly": 0, "role": "creator"},
        "members": family_members(db, fid),
    }


@router.post("/invite")
def invite(db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)):
    _require_creator(auth)
    if not auth.family_id:
        raise HTTPException(status_code=422, detail="尚未加入家庭")
    # 重复生成即失效旧的（删旧行）
    db.query(InviteCode).filter(InviteCode.family_id == auth.family_id).delete(synchronize_session=False)
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.add(InviteCode(family_id=auth.family_id, code=code, created_by=auth.user_id, expires_at=expires))
    audit_service.record(db, auth.family_id, auth, action="invite", target_type="family", target_id=auth.family_id,
                         text="生成家庭邀请码（7 天有效）")
    db.commit()
    return {"code": code, "expires_at": expires}


@router.post("/join")
def join(body: JoinIn, db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth),
         _rl=rate_limit("join", settings.rl_join, settings.rl_join_window)):
    """凭邀请码加入：8 位码 32 字母表 ≈ 2^40 熵，本身不可爆破；
    限流是为防「码被改成短码」或实现变更后立刻变成可爆破面，也挡住批量试码刷库。"""
    code = (body.code or "").strip().upper()
    ic = db.query(InviteCode).filter(InviteCode.code == code).first()
    if not ic or ic.expires_at < utc_now_iso():
        raise HTTPException(status_code=422, detail="邀请码无效或已过期")
    fam = db.get(Family, ic.family_id)
    if fam is None:
        raise HTTPException(status_code=422, detail="邀请码无效或已过期")
    if ic.family_id == auth.family_id:
        raise HTTPException(status_code=422, detail="已在该家庭中")
    user = db.get(User, auth.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    # 归属唯一：加入新家庭 = 与当前家庭解绑（个人资料、账号设置一律不动）
    left = _detach(db, auth, auth.family_id)
    count = db.query(FamilyMember).filter(FamilyMember.family_id == ic.family_id).count()
    _bind(db, auth, ic.family_id, "member", PALETTE[count % len(PALETTE)])
    audit_service.record(db, ic.family_id, auth, action="join", target_type="family", target_id=ic.family_id,
                         text=f"「{_name_of(db, user.id)}」凭邀请码加入家庭空间")
    db.commit()
    return {
        "family": {"id": fam.id, "name": fam.name, "readonly": int(fam.readonly or 0), "role": "member"},
        "members": family_members(db, fam.id),
        "left_family": left,
    }


@router.patch("/readonly")
def set_readonly(body: FamilyReadonlyIn, db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)):
    _require_creator(auth)
    fam = db.get(Family, auth.family_id)
    if fam is None:
        raise HTTPException(status_code=404, detail="家庭不存在")
    fam.readonly = 1 if body.readonly else 0
    audit_service.record(
        db, auth.family_id, auth, action="readonly", target_type="family", target_id=auth.family_id,
        text=("开启家庭只读开关 · 全体成员暂时仅浏览" if fam.readonly else "关闭家庭只读开关 · 恢复全体成员编辑"),
    )
    db.commit()
    return {"family": _family_dict(db, auth), "members": family_members(db, auth.family_id)}


@router.patch("/members/{user_id}")
def set_member_role(user_id: str, body: MemberRoleIn, db: Session = Depends(get_db),
                    auth: AuthContext = Depends(get_auth)):
    _require_creator(auth)
    if body.role not in ("creator", "member"):
        raise HTTPException(status_code=422, detail="角色不合法")
    member = db.query(FamilyMember).filter(FamilyMember.family_id == auth.family_id,
                                           FamilyMember.user_id == user_id).first()
    if member is None:
        raise HTTPException(status_code=404, detail="成员不存在")
    # 不能把自己降级：家庭会永久失去管理者（没人再能邀请、踢人、开只读、清空数据）
    if user_id == auth.user_id and body.role != "creator":
        raise HTTPException(status_code=422, detail="不能取消自己的创建者身份")
    # 转让给他人时同步家庭创建者指针，避免 family.creator_id 与成员行角色不一致
    if body.role == "creator":
        others = (db.query(FamilyMember)
                  .filter(FamilyMember.family_id == auth.family_id,
                          FamilyMember.user_id != user_id,
                          FamilyMember.role == "creator")
                  .all())
        for other in others:
            other.role = "member"
    member.role = body.role
    fam = db.get(Family, auth.family_id)
    if fam is not None and body.role == "creator":
        fam.creator_id = user_id
    audit_service.record(
        db, auth.family_id, auth, action="role", target_type="member", target_id=user_id,
        text=f"将「{_name_of(db, user_id)}」的角色调整为「{_ROLE_TEXT.get(body.role, body.role)}」",
    )
    db.commit()
    return {"members": family_members(db, auth.family_id)}


@router.delete("/members/{user_id}")
def remove_member(user_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)):
    _require_creator(auth)
    if user_id == auth.user_id:
        # 创建者不能把自己移出：离开本家庭的唯一路径是凭邀请码加入其他家庭
        raise HTTPException(status_code=422, detail="创建者不能移除自己，可用邀请码加入其他家庭来离开")
    member = db.query(FamilyMember).filter(FamilyMember.family_id == auth.family_id,
                                           FamilyMember.user_id == user_id).first()
    if member is None:
        raise HTTPException(status_code=404, detail="成员不存在")
    db.delete(member)
    audit_service.record(db, auth.family_id, auth, action="leave", target_type="member", target_id=user_id,
                         text=f"「{_name_of(db, user_id)}」退出家庭空间")
    # 归属唯一：移除即与该家庭解绑，优先回落到其自己创建的家庭，否则置空（need_family）
    user = db.get(User, user_id)
    if user and user.family_id == auth.family_id:
        keep = ""
        own = db.query(Family).filter(Family.creator_id == user_id, Family.id != auth.family_id).first()
        if own:
            keep = own.id
            if not db.query(FamilyMember).filter(FamilyMember.family_id == own.id,
                                                 FamilyMember.user_id == user_id).first():
                db.add(FamilyMember(family_id=own.id, user_id=user_id, role="creator",
                                    color=PALETTE[0], joined_at=utc_now_iso()))
        user.family_id = keep
        for row in _memberships(db, user_id):
            if row.family_id != keep:
                db.delete(row)
    # 无需撤销令牌：鉴权时 family_id 是每次实时查库的，解绑后旧令牌立刻失去原家庭数据访问权；
    # 该用户若回落到自己创建的家庭，还要继续用现有会话，强制下线反而打断正常使用。
    db.commit()
    return {"members": family_members(db, auth.family_id)}
