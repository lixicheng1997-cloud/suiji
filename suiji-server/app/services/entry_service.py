"""记录服务：创建/更新/软删/恢复/彻底删除/游标分页 + measure/milestone 副作用。"""
import base64

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..core.deps import AuthContext
from ..core.redis_client import idem_store
from ..domain import growth_lms
from ..domain.dates import age_months, age_text, utc_now_iso
from ..models import Baby, Entry, EntryMedia, FileObject, GrowthPoint, Measurement, MilestoneRecord
from . import audit_service
from . import notify_service
from .ids import gen_id
from .rows import entry_row

# mood（心情）是客户端 mock.js 的正类型，note 是它的历史别名：
# 快速记录面板给出的「心情」 tile 走 type=mood，这里不收就永远 422 存不下来
TYPES = {"feeding", "sleep", "milestone", "measure", "poop", "temp", "med", "photo", "note", "mood", "voice"}

_MEASURE_METRICS = ("height", "weight", "head")

_actor_name = notify_service.actor_name
_bump_family_version = notify_service.bump_family_version


def _notify_event(db: Session, auth: AuthContext, entry: Entry, action: str = "create") -> None:
    """给同家庭其他成员逐人落一条家人动态通知（读过即删，由 GET/POST /notifications 消费）。

    action:
      - create：新建记录，文案「X 记录了一次喂养」；补录（is_backfilled）不通知。
      - delete：软删记录，文案「X 删除了记录「标题」」。
      - restore：从回收站恢复，文案「X 恢复了记录「标题」」。
    修改（PUT）不通知家人——误触编辑会刷屏；数据对齐靠 events_version 水位重拉 bootstrap。
    按收件人 user_id 精确投递（排除操作者本人）。
    """
    if action == "create" and entry.is_backfilled:
        return
    actor = _actor_name(db, auth)
    label = (entry.title or "").strip()
    label_seg = f"「{label}」" if label else f"记录 {entry.id[-6:]}"
    if action == "create":
        text = notify_service.FEED_TEXT.get(entry.type, "记录了一条动态")
        content = f"{actor} {text}" + (f"「{label}」" if label else "")
        ntype = "feed"
    elif action == "delete":
        content = f"{actor} 删除了{label_seg}"
        ntype = "delete"
    elif action == "restore":
        content = f"{actor} 恢复了{label_seg}"
        ntype = "restore"
    else:
        return
    notify_service.notify_family(db, auth, ntype=ntype, content=content,
                                 entry_id=entry.id, actor=actor)


def _as_int(v) -> int:
    return 1 if v in (1, True, "1", "true") else 0


def _check_note(note) -> None:
    """备注走 EncryptedString(2048)：密文列宽按字符算，约 720 个汉字就到顶，
    再长会在 Postgres 上 value too long → 500。超限直接 422，让客户端提示改写。"""
    if isinstance(note, str) and len(note) > 700:
        raise HTTPException(status_code=422, detail="备注过长（上限 700 字）")


def _active_baby_id(db: Session, family_id: str) -> str:
    b = (
        db.query(Baby)
        .filter(Baby.family_id == family_id, Baby.is_active == 1)
        .first()
    )
    return b.id if b else ""


def _find_baby(db: Session, family_id: str, baby_id: str) -> Baby | None:
    if not baby_id:
        return None
    b = db.get(Baby, baby_id)
    return b if b and b.family_id == family_id else None


def _resolve_baby_id(db: Session, family_id: str, baby_id: str, default: str = "") -> str:
    """把客户端传入的 baby_id 收敛成本家庭的宝宝；落不到本家庭就 403。

    之前的实现只是「拿不到 baby 就算不出百分位」，并不拒绝跨家庭的 baby_id：
    结果是自家记录可以挂到别人家的宝宝上（数据污染、生长曲线错算），
    也让「记录归属」这个最关键的隔离边界出现了一个客户端可控的口子。
    """
    if not baby_id:
        return default
    if _find_baby(db, family_id, baby_id) is None:
        raise HTTPException(status_code=403, detail="无权访问该宝宝")
    return baby_id


def _apply_measure(db: Session, entry: Entry, baby: Baby | None) -> None:
    """按 payload 生成 measurement 行并算百分位落 growth_point。"""
    payload = entry.payload or {}
    for metric in _MEASURE_METRICS:
        try:
            value = float(payload.get(metric) or 0)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        m = Measurement(
            id=gen_id("m"), family_id=entry.family_id, entry_id=entry.id,
            baby_id=entry.baby_id, metric=metric, value=value,
            occurred_at=entry.occurred_at,
            corrected_age_flag=_as_int(baby and (baby.gestational_weeks or 0) and baby.gestational_weeks < 37),
        )
        db.add(m)
        if baby and baby.birth_date:
            age_m = age_months(baby.birth_date, entry.occurred_at, baby.gestational_weeks)
            p = growth_lms.percentile_of(metric, baby.gender, age_m, value)
            db.add(GrowthPoint(
                measurement_id=m.id, percentile_p=round(p, 2),
                z_score=round(growth_lms.z_from_percentile(p), 3),
                standard_version=growth_lms.standard_version(),
            ))


def _rebuild_measurements(db: Session, entry: Entry) -> None:
    old_ids = [m.id for m in db.query(Measurement).filter(Measurement.entry_id == entry.id)]
    if old_ids:
        db.query(GrowthPoint).filter(GrowthPoint.measurement_id.in_(old_ids)).delete(synchronize_session=False)
        db.query(Measurement).filter(Measurement.id.in_(old_ids)).delete(synchronize_session=False)
    _apply_measure(db, entry, _find_baby(db, entry.family_id, entry.baby_id))


def _apply_milestone(db: Session, entry: Entry) -> None:
    """payload.name 匹配该宝宝 milestone_record → 置达成；不在预置清单则新建自定义里程碑。"""
    name = (entry.payload or {}).get("name")
    if not name:
        return
    ms = (
        db.query(MilestoneRecord)
        .filter(MilestoneRecord.family_id == entry.family_id,
                MilestoneRecord.baby_id == entry.baby_id,
                MilestoneRecord.name == name)
        .first()
    )
    baby = _find_baby(db, entry.family_id, entry.baby_id)
    month = (age_text(baby.birth_date, entry.occurred_at, baby.gestational_weeks) + "达成"
             if baby and baby.birth_date else "已达成")
    if not ms:
        ms = MilestoneRecord(
            id=gen_id("msr"), family_id=entry.family_id, baby_id=entry.baby_id or "",
            name=name, domain="自定义", month="", ref="",
            done=False, achieved_at="", source_entry_id="", creator="", sort=999,
        )
        db.add(ms)
    ms.done = True
    ms.achieved_at = entry.occurred_at
    ms.source_entry_id = entry.id
    ms.creator = entry.creator or ""
    ms.month = month


def create_entry(db: Session, auth: AuthContext, body: dict, idem_key: str = "") -> dict:
    """POST /entries：幂等命中直接返回已存响应；否则建行 + 副作用。"""
    if idem_key:
        hit = idem_store.get(auth.family_id, idem_key)
        if hit is not None:
            return hit

    etype = body.get("type")
    if etype not in TYPES:
        raise HTTPException(status_code=422, detail="未知的记录类型")
    _check_note(body.get("note"))

    now = utc_now_iso()
    baby_id = _resolve_baby_id(db, auth.family_id, body.get("baby_id"),
                               _active_baby_id(db, auth.family_id))
    entry = Entry(
        id=body.get("id") or gen_id("e"),
        family_id=auth.family_id,
        baby_id=baby_id,
        type=etype,
        occurred_at=body.get("occurred_at") or now,
        created_at=body.get("created_at") or now,
        updated_at=body.get("updated_at") or now,
        is_backfilled=_as_int(body.get("is_backfilled")),
        note=body.get("note") or "",
        # 记录人只认令牌，不采信客户端传的 creator 串（客户端传的是注册昵称，
        # 与成员表展示名不同源，靠名字解析会退化成「家人」）；ID 才是权威依据。
        creator=_actor_name(db, auth),
        creator_id=auth.user_id,
        title=body.get("title") or "",
        meta=body.get("meta") or "",
        badge=body.get("badge") or "",
        photo=body.get("photo") or "",
        payload=body.get("payload") or {},
    )
    dup = db.get(Entry, entry.id)
    if dup is not None:
        if dup.family_id != auth.family_id:
            raise HTTPException(status_code=403, detail="无权访问该记录")
        # 同 id 重复提交（幂等键缺失的兜底）：直接返回既有行
        row = entry_row(dup)
        if idem_key:
            idem_store.set(auth.family_id, idem_key, row)
        return row

    db.add(entry)
    db.flush()
    if entry.type == "measure":
        _apply_measure(db, entry, _find_baby(db, auth.family_id, baby_id))
    elif entry.type == "milestone":
        _apply_milestone(db, entry)
    _notify_event(db, auth, entry, action="create")
    _bump_family_version(db, auth.family_id)
    label = f"「{entry.title}」" if entry.title else f" {entry.id[-6:]}"
    audit_service.record(db, auth.family_id, auth, action="create", target_type="entry",
                         target_id=entry.id, text=f"新增记录{label}")
    db.commit()
    db.refresh(entry)

    row = entry_row(entry)
    if idem_key:
        idem_store.set(auth.family_id, idem_key, row)
    return row


def update_entry(db: Session, auth: AuthContext, entry_id: str, body: dict) -> dict:
    from ..repositories import scoped_get

    entry = scoped_get(db, Entry, entry_id, auth.family_id)
    if body.get("type") is not None and body["type"] not in TYPES:
        raise HTTPException(status_code=422, detail="未知的记录类型")
    _check_note(body.get("note"))
    for field in ("baby_id", "type", "occurred_at", "note",
                  "title", "meta", "badge", "photo"):
        if field in body and body[field] is not None:
            if field == "baby_id":
                # 改挂宝宝同样要校验归属：否则可以把自己家的记录挂到别人家宝宝名下
                entry.baby_id = _resolve_baby_id(db, auth.family_id, body[field], entry.baby_id)
            else:
                setattr(entry, field, body[field])
    if "is_backfilled" in body:
        entry.is_backfilled = _as_int(body["is_backfilled"])
    if "payload" in body:
        entry.payload = body["payload"] or {}
    entry.updated_at = body.get("updated_at") or utc_now_iso()
    if entry.type == "measure":
        _rebuild_measurements(db, entry)
    elif entry.type == "milestone":
        _apply_milestone(db, entry)
    _bump_family_version(db, auth.family_id)  # 修改不通知家人，但水位线要让客户端重拉对齐
    db.commit()
    db.refresh(entry)
    return entry_row(entry)


def soft_delete(db: Session, auth: AuthContext, entry_id: str) -> dict:
    from ..repositories import scoped_get

    entry = scoped_get(db, Entry, entry_id, auth.family_id)
    entry.deleted_at = utc_now_iso()
    entry.deleted_by = _actor_name(db, auth)
    entry.deleted_by_id = auth.user_id
    _notify_event(db, auth, entry, action="delete")
    _bump_family_version(db, auth.family_id)
    db.commit()
    db.refresh(entry)
    return entry_row(entry)


def restore(db: Session, auth: AuthContext, entry_id: str) -> dict:
    from ..repositories import scoped_get

    entry = scoped_get(db, Entry, entry_id, auth.family_id)
    entry.deleted_at = None
    entry.deleted_by = None
    entry.deleted_by_id = None
    _notify_event(db, auth, entry, action="restore")
    _bump_family_version(db, auth.family_id)
    db.commit()
    db.refresh(entry)
    return entry_row(entry)


def purge_entry(db: Session, entry: Entry) -> None:
    """彻底删除：连同 measurement/growth_point/media 与挂载的非结构化文件。"""
    from ..media.store import get_store

    from . import file_service

    m_ids = [m.id for m in db.query(Measurement).filter(Measurement.entry_id == entry.id)]
    if m_ids:
        db.query(GrowthPoint).filter(GrowthPoint.measurement_id.in_(m_ids)).delete(synchronize_session=False)
        db.query(Measurement).filter(Measurement.id.in_(m_ids)).delete(synchronize_session=False)

    # 挂在记录上的非结构化文件：台账行删除后，无其他引用才释放对象存储字节
    for fo in db.query(FileObject).filter(FileObject.family_id == entry.family_id,
                                           FileObject.business_type == "entry",
                                           FileObject.business_id == entry.id):
        if fo.storage_key and not file_service.object_in_use(
                db, entry.family_id, fo.storage_key, exclude_file_id=fo.id):
            get_store().delete(fo.storage_key)
        db.delete(fo)

    for md in db.query(EntryMedia).filter(EntryMedia.entry_id == entry.id):
        # 同家庭去重复用的 storage_key：仅当无其他行（媒体或文件台账）引用时才删字节
        db.query(FileObject).filter(FileObject.family_id == entry.family_id,
                                    FileObject.business_type == "entry_media",
                                    FileObject.business_id == md.id).delete(synchronize_session=False)
        db.flush()
        if md.storage_key and not file_service.object_in_use(
                db, entry.family_id, md.storage_key, exclude_media_id=md.id):
            get_store().delete(md.storage_key)
        db.delete(md)
    db.delete(entry)


def encode_cursor(occurred_at: str, entry_id: str) -> str:
    raw = f"{occurred_at}|{entry_id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> tuple[str, str] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        occ, _, eid = raw.partition("|")
        return (occ, eid)
    except Exception:
        return None


def list_entries(db: Session, auth: AuthContext, baby: str = "", etype: str = "",
                 cursor: str = "", limit: int = 20) -> dict:
    q = db.query(Entry).filter(Entry.family_id == auth.family_id, Entry.deleted_at.is_(None))
    if baby:
        q = q.filter(Entry.baby_id == baby)
    if etype and etype != "all":
        q = q.filter(Entry.type == etype)
    if cursor:
        pos = decode_cursor(cursor)
        if pos:
            occ, eid = pos
            q = q.filter(or_(Entry.occurred_at < occ, and_(Entry.occurred_at == occ, Entry.id < eid)))
    rows = q.order_by(Entry.occurred_at.desc(), Entry.id.desc()).limit(limit + 1).all()
    items = [entry_row(r) for r in rows[:limit]]
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(last.occurred_at, last.id)
    return {"items": items, "next_cursor": next_cursor}


def timeline_page(db: Session, auth: AuthContext, baby: str = "",
                  cursor: str = "", limit: int = 10) -> dict:
    """主页时光轴专用分页（GET /entries/timeline）。

    数据量增长后主页不再读 bootstrap 全量缓存，改走本端点按游标逐页拉取：
    - baby 缺省取当前活跃宝宝；同时包含历史无 baby_id 的记录（与客户端旧口径一致）；
    - 排序 occurred_at desc, id desc，游标编码与 list_entries 相同；
    - day_totals=本页涉及日期的全天真实条数（跨页的天不受分页影响），
      供日期分隔行显示准确条数；返回 {items, next_cursor, has_more, day_totals}。
    """
    baby_id = baby or _active_baby_id(db, auth.family_id)

    def _scoped(base):
        q = base.filter(Entry.family_id == auth.family_id, Entry.deleted_at.is_(None))
        if baby_id:
            q = q.filter(or_(Entry.baby_id == baby_id, Entry.baby_id.is_(None), Entry.baby_id == ""))
        return q

    q = _scoped(db.query(Entry))
    if cursor:
        pos = decode_cursor(cursor)
        if pos:
            occ, eid = pos
            q = q.filter(or_(Entry.occurred_at < occ, and_(Entry.occurred_at == occ, Entry.id < eid)))
    rows = q.order_by(Entry.occurred_at.desc(), Entry.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    items = [entry_row(r) for r in rows[:limit]]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(last["occurred_at"], last["id"])
    # 本页涉及日期的全天条数（不带游标条件，跨页的天也计全量）
    days = sorted({(it["occurred_at"] or "")[:10] for it in items if it["occurred_at"]})
    day_totals: dict = {}
    if days:
        # SELECT / WHERE / GROUP BY 必须复用同一个 day 表达式对象：每次重新构造
        # func.substr(...) 会各自生成绑定参数（substr_2 与 substr_4），PostgreSQL
        # 按表达式文本比对 GROUP BY，判定两处不是同一列 → GroupingError 500
        # （SQLite 不校验，测试库里看不出来）。
        day = func.substr(Entry.occurred_at, 1, 10)
        counts = (
            _scoped(db.query(day, func.count(Entry.id)))
            .filter(day.in_(days))
            .group_by(day)
            .all()
        )
        day_totals = {d: int(n) for d, n in counts}
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more, "day_totals": day_totals}


def search_page(db: Session, auth: AuthContext, baby: str = "", kw: str = "", etype: str = "",
                cursor: str = "", limit: int = 10) -> dict:
    """搜索专用分页（GET /entries/search）。

    关键词对 title/note/meta/creator/occurred_at 做大小写不敏感的子串匹配
    （occurred_at 为 ISO 字符串，客户端把「10月19」归一化成「10-19」后可命中日期）；
    type 支持 all；分页/排序/游标与 timeline_page 完全一致，返回 {items, next_cursor, has_more}。
    q 为空时退化为最近记录分页（与时光轴同序）。
    """
    baby_id = baby or _active_baby_id(db, auth.family_id)
    q = db.query(Entry).filter(Entry.family_id == auth.family_id, Entry.deleted_at.is_(None))
    if baby_id:
        q = q.filter(or_(Entry.baby_id == baby_id, Entry.baby_id.is_(None), Entry.baby_id == ""))
    if etype and etype != "all":
        q = q.filter(Entry.type == etype)
    word = (kw or "").strip()
    if word:
        # LIKE 通配符转义，避免用户输入 %/_ 影响匹配
        esc = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pat = f"%{esc}%"
        q = q.filter(or_(
            Entry.title.ilike(pat, escape="\\"), Entry.note.ilike(pat, escape="\\"),
            Entry.meta.ilike(pat, escape="\\"), Entry.creator.ilike(pat, escape="\\"),
            Entry.occurred_at.ilike(pat, escape="\\")))
    if cursor:
        pos = decode_cursor(cursor)
        if pos:
            occ, eid = pos
            q = q.filter(or_(Entry.occurred_at < occ, and_(Entry.occurred_at == occ, Entry.id < eid)))
    rows = q.order_by(Entry.occurred_at.desc(), Entry.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    items = [entry_row(r) for r in rows[:limit]]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(last["occurred_at"], last["id"])
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}
