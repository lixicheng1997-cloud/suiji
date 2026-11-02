"""操作留痕服务（FR-22）：写入 audit_log 与按 180 天保留期读取。

留痕只由服务端在关键操作发生时写入，不对外提供任何增改删接口（成员不可自行删除）。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..core.deps import AuthContext
from ..domain.dates import utc_now_iso
from ..models import AuditLog, FamilyMember, Setting, User
from .ids import gen_id
from .rows import audit_row, display_name

KEEP_DAYS = 180


def record(db: Session, family_id: str, actor: AuthContext | None = None, action: str = "",
           text: str = "", target_type: str = "", target_id: str = "",
           actor_name: str = "", actor_id: str = "", created_at: str = "") -> AuditLog | None:
    """写一条留痕；无家庭归属（尚未关联家庭）时不落行。

    调用方负责在自身事务里 commit；family_id 为空直接返回 None 而非抛错，
    避免留痕副作用影响主流程（如创建家庭之前、尚无家庭时）。
    """
    if not family_id:
        return None
    row = AuditLog(
        id=gen_id("a"),
        family_id=family_id,
        action=action,
        actor_id=actor_id or (actor.user_id if actor else ""),
        actor_name=actor_name or (actor.name or (actor.username if actor else "")) or "家人",
        target_type=target_type,
        target_id=target_id or "",
        text=text,
        created_at=created_at or utc_now_iso(),
    )
    db.add(row)
    return row


def list_recent(db: Session, family_id: str, limit: int = 200, days: int = KEEP_DAYS,
                offset: int = 0) -> list[dict]:
    """近 `days` 天内的家庭留痕，倒序返回（默认 180 天，与保留期一致）。

    offset/limit 供客户端上滑分页：offset 从 0 起按页递增。
    """
    if not family_id:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.family_id == family_id, AuditLog.created_at >= cutoff)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 500)))
        .all()
    )
    # 显示口径（操作记录页，绝不透出登录账号）：
    # - actor_name 读取时按 actor_id 实时解析统一显示名（家长昵称 → 注册昵称 → 关系 → 家人）；
    # - actor_relation 取家长信息 parent.relation（与宝宝关系，未设置为空串）；
    # - text 里历史落库的用户名（注册默认名=登录账号）按同一口径替换为显示名。
    actor_ids = {r.actor_id for r in rows if r.actor_id}
    member_ids = {uid for (uid,) in db.query(FamilyMember.user_id)
                  .filter(FamilyMember.family_id == family_id).all()}
    ids = actor_ids | member_ids
    info_map: dict[str, tuple[str, str]] = {}
    repl: dict[str, str] = {}
    if ids:
        for u in db.query(User).filter(User.id.in_(ids)).all():
            st = db.get(Setting, u.id)
            parent = ((st.data or {}).get("parent") or {}) if st else {}
            dn = display_name(u, parent)
            info_map[u.id] = (dn, (parent.get("relation") or ""))
            if u.username and u.username != dn:
                repl[u.username] = dn
    out = []
    for r in rows:
        d = audit_row(r)
        if r.actor_id and r.actor_id in info_map:
            nm, rel = info_map[r.actor_id]
            d["actor_name"] = nm
            d["actor_relation"] = rel
        else:
            d["actor_relation"] = ""
            if d.get("actor_name") in repl:
                d["actor_name"] = repl[d["actor_name"]]
        txt = d.get("text") or ""
        for uname, dn in repl.items():
            if uname in txt:
                txt = txt.replace(uname, dn)
        d["text"] = txt
        out.append(d)
    return out
