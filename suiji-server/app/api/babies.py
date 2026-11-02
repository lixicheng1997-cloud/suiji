"""宝宝 /babies（契约 §5）：创建时服务端初始化里程碑与疫苗排期。"""
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import get_auth, require_write
from ..domain.dates import today_utc, utc_now_iso
from ..models import Baby
from ..repositories import scoped_get
from ..schemas import BabyIn
from ..services.baby_service import ensure_schedule, replan_vaccines
from ..services.ids import gen_id
from ..services.rows import baby_row

router = APIRouter(prefix="/babies", tags=["babies"])

_UPDATABLE = ("name", "birth_date", "gestational_weeks", "gender",
              "birth_length", "birth_weight", "avatar", "allergy")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_baby(body: dict) -> None:
    """建档/改档入参校验：客户端已限幅，这里挡住旧版本与直连接口。

    超长/畸形值落库是 Postgres 侧的 data_error（500），且 birth_date 一旦不是
    'YYYY-MM-DD'，疫苗排期与矫正月龄的日期运算会整体算错——比报错更难发现。
    """
    name = body.get("name")
    if isinstance(name, str) and len(name) > 20:
        raise HTTPException(status_code=422, detail="宝宝昵称过长（上限 20 字）")
    bd = body.get("birth_date")
    if bd and not _DATE_RE.match(str(bd)):
        raise HTTPException(status_code=422, detail="出生日期格式应为 YYYY-MM-DD")
    if bd and str(bd) > today_utc():
        # 未来的出生日期会让月龄/矫正月龄/疫苗排期整体算成负数
        raise HTTPException(status_code=422, detail="出生日期不能晚于今天")
    gw = body.get("gestational_weeks")
    if gw not in (None, "") and not (20 <= int(gw) <= 42):
        raise HTTPException(status_code=422, detail="出生胎周应在 20–42 周之间")
    bl = body.get("birth_length")
    if bl not in (None, "") and not (0 <= float(bl) <= 80):
        raise HTTPException(status_code=422, detail="出生身长应在 0–80 cm 之间")
    bw = body.get("birth_weight")
    if bw not in (None, "") and not (0 <= float(bw) <= 10):
        raise HTTPException(status_code=422, detail="出生体重应在 0–10 kg 之间")
    av = body.get("avatar")
    if isinstance(av, str) and len(av) > 64:
        # 列宽 String(64)；服务端自拼的 /api/v1/files/{id}/download 最长 56 字符，留足余量
        raise HTTPException(status_code=422, detail="头像地址过长，请重新上传")
    al = body.get("allergy")
    if isinstance(al, str) and len(al) > 700:
        raise HTTPException(status_code=422, detail="过敏史过长（上限 700 字）")


@router.get("")
def list_babies(db: Session = Depends(get_db), auth=Depends(get_auth)):
    rows = db.query(Baby).filter(Baby.family_id == auth.family_id).order_by(Baby.created_at).all()
    return [baby_row(b) for b in rows]


@router.post("")
def create_baby(body: BabyIn, db: Session = Depends(get_db), auth=Depends(require_write)):
    now = utc_now_iso()
    _check_baby(body.model_dump())
    count = db.query(Baby).filter(Baby.family_id == auth.family_id).count()
    # 指定 id 冲突时统一返回同一条文案，不区分「是本家庭的还是别人的」——
    # 区分了就等于提供一个跨家庭 ID 存在性 oracle（可枚举他人宝宝 ID）
    if (body.id or "") and db.get(Baby, body.id) is not None:
        raise HTTPException(status_code=422, detail="宝宝档案已存在")
    baby = Baby(
        id=body.id or gen_id("baby"),
        family_id=auth.family_id,
        name=body.name or "宝宝",
        birth_date=body.birth_date or today_utc(),
        gestational_weeks=int(body.gestational_weeks or 40),
        gender=body.gender if body.gender in ("boy", "girl") else "boy",
        birth_length=float(body.birth_length or 0),
        birth_weight=float(body.birth_weight or 0),
        avatar=body.avatar or "",
        allergy=body.allergy or "",
        is_active=1 if count == 0 else 0,  # 首个宝宝自动 active
        created_at=body.created_at or now,
        updated_at=body.updated_at or now,
    )
    db.add(baby)
    db.flush()
    ensure_schedule(db, baby)
    db.commit()
    db.refresh(baby)
    return baby_row(baby)


@router.put("/{baby_id}")
def update_baby(baby_id: str, body: BabyIn, db: Session = Depends(get_db), auth=Depends(require_write)):
    baby = scoped_get(db, Baby, baby_id, auth.family_id)
    old_birth = baby.birth_date
    data = body.model_dump(exclude_unset=True)  # 仅更新请求中出现的字段
    _check_baby(data)
    for field in _UPDATABLE:
        # avatar/allergy 允许显式清空（客户端每次 PUT 传整行，""就是「用户删掉了」）；
        # 其余字段仍按「空串=没传」处理，避免半截 patch 把必填资料抹掉
        if field in data and data[field] is not None and (data[field] != "" or field in ("avatar", "allergy")):
            setattr(baby, field, data[field])
    if data.get("is_active") == 1 and not baby.is_active:
        db.query(Baby).filter(Baby.family_id == auth.family_id, Baby.id != baby.id).update({"is_active": 0})
        baby.is_active = 1
    baby.updated_at = data.get("updated_at") or utc_now_iso()
    if baby.birth_date != old_birth:
        replan_vaccines(db, baby, old_birth)
    db.commit()
    db.refresh(baby)
    return baby_row(baby)


@router.post("/{baby_id}/activate")
def activate(baby_id: str, db: Session = Depends(get_db), auth=Depends(require_write)):
    baby = scoped_get(db, Baby, baby_id, auth.family_id)
    db.query(Baby).filter(Baby.family_id == auth.family_id, Baby.id != baby.id).update({"is_active": 0})
    baby.is_active = 1
    db.commit()
    db.refresh(baby)
    return baby_row(baby)
