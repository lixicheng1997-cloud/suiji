"""建档排期：里程碑清单 + 国家免疫规划（按出生日期 plan_date）。"""
import json
from functools import lru_cache

from sqlalchemy.orm import Session

from ..core.config import settings
from ..domain.dates import add_months_str, utc_now_iso
from ..models import Baby, MilestoneRecord, Vaccine
from .ids import gen_id


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
