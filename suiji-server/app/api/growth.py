"""生长曲线 /growth/curve（契约 §13）：供导出与校验，客户端图表仍用本地参考带。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import get_auth
from ..domain import growth_lms
from ..domain.dates import age_months
from ..models import Baby, GrowthPoint, Measurement
from ..repositories import scoped_get

router = APIRouter(prefix="/growth", tags=["growth"])


@router.get("/curve")
def curve(metric: str = Query("weight"), baby_id: str = Query(""),
          db: Session = Depends(get_db), auth=Depends(get_auth)):
    if metric not in ("weight", "height", "head"):
        raise HTTPException(status_code=422, detail="未知指标")
    baby = None
    if baby_id:
        baby = scoped_get(db, Baby, baby_id, auth.family_id)
    else:
        baby = db.query(Baby).filter(Baby.family_id == auth.family_id, Baby.is_active == 1).first()
        if baby is None:
            baby = db.query(Baby).filter(Baby.family_id == auth.family_id).order_by(Baby.created_at).first()
    if baby is None:
        return {"points": [], "standard_version": growth_lms.standard_version()}

    points = []
    for m in db.query(Measurement).filter(Measurement.family_id == auth.family_id,
                                          Measurement.metric == metric).all():
        if m.baby_id and m.baby_id != baby.id:
            continue
        age_m = age_months(baby.birth_date, m.occurred_at, baby.gestational_weeks)
        if age_m < 0:
            continue
        gp = db.get(GrowthPoint, m.id)
        p = gp.percentile_p if gp is not None else growth_lms.percentile_of(
            metric, baby.gender, age_m, m.value)
        points.append({"ageM": round(age_m, 2), "value": m.value, "percentile": round(p, 1)})
    points.sort(key=lambda x: x["ageM"])
    return {"points": points, "standard_version": growth_lms.standard_version()}
