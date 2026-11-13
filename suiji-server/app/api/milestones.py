"""里程碑 /milestones（契约 §9）。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import AuthContext, get_auth, require_write
from ..models import MilestoneRecord
from ..repositories import scoped_get
from ..schemas import MilestonePatch
from ..services import notify_service
from ..services.rows import milestone_row

router = APIRouter(prefix="/milestones", tags=["milestones"])

# creator 是历史名字串，归属以 creator_id 为准，不接受客户端改写
_PATCH_FIELDS = ("done", "achieved_at", "source_entry_id", "month")


def _assert_writable(auth: AuthContext, m: MilestoneRecord) -> None:
    """创建者任意；成员可勾选系统预置清单（creator_id 为空的共享行）或本人达成的里程碑。"""
    if auth.role == "creator":
        return
    if not m.creator_id or m.creator_id == auth.user_id:
        return
    raise HTTPException(status_code=403, detail="只能修改自己达成的里程碑")


@router.get("")
def list_milestones(baby_id: str = Query(""), db: Session = Depends(get_db), auth=Depends(get_auth)):
    q = db.query(MilestoneRecord).filter(MilestoneRecord.family_id == auth.family_id)
    if baby_id:
        q = q.filter(MilestoneRecord.baby_id == baby_id)
    return [milestone_row(m) for m in q.order_by(MilestoneRecord.sort).all()]


@router.put("/{milestone_id}")
def update(milestone_id: str, body: MilestonePatch, db: Session = Depends(get_db), auth=Depends(require_write)):
    m = scoped_get(db, MilestoneRecord, milestone_id, auth.family_id)
    _assert_writable(auth, m)
    data = body.model_dump(exclude_unset=True)
    was_done = bool(m.done)
    for f in _PATCH_FIELDS:
        if f in data and data[f] is not None:
            setattr(m, f, data[f])
    # 仅在「未达成 → 达成」时通知家人：反复改日期/取消达成不该刷屏
    just_achieved = (not was_done) and bool(m.done)
    db.commit()
    db.refresh(m)
    if just_achieved:
        notify_service.notify_family(
            db, auth, ntype="milestone",
            content=f"{notify_service.actor_name(db, auth)} 达成了里程碑「{m.name}」",
            entry_id=m.source_entry_id or "")
        db.commit()
    return milestone_row(m)
