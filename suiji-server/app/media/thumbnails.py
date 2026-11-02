"""图片缩略图变体生成 + HEIC 转码：上传时同步生成 thumb(宽400) / small(宽800) 两档 JPEG。

目的：列表页/相册只显示小图，不该下载 3-10MB 的原图。
  - thumb: 宽 400px，JPEG q=80，用于时光轴列表/搜索结果/头像
  - small: 宽 800px，JPEG q=82，用于详情页/大图预览
  - 原图保留不动，点开放大时才拉

HEIC 转码：iPhone 用户上传的 HEIC 在 Android/Web 上解码慢甚至无法显示，
上传时直接转 JPEG（质量 85），体积通常比 HEIC 大 20-30%，但兼容性好。
需要 pillow-heif 插件；未安装时跳过（HEIC 原样存储，仅生成 JPEG 缩略图）。

失败/非图片/Pillow 不可用一律静默跳过，不阻断上传主流程。
变体对象存到对象存储，key 规则：原 key = family/date/name.jpg
  thumb: family/date/name.thumb.jpg
  small: family/date/name.small.jpg
对应 key 写入 FileObject.meta: {"thumb_key": "...", "small_key": "..."}
"""
import io
import logging

logger = logging.getLogger(__name__)

THUMB_MAX_WIDTH = 400
SMALL_MAX_WIDTH = 800
JPEG_QUALITY_THUMB = 80
JPEG_QUALITY_SMALL = 82
JPEG_QUALITY_FROM_HEIC = 85

_pillow_ok: bool | None = None
_heif_ok: bool | None = None


def _has_pillow() -> bool:
    global _pillow_ok
    if _pillow_ok is None:
        try:
            from PIL import Image  # noqa: F401
            _pillow_ok = True
        except ImportError:
            logger.warning("Pillow 未安装，缩略图生成跳过")
            _pillow_ok = False
    return _pillow_ok


def _resize_to_jpeg(data: bytes, max_width: int, quality: int) -> bytes | None:
    """把图片字节缩到 max_width 宽（等比），输出 JPEG 字节。失败或原图已更小返回 None。"""
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        if getattr(im, "n_frames", 1) > 1:  # 动图：只取第一帧会丢动画，跳过
            return None
        try:
            im = ImageOps.exif_transpose(im)  # 手机照片方向修正
        except Exception:
            pass
        w, h = im.size
        if w <= max_width:
            return None  # 已经够小，不生成
        new_h = max(1, int(h * max_width / w))
        im = im.resize((max_width, new_h), Image.LANCZOS)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
        return buf.getvalue()
    except Exception as exc:
        logger.warning("缩略图生成失败（max_width=%d）：%s", max_width, exc)
        return None


def generate_variants(data: bytes, content_type: str) -> dict:
    """返回 {"thumb": bytes, "small": bytes}；不适用或失败返回 {}。"""
    if not content_type.startswith("image/"):
        return {}
    if content_type == "image/gif":  # 动图不压
        return {}
    if not _has_pillow():
        return {}
    thumb = _resize_to_jpeg(data, THUMB_MAX_WIDTH, JPEG_QUALITY_THUMB)
    small = _resize_to_jpeg(data, SMALL_MAX_WIDTH, JPEG_QUALITY_SMALL)
    out: dict = {}
    if thumb:
        out["thumb"] = thumb
    if small:
        out["small"] = small
    return out


def variant_storage_key(original_key: str, variant: str) -> str:
    """根据原 storage_key 派生变体 key：family/date/name.jpg → family/date/name.thumb.jpg

    无扩展名时直接追加 .thumb.jpg 后缀。
    """
    if variant not in ("thumb", "small"):
        return original_key
    name = original_key.rsplit("/", 1)[-1]
    if "." in name:
        head, _, _ = original_key.rpartition(".")
        return f"{head}.{variant}.jpg"
    return f"{original_key}.{variant}.jpg"


def _has_heif() -> bool:
    """pillow-heif 插件是否可用（能读 HEIC/HEIF）。"""
    global _heif_ok
    if _heif_ok is None:
        try:
            import pillow_heif  # noqa: F401
            pillow_heif.register_heif_opener()
            _heif_ok = True
        except ImportError:
            logger.info("pillow-heif 未安装，HEIC 图片将原样存储（不转 JPEG）")
            _heif_ok = False
    return _heif_ok


def transcode_heic_to_jpeg(data: bytes, content_type: str) -> tuple[bytes, str] | None:
    """HEIC/HEIF 转 JPEG。返回 (新 bytes, 'image/jpeg')；非 HEIC 或失败返回 None。

    iPhone 照片默认 HEIC，Android/Web 解码兼容性差；转 JPEG 后所有平台都能直接显示。
    转码保留原始分辨率，质量 85，体积通常比 HEIC 大 20-30%。
    """
    if content_type not in ("image/heic", "image/heif"):
        return None
    if not _has_pillow() or not _has_heif():
        return None
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        try:
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=JPEG_QUALITY_FROM_HEIC, optimize=True)
        out = buf.getvalue()
        logger.info("HEIC → JPEG 转码：%d → %d 字节", len(data), len(out))
        return out, "image/jpeg"
    except Exception as exc:
        logger.warning("HEIC 转 JPEG 失败：%s", exc)
        return None
