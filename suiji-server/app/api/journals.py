"""AI 日记 /journals（契约 §11）：生成管线在服务端，Key 绝不下发。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import get_auth, require_write
from ..domain.dates import utc_now_iso
from ..models import AiJournal
from ..repositories import scoped_get
from ..schemas import JournalGenerateIn, JournalUpdateIn
from ..services import journal_service
from ..services.rows import journal_row

router = APIRouter(prefix="/journals", tags=["journals"])


@router.post("/generate")
def generate(body: JournalGenerateIn, db: Session = Depends(get_db), auth=Depends(require_write)):
    return journal_service.generate(db, auth, body.model_dump())


@router.get("")
def list_journals(db: Session = Depends(get_db), auth=Depends(get_auth)):
    rows = db.query(AiJournal).filter(AiJournal.family_id == auth.family_id).order_by(AiJournal.created_at.desc()).all()
    return [journal_row(j) for j in rows]


@router.put("/{journal_id}")
def update(journal_id: str, body: JournalUpdateIn, db: Session = Depends(get_db), auth=Depends(require_write)):
    j = scoped_get(db, AiJournal, journal_id, auth.family_id)
    if body.paras is not None:
        j.paras = body.paras
    if body.status is not None:
        if body.status not in ("draft", "archived"):
            from fastapi import HTTPException

            raise HTTPException(status_code=422, detail="状态不合法")
        j.status = body.status
    j.updated_at = utc_now_iso()
    db.commit()
    db.refresh(j)
    return journal_row(j)
