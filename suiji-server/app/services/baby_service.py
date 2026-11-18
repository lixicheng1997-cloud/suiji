"""建档排期：里程碑清单 + 国家免疫规划（按出生日期 plan_date）。"""
import json
from functools import lru_cache

from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.deps import AuthContext
from ..domain.dates import add_months_str, utc_now_iso
from ..models import AiJournal, Baby, Entry, EntryMedia, FileObject, MilestoneRecord, Vaccine
from . import entry_service, file_service
from .ids import gen_id
from .rows import baby_row


@lru_cache(maxsize=2)
def _load_config(name: str) -> list[dict]:
    path = settings.static_config_dir / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def milestone_defs() -> list[dict]:
    return _load_config("milestones.json")


def vaccine_schedule() -> list[dict]:
    return _load_config("vaccine_schedule.json")


def ensure_schedule(db: Session, baby: Baby) -> None:
    """为该宝宝补齐里程碑与疫苗排期（幂等：已存在的按 name/code 跳过）。"""
    now = utc_now_iso()
    existing_ms = {m.name for m in db.query(MilestoneRecord).filter(MilestoneRecord.baby_id == baby.id)}
    for i, d in enumerate(milestone_defs()):
        if d["name"] in existing_ms:
            continue
        db.add(MilestoneRecord(
            id=gen_id("msr"), family_id=baby.family_id, baby_id=baby.id,
            name=d["name"], domain=d["domain"], month=d["month"], ref=d["ref"],
            done=False, achieved_at="", source_entry_id="", creator="",
            sort=int(d.get("sort", i)),
        ))
    existing_vc = {v.code for v in db.query(Vaccine).filter(Vaccine.baby_id == baby.id)}
    for i, s in enumerate(vaccine_schedule()):
        if s["code"] in existing_vc:
            continue
        db.add(Vaccine(
            id=gen_id("v"), family_id=baby.family_id, baby_id=baby.id,
            code=s["code"], n=s["n"], dose=s["dose"], age=s["age"],
            months=int(s["months"]), cls=s["cls"], sort=i,
            plan_date=add_months_str(baby.birth_date, int(s["months"])),
            done=False, done_date="", org="", lot="", remind=True, remind_lead=7,
            created_at=now, updated_at=now,
        ))


def replan_vaccines(db: Session, baby: Baby, old_birth_date: str = "") -> None:
    """出生日期变化：重排 plan_date 并刷新派生字段，保留接种状态与提醒设置。

    old_birth_date 给定时，可识别「用户手改过的预期接种日期」——该剂次的 plan_date
    与旧出生日期算出的排期不一致即视为自定义，重排时保持不变（否则会被覆盖）。
    """
    by_code = {s["code"]: s for s in vaccine_schedule()}
    rows = db.query(Vaccine).filter(Vaccine.baby_id == baby.id).all()
    have = set()
    for v in rows:
        s = by_code.get(v.code)
        if not s:
            continue  # 不在规划内的历史 code 保持原样
        have.add(v.code)
        v.n, v.dose, v.age = s["n"], s["dose"], s["age"]
        v.months, v.cls = int(s["months"]), s["cls"]
        custom = bool(old_birth_date) and v.plan_date and v.plan_date != add_months_str(old_birth_date, v.months)
        if not custom:
            v.plan_date = add_months_str(baby.birth_date, v.months)
        v.updated_at = utc_now_iso()
    # 配置新增的剂次补插
    now = utc_now_iso()
    for i, s in enumerate(vaccine_schedule()):
        if s["code"] in have:
            continue
        db.add(Vaccine(
            id=gen_id("v"), family_id=baby.family_id, baby_id=baby.id,
            code=s["code"], n=s["n"], dose=s["dose"], age=s["age"],
            months=int(s["months"]), cls=s["cls"], sort=i,
            plan_date=add_months_str(baby.birth_date, int(s["months"])),
            done=False, done_date="", org="", lot="", remind=True, remind_lead=7,
            created_at=now, updated_at=now,
        ))


# ---------- 软删 / 恢复 / 彻底删除（与 entry 同口径，回收站保留 30 天） ----------

def soft_delete(db: Session, auth: AuthContext, baby: Baby) -> dict:
    """软删档案：deleted_at 写当前时刻；若为 active，切到同家庭另一未删档案。

    删除档案不级联删记录（记录仍在 entry 表，只是 baby_id 指向已软删档案），
    恢复档案后记录自动重新可见。彻底删除时才级联物理清除。
    """
    baby.deleted_at = utc_now_iso()
    baby.updated_at = baby.deleted_at
    if baby.is_active:
        baby.is_active = 0
        nxt = (db.query(Baby)
               .filter(Baby.family_id == auth.family_id, Baby.id != baby.id,
                       Baby.deleted_at.is_(None))
               .order_by(Baby.created_at)
               .first())
        if nxt:
            nxt.is_active = 1
    db.commit()
    db.refresh(baby)
    return baby_row(baby)


def restore(db: Session, baby: Baby) -> dict:
    """恢复档案：清 deleted_at；若当前家庭无 active 档案，本档案自动接管。"""
    baby.deleted_at = None
    baby.updated_at = utc_now_iso()
    if not baby.is_active:
        has_active = (db.query(Baby)
                      .filter(Baby.family_id == baby.family_id, Baby.deleted_at.is_(None),
                              Baby.is_active == 1, Baby.id != baby.id)
                      .first())
        if not has_active:
            baby.is_active = 1
    db.commit()
    db.refresh(baby)
    return baby_row(baby)


def purge_baby(db: Session, baby: Baby) -> None:
    """彻底删除：级联物理清除该档案下的记录/疫苗/里程碑/日记 + 媒体与文件字节。

    记录走 entry_service.purge_entry（含 measurement/growth_point/media/文件引用判定）；
    档案级文件（头像等）单独释放；其余 baby_id 行直接删除。
    """
    # 1. 记录（含其挂载的媒体/测量/生长点/文件字节）
    for e in db.query(Entry).filter(Entry.baby_id == baby.id).all():
        entry_service.purge_entry(db, e)
    # 2. 档案级文件（business_type='baby'，头像等）：先查引用再释放字节
    for fo in db.query(FileObject).filter(FileObject.family_id == baby.family_id,
                                          FileObject.business_type == "baby",
                                          FileObject.business_id == baby.id).all():
        key = fo.storage_key or ""
        db.delete(fo)
        db.commit()
        if key and not file_service.object_in_use(db, baby.family_id, key):
            try:
                from ..media.store import get_store
                get_store().delete(key)
            except Exception:
                pass
    # 3. 孤儿 EntryMedia（entry 已删但 baby_id 残留，理论上不应存在，做兜底）
    db.query(EntryMedia).filter(EntryMedia.baby_id == baby.id).delete(synchronize_session=False)
    # 4. 疫苗排期 / 里程碑 / AI 日记
    db.query(Vaccine).filter(Vaccine.baby_id == baby.id).delete(synchronize_session=False)
    db.query(MilestoneRecord).filter(MilestoneRecord.baby_id == baby.id).delete(synchronize_session=False)
    db.query(AiJournal).filter(AiJournal.baby_id == baby.id).delete(synchronize_session=False)
    # 5. 档案本身
    db.delete(baby)
    db.commit()
