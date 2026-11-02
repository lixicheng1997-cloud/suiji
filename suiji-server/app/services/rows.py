"""ORM → 契约 §1 行形状序列化（snake_case；标志位 0/1 与 bool 严格对齐客户端旧行）。"""
from ..models import (AiJournal, AuditLog, Baby, Entry, EntryMedia, FamilyMember, FileObject, Measurement,
                      MilestoneRecord, User, Vaccine)


def display_name(user: User, parent: dict | None = None) -> str:
    """成员展示名统一口径（绝不透出登录账号）：
    家长昵称（parent.name，等于用户名时视为未设置）→ 注册昵称（User.name，同上）
    → 与宝宝关系 → 家人。"""
    parent = parent or {}
    pname = (parent.get("name") or "").strip()
    if pname and pname != user.username:
        return pname
    if user.name and user.name != user.username:
        return user.name
    rel = (parent.get("relation") or "").strip()
    if rel:
        return rel
    return "家人"


def actor_label(user: User, parent: dict | None = None) -> str:
    """动态/通知里「记录人」的展示口径：与宝宝关系在前、昵称在后（「妈妈 · 李芳」）。

    与 display_name 的区别：display_name 是成员行的「名字」字段（昵称优先，关系在
    member_row.relation 里另列，家庭卡两张分开摆），反过来用会让家庭页出现
    「妈妈 · 妈妈」。这里的关系与昵称同样都不含登录账号（昵称等于账号名视为未设置）。
    """
    rel = ((parent or {}).get("relation") or "").strip()
    nm = display_name(user, parent)
    if nm == "家人":
        nm = ""
    if rel and nm and nm != rel:
        return rel + " · " + nm
    return rel or nm or "家人"


def baby_row(b: Baby) -> dict:
    return {
        "id": b.id, "name": b.name, "birth_date": b.birth_date,
        "gestational_weeks": int(b.gestational_weeks or 0), "gender": b.gender,
        "birth_length": b.birth_length, "birth_weight": b.birth_weight,
        "avatar": b.avatar or "", "allergy": b.allergy or "",
        "is_active": int(b.is_active or 0),
        "created_at": b.created_at, "updated_at": b.updated_at,
    }


def entry_row(e: Entry, with_trash_fields: bool = True) -> dict:
    row = {
        "id": e.id, "baby_id": e.baby_id or "", "type": e.type,
        "occurred_at": e.occurred_at, "created_at": e.created_at, "updated_at": e.updated_at,
        "is_backfilled": int(e.is_backfilled or 0),
        "note": e.note or "", "creator": e.creator or "", "creator_id": e.creator_id or "",
        "title": e.title or "", "meta": e.meta or "", "badge": e.badge or "",
        "photo": e.photo or "", "payload": e.payload or {},
        "deleted_at": e.deleted_at if e.deleted_at else None,
    }
    # deleted_by 仅在已软删时输出（与客户端回收站行一致）
    if with_trash_fields and e.deleted_at:
        row["deleted_by"] = e.deleted_by or ""
        row["deleted_by_id"] = e.deleted_by_id or ""
    return row


def media_row(m: EntryMedia) -> dict:
    url = f"/api/v1/media/{m.id}"
    return {
        "id": m.id, "entry_id": m.entry_id or "", "baby_id": m.baby_id or "",
        "storage_key": m.storage_key or "", "url": url, "local_path": url,
        "sha256": m.sha256 or "", "size": int(m.size or 0),
        "width": int(m.width or 0), "height": int(m.height or 0),
    }


def file_row(f: FileObject) -> dict:
    """非结构化文件行：字节在 MinIO，库里只有 storage_key（对象路径）与元信息。"""
    return {
        "id": f.id, "business_type": f.business_type or "", "business_id": f.business_id or "",
        "baby_id": f.baby_id or "", "original_name": f.original_name or "",
        "content_type": f.content_type or "", "ext": f.ext or "",
        "storage_key": f.storage_key or "",
        "url": f"/api/v1/files/{f.id}/download",
        "sha256": f.sha256 or "", "size": int(f.size or 0),
        "uploader_id": f.uploader_id or "", "created_at": f.created_at or "",
        "updated_at": f.updated_at or "", "meta": f.meta or {},
    }


def measurement_row(m: Measurement) -> dict:
    return {
        "id": m.id, "entry_id": m.entry_id or "", "baby_id": m.baby_id or "",
        "metric": m.metric, "value": m.value, "occurred_at": m.occurred_at,
        "corrected_age_flag": int(m.corrected_age_flag or 0),
    }


def milestone_row(m: MilestoneRecord) -> dict:
    return {
        "id": m.id, "baby_id": m.baby_id or "", "name": m.name, "domain": m.domain,
        "month": m.month, "ref": m.ref, "done": bool(m.done),
        "achieved_at": m.achieved_at or "", "source_entry_id": m.source_entry_id or "",
        "creator": m.creator or "", "sort": int(m.sort or 0),
    }


def vaccine_row(v: Vaccine) -> dict:
    return {
        "id": v.id, "code": v.code, "baby_id": v.baby_id or "", "n": v.n, "dose": v.dose,
        "age": v.age, "months": int(v.months or 0), "cls": v.cls, "sort": int(v.sort or 0),
        "plan_date": v.plan_date, "done": bool(v.done), "done_date": v.done_date or "",
        "org": v.org or "", "lot": v.lot or "", "remind": bool(v.remind),
        "remind_lead": int(v.remind_lead or 0),
        "created_at": v.created_at, "updated_at": v.updated_at,
    }


def journal_row(j: AiJournal) -> dict:
    return {
        "id": j.id, "baby_id": j.baby_id or "", "range": j.range,
        "range_start": j.range_start, "range_end": j.range_end,
        "paras": j.paras or [], "status": j.status,
        "model_version": j.model_version, "prompt_version": j.prompt_version,
        "fact_count": int(j.fact_count or 0), "created_at": j.created_at, "updated_at": j.updated_at,
    }


def member_row(user: User, member: FamilyMember, avatar: str = "", relation: str = "", name: str = "") -> dict:
    return {"id": user.id, "name": name or user.name, "role": member.role, "color": member.color,
            "avatar": avatar or "", "relation": relation or ""}


def audit_row(a: AuditLog) -> dict:
    """操作留痕行（FR-22）：只读，服务端不提供增改删接口。"""
    return {
        "id": a.id, "action": a.action or "", "actor_id": a.actor_id or "",
        "actor_name": a.actor_name or "家人", "target_type": a.target_type or "",
        "target_id": a.target_id or "", "text": a.text or "", "created_at": a.created_at,
    }


def user_row(u: User) -> dict:
    return {"id": u.id, "name": u.name, "username": u.username, "is_admin": int(u.is_admin or 0)}
