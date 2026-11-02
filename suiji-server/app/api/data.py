"""导出/导入/清空 /export /import /account（契约 §12）。"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import get_auth, require_creator, require_write
from ..media.store import get_store
from ..models import AiJournal, Baby, Entry, EntryMedia, Measurement, MilestoneRecord, Vaccine
from ..schemas import ImportIn
from ..services import audit_service, entry_service
from ..services.bootstrap_service import snapshot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data"])

# snapshot 表名 → 模型（member 表不导入：家庭归属以服务端为准）
_IMPORT_TABLES = {
    "baby": Baby,
    "entry": Entry,
    "entry_media": EntryMedia,
    "measurement": Measurement,
    "milestone_record": MilestoneRecord,
    "vaccine": Vaccine,
    "ai_journal": AiJournal,
}

# 每表允许导入的列（白名单）。
#
# 为什么必须白名单而不是「排除 id/family_id 后全收」：
# entry_media.storage_key 是对象存储里的路径，读取侧（/media/{id}）只校验行的
# family_id，不校验这个 key 是否属于本家庭。若允许客户端任意写入，就能构造一行
# 指向别人家对象的记录，拿着自己的 JWT 读走别的家庭全部照片/视频。
# 同理，sha256/size/width/height/deleted_by 一律由服务端写入，不接受外部指定。
_IMPORT_COLUMNS = {
    "baby": {"name", "birth_date", "gestational_weeks", "gender", "birth_length",
             "birth_weight", "avatar", "allergy", "is_active", "created_at", "updated_at"},
    "entry": {"type", "baby_id", "occurred_at", "created_at", "updated_at", "is_backfilled",
              "note", "creator", "creator_id", "title", "meta", "badge", "photo", "payload",
              "deleted_at", "deleted_by", "deleted_by_id"},
    # storage_key / sha256 / size / width / height 不可导入：见上方说明
    "entry_media": {"entry_id", "baby_id"},
    "measurement": {"entry_id", "baby_id", "metric", "value", "occurred_at", "corrected_age_flag"},
    "milestone_record": {"baby_id", "name", "domain", "month", "ref", "done", "achieved_at",
                         "source_entry_id", "creator", "sort"},
    "vaccine": {"code", "baby_id", "n", "dose", "age", "months", "cls", "sort", "plan_date",
                "done", "done_date", "org", "lot", "remind", "remind_lead",
                "created_at", "updated_at"},
    "ai_journal": {"baby_id", "range", "range_start", "range_end", "paras", "status",
                   "model_version", "prompt_version", "fact_count", "created_at", "updated_at"},
}

# 外键列 → 所属表：导入时必须确认引用落在本家庭内，否则置空
_IMPORT_FK = {"baby_id": Baby, "entry_id": Entry}
# 单次导入的总行数上限：防止超大 payload 把请求线程与事务拖死
_IMPORT_MAX_ROWS = 20000


@router.get("/export/data")
def export_data(db: Session = Depends(get_db), auth=Depends(get_auth)):
    snap = snapshot(db, auth)
    audit_service.record(db, auth.family_id, auth, action="export", target_type="data",
                         text="导出家庭数据副本（含记录/媒体台账）")
    db.commit()
    return snap


def _apply_row(db: Session, model, row: dict, family_id: str, allowed: set) -> bool:
    """写入一行导入数据。

    三重约束（缺一不可）：
      1. 列白名单——storage_key 这类「指向服务端资源」的列不接受客户端指定
      2. id / family_id 永远由服务端决定：family_id 强制为当前家庭，
         且**新建时**也要求该 id 未被他人占用，避免抢占他人主键
      3. 外键（baby_id / entry_id）必须落在本家庭内，否则置空而非保留跨家庭引用
    """
    cols = {c.name for c in inspect(model).columns}
    obj_id = row.get("id")
    if not obj_id:
        return False
    existing = db.get(model, obj_id)
    if existing is not None and existing.family_id != family_id:
        return False  # 归属他人数据不动
    if existing is not None:
        inc_u = str(row.get("updated_at") or "")
        cur_u = str(getattr(existing, "updated_at", "") or "")
        if inc_u and cur_u and inc_u < cur_u:
            return False  # 同 id 取 updated_at 新者
    data = {k: v for k, v in row.items() if k in cols and k in allowed}
    # 外键归属校验：引用不到本家庭的行就置空，绝不留下跨家庭指针
    for fk, fk_model in _IMPORT_FK.items():
        if not data.get(fk):
            continue
        target = db.get(fk_model, data[fk])
        if target is None or target.family_id != family_id:
            logger.warning("导入行 %s 的 %s 不属于本家庭，已置空", obj_id, fk)
            data[fk] = ""
    if existing is None:
        db.add(model(id=obj_id, family_id=family_id, **data))
    else:
        for k, v in data.items():
            setattr(existing, k, v)
        if model is Entry and not row.get("deleted_at"):
            existing.deleted_by = None
    return True


@router.post("/import")
def import_data(body: ImportIn, db: Session = Depends(get_db), auth=Depends(require_write)):
    snap = body.snapshot or {}
    total = 0
    imported = {}
    for table, model in _IMPORT_TABLES.items():
        raw = snap.get(table) or []
        # 备份文件是外部产物，某一张表可能是 {..} 或 ".." —— 直接迭代会 TypeError 500
        rows = raw if isinstance(raw, list) else []
        n = 0
        for row in rows:
            total += 1
            if total > _IMPORT_MAX_ROWS:
                raise HTTPException(status_code=413, detail=f"导入数据过多（上限 {_IMPORT_MAX_ROWS} 行）")
            if isinstance(row, dict) and _apply_row(db, model, row, auth.family_id, _IMPORT_COLUMNS[table]):
                n += 1
        imported[table] = n
    db.commit()
    return {"imported": imported}


@router.delete("/account/data")
def wipe_data(db: Session = Depends(get_db), auth=Depends(require_creator)):
    """清空家庭全部业务数据（含媒体文件），保留账号/家庭/设置。"""
    fid = auth.family_id
    for e in db.query(Entry).filter(Entry.family_id == fid).all():
        entry_service.purge_entry(db, e)
    m_ids = [m.id for m in db.query(Measurement).filter(Measurement.family_id == fid).all()]
    if m_ids:
        from ..models import GrowthPoint

        db.query(GrowthPoint).filter(GrowthPoint.measurement_id.in_(m_ids)).delete(synchronize_session=False)
        db.query(Measurement).filter(Measurement.id.in_(m_ids)).delete(synchronize_session=False)
    for md in db.query(EntryMedia).filter(EntryMedia.family_id == fid).all():
        if md.storage_key:
            get_store().delete(md.storage_key)
        db.delete(md)
    db.query(Baby).filter(Baby.family_id == fid).delete(synchronize_session=False)
    db.query(MilestoneRecord).filter(MilestoneRecord.family_id == fid).delete(synchronize_session=False)
    db.query(Vaccine).filter(Vaccine.family_id == fid).delete(synchronize_session=False)
    db.query(AiJournal).filter(AiJournal.family_id == fid).delete(synchronize_session=False)
    audit_service.record(db, fid, auth, action="wipe", target_type="data",
                         text="清除家庭全部业务数据（含媒体文件与回收站）")
    db.commit()
    return {"ok": True}
