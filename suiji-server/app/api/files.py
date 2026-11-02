"""非结构化文件 /files：字节统一存 MinIO，结构化库只存 storage_key（对象路径）。

下载支持 `Authorization: Bearer` 或 `?token=`（便于 <img src>/<a href> 直连）；
无/非法 token 一律 403。字面量路由（/batch、/stats）必须先于 /{file_id} 注册。
"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..core.deps import AuthContext, require_family, require_family_write, resolve_token
from ..core.rate_limit import limit as rate_limit
from ..core.security import ACCESS, MEDIA
from ..media.store import get_store
from ..models import FileObject
from ..schemas import FilePatch
from ..services import file_service
from ..services.rows import file_row

router = APIRouter(prefix="/files", tags=["files"])

# 下载响应统一附加的硬化头：禁止浏览器把响应猜成别的内容类型去渲染
_SAFE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    # 图片/文件内容不可变（storage_key 不可变，同 key 永远同字节），
    # 允许客户端缓存一天；URL 带 ?token= 是私域令牌，所以用 private 而不是 public。
    "Cache-Control": "private, max-age=86400",
}


def _auth(request: Request, token: str, db: Session) -> AuthContext:
    """Header 优先，query ?token= 兜底；无效一律 403（契约与 /media 一致）。

    URL 里只认 **media** 令牌：它会落进 nginx access_log、浏览器历史、Referer，
    必须是「只能下载、不能调业务接口」的受限令牌。
    之前这里把 access 也放进了 query，等于把完整业务凭证写进日志——
    access 令牌仍然可以用，但只允许走 Authorization 头。
    """
    header = request.headers.get("Authorization") or ""
    bearer = header[7:] if header.startswith("Bearer ") else ""
    if token:
        auth = resolve_token(db, token, types=(MEDIA,))
    else:
        auth = resolve_token(db, bearer, types=(ACCESS, MEDIA))
    if auth is None:
        raise HTTPException(status_code=403, detail="无权访问该文件")
    return auth


def _inline_ok(row: FileObject) -> bool:
    """是否允许在浏览器里内联渲染。

    只有上传时嗅探确认过的图片/视频/音频/PDF 才放行；其余一律当附件下载。
    （历史数据里可能存着客户端伪造的 text/html，这里一并挡住。）
    """
    ct = (row.content_type or "").lower()
    return ct.startswith(("image/", "video/", "audio/")) or ct == "application/pdf"


@router.post("")
def upload(file: UploadFile = File(...), business_type: str = Form(""),
           business_id: str = Form(""), baby_id: str = Form(""),
           db: Session = Depends(get_db), auth: AuthContext = Depends(require_family_write),
           _rl=rate_limit("upload", settings.rl_upload, settings.rl_upload_window)):
    """POST /files：multipart 上传，返回文件行（storage_key 即对象存储路径）。"""
    return file_service.upload_file(db, auth, file, business_type, business_id, baby_id)


@router.post("/batch")
def upload_batch(files: list[UploadFile] = File(...), business_type: str = Form(""),
                 business_id: str = Form(""), baby_id: str = Form(""),
                 db: Session = Depends(get_db), auth: AuthContext = Depends(require_family_write),
                 _rl=rate_limit("upload", settings.rl_upload, settings.rl_upload_window)):
    """POST /files/batch：一次挂多个文件到同一业务；单个失败不中断其余（记入 errors）。"""
    if not files:
        raise HTTPException(status_code=422, detail="缺少文件")
    return file_service.upload_many(db, auth, files, business_type, business_id, baby_id)


@router.get("")
def list_files(business_type: str = Query(""), business_id: str = Query(""),
               baby_id: str = Query(""), keyword: str = Query(""),
               limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
               db: Session = Depends(get_db), auth: AuthContext = Depends(require_family)):
    return file_service.list_files(db, auth, business_type, business_id, baby_id,
                                   keyword, limit, offset)


@router.get("/stats")
def stats(db: Session = Depends(get_db), auth: AuthContext = Depends(require_family)):
    """当前家庭的非结构化文件数量与占用字节。"""
    return file_service.stats(db, auth)


@router.get("/{file_id}")
def get_one(file_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(require_family)):
    return file_row(file_service.get_file(db, auth, file_id))


@router.patch("/{file_id}")
def update(file_id: str, body: FilePatch, db: Session = Depends(get_db),
           auth: AuthContext = Depends(require_family_write)):
    """改名 / 挂载或改挂业务（business_type+business_id）；文件内容与路径不可变。"""
    return file_service.update_file(db, auth, file_id, body.model_dump(exclude_unset=True))


@router.delete("/{file_id}")
def delete(file_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(require_family_write)):
    """删除文件行；同家庭无其他引用时一并删除对象存储中的字节。"""
    return file_service.delete_file(db, auth, file_id)


@router.get("/{file_id}/url")
def temp_url(file_id: str, expires: int = Query(0, ge=0),
             db: Session = Depends(get_db), auth: AuthContext = Depends(require_family)):
    """临时直链（MinIO 预签名）；本地磁盘后端 url=null，请走 /download。"""
    return file_service.temp_url(file_service.get_file(db, auth, file_id), expires)


@router.get("/{file_id}/download")
def download(file_id: str, request: Request, token: str = Query(""),
             inline: int = Query(0), variant: str = Query(""),
             db: Session = Depends(get_db)):
    """下载字节：优先 307 跳 MinIO 预签名，否则服务端流式回源。inline=1 用于图片预览。

    variant=thumb|small：返回上传时预生成的缩略图变体（列表页用，体积小一个数量级）。
    变体对象不存在（历史数据未生成）时静默回退到原图。

    代理回源这条路径支持单段 `Range: bytes=a-b`（206 + Content-Range），
    否则 <audio>/<video> 播放器（iOS Safari、微信 innerAudioContext）拿不到可拖动字节流。
    """
    # 手写鉴权（支持 ?token= 给 <img src> 直连）后仍需过家庭门控
    auth = require_family(_auth(request, token, db))
    row: FileObject = file_service.get_file(db, auth, file_id)
    store = get_store()
    media_type = row.content_type or "application/octet-stream"

    # 选择要返回的对象 key：默认原图；variant=thumb/small 时从 meta 取预生成的变体 key
    effective_key = row.storage_key
    if variant in ("thumb", "small"):
        vk = (row.meta or {}).get(f"{variant}_key", "") if isinstance(row.meta, dict) else ""
        if vk:
            effective_key = vk
            media_type = "image/jpeg"  # 变体固定 JPEG

    # 内容类型不安全（如历史遗留的 text/html）时强制下载：
    # 内联渲染会让上传的 HTML 在 API 源站同源执行脚本（存储型 XSS）。
    inline = 1 if (inline and _inline_ok(row)) else 0
    # 预签名直连对象存储（带鉴权与有效期，避免大文件占用 API 带宽）。
    # effective_key 可能是缩略图变体 key，同样在 MinIO 里，直接 presign 即可。
    # <img>/<video> 标签不关心 Content-Disposition，直连 MinIO 浏览器照样能渲染；
    # 只有直接在浏览器地址栏打开 PDF 等场景才需要 inline disposition，那种场景量极少。
    use_proxy = (settings.media_download_mode == "proxy"
                 or not settings.minio_public_url)
    if not use_proxy:
        signed = store.url(effective_key, expires=settings.media_url_expires)
        if signed:
            return RedirectResponse(url=signed, status_code=307, headers=_SAFE_HEADERS)

    headers = dict(_SAFE_HEADERS, **_disposition(row, inline), **_RANGE_HEADERS)
    # ETag：用 sha256 前 16 位，支持 304 协商缓存
    if row.sha256:
        headers["ETag"] = f'"{row.sha256[:16]}"'
    total = _object_size_for_key(store, row, effective_key)
    rng = _parse_range(request.headers.get("range"), total) if total else None
    if rng is False:
        # 语法正确但越界：按 RFC 9110 回 416，播放器据此停止重试
        raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable",
                            headers=dict(headers, **{"Content-Range": f"bytes */{total}"}))

    stream = store.open_stream(effective_key, *(rng or (None, None)))
    if stream is not None:
        if rng:
            headers["Content-Range"] = f"bytes {rng[0]}-{rng[1]}/{total}"
            headers["Content-Length"] = str(rng[1] - rng[0] + 1)
            return StreamingResponse(stream, media_type=media_type, headers=headers, status_code=206)
        return StreamingResponse(stream, media_type=media_type, headers=headers)
    # 变体对象不存在（历史数据）：回退到原图
    if variant and effective_key != row.storage_key:
        stream = store.open_stream(row.storage_key, *(rng or (None, None)))
        if stream is not None:
            if rng:
                headers["Content-Range"] = f"bytes {rng[0]}-{rng[1]}/{_object_size(store, row)}"
                headers["Content-Length"] = str(rng[1] - rng[0] + 1)
                return StreamingResponse(stream, media_type=row.content_type or "application/octet-stream",
                                        headers=headers, status_code=206)
            return StreamingResponse(stream, media_type=row.content_type or "application/octet-stream",
                                    headers=headers)
    path = store.path(effective_key)
    if path is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    if rng is None and request.headers.get("range"):
        # 语法非法的 Range 按 RFC 9110 忽略并回整份 200（对象存储流式路径就是这个行为）。
        # FileResponse 会自己再解析一遍并回 400，两个后端会给出不同答案，先从 scope 摘掉。
        _drop_range(request)
    # FileResponse 自带 Range/206 处理，无需在这里再算一遍区间
    return FileResponse(path, media_type=media_type, headers=headers)


def _drop_range(request: Request) -> None:
    """把 Range / If-Range 从 ASGI scope 里移除，让下游当无 Range 请求处理。"""
    request.scope["headers"] = [(k, v) for k, v in request.scope["headers"]
                                if k not in (b"range", b"if-range")]


# 播放器要先看到「支持分段」才会发起 Range 请求；预签名跳转那条路径由 MinIO 提供同头
_RANGE_HEADERS = {"Accept-Ranges": "bytes"}

_MAX_RANGE_SPAN = 16 * 1024 * 1024  # 单段最多回 16MB：挡住 bytes=0- 把整桶拉爆的用法


def _object_size(store, row: FileObject) -> int:
    """对象总长：优先库里的 size，缺失（历史行）再问存储后端。"""
    try:
        n = int(row.size or 0)
    except (TypeError, ValueError, AttributeError):
        n = 0
    return n or int(store.size(row.storage_key) or 0)


def _object_size_for_key(store, row: FileObject, storage_key: str) -> int:
    """指定 key 的对象总长；变体 key 库里没存 size，直接问存储后端。"""
    if storage_key == row.storage_key:
        return _object_size(store, row)
    try:
        return int(store.size(storage_key) or 0)
    except Exception:
        return 0


def _parse_range(header: str | None, total: int):
    """解析单段 Range。

    返回 (start, end) 闭区间；无 Range / 语法非法 → None（按整份回 200）；
    语法正确但起点越界 → False（上层回 416）。多段 Range 不支持，退化成整份回流。
    """
    if not header or not header.startswith("bytes="):
        return None
    spec = header[6:].split(",")[0].strip()
    if "-" not in spec:
        return None
    a, _, b = spec.partition("-")
    try:
        if not a:  # bytes=-N：取尾 N 字节
            n = int(b)
            if n <= 0:
                return None
            start, end = max(0, total - n), total - 1
        else:
            start = int(a)
            end = total - 1 if not b else min(int(b), total - 1)
    except ValueError:
        return None
    if start >= total or start < 0 or end < start:
        return False
    return start, min(end, start + _MAX_RANGE_SPAN - 1)


def _disposition(row: FileObject, inline: int) -> dict:
    name = (row.original_name or row.id or "file").replace('"', "")
    ascii_name = name.encode("ascii", "ignore").decode() or "file"
    # inline 之外一律 attachment：不让浏览器把响应当页面渲染
    kind = "inline" if inline else "attachment"
    return {"Content-Disposition": f"{kind}; filename=\"{ascii_name}\"; "
                                   f"filename*=UTF-8''{quote(name)}"}
