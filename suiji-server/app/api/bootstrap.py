"""引导 /bootstrap（契约 §3）：全量快照填充客户端缓存。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import get_auth
from ..services.bootstrap_service import snapshot

router = APIRouter(tags=["bootstrap"])


@router.get("/bootstrap")
def bootstrap(db: Session = Depends(get_db), auth=Depends(get_auth)):
    return snapshot(db, auth)
