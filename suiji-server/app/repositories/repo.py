"""仓储层：跨家庭隔离的唯一入口（不存在 404 / 异家庭 403 并留日志）。"""
import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger("suiji.repo")


def scoped_get(db: Session, model, obj_id: str, family_id: str):
    row = db.get(model, obj_id)
    if row is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    owner = getattr(row, "family_id", "")
    if owner != family_id:
        # 日志只记类型与 id，不落敏感内容
        logger.warning("越权访问拦截：model=%s id=%s 请求家庭=%s", model.__name__, obj_id, family_id)
        raise HTTPException(status_code=403, detail="无权访问该记录")
    return row
