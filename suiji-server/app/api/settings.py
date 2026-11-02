"""设置 /settings（契约 §10）：每用户一个 JSON 对象，单键写入。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import get_auth, require_write
from ..models import Setting
from ..schemas import SettingsIn

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(db: Session = Depends(get_db), auth=Depends(get_auth)):
    row = db.get(Setting, auth.user_id)
    return (row.data or {}) if row else {}


@router.put("")
def put_setting(body: SettingsIn, db: Session = Depends(get_db), auth=Depends(require_write)):
    row = db.get(Setting, auth.user_id)
    if row is None:
        row = Setting(user_id=auth.user_id, data={body.key: body.value})
        db.add(row)
    else:
        data = dict(row.data or {})
        data[body.key] = body.value
        row.data = data  # JSON 列需整体重新赋值以触发变更检测
    db.commit()
    db.refresh(row)
    return row.data or {}
