"""管理后台 /admin：数据概览、用户与家庭管理、审计日志、媒体中心。

鉴权口径：
  - 除媒体字节通道外，全部端点挂 require_admin（Bearer access + is_admin 实时查库）；
  - /media/{id}/content 供 <img>/<video> 直连：query 只认受限 media 令牌 + is_admin 校验，
    与 /files/{id}/download 同款「URL 不落业务凭证」策略；
  - 不挂 require_family：管理员的「系统管理」家庭被误删时后台不能自锁。

隐私口径：媒体中心是跨家庭特权——看原图/完整媒体必写 admin_media_view 留痕；
列表页缩略图批量请求不留痕（避免刷屏）。
"""
import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import AuthContext, require_admin, resolve_token
from ..core.security import MEDIA, hash_password
from ..core.session_store import session_store
from ..domain.dates import utc_now_iso
from ..models import (AiJournal, AuditLog, Baby, Entry, EntryMedia, Family,
                      FamilyMember, FileObject, User)
from ..schemas import UserStatusIn
from ..services import audit_service, file_service
from ..services.rows import audit_row, file_row
from .files import serve_file

router = APIRouter(prefix="/admin", tags=["admin"])

_TEMP_PWD_ALPHABET = string.ascii_letters + string.digits


def _temp_password() -> str:
    """一次性临时密码：Sj@ + 10 位随机字母数字。

    带符号保证非纯字母/纯数字（auth 的口令强度校验），长度 13 位以上，
    展示一次后即失效（用户下次登录应自行改密）。
    """
    return "Sj@" + "".join(secrets.choice(_TEMP_PWD_ALPHABET) for _ in range(10))


def _family_names(db: Session, family_ids: set[str]) -> dict[str, str]:
    ids = {i for i in family_ids if i}
    if not ids:
        return {}
    return {f.id: f.name for f in db.query(Family).filter(Family.id.in_(ids)).all()}


def _display_names(db: Session, user_ids: set[str]) -> dict[str, str]:
    ids = {i for i in user_ids if i}
    if not ids:
        return {}
    return {u.id: (u.name or u.username)
            for u in db.query(User).filter(User.id.in_(ids)).all()}


def _day_bounds(start: str, end: str) -> tuple[str, str]:
    """'YYYY-MM-DD' → (>= start, < end+1天) 的字符串比较边界。

    时间字段混存（ISO Z 串 / 本地格式），按前 10 位字典序比较是近似口径，
    UI 已标注；日粒度统计误差可接受。
    """
    lo = (start or "").strip()[:10]
    hi = ""
    if (end or "").strip():
        try:
            d = datetime.strptime(end.strip()[:10], "%Y-%m-%d") + timedelta(days=1)
            hi = d.strftime("%Y-%m-%d")
        except ValueError:
            hi = ""
    return lo, hi


# ---------- 会话自检 ----------

@router.get("/me")
def admin_me(db: Session = Depends(get_db), auth: AuthContext = Depends(require_admin)):
    """前端守卫用：确认当前令牌仍是管理员（被撤权/停用后立即失效）。"""
    user = db.get(User, auth.user_id)
    return {"id": auth.user_id, "username": auth.username, "name": auth.name,
            "is_admin": 1, "status": int(user.status or 0) if user else 1}


# ---------- 数据概览 ----------

@router.get("/stats/overview")
def stats_overview(db: Session = Depends(get_db), auth: AuthContext = Depends(require_admin)):
    def cnt(q) -> int:
        return int(q.scalar() or 0)

    today = utc_now_iso()[:10]
    return {
        "users": cnt(db.query(func.count(User.id))),
        "families": cnt(db.query(func.count(Family.id))),
        "babies": cnt(db.query(func.count(Baby.id)).filter(Baby.deleted_at.is_(None))),
        "entries": cnt(db.query(func.count(Entry.id)).filter(Entry.deleted_at.is_(None))),
        "files": cnt(db.query(func.count(FileObject.id)).filter(FileObject.deleted_at.is_(None))),
        "storage_bytes": cnt(db.query(func.coalesce(func.sum(FileObject.size), 0))
                             .filter(FileObject.deleted_at.is_(None))),
        "llm_journals": cnt(db.query(func.count(AiJournal.id))
                            .filter(AiJournal.model_version != "template")),
        "users_today": cnt(db.query(func.count(User.id)).filter(User.created_at >= today)),
        "entries_today": cnt(db.query(func.count(Entry.id)).filter(Entry.created_at >= today)),
        "note": "按服务端 UTC 日界统计；历史时间格式混存，日粒度存在少量误差",
    }


@router.get("/stats/trend")
def stats_trend(days: int = Query(7, ge=1, le=90),
                db: Session = Depends(get_db), auth: AuthContext = Depends(require_admin)):
    """按日桶的新增用户/记录折线（substr(created_at,1,10) 字符串口径）。"""
    start_day = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    def bucket(model) -> dict[str, int]:
        rows = (db.query(func.substr(model.created_at, 1, 10).label("d"), func.count(model.id))
                .filter(model.created_at >= start_day)
                .group_by("d").all())
        return {d: int(c) for d, c in rows if d}

    umap = bucket(User)
    emap = bucket(Entry)
    base = datetime.strptime(start_day, "%Y-%m-%d")
    items = []
    for i in range(days):
        d = (base + timedelta(days=i)).strftime("%Y-%m-%d")
        items.append({"date": d, "users": umap.get(d, 0), "entries": emap.get(d, 0)})
    return {"days": days, "items": items, "note": "UTC 日界；时间混存误差可接受"}


# ---------- 用户管理 ----------

@router.get("/users")
def list_users(kw: str = Query(""), page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
               db: Session = Depends(get_db), auth: AuthContext = Depends(require_admin)):
    q = db.query(User)
    kw = (kw or "").strip()
    if kw:
        like = f"%{kw}%"
        q = q.filter(or_(User.username.like(like), User.name.like(like), User.id.like(like)))
    total = q.count()
    rows = q.order_by(User.created_at.desc(), User.id.desc()) \
            .offset((page - 1) * size).limit(size).all()
    fam_names = _family_names(db, {u.family_id for u in rows})
    roles: dict[tuple[str, str], str] = {}
    fids = {u.family_id for u in rows if u.family_id}
    if fids:
        for m in db.query(FamilyMember).filter(FamilyMember.family_id.in_(fids),
                                               FamilyMember.user_id.in_({u.id for u in rows})):
            roles[(m.family_id, m.user_id)] = m.role
    items = [{
        "id": u.id, "username": u.username, "name": u.name or "",
        "is_admin": int(u.is_admin or 0), "status": int(u.status or 0),
        "family_id": u.family_id or "", "family_name": fam_names.get(u.family_id, ""),
        "role": roles.get((u.family_id, u.id), ""),
        "created_at": u.created_at or "",
        "deletion_scheduled_at": u.deletion_scheduled_at or "",
    } for u in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/users/{user_id}")
def user_detail(user_id: str, db: Session = Depends(get_db),
                auth: AuthContext = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    memberships = []
    for m in db.query(FamilyMember).filter(FamilyMember.user_id == user_id).all():
        fam = db.get(Family, m.family_id)
        memberships.append({"family_id": m.family_id, "family_name": fam.name if fam else "",
                            "role": m.role, "joined_at": m.joined_at or ""})
    babies = 0
    if user.family_id:
        babies = int(db.query(func.count(Baby.id))
                     .filter(Baby.family_id == user.family_id, Baby.deleted_at.is_(None))
                     .scalar() or 0)
    entries = int(db.query(func.count(Entry.id))
                  .filter(Entry.creator_id == user.id, Entry.deleted_at.is_(None))
                  .scalar() or 0)
    return {
        "id": user.id, "username": user.username, "name": user.name or "",
        "is_admin": int(user.is_admin or 0), "status": int(user.status or 0),
        "family_id": user.family_id or "", "created_at": user.created_at or "",
        "deletion_scheduled_at": user.deletion_scheduled_at or "",
        "memberships": memberships, "babies": babies, "entries": entries,
    }


@router.post("/users/{user_id}/status")
def set_user_status(body: UserStatusIn, user_id: str, db: Session = Depends(get_db),
                    auth: AuthContext = Depends(require_admin)):
    """停用/启用账号。停用 = bump_epoch 全端下线 + login/refresh/_resolve 三层拦截。

    防护：不能停用自己、不能停用管理员账号（防止把后台唯一入口关掉）。
    """
    if body.status not in (0, 1):
        raise HTTPException(status_code=422, detail="status 只能是 0（启用）或 1（停用）")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.status == 1:
        if target.id == auth.user_id:
            raise HTTPException(status_code=400, detail="不能停用自己的账号")
        if int(target.is_admin or 0):
            raise HTTPException(status_code=400, detail="不能停用管理员账号")
    target.status = int(body.status)
    audit_service.record(db, auth.family_id, actor=auth, action="admin_user",
                         target_type="user", target_id=target.id,
                         text=f"{'停用' if body.status == 1 else '启用'}账号 {target.username}")
    db.commit()
    if body.status == 1:
        session_store.bump_epoch(target.id)
    return {"id": target.id, "status": target.status}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: str, db: Session = Depends(get_db),
                   auth: AuthContext = Depends(require_admin)):
    """管理员特权路径：服务端生成一次性临时密码，不校验旧密码。

    防护：不能重置自己（应走 App 内改密）、不能重置管理员账号。
    重置后 bump_epoch：旧令牌立即失效，用户必须用临时密码重新登录。
    """
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == auth.user_id:
        raise HTTPException(status_code=400, detail="不能重置自己的密码，请在 App 内修改")
    if int(target.is_admin or 0):
        raise HTTPException(status_code=400, detail="不能重置管理员账号的密码")
    temp = _temp_password()
    target.password_hash = hash_password(temp)
    audit_service.record(db, auth.family_id, actor=auth, action="admin_user",
                         target_type="user", target_id=target.id,
                         text=f"重置账号 {target.username} 的密码")
    db.commit()
    session_store.bump_epoch(target.id)
    return {"id": target.id, "temp_password": temp}


# ---------- 家庭管理 ----------

@router.get("/families")
def list_families(kw: str = Query(""), page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db), auth: AuthContext = Depends(require_admin)):
    q = db.query(Family)
    kw = (kw or "").strip()
    if kw:
        like = f"%{kw}%"
        q = q.filter(or_(Family.name.like(like), Family.id.like(like)))
    total = q.count()
    rows = q.order_by(Family.created_at.desc(), Family.id.desc()) \
            .offset((page - 1) * size).limit(size).all()
    fids = {f.id for f in rows}
    if not fids:
        return {"items": [], "total": total, "page": page, "size": size}

    def _grouped_count(model, extra=None) -> dict[str, int]:
        q2 = db.query(model.family_id, func.count(model.id)).filter(model.family_id.in_(fids))
        if extra is not None:
            q2 = q2.filter(extra)
        return {fid: int(c) for fid, c in q2.group_by(model.family_id).all()}

    member_cnt = _grouped_count(FamilyMember)
    baby_cnt = _grouped_count(Baby, Baby.deleted_at.is_(None))
    entry_cnt = _grouped_count(Entry, Entry.deleted_at.is_(None))
    creator_names = _display_names(db, {f.creator_id for f in rows})
    items = [{
        "id": f.id, "name": f.name or "", "creator_id": f.creator_id or "",
        "creator_name": creator_names.get(f.creator_id, ""), "created_at": f.created_at or "",
        "member_count": member_cnt.get(f.id, 0), "baby_count": baby_cnt.get(f.id, 0),
        "entry_count": entry_cnt.get(f.id, 0),
    } for f in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/families/{family_id}/members")
def family_members(family_id: str, db: Session = Depends(get_db),
                   auth: AuthContext = Depends(require_admin)):
    """家庭成员名单：管理端解绑操作的入口数据（v1 解绑 UI 需要按家庭看成员）。"""
    fam = db.get(Family, family_id)
    if not fam:
        raise HTTPException(status_code=404, detail="家庭不存在")
    members = db.query(FamilyMember).filter(FamilyMember.family_id == family_id) \
               .order_by(FamilyMember.joined_at).all()
    items = []
    for m in members:
        u = db.get(User, m.user_id)
        if not u:
            continue
        items.append({"user_id": u.id, "username": u.username, "name": u.name or "",
                      "role": m.role, "color": m.color or "", "joined_at": m.joined_at or "",
                      "is_admin": int(u.is_admin or 0), "status": int(u.status or 0),
                      "is_creator": fam.creator_id == u.id})
    return {"family_id": fam.id, "family_name": fam.name or "",
            "creator_id": fam.creator_id or "", "items": items}


@router.post("/families/{family_id}/members/{user_id}/unbind")
def unbind_member(family_id: str, user_id: str, db: Session = Depends(get_db),
                  auth: AuthContext = Depends(require_admin)):
    """强制解绑：删成员行 + 清 user.family_id，写审计留痕。

    不 bump_epoch：客户端拉到 409 need_family 回引导页是预期行为，
    历史数据留在原家庭，重新加入后仍可见。
    防护：不能解绑自己 / 管理员 / 家庭创建者（防止把家庭搞成无主状态）。
    """
    member = (db.query(FamilyMember)
              .filter(FamilyMember.family_id == family_id, FamilyMember.user_id == user_id)
              .first())
    if not member:
        raise HTTPException(status_code=404, detail="该用户不在此家庭")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == auth.user_id:
        raise HTTPException(status_code=400, detail="不能解绑自己")
    if int(target.is_admin or 0):
        raise HTTPException(status_code=400, detail="不能解绑管理员账号")
    fam = db.get(Family, family_id)
    if fam and fam.creator_id == target.id:
        raise HTTPException(status_code=400, detail="不能解绑家庭创建者，请先在 App 内转移或解散家庭")
    db.delete(member)
    if target.family_id == family_id:
        target.family_id = ""
    audit_service.record(db, family_id, actor=auth, action="admin_unbind",
                         target_type="member", target_id=target.id,
                         text=f"管理员将 {target.username} 移出家庭「{fam.name if fam else family_id}」")
    db.commit()
    return {"ok": True, "user_id": target.id, "family_id": family_id}


# ---------- 审计日志 ----------

@router.get("/audit")
def list_audit(actor: str = Query(""), family: str = Query(""), action: str = Query(""),
               start: str = Query(""), end: str = Query(""),
               page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
               db: Session = Depends(get_db), auth: AuthContext = Depends(require_admin)):
    """跨家庭查 audit_log：可按操作人（id/名字/文本模糊）、家庭、动作、日期区间过滤。"""
    q = db.query(AuditLog)
    if family:
        q = q.filter(AuditLog.family_id == family.strip())
    if action:
        q = q.filter(AuditLog.action == action.strip())
    actor_kw = (actor or "").strip()
    if actor_kw:
        like = f"%{actor_kw}%"
        q = q.filter(or_(AuditLog.actor_id == actor_kw, AuditLog.actor_name.like(like),
                         AuditLog.text.like(like)))
    lo, hi = _day_bounds(start, end)
    if lo:
        q = q.filter(AuditLog.created_at >= lo)
    if hi:
        q = q.filter(AuditLog.created_at < hi)
    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()) \
            .offset((page - 1) * size).limit(size).all()
    fam_names = _family_names(db, {a.family_id for a in rows})
    items = [dict(audit_row(a), family_id=a.family_id, family_name=fam_names.get(a.family_id, ""))
             for a in rows]
    return {"items": items, "total": total, "page": page, "size": size}


# ---------- 媒体中心 ----------

@router.get("/media")
def media_list(family: str = Query(""), mtype: str = Query("", alias="type"),
               start: str = Query(""), end: str = Query(""),
               page: int = Query(1, ge=1), size: int = Query(24, ge=1, le=100),
               db: Session = Depends(get_db), auth: AuthContext = Depends(require_admin)):
    """跨家庭文件台账：按 content_type 前缀分 image/video/audio/other，join 家庭/上传者/记录归属。

    缩略图与预览地址是管理端 content 通道的基础路径，前端拼上 media 令牌后使用。
    """
    q = db.query(FileObject).filter(FileObject.deleted_at.is_(None))
    if family:
        q = q.filter(FileObject.family_id == family.strip())
    t = (mtype or "").strip().lower()
    if t in ("image", "video", "audio"):
        q = q.filter(FileObject.content_type.like(f"{t}/%"))
    elif t == "other":
        q = q.filter(~FileObject.content_type.like("image/%"),
                     ~FileObject.content_type.like("video/%"),
                     ~FileObject.content_type.like("audio/%"))
    lo, hi = _day_bounds(start, end)
    if lo:
        q = q.filter(FileObject.created_at >= lo)
    if hi:
        q = q.filter(FileObject.created_at < hi)
    total = q.count()
    rows = q.order_by(FileObject.created_at.desc(), FileObject.id.desc()) \
            .offset((page - 1) * size).limit(size).all()
    fam_names = _family_names(db, {r.family_id for r in rows})
    uploader_names = _display_names(db, {r.uploader_id for r in rows})
    # entry 归属反查：与 file_service._entry_for_file 同口径，但去掉家庭过滤（admin 特权）
    entry_ids = {r.business_id for r in rows if r.business_type == "entry" and r.business_id}
    media_ids = {r.business_id for r in rows if r.business_type == "entry_media" and r.business_id}
    emap: dict[str, str] = {}
    if media_ids:
        for m in db.query(EntryMedia).filter(EntryMedia.id.in_(media_ids)).all():
            if m.entry_id:
                emap[m.id] = m.entry_id
                entry_ids.add(m.entry_id)
    live_entries = {e for (e,) in db.query(Entry.id).filter(Entry.id.in_(entry_ids)).all()} if entry_ids else set()
    items = []
    for r in rows:
        d = file_row(r)
        d["family_name"] = fam_names.get(r.family_id, "")
        d["uploader_name"] = uploader_names.get(r.uploader_id, "")
        eid = ""
        if r.business_type == "entry":
            eid = r.business_id
        elif r.business_type == "entry_media":
            eid = emap.get(r.business_id, "")
        d["entry_id"] = eid if eid in live_entries else ""
        d["thumb_url"] = f"/api/v1/admin/media/{r.id}/content?inline=1&variant=thumb"
        d["content_url"] = f"/api/v1/admin/media/{r.id}/content?inline=1"
        items.append(d)
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/media/{file_id}/content")
def media_content(file_id: str, request: Request, token: str = Query(""),
                  inline: int = Query(0), variant: str = Query(""),
                  db: Session = Depends(get_db)):
    """媒体字节通道（跨家庭特权）：<img>/<video> 直连用。

    鉴权只认 query 里的受限 media 令牌（会进 access_log/历史，不能调业务接口）
    + is_admin 实时查库；字节管线与 /files/{id}/download 完全一致（serve_file）。
    留痕：看原图/完整媒体（variant 为空）记一条 admin_media_view；缩略图批量请求不留痕。
    """
    auth = resolve_token(db, token, types=(MEDIA,))
    if auth is None or not auth.is_admin:
        raise HTTPException(status_code=403, detail="无权访问该文件")
    row = db.get(FileObject, file_id)
    if row is None or row.deleted_at:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not variant:
        audit_service.record(db, row.family_id, actor=auth, action="admin_media_view",
                             target_type="file", target_id=row.id,
                             text=f"查看文件 {row.original_name or row.id}")
        db.commit()
    return serve_file(row, request, inline, variant)
