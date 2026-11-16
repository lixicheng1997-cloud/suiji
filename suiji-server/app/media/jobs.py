"""缩略图变体的后台生成：把 LANCZOS 缩放从请求线程里搬出去。

实测一张 12MP 照片的 multipart 上传，请求线程 1217ms 里有 708ms 是两张缩略图。
这 708ms 客户端没有任何理由在等：原图此刻已经落进对象存储，下载端点在
`variant=thumb` 缺 key 时自动回落原图，列表页首屏不会因为晚一秒出缩略图而坏掉。

线程数刻意设上限：uvicorn 单 worker 的默认线程池要留给请求本身，
后台任务最多占这几个核。宁可排队，也不让正在上传的请求被 CPU 抢走。
进程重启会丢掉排队中的任务——后果只是这份文件没有缩略图（回落原图），
不影响可读性，因此不做持久化队列。
"""
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from threading import Lock

from ..core.config import settings
from ..core.db import SessionLocal
from ..media.thumbnails import generate_variants
from ..models import FileObject
from .store import get_store

logger = logging.getLogger(__name__)

_pool: ThreadPoolExecutor | None = None
_lock = Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _executor() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                _pool = ThreadPoolExecutor(max_workers=max(1, settings.media_workers),
                                           thread_name_prefix="suiji-media")
    return _pool


def submit(file_id: str, family_id: str) -> None:
    """排队生成该行的缩略图变体；队列满/进程异常只记日志，不影响已完成的上传。"""
    try:
        _executor().submit(_run, file_id, family_id)
    except Exception as exc:
        logger.warning("缩略图任务排队失败 file=%s：%s", file_id, exc)


def _sibling_keys(db, row: FileObject) -> dict:
    """同家庭同 storage_key 的其他行已生成过变体：直接复用 key，不再重算字节。

    同内容复用同一对象路径（existing_key）时走这条路，一份原图只有一套缩略图。
    """
    if not row.storage_key:
        return {}
    rows = (db.query(FileObject)
              .filter(FileObject.family_id == row.family_id,
                      FileObject.storage_key == row.storage_key,
                      FileObject.id != row.id,
                      FileObject.deleted_at.is_(None))
              .all())
    for other in rows:
        meta = other.meta if isinstance(other.meta, dict) else {}
        if meta.get("thumb_key") or meta.get("small_key"):
            return {k: meta[k] for k in ("thumb_key", "small_key") if meta.get(k)}
    return {}


def _read_object(key: str) -> bytes:
    stream = get_store().open_stream(key)
    if stream is None:
        return b""
    return b"".join(stream)


def _stem(row: FileObject) -> str:
    """变体对象的文件名主干：沿用原文件名（与请求内生成时的命名一致），缺失时退回对象名。"""
    for cand in (row.original_name or "", row.storage_key.rsplit("/", 1)[-1] if row.storage_key else ""):
        name = cand.rsplit("/", 1)[-1]
        stem = name.rsplit(".", 1)[0] if "." in name else name
        if stem.strip():
            return stem.strip()
    return "file"


def _run(file_id: str, family_id: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(FileObject, file_id)
        if row is None or row.family_id != family_id or row.deleted_at:
            return
        content_type = (row.content_type or "").lower()
        if not content_type.startswith("image/"):
            return
        meta = dict(row.meta or {})
        if meta.get("thumb_key") or meta.get("small_key"):
            return

        reuse = _sibling_keys(db, row)
        if reuse:
            meta.update(reuse)
        else:
            data = _read_object(row.storage_key)
            if not data:
                logger.warning("缩略图生成跳过 file=%s：对象不可读", file_id)
                return
            variants = generate_variants(data, content_type)
            if not variants:
                return
            # 直传登记的行没有 sha256，同名冲突消解需要它：按真实字节补算，
            # 只用于给变体 key 去重，不回写台账（回写会撞 uq_file_dedup）。
            sha = row.sha256 or hashlib.sha256(data).hexdigest()
            stem = _stem(row)
            store = get_store()
            for kind in ("thumb", "small"):
                blob = variants.get(kind)
                if not blob:
                    continue
                meta[kind + "_key"] = store.save_stream(
                    BytesIO(blob), len(blob), sha, ".jpg", "image/jpeg",
                    family_id=row.family_id, filename=f"{stem}.{kind}.jpg",
                    baby_id=row.baby_id or "", user_id=row.uploader_id or "")

        row.meta = meta          # JSON 列要整体赋值才算变更
        row.updated_at = _now()
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("缩略图生成失败 file=%s：%s", file_id, exc)
    finally:
        db.close()
