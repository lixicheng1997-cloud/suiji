"""上传内容的类型校验：扩展名白名单 + magic bytes 嗅探 + 内联渲染门控。

三件事分开做，缺一不可：

  1. **扩展名白名单**（而不是「后缀长得像个后缀就放行」）
     早先只校验后缀格式（`^\\.[0-9A-Za-z]{1,8}$`），于是 `.html` / `.svg` / `.js`
     都能上传；配合下载端点在 API 源站按文件名推断 Content-Type 且不带
     Content-Disposition，就变成了存储型 XSS——攻击者上传一个 .html，
     让家庭成员访问 `/media/{id}` 即在与 API 同源的上下文里执行脚本。

  2. **magic bytes 嗅探**
     扩展名和 Content-Type 都由客户端提供，可以随便填。只信字节本身：
     声明是 png 但字节是 HTML 的一律拒绝，避免「改名绕过白名单」。

  3. **内联渲染门控**
     只有嗅探确认是图片/视频/音频/PDF 的内容才允许 `inline`；
     其余一律 `attachment`，浏览器不会把它当页面渲染。
     同时固定 `Content-Type`，不回显客户端传来的值。
"""
from __future__ import annotations

# 允许上传的扩展名（小写，含点）。
# 刻意排除一切能被浏览器当文档渲染的类型：html/htm/svg/xml/xhtml/js/mhtml。
ALLOWED_EXT = {
    # 图片
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif", ".avif", ".tiff",
    # 音视频
    ".mp4", ".mov", ".m4v", ".webm", ".3gp", ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac",
    # 文档与归档（备份包 / 成长档案导出）
    ".pdf", ".txt", ".csv", ".json", ".zip",
}

# 嗅探结果 → 是否允许 inline 渲染 + 固定的响应 Content-Type
_KIND_META = {
    "jpeg": (True, "image/jpeg"),
    "png": (True, "image/png"),
    "gif": (True, "image/gif"),
    "webp": (True, "image/webp"),
    "bmp": (True, "image/bmp"),
    "tiff": (True, "image/tiff"),
    "avif": (True, "image/avif"),
    "heic": (False, "image/heic"),   # 浏览器普遍不支持内联，一律下载
    "mp4": (True, "video/mp4"),
    # ftyp brand 为 M4A/M4B/M4P 的纯音频容器：不能按 mp4 视频回，
    # 否则宝宝语音在客户端里被当成视频类型处理。
    "m4a": (True, "audio/mp4"),
    "webm": (True, "video/webm"),
    "ogv": (True, "video/ogg"),
    "mp3": (True, "audio/mpeg"),
    "wav": (True, "audio/wav"),
    "ogg": (True, "audio/ogg"),
    "flac": (True, "audio/flac"),
    "pdf": (True, "application/pdf"),  # PDF 内联由浏览器内置阅读器渲染，脚本能力受限
    "zip": (False, "application/zip"),
    "text": (False, "text/plain"),     # 纯文本也可能被当 HTML 嗅探，只做附件
    "other": (False, "application/octet-stream"),
}


def sniff(data: bytes) -> str:
    """按 magic bytes 判断真实类型，返回 _KIND_META 的键；无法识别返回 other。

    只看前 32 字节（够定位所有容器签名），避免为大文件做无谓拷贝。
    """
    if not data:
        return "other"
    head = data[:32]
    if head[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:2] == b"BM":
        return "bmp"
    if head[:4] == b"%PDF":
        return "pdf"
    if head[:2] == b"PK" and head[2:4] in (b"\x03\x04", b"\x05\x06", b"\x07\x08"):
        return "zip"
    if head[:3] == b"ID3" or (head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "mp3"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"OggS":
        return "ogg"
    if head[:4] == b"fLaC":
        return "flac"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1"):
            return "heic"
        if brand in (b"avif", b"avis"):
            return "avif"
        if brand in (b"qt  ",):
            return "mp4"  # QuickTime 容器，按 mp4 处理
        if brand in (b"M4A ", b"M4B ", b"M4P "):
            return "m4a"  # 纯音频容器（App 端录音落在这一支）
        return "mp4"      # 其余 ftyp（含 M4V / mp42 / isom）按视频容器处理
    if head[:4] == b"\x1aE\xdf\xa3":  # Matroska / WebM
        return "webm"
    # 文本类：只允许纯 ASCII/UTF-8 可打印字符（不含控制字符），
    # 用于放行 .txt/.csv/.json 备份，同时挡住伪装成文本的 HTML
    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError:
        return "other"
    stripped = text.strip()
    if stripped and all(ch.isprintable() or ch in "\r\n\t" for ch in stripped):
        return "text"
    return "other"


def normalize_ext(name: str) -> str:
    """取小写扩展名；没有或不在白名单里返回空串。"""
    if "." not in name:
        return ""
    ext = "." + name.rsplit(".", 1)[-1].lower()
    return ext if ext in ALLOWED_EXT else ""


def is_allowed_ext(ext: str) -> bool:
    return (ext or "").lower() in ALLOWED_EXT


# 嗅探结果 → 规范扩展名。只收录 magic bytes 能确认的媒体类型；
# text/other 不在表内——没有扩展名的文本可能就是 HTML/JS，未知字节一律不放行。
KIND_EXT = {
    "jpeg": ".jpg", "png": ".png", "gif": ".gif", "webp": ".webp",
    "bmp": ".bmp", "tiff": ".tiff", "avif": ".avif", "heic": ".heic",
    "mp4": ".mp4", "m4a": ".m4a", "webm": ".webm", "ogv": ".ogg",
    "mp3": ".mp3", "wav": ".wav", "ogg": ".ogg", "flac": ".flac", "pdf": ".pdf",
}


def ext_from_kind(kind: str) -> str:
    """按真实字节类型推导扩展名（返回空串表示无法安全推导）。

    用于移动端临时文件：H5 选图给 blob: URL、Android 相册给 content:// URI，
    multipart 文件名末段是 UUID/数字 id，根本没有扩展名。
    扩展名由嗅探结果而非客户端提供的文件名决定，不存在改名绕过的问题。
    """
    return KIND_EXT.get(kind, "")


def inline_policy(kind: str) -> tuple[bool, str]:
    """返回 (是否允许 inline 渲染, 固定使用的 Content-Type)。"""
    return _KIND_META.get(kind, (False, "application/octet-stream"))
