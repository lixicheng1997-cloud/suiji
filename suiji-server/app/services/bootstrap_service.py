"""bootstrap 全量快照（契约 §3）：一次请求填充客户端缓存。"""
from sqlalchemy.orm import Session

from ..core.deps import AuthContext
from ..models import (
    AiJournal,
    Baby,
    Entry,
    EntryMedia,
    Family,
    FamilyMember,
    Measurement,
    MilestoneRecord,
    Setting,
    User,
    Vaccine,
)
from .rows import (
    baby_row,
    display_name,
    entry_row,
    journal_row,
    media_row,
    measurement_row,
    member_row,
    milestone_row,
    user_row,
    vaccine_row,
)


def family_members(db: Session, family_id: str) -> list[dict]:
    rows = db.query(FamilyMember).filter(FamilyMember.family_id == family_id).all()
    out = []
    for fm in rows:
        u = db.get(User, fm.user_id)
        if u:
            # 成员头像/与宝宝关系：取该用户设置 parent.avatar / parent.relation（家长信息页保存）
            st = db.get(Setting, u.id)
            parent = ((st.data or {}).get("parent") or {}) if st else {}
            avatar = parent.get("avatar") or ""
            relation = parent.get("relation") or ""
            out.append(member_row(u, fm, avatar, relation, display_name(u, parent)))
    return out


def snapshot(db: Session, auth: AuthContext) -> dict:
    fam = db.get(Family, auth.family_id) if auth.family_id else None
    fid = fam.id if fam else ""
    active = db.query(Baby).filter(Baby.family_id == fid, Baby.is_active == 1).first()
    settings_row = db.get(Setting, auth.user_id)
    user = db.get(User, auth.user_id)
    return {
        "user": user_row(user) if user else None,
        "family": {
            "id": fid,
            "name": fam.name if fam else "",
            "readonly": int(fam.readonly or 0) if fam else 0,
            "role": auth.role,
            # 事件版本水位：客户端据此判断「距上次快照后家里有没有发生过变更」
            "events_version": int(fam.events_version or 0) if fam else 0,
            "members": family_members(db, fid),
        },
        "active_baby_id": active.id if active else "",
        "babies": [baby_row(b) for b in db.query(Baby).filter(Baby.family_id == fid).order_by(Baby.created_at)],
        "entries": [
            entry_row(e)
            for e in db.query(Entry)
            .filter(Entry.family_id == fid, Entry.deleted_at.is_(None))
            .order_by(Entry.occurred_at.desc())
        ],
        "measurements": [measurement_row(m) for m in db.query(Measurement).filter(Measurement.family_id == fid)],
        "media": [media_row(m) for m in db.query(EntryMedia).filter(EntryMedia.family_id == fid)],
        "milestone_records": [
            milestone_row(m)
            for m in db.query(MilestoneRecord).filter(MilestoneRecord.family_id == fid).order_by(MilestoneRecord.sort)
        ],
        "vaccines": [
            vaccine_row(v) for v in db.query(Vaccine).filter(Vaccine.family_id == fid).order_by(Vaccine.sort, Vaccine.months)
        ],
        "journals": [
            journal_row(j)
            for j in db.query(AiJournal).filter(AiJournal.family_id == fid).order_by(AiJournal.created_at.desc())
        ],
        "settings": (settings_row.data or {}) if settings_row else {},
        "trash": [
            entry_row(e)
            for e in db.query(Entry)
            .filter(Entry.family_id == fid, Entry.deleted_at.isnot(None))
            .order_by(Entry.deleted_at.desc())
        ],
    }
