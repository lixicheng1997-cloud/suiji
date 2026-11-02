"""疫苗 /vaccines（契约 §8）：剂次状态与提醒为原始字段，派生状态归客户端。"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import get_auth, require_write
from ..domain.dates import utc_now_iso
from ..models import Vaccine
from ..repositories import scoped_get
from ..schemas import SyncRowsIn, VaccinePatch
from ..services import notify_service
from ..services.rows import vaccine_row

router = APIRouter(prefix="/vaccines", tags=["vaccines"])
logger = logging.getLogger(__name__)

_PATCH_FIELDS = ("plan_date", "done", "done_date", "org", "lot", "remind", "remind_lead")

# 列宽上限：客户端已按同口径拦截，这里兜住旧版本客户端与直连接口，
# 超长写 varchar(64)/varchar(10) 在 Postgres 上是 data_error，整笔请求 500
_TEXT_LIMITS = {"org": 20, "lot": 20, "plan_date": 10, "done_date": 10}


def _fit(field: str, value):
    if isinstance(value, str):
        lim = _TEXT_LIMITS.get(field)
        if lim and len(value) > lim:
            logger.warning("疫苗字段 %s 超长（%d 字），已截到 %d 字", field, len(value), lim)
            return value[:lim]
    return value


def _dose_label(v: Vaccine) -> str:
    return (v.n or "疫苗") + ((" " + v.dose) if v.dose else "")


@router.get("")
def list_vaccines(baby_id: str = Query(""), db: Session = Depends(get_db), auth=Depends(get_auth)):
    q = db.query(Vaccine).filter(Vaccine.family_id == auth.family_id)
    if baby_id:
        q = q.filter(Vaccine.baby_id == baby_id)
    return [vaccine_row(v) for v in q.order_by(Vaccine.sort, Vaccine.months).all()]


@router.post("/sync")
def sync(body: SyncRowsIn, db: Session = Depends(get_db), auth=Depends(require_write)):
    """批量更新（ensureVaccineSchedule / 一键开关用）：按 code(+baby_id) 定位。"""
    count = 0
    now = utc_now_iso()
    newly_done: list[str] = []
    for item in body.rows:
        code = item.get("code")
        if not code:
            continue
        baby_id = item.get("baby_id") or ""
        q = db.query(Vaccine).filter(Vaccine.family_id == auth.family_id, Vaccine.code == code)
        if baby_id:
            q = q.filter(Vaccine.baby_id == baby_id)
        for v in q.all():
            changed = False
            was_done = bool(v.done)
            for f in _PATCH_FIELDS:
                if f in item and getattr(v, f) != item[f]:
                    setattr(v, f, _fit(f, item[f]))
                    changed = True
            if changed:
                v.updated_at = now
                count += 1
            if (not was_done) and bool(v.done):
                newly_done.append(_dose_label(v))
    db.commit()
    # 批量打卡合并成一条：一次勾完五剂不该弹五条
    if newly_done:
        names = "、".join(newly_done[:2]) + (" 等 %d 剂" % len(newly_done) if len(newly_done) > 2 else "")
        notify_service.notify_family(
            db, auth, ntype="vaccine",
            content=f"{notify_service.actor_name(db, auth)} 完成了疫苗接种：{names}")
        db.commit()
    return {"count": count}


@router.put("/{vaccine_id}")
def update(vaccine_id: str, body: VaccinePatch, db: Session = Depends(get_db), auth=Depends(require_write)):
    v = scoped_get(db, Vaccine, vaccine_id, auth.family_id)
    data = body.model_dump(exclude_unset=True)
    was_done = bool(v.done)
    for f in _PATCH_FIELDS:
        if f in data and data[f] is not None:
            setattr(v, f, _fit(f, data[f]))
    v.updated_at = utc_now_iso()
    # 仅「未接种 → 已接种」通知；取消完成、改日期/机构/批号都不打扰家人
    just_done = (not was_done) and bool(v.done)
    label = _dose_label(v)
    db.commit()
    db.refresh(v)
    if just_done:
        notify_service.notify_family(
            db, auth, ntype="vaccine",
            content=f"{notify_service.actor_name(db, auth)} 完成了疫苗接种「{label}」")
        db.commit()
    return vaccine_row(v)
