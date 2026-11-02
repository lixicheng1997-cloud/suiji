"""媒体 /media（契约 §7）：multipart 上传 + 鉴权下载（无/非法 token 按契约返回 403）。"""
import logging
import mimetypes

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..core.deps import (AuthContext, require_family, require_family_write,
                         resolve_token)
from ..core.rate_limit import limit as rate_limit
from ..core.security import ACCESS, MEDIA
from ..media.compress import compress_image
from ..media.store import get_store
from ..media.thumbnails import generate_variants, transcode_heic_to_jpeg
from ..models import Entry, EntryMedia
from ..repositories import scoped_get
from ..services.file_service import head_of, read_spool, validate_content
from ..services.ids import gen_id
from ..services.rows import media_row

router = APIRouter(prefix="/media", tags=["media"])

logger = logging.getLogger(__name__)

# 下载响应的硬化头：禁止浏览器把响应猜成别的内容类型去渲染
_SAFE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    # 内容不可变，允许客户端缓存一天（私域，用 private）
    "Cache-Control": "private, max-age=86400",
}


@router.post("")
def upload(file: UploadFile = File(...), entry_id: str = Form(""),
           db: Session = Depends(get_db), auth: AuthContext = Depends(require_family_write),
           _rl=rate_limit("upload", settings.rl_upload, settings.rl_upload_window)):
    """POST /media：分块读流（不再整读进内存），类型与 /files 走同一套校验。

    早先是 `data = file.file.read()` 全量入内存后才判 200MB 上限——
    并发几个请求就能把进程内存顶满；且上限硬编码，改 FILE_MAX_BYTES 对它无效。
    """
    name = file.filename or ""
    spool, sha, size = read_spool(file, settings.file_max_bytes)
    head = b""
    try:
        head = head_of(spool)
        suffix, content_type = validate_content(name, head)
        baby_id = ""
        if entry_id:
            e = scoped_get(db, Entry, entry_id, auth.family_id)
            baby_id = e.baby_id or ""

        # 同家庭 sha 去重：同记录重复上传直接复用行
        dup = db.query(EntryMedia).filter(EntryMedia.family_id == auth.family_id,
                                          EntryMedia.sha256 == sha,
                                          EntryMedia.entry_id == (entry_id or "")).first()
        if dup is not None:
            return media_row(dup)

        # 图片无损重压后再入对象存储：台账与下载拿到的都是压缩后的字节
        spool, sha, size = compress_image(spool, content_type, sha, size)
        head = head_of(spool)
        dup = db.query(EntryMedia).filter(EntryMedia.family_id == auth.family_id,
                                          EntryMedia.sha256 == sha,
                                          EntryMedia.entry_id == (entry_id or "")).first()
        if dup is not None:
            return media_row(dup)

        # HEIC → JPEG 转码（iPhone 照片兼容性）
        spool.seek(0)
        _raw = spool.read()
        _tc = transcode_heic_to_jpeg(_raw, content_type)
        if _tc:
            from tempfile import SpooledTemporaryFile
            new_bytes, content_type = _tc
            suffix = ".jpg"
            size = len(new_bytes)
            import hashlib
            sha = hashlib.sha256(new_bytes).hexdigest()
            spool.close()
            spool = SpooledTemporaryFile(max_size=8 * 1024 * 1024)
            spool.write(new_bytes)
            spool.seek(0)
            _raw = new_bytes
            dup = db.query(EntryMedia).filter(EntryMedia.family_id == auth.family_id,
                                              EntryMedia.sha256 == sha,
                                              EntryMedia.entry_id == (entry_id or "")).first()
            if dup is not None:
                return media_row(dup)

        reuse = db.query(EntryMedia).filter(EntryMedia.family_id == auth.family_id,
                                            EntryMedia.sha256 == sha).first()
        if reuse is not None:
            storage_key = reuse.storage_key  # 同家庭同内容：复用已存对象
        else:
            from ..services import file_service

            storage_key = file_service.existing_key(db, auth.family_id, sha) or get_store().save_stream(
                spool, size, sha, suffix, content_type,
                family_id=auth.family_id, filename=name)

        # 生成并存缩略图变体（仅图片）
        spool.seek(0)
        compressed = spool.read()
        variants = generate_variants(compressed, content_type)
        thumb_key = ""
        small_key = ""
        if variants and not reuse:
            from io import BytesIO
            from ..media.thumbnails import variant_storage_key
            stem = name.rsplit(".", 1)[0] if "." in name else name
            if "thumb" in variants:
                thumb_key = get_store().save_stream(
                    BytesIO(variants["thumb"]), len(variants["thumb"]),
                    sha, ".jpg", "image/jpeg",
                    family_id=auth.family_id, filename=stem + ".thumb.jpg")
            if "small" in variants:
                small_key = get_store().save_stream(
                    BytesIO(variants["small"]), len(variants["small"]),
                    sha, ".jpg", "image/jpeg",
                    family_id=auth.family_id, filename=stem + ".small.jpg")
    finally:
        spool.close()

    row = EntryMedia(
        id=gen_id("md"), family_id=auth.family_id, entry_id=entry_id or "",
        baby_id=baby_id, storage_key=storage_key, sha256=sha,
        size=size, width=0, height=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _register_file(db, auth, row, name, sha, size, head_bytes=head,
                   thumb_key=thumb_key, small_key=small_key)
    return media_row(row)


def _register_file(db: Session, auth: AuthContext, row: EntryMedia, name: str,
                   sha: str, size: int, head_bytes: bytes = b"",
                   thumb_key: str = "", small_key: str = "") -> None:
    """同步登记到统一文件台账（字节已在对象存储，这里只补一行路径记录）。"""
    from ..services import file_service

    try:
        extra_meta = {}
        if thumb_key:
            extra_meta["thumb_key"] = thumb_key
        if small_key:
            extra_meta["small_key"] = small_key
        file_service.register_uploaded(
            db, auth, storage_key=row.storage_key, sha256_hex=sha, size=size,
            original_name=name, content_type="", business_type="entry_media",
            business_id=row.id, baby_id=row.baby_id or "", head=head_bytes,
            meta=extra_meta)
        db.commit()
    except Exception as exc:  # 台账失败不阻断媒体主流程
        db.rollback()
        logger.warning("登记文件台账失败 media=%s：%s", row.id, exc)


@router.get("/{media_id}")
def download(media_id: str, request: Request, token: str = Query(""),
             variant: str = Query(""), db: Session = Depends(get_db)):
    """需鉴权：无 / 非法 / 已撤销 token 按契约 §7 返回 403（签名等价物）。

    与 /files 一致：Header 优先，?token= 兜底（<img src> 无法带 Header），
    且只放行 access / media 两类（media 为下载专用受限令牌）。
    variant=thumb|small：返回预生成的缩略图（列表页用），不存在则回退原图。
    """
    header = request.headers.get("Authorization") or ""
    bearer = header[7:] if header.startswith("Bearer ") else ""
    # URL 里只认 media 令牌：?token= 会落进 nginx 日志 / 浏览器历史 / Referer，
    # 必须是「只能下载、不能调业务接口」的受限令牌；access 令牌只走 Authorization 头。
    if token:
        auth = resolve_token(db, token, types=(MEDIA,))
    else:
        auth = resolve_token(db, bearer, types=(ACCESS, MEDIA))
    if auth is None:
        raise HTTPException(status_code=403, detail="无权访问该媒体")
    # 家庭门控：账号未关联家庭（未走完引导）→ 与业务接口一致的 409 need_family
    if not auth.family_id:
        raise HTTPException(status_code=409, detail="need_family")
    row = scoped_get(db, EntryMedia, media_id, auth.family_id)
    # 纵深防御：对象路径首段必须是本家庭目录，挡住任何来源异常的跨家庭读取
    _assert_key_owner(row.storage_key or "", auth.family_id)
    store = get_store()
    media_type = _media_type_of(db, row)

    # 选择对象 key：默认原图；variant 时从 FileObject 台账反查缩略图 key
    effective_key = row.storage_key or ""
    if variant in ("thumb", "small"):
        vk = _variant_key_of(db, effective_key, variant)
        if vk:
            effective_key = vk
            media_type = "image/jpeg"

    headers = dict(_SAFE_HEADERS)
    if row.sha256:
        headers["ETag"] = f'"{row.sha256[:16]}"'

    # MinIO：优先 307 跳预签名 URL（客户端直连对象存储），否则服务端代理回源
    # effective_key 可能是缩略图变体 key，同样在 MinIO 里，直接 presign。
    if (settings.media_download_mode != "proxy"
            and settings.minio_public_url):
        signed = store.url(effective_key, expires=settings.media_url_expires)
        if signed:
            return RedirectResponse(url=signed, status_code=307, headers=headers)

    stream = store.open_stream(effective_key)
    if stream is not None:
        return StreamingResponse(stream, media_type=media_type, headers=headers)
    # 变体对象不存在（历史数据）：回退原图
    if variant and effective_key != (row.storage_key or ""):
        stream = store.open_stream(row.storage_key)
        if stream is not None:
            return StreamingResponse(stream,
                                    media_type=_media_type_of(db, row),
                                    headers=headers)
    path = store.path(effective_key)
    if path is None:
        raise HTTPException(status_code=404, detail="媒体文件不存在")
    return FileResponse(path, media_type=media_type, headers=headers)


def _variant_key_of(db: Session, storage_key: str, variant: str) -> str:
    """从 FileObject 台账反查同 storage_key 对应的缩略图对象 key。"""
    if not storage_key or variant not in ("thumb", "small"):
        return ""
    from ..models import FileObject
    frow = (db.query(FileObject)
            .filter(FileObject.storage_key == storage_key)
            .order_by(FileObject.created_at.desc())
            .first())
    if frow is None or not isinstance(frow.meta, dict):
        return ""
    return frow.meta.get(f"{variant}_key", "") or ""


def _assert_key_owner(storage_key: str, family_id: str) -> None:
    """对象路径首段必须是本家庭（对象按 `{family_id}/{日期}/{文件名}` 归档）。

    storage_key 来自数据库，正常情况下一定属于本家庭；这里作为纵深防御，
    挡住历史脏数据 / 导入残留等来源异常造成的跨家庭读取。
    """
    first = (storage_key or "").replace("\\", "/").split("/", 1)[0]
    if first and first != family_id:
        raise HTTPException(status_code=403, detail="无权访问该媒体")


def _media_type_of(db: Session, row: EntryMedia) -> str:
    """响应 Content-Type：优先取文件台账里登记的（上传时嗅探写入的安全值），
    不再按文件名凭空推断——也不回显客户端传来、被写进库里的类型。"""
    from ..models import FileObject

    ct = ""
    if row.storage_key:
        frow = (db.query(FileObject)
                .filter(FileObject.storage_key == row.storage_key)
                .order_by(FileObject.created_at.desc())
                .first())
        if frow is not None and frow.content_type:
            ct = frow.content_type
    return ct or mimetypes.guess_type(row.storage_key or "")[0] or "application/octet-stream"
