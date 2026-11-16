"""非结构化文件服务：字节统一入对象存储（MinIO），结构化库只存 storage_key 与元信息。

对外能力：上传（单/多）、列表、详情、绑定业务、删除（引用计数释放对象）、用量统计。
字节在对象存储里按 `{family_id}/{YYYY-MM-DD}/{文件名}` 归档（家庭隔离 + 按天分目录）；
同家庭同内容（sha256）复用同一个对象，一份字节可被多条台账引用。
"""
import hashlib
import logging
import mimetypes
import re
from datetime import datetime, timezone
from tempfile import SpooledTemporaryFile

from fastapi import HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.deps import AuthContext
from ..media import jobs, safety
from ..media.compress import compress_image
from ..media.store import CosMediaStore, get_store, object_key
from ..media.thumbnails import transcode_heic_to_jpeg
from ..models import Baby, Entry, EntryMedia, FileObject
from ..repositories import scoped_get
from ..services.ids import gen_id
from ..services.rows import file_row

logger = logging.getLogger(__name__)

_SUFFIX_RE = re.compile(r"^\.[0-9A-Za-z]{1,8}$")
_CHUNK = 1024 * 1024
_SPOOL_MAX = 8 * 1024 * 1024  # 小文件走内存缓冲，大文件自动落临时盘
# 声明成文本但内容里出现这些标记 = 实际是 HTML/SVG/XML：浏览器会当页面渲染，
# 在 API 源站同源执行脚本。一律拒绝，不看扩展名怎么说。
_HTML_MARKERS = (b"<!doctype html", b"<html", b"<script", b"<svg", b"<?xml",
                 b"<iframe", b"javascript:")
_SNIFF_BYTES = 4096
_TEXT_EXT = (".json", ".csv", ".txt")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ext_of(name: str) -> str:
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return ext if _SUFFIX_RE.match(ext) else ""


def _content_type_of(upload: UploadFile, name: str) -> str:
    return (upload.content_type or mimetypes.guess_type(name)[0]
            or "application/octet-stream").split(";")[0].strip()


def read_spool(upload: UploadFile, max_bytes: int) -> tuple[SpooledTemporaryFile, str, int]:
    """分块读取上传流：小文件内存缓冲、大文件落临时盘，同时算 sha256 与大小。"""
    digest = hashlib.sha256()
    size = 0
    spool = SpooledTemporaryFile(max_size=_SPOOL_MAX)
    try:
        while True:
            chunk = upload.file.read(_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(status_code=422,
                                    detail=f"文件超过 {max_bytes // (1024 * 1024)}MB 上限")
            digest.update(chunk)
            spool.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="文件为空")
    except Exception:
        spool.close()
        raise
    spool.seek(0)
    return spool, digest.hexdigest(), size


def validate_content(name: str, head: bytes) -> tuple[str, str]:
    """上传内容校验：扩展名白名单 + magic bytes 嗅探，返回 (归一化 ext, 服务端认定的 Content-Type)。

    扩展名与 Content-Type 都由客户端提供，两个都不能信：
      - 扩展名决定文件能不能被当成页面渲染 → 必须过白名单（html/svg/js 一律拒）
      - Content-Type 会被下载端点原样回显 → 必须用字节嗅探的结果覆盖
    """
    kind = safety.sniff(head)
    ext = safety.normalize_ext(name)
    if not ext:
        # 无扩展名或扩展名不在白名单：按真实字节推导（移动端 blob:/content: 临时文件没有扩展名）。
        # 推导只认 magic bytes 确认的媒体类型，html/svg/js 等嗅探成 text/other 的仍会被拒。
        ext = safety.ext_from_kind(kind)
        if not ext:
            raise HTTPException(status_code=422, detail="不支持的文件类型")
    if kind == "text":
        low = head.lower()
        for marker in _HTML_MARKERS:
            if marker in low:
                raise HTTPException(status_code=422, detail="不支持的文件类型")
    if kind == "text" and ext in _TEXT_EXT:
        content_type = mimetypes.guess_type(ext)[0] or "text/plain"
    else:
        content_type = safety.inline_policy(kind)[1]
    return ext, content_type


def head_of(spool) -> bytes:
    """取文件开头若干字节用于嗅探，读完后把游标归位。"""
    try:
        spool.seek(0)
        head = spool.read(_SNIFF_BYTES)
    finally:
        spool.seek(0)
    return head or b""


def _head_of_bytes(data: bytes) -> bytes:
    return data[:_SNIFF_BYTES]


def _check_owner(db: Session, auth: AuthContext, business_type: str,
                 business_id: str, baby_id: str) -> None:
    """业务挂载点必须属于当前家庭，避免把文件挂到别人的记录上。

    用「未知 business_type 一律拒绝 business_id」而不是「只校验认识的两种」：
    白名单式放行会随着新增挂载类型（entry_media / other / 未来任何值）逐个漏掉，
    漏掉的那个就是可以指向任意外部 id 的口子。
    """
    if business_id:
        if business_type == "entry":
            scoped_get(db, Entry, business_id, auth.family_id)
        elif business_type == "baby":
            scoped_get(db, Baby, business_id, auth.family_id)
        elif business_type == "entry_media":
            scoped_get(db, EntryMedia, business_id, auth.family_id)
        elif business_type in ("", "other"):
            # 未绑定业务 / 自由挂载：business_id 由客户端自定义，不指向库内资源，
            # 但仍禁止写成别的家庭的资源 id（避免后续按 id 反查时越界）
            pass
        else:
            raise HTTPException(status_code=422, detail="不支持的挂载类型")
    if baby_id:
        scoped_get(db, Baby, baby_id, auth.family_id)


def _existing(db: Session, family_id: str, sha: str, business_type: str, business_id: str):
    """同家庭 + 同内容 + 同业务挂载点：直接复用，不重复上传。"""
    return (
        db.query(FileObject)
        .filter(FileObject.family_id == family_id, FileObject.sha256 == sha,
                FileObject.business_type == business_type,
                FileObject.business_id == business_id,
                FileObject.deleted_at.is_(None))
        .first()
    )


def existing_key(db: Session, family_id: str, sha: str) -> str:
    """同家庭 + 同内容：返回已上传对象的 storage_key（空串表示还没存过）。

    对象路径是 `{family}/{日期}/{文件名}`，同名不同内容会落到不同 key，
    所以这里按 sha 复用已有对象，保证同一份字节在家庭内只存一份。
    """
    if not sha:
        return ""
    row = (
        db.query(FileObject)
        .filter(FileObject.family_id == family_id, FileObject.sha256 == sha,
                FileObject.deleted_at.is_(None), FileObject.storage_key != "")
        .order_by(FileObject.created_at.asc(), FileObject.id.asc())
        .first()
    )
    return (row.storage_key or "") if row else ""


def _insert_row(db: Session, auth: AuthContext, storage_key: str, name: str,
                content_type: str, ext: str, sha: str, size: int, business_type: str,
                business_id: str, baby_id: str, meta: dict | None = None) -> dict:
    row = FileObject(
        id=gen_id("file"), family_id=auth.family_id,
        business_type=business_type, business_id=business_id, baby_id=baby_id,
        original_name=name[:255], content_type=content_type[:128], ext=ext,
        storage_key=storage_key, sha256=sha, size=size,
        uploader_id=auth.user_id, created_at=_now(), updated_at="", meta=meta or {},
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except IntegrityError:  # 并发上传同一内容到同一挂载点：回落到已有行
        db.rollback()
        dup = _existing(db, auth.family_id, sha, business_type, business_id)
        if dup is None:
            raise
        return file_row(dup)
    return file_row(row)


def upload_file(db: Session, auth: AuthContext, upload: UploadFile, business_type: str = "",
                business_id: str = "", baby_id: str = "", duration: float = 0) -> dict:
    """上传单个文件：字节入对象存储，数据库只写一行路径台账。

    duration：客户端在选视频/录制后从 tempFile 读到的时长（秒），仅对 video/* 生效。
    服务端不做容器解析（无 ffmpeg），以客户端上报值为准做硬上限兜底——
    前端录制时已用 maxDuration 限制，这里是防绕过/选相册长视频的第二道闸。
    """
    business_type = (business_type or "").strip().lower()
    business_id = (business_id or "").strip()
    baby_id = (baby_id or "").strip()
    _check_owner(db, auth, business_type, business_id, baby_id)

    name = upload.filename or ""
    # read_spool 会按 max_bytes 截断；先按通用上限读，读完再看是否为视频并按视频上限重校
    spool, sha, size = read_spool(upload, settings.file_max_bytes)
    ext, content_type = validate_content(name, head_of(spool))

    is_video = content_type.startswith("video/")
    if is_video:
        # 视频单文件大小硬上限（30s@高码率约 30-50MB，给到 100MB 留余量）
        if size > settings.video_max_bytes:
            spool.close()
            raise HTTPException(
                status_code=422,
                detail=f"视频超过 {settings.video_max_bytes // (1024 * 1024)}MB 上限，请压缩后再传")
        # 时长校验：客户端上报 ≤0 时跳过（图片/音频不会传）；>上限直接拒
        try:
            dur = float(duration or 0)
        except (TypeError, ValueError):
            dur = 0.0
        if dur > settings.video_max_seconds:
            spool.close()
            raise HTTPException(
                status_code=422,
                detail=f"视频最长 {settings.video_max_seconds} 秒，请剪辑后再传")

    dup = _existing(db, auth.family_id, sha, business_type, business_id)
    if dup is not None:  # 同挂载点已有相同内容：直接返回已有台账行
        spool.close()
        return file_row(dup)

    # 图片无损重压后再入对象存储：此后去重、台账、下载拿到的都是压缩后的字节
    spool, sha, size = compress_image(spool, content_type, sha, size)
    dup = _existing(db, auth.family_id, sha, business_type, business_id)
    if dup is not None:  # 压缩后与已有台账内容一致（如同一图的多次上传）
        spool.close()
        return file_row(dup)

    # HEIC → JPEG 转码（iPhone 照片在 Android/Web 解码兼容性差）
    # 只有嗅探确认是 HEIC 才把整份读进内存：JPEG/PNG 的字节已经在 spool 里，白读一次是峰值内存
    if content_type in ("image/heic", "image/heif"):
        spool.seek(0)
        transcoded = transcode_heic_to_jpeg(spool.read(), content_type)
        if transcoded:
            new_bytes, content_type = transcoded
            ext = ".jpg"
            size = len(new_bytes)
            sha = hashlib.sha256(new_bytes).hexdigest()
            spool.close()
            spool = SpooledTemporaryFile(max_size=_SPOOL_MAX)
            spool.write(new_bytes)
            spool.seek(0)
            # 转码后可能命中已有行（同一 HEIC 之前转过）
            dup = _existing(db, auth.family_id, sha, business_type, business_id)
            if dup is not None:
                spool.close()
                return file_row(dup)

    try:
        reuse = existing_key(db, auth.family_id, sha)
        if reuse:  # 家庭内已存过这份字节：新台账行直接复用同一对象路径
            storage_key = reuse
        else:
            storage_key = get_store().save_stream(
                spool, size, sha, ext, content_type,
                family_id=auth.family_id, filename=name,
                baby_id=baby_id, user_id=auth.user_id)
    finally:
        spool.close()

    meta: dict = {}
    # 视频：把客户端上报的时长（秒）写进 meta，详情/列表页直接显示，避免每次播放再 probe
    if is_video and dur > 0:
        meta["duration"] = round(dur, 2)

    out = _insert_row(db, auth, storage_key, name, content_type, ext, sha, size,
                      business_type, business_id, baby_id, meta=meta)
    if content_type.startswith("image/"):
        # 两张缩略图（12MP 实测 708ms，占请求线程 CPU 的近六成）交给后台线程池。
        # 下载端点在 meta 里没有变体 key 时自动回落原图，所以响应可以立刻返回。
        jobs.submit(out["id"], auth.family_id)
    return out


def upload_many(db: Session, auth: AuthContext, uploads: list[UploadFile], business_type: str = "",
                business_id: str = "", baby_id: str = "") -> dict:
    items, errors = [], []
    for up in uploads:
        try:
            items.append(upload_file(db, auth, up, business_type, business_id, baby_id))
        except HTTPException as exc:
            errors.append({"filename": up.filename or "", "detail": exc.detail})
        except Exception as exc:  # 单个失败不污染整批
            db.rollback()
            logger.warning("批量上传失败 file=%s：%s", up.filename, exc)
            errors.append({"filename": up.filename or "", "detail": "上传失败"})
    return {"items": items, "errors": errors, "count": len(items)}


def register_uploaded(db: Session, auth: AuthContext, storage_key: str, sha256_hex: str, size: int,
                      original_name: str = "", content_type: str = "", business_type: str = "",
                      business_id: str = "", baby_id: str = "", head: bytes = b"",
                      meta: dict | None = None) -> FileObject | None:
    """登记已上传对象（/media 复用）：只写台账行，不重复上传字节。

    head 传入文件开头字节用于嗅探：这里的 content_type 同样来自客户端，不能直写库。
    meta 用于附加元信息（如缩略图 key），与已有 meta 合并。
    """
    business_type = (business_type or "").strip().lower()
    # sha 为空（直传骨架暂不算摘要）时不做内容去重复用：否则多个空 sha 行会互相误判为同一份内容
    dup = _existing(db, auth.family_id, sha256_hex, business_type, business_id) if sha256_hex else None
    if dup is not None:
        if meta:  # 已有行：合并缩略图 key
            changed = False
            for k, v in meta.items():
                if v and not (dup.meta or {}).get(k):
                    if not isinstance(dup.meta, dict):
                        dup.meta = {}
                    dup.meta[k] = v
                    changed = True
            if changed:
                dup.updated_at = _now()
                db.commit()
        return dup
    ext, safe_ct = validate_content(original_name or "", head or b"")
    row_meta: dict = dict(meta or {})
    row = FileObject(
        id=gen_id("file"), family_id=auth.family_id,
        business_type=business_type, business_id=business_id or "", baby_id=baby_id or "",
        original_name=(original_name or "")[:255],
        content_type=safe_ct[:128],
        ext=ext,
        storage_key=storage_key, sha256=sha256_hex, size=int(size or 0),
        uploader_id=auth.user_id, created_at=_now(), updated_at="", meta=row_meta,
    )
    db.add(row)
    db.flush()
    return row


def issue_presign(db: Session, auth: AuthContext, payload: dict) -> dict:
    """为直传签发短时 PUT 预签名 URL（骨架：直传失败/不支持时前端回退 multipart）。

    返回 `{direct: True, upload_url, storage_key, content_type, expires}`；
    当前后端不支持直传（local 磁盘）或预签名失败时返回 `{direct: False}`。

    注意：这里只做大小/时长/挂载点校验，内容类型以登记回调回源嗅探为准，
    客户端声明的 content_type 不参与安全判定。
    """
    business_type = (payload.get("business_type") or "").strip().lower()
    business_id = (payload.get("business_id") or "").strip()
    baby_id = (payload.get("baby_id") or "").strip()
    _check_owner(db, auth, business_type, business_id, baby_id)

    name = str(payload.get("original_name") or payload.get("filename") or "").strip()
    size = int(payload.get("size") or 0)
    try:
        duration = float(payload.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    ct = str(payload.get("content_type") or "").split(";")[0].strip().lower()

    if size > settings.file_max_bytes:
        raise HTTPException(status_code=422,
                            detail=f"文件超过 {settings.file_max_bytes // (1024 * 1024)}MB 上限")
    if ct.startswith("video/"):
        if size > settings.video_max_bytes:
            raise HTTPException(status_code=422,
                                detail=f"视频超过 {settings.video_max_bytes // (1024 * 1024)}MB 上限")
        if duration > settings.video_max_seconds:
            raise HTTPException(status_code=422,
                                detail=f"视频最长 {settings.video_max_seconds} 秒，请剪辑后再传")

    # 直传阶段还没有 sha256：文件名追加随机短码保证 key 唯一，登记时直接复用该 key
    suffix = safety.normalize_ext(name)
    rand = gen_id("d")[:8]
    stem = name.rsplit(".", 1)[0] if "." in name else name
    stem = stem.strip() or "direct"
    fname = f"{stem}_{rand}{suffix}" if suffix else f"{stem}_{rand}"

    key = object_key(auth.family_id, fname, suffix, sha256_hex="",
                     content_type=ct, baby_id=baby_id, user_id=auth.user_id)
    store = get_store()
    # COS 走 PostObject 表单直传（uni.uploadFile 三端兼容）；其他后端维持 PUT 预签名（H5）。
    if isinstance(store, CosMediaStore):
        post = store.presigned_post(key, ct, size=size, expires=settings.media_url_expires)
        if not post:
            return {"direct": False}
        return {
            "direct": True,
            **post,
            "storage_key": key,
            "content_type": ct or "application/octet-stream",
            "expires": settings.media_url_expires,
        }
    upload_url = store.presigned_put(key, ct, expires=settings.media_url_expires)
    if not upload_url:
        return {"direct": False}
    return {
        "direct": True,
        "method": "put",
        "upload_url": upload_url,
        "storage_key": key,
        "content_type": ct or "application/octet-stream",
        "expires": settings.media_url_expires,
    }


def register_direct(db: Session, auth: AuthContext, payload: dict) -> dict:
    """直传完成后登记台账：回源读头字节做 magic bytes 嗅探，复用 register_uploaded 写行。

    storage_key 必须由预签名接口下发；路径首段必须是本家庭目录（纵深防御，挡住跨家庭登记）。
    """
    business_type = (payload.get("business_type") or "").strip().lower()
    business_id = (payload.get("business_id") or "").strip()
    baby_id = (payload.get("baby_id") or "").strip()
    _check_owner(db, auth, business_type, business_id, baby_id)

    key = str(payload.get("storage_key") or "").strip().replace("\\", "/")
    if not key:
        raise HTTPException(status_code=422, detail="缺少 storage_key")
    first = key.split("/", 1)[0]
    if first != auth.family_id:
        raise HTTPException(status_code=403, detail="无权访问该文件")

    store = get_store()
    if not store.exists(key):
        raise HTTPException(status_code=409, detail="直传对象不存在，请重新上传")

    # 回源读头 32 字节嗅探：不信客户端声明的类型，与 multipart 上传同一套安全判定
    head = b""
    stream = store.open_stream(key, 0, 31)
    if stream is not None:
        head = b"".join(stream)[:32]
    if not head:
        raise HTTPException(status_code=409, detail="直传对象不可读，请重新上传")

    name = str(payload.get("original_name") or "")
    try:
        duration = float(payload.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0

    # 体积以对象存储的权威统计为准，不采信客户端上报值：
    # presign 时还没字节，客户端报 0 就能绕过 200MB/100MB 上限，直传通道等于开后门。
    size = store.size(key) or 0
    if size <= 0:
        raise HTTPException(status_code=409, detail="直传对象不可读，请重新上传")
    if size > settings.file_max_bytes:
        raise HTTPException(status_code=422,
                            detail=f"文件超过 {settings.file_max_bytes // (1024 * 1024)}MB 上限")
    kind_ct = safety.inline_policy(safety.sniff(head))[1]
    if kind_ct.startswith("video/"):
        if size > settings.video_max_bytes:
            raise HTTPException(status_code=422,
                                detail=f"视频超过 {settings.video_max_bytes // (1024 * 1024)}MB 上限")
        if duration > settings.video_max_seconds:
            raise HTTPException(status_code=422,
                                detail=f"视频最长 {settings.video_max_seconds} 秒，请剪辑后再传")
    meta: dict = {"direct": True}
    if kind_ct.startswith("video/") and duration > 0:
        meta["duration"] = round(duration, 2)

    row = register_uploaded(
        db, auth, storage_key=key, sha256_hex="", size=size,
        original_name=name, content_type=kind_ct,
        business_type=business_type, business_id=business_id, baby_id=baby_id,
        head=head, meta=meta)
    db.commit()
    if kind_ct.startswith("image/"):
        # 直传绕过了服务端的图片管线，缩略图同样靠后台补齐（缺失期间下载回落原图）
        jobs.submit(row.id, auth.family_id)
    return file_row(row)


def list_files(db: Session, auth: AuthContext, business_type: str = "", business_id: str = "",
               baby_id: str = "", keyword: str = "", limit: int = 50, offset: int = 0) -> dict:
    q = db.query(FileObject).filter(FileObject.family_id == auth.family_id,
                                    FileObject.deleted_at.is_(None))
    if business_type:
        q = q.filter(FileObject.business_type == business_type.strip().lower())
    if business_id:
        q = q.filter(FileObject.business_id == business_id)
    if baby_id:
        q = q.filter(FileObject.baby_id == baby_id)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(FileObject.original_name.like(like))
    total = q.count()
    rows = q.order_by(FileObject.created_at.desc(), FileObject.id.desc()) \
            .offset(max(0, offset)).limit(max(1, min(limit, 200))).all()
    return {"items": [file_row(r) for r in rows], "total": total,
            "limit": limit, "offset": offset}


def get_file(db: Session, auth: AuthContext, file_id: str) -> FileObject:
    row = scoped_get(db, FileObject, file_id, auth.family_id)
    if row.deleted_at:
        raise HTTPException(status_code=404, detail="文件不存在")
    return row


def _entry_for_file(db: Session, auth: AuthContext, row: FileObject) -> Entry | None:
    """定位附件所属记录：entry 直挂；entry_media 反查 media → entry；其余类型无记录归属。"""
    if row.business_type == "entry":
        return scoped_get(db, Entry, row.business_id, auth.family_id)
    if row.business_type == "entry_media":
        md = scoped_get(db, EntryMedia, row.business_id, auth.family_id)
        if md.entry_id:
            return scoped_get(db, Entry, md.entry_id, auth.family_id)
    return None


def _assert_record_owner(db: Session, auth: AuthContext, row: FileObject) -> None:
    """附件跟随记录归属（两角色模型 v1.3）。

    - 创建者：任意附件放行；
    - 成员：挂在本人创建记录上的附件可改/删；宝宝头像等档案资料随宝宝档案可写，
      不做个人归属；未挂具体记录（other/空）或所属记录为无主历史记录时，成员不可处置；
    归属以服务端令牌解析的 user_id 为准，不采信上传人名字串。
    """
    if auth.role == "creator":
        return
    if row.business_type == "baby":
        # 宝宝档案资料：随档案可写（成员可参与建档/改档），不做个人归属校验
        return
    entry = _entry_for_file(db, auth, row)
    if entry is not None and entry.creator_id and entry.creator_id == auth.user_id:
        return
    raise HTTPException(status_code=403, detail="只能修改或删除自己记录上的文件")


def update_file(db: Session, auth: AuthContext, file_id: str, patch: dict) -> dict:
    """改名 / 挂载或改挂业务：只允许改元信息，storage_key 与内容不可变。"""
    row = get_file(db, auth, file_id)
    _assert_record_owner(db, auth, row)
    business_type = patch.get("business_type")
    business_id = patch.get("business_id")
    baby_id = patch.get("baby_id")
    if business_type is not None:
        business_type = (business_type or "").strip().lower()
        row.business_type = business_type
    else:
        business_type = row.business_type
    if business_id is not None:
        row.business_id = business_id.strip()
    if baby_id is not None:
        row.baby_id = baby_id.strip()
    if "original_name" in patch and patch["original_name"] is not None:
        row.original_name = str(patch["original_name"])[:255]
    if "meta" in patch and isinstance(patch["meta"], dict):
        row.meta = patch["meta"]
    _check_owner(db, auth, business_type, row.business_id, row.baby_id)
    row.updated_at = _now()
    try:
        db.commit()
    except IntegrityError:  # 目标挂载点已有相同内容的文件
        db.rollback()
        raise HTTPException(status_code=422, detail="该挂载点已存在相同文件")
    db.refresh(row)
    return file_row(row)


def object_in_use(db: Session, family_id: str, storage_key: str, exclude_file_id: str = "",
                  exclude_media_id: str = "") -> bool:
    """同家庭是否还有别的文件行/媒体行引用同一个对象：有则不能删字节。"""
    if not storage_key:
        return False
    q = db.query(FileObject).filter(FileObject.family_id == family_id,
                                    FileObject.storage_key == storage_key)
    if exclude_file_id:
        q = q.filter(FileObject.id != exclude_file_id)
    if q.first() is not None:
        return True
    m = db.query(EntryMedia).filter(EntryMedia.family_id == family_id,
                                    EntryMedia.storage_key == storage_key)
    if exclude_media_id:
        m = m.filter(EntryMedia.id != exclude_media_id)
    return m.first() is not None


def delete_file(db: Session, auth: AuthContext, file_id: str) -> dict:
    """删除台账行；无其他引用时一并释放对象存储里的字节。"""
    row = get_file(db, auth, file_id)
    _assert_record_owner(db, auth, row)
    storage_key = row.storage_key or ""
    file_id_value = row.id
    db.delete(row)
    db.commit()
    if not object_in_use(db, auth.family_id, storage_key, exclude_file_id=""):
        try:
            get_store().delete(storage_key)
        except Exception as exc:
            logger.warning("释放对象失败 %s：%s", storage_key, exc)
    return {"id": file_id_value, "storage_key": storage_key}


def stats(db: Session, auth: AuthContext) -> dict:
    from sqlalchemy import func

    row = (
        db.query(func.count(FileObject.id), func.coalesce(func.sum(FileObject.size), 0))
        .filter(FileObject.family_id == auth.family_id, FileObject.deleted_at.is_(None))
        .one()
    )
    by_type = (
        db.query(FileObject.business_type, func.count(FileObject.id),
                 func.coalesce(func.sum(FileObject.size), 0))
        .filter(FileObject.family_id == auth.family_id, FileObject.deleted_at.is_(None))
        .group_by(FileObject.business_type)
        .all()
    )
    return {
        "count": int(row[0] or 0),
        "total_size": int(row[1] or 0),
        "by_business_type": [
            {"business_type": t or "", "count": int(c or 0), "total_size": int(s or 0)}
            for t, c, s in by_type
        ],
    }


def temp_url(row: FileObject, expires: int = 0) -> dict:
    """临时直链（MinIO 预签名）；本地磁盘后端不支持则返回 None，客户端走 /download 代理。

    预签名 URL 是「绕过 JWT 的免鉴权直连」，拿到即等于拿到该文件，
    所以有效期必须由服务端封顶——客户端传 1 年也只会拿到 1 小时。
    """
    seconds = int(expires or settings.media_url_expires or 600)
    seconds = max(60, min(seconds, settings.media_url_max_expires))
    url = get_store().url(row.storage_key, expires=seconds) if row.storage_key else None
    return {"id": row.id, "url": url, "expires": seconds,
            "download_url": f"/api/v1/files/{row.id}/download"}
