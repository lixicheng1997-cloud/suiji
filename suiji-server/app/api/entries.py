"""记录 /entries（契约 §6）：幂等创建、软删回收站、游标分页。

注意路由注册顺序：/entries/trash 必须先于 /entries/{id}，避免 trash 被路径参数吞掉。
"""
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import get_auth, require_write
from ..models import Entry
from ..repositories import scoped_get
from ..schemas import EntryIn
from ..services import audit_service, cleanup_service, entry_service
from ..services.rows import entry_row

router = APIRouter(prefix="/entries", tags=["entries"])


def _entry_label(row: dict) -> str:
    """留痕里的记录指代：优先用摘要标题，缺省退回记录 id 短尾。"""
    title = (row or {}).get("title") or ""
    return f"「{title}」" if title else f"记录 {str((row or {}).get('id') or '')[-6:]}"


@router.post("")
def create(body: EntryIn, db: Session = Depends(get_db), auth=Depends(require_write),
           idempotency_key: str = Header(default="", alias="Idempotency-Key")):
    """POST /entries：body 为 entry 行；Idempotency-Key 命中直接返回已存响应。"""
    return entry_service.create_entry(db, auth, body.model_dump(), idempotency_key)


@router.get("")
def list_entries(baby: str = Query(""), type: str = Query(""), cursor: str = Query(""),
                 limit: int = Query(20, ge=1, le=200),
                 db: Session = Depends(get_db), auth=Depends(get_auth)):
    return entry_service.list_entries(db, auth, baby, type, cursor, limit)


@router.get("/timeline")
def timeline(cursor: str = Query(""), limit: int = Query(10, ge=1, le=50), baby: str = Query(""),
             db: Session = Depends(get_db), auth=Depends(get_auth)):
    """主页时光轴专用分页端点：游标分页、每页 10 条（数据量大，主页不再读 bootstrap 全量缓存）。

    字面量路由必须先于 /entries/{id} 注册，避免 timeline 被路径参数吞掉。
    """
    return entry_service.timeline_page(db, auth, baby, cursor, limit)


@router.get("/search")
def search(q: str = Query(""), type: str = Query(""), baby: str = Query(""),
           cursor: str = Query(""), limit: int = Query(10, ge=1, le=50),
           db: Session = Depends(get_db), auth=Depends(get_auth)):
    """关键词搜索专用分页端点：title/note/meta/creator/occurred_at 子串匹配 + type 过滤，
    游标分页同 /timeline（数据量大，搜索页不再读 bootstrap 全量缓存）。

    字面量路由必须先于 /entries/{id} 注册，避免 search 被路径参数吞掉。
    """
    return entry_service.search_page(db, auth, baby, q, type, cursor, limit)


# ---- 回收站：字面量路由必须先于 /entries/{id} 注册 ----

@router.delete("/trash")
def clear_trash(db: Session = Depends(get_db), auth=Depends(require_write)):
    rows = db.query(Entry).filter(Entry.family_id == auth.family_id, Entry.deleted_at.isnot(None)).all()
    for e in rows:
        entry_service.purge_entry(db, e)
    if rows:
        audit_service.record(db, auth.family_id, auth, action="purge", target_type="trash",
                             text=f"彻底删除回收站中的 {len(rows)} 条记录")
    db.commit()
    return {"count": len(rows)}


@router.delete("/trash/{entry_id}")
def purge(entry_id: str, db: Session = Depends(get_db), auth=Depends(require_write)):
    entry = scoped_get(db, Entry, entry_id, auth.family_id)
    label = _entry_label(entry_row(entry))
    entry_service.purge_entry(db, entry)
    audit_service.record(db, auth.family_id, auth, action="purge", target_type="entry", target_id=entry_id,
                         text=f"彻底删除记录{label}")
    db.commit()
    return {"id": entry_id}


@router.get("/trash")
def list_trash(db: Session = Depends(get_db), auth=Depends(get_auth)):
    # 惰性清理：过期项（软删超 30 天等）在展示前物理清除，失败不影响列表
    try:
        cleanup_service.purge_expired(db)
    except Exception:
        pass
    rows = db.query(Entry).filter(Entry.family_id == auth.family_id,
                                  Entry.deleted_at.isnot(None)).order_by(Entry.deleted_at.desc()).all()
    return {"items": [entry_row(r) for r in rows]}


# ---- 单条操作 ----

@router.get("/{entry_id}")
def get_one(entry_id: str, db: Session = Depends(get_db), auth=Depends(get_auth)):
    """单条查看（含跨家庭 403/404 防护）。"""
    return entry_row(scoped_get(db, Entry, entry_id, auth.family_id))


@router.put("/{entry_id}")
def update(entry_id: str, body: EntryIn, db: Session = Depends(get_db), auth=Depends(require_write)):
    return entry_service.update_entry(db, auth, entry_id, body.model_dump(exclude_unset=True))


@router.delete("/{entry_id}")
def soft_delete(entry_id: str, db: Session = Depends(get_db), auth=Depends(require_write)):
    row = entry_service.soft_delete(db, auth, entry_id)
    audit_service.record(db, auth.family_id, auth, action="delete", target_type="entry", target_id=entry_id,
                         text=f"删除记录{_entry_label(row)} · 已移入回收站")
    db.commit()
    return row


@router.post("/{entry_id}/restore")
def restore(entry_id: str, db: Session = Depends(get_db), auth=Depends(require_write)):
    return entry_service.restore(db, auth, entry_id)
