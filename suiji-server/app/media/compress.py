"""图片上传前的无损压缩：像素级不变地重压，字节更小才替换原图，再入对象存储。

策略（只认真正的「无损」，不做任何有损重编码）：
  - PNG / 静态 GIF：Pillow `optimize=True` 重压缩（只改编码，不动像素；
    动图重编码会丢帧，n_frames>1 一律跳过）。
  - JPEG：`jpegtran -copy all -optimize -progressive`（libjpeg-turbo 的
    哈夫曼表/熵编码优化 + 渐进式重排，真无损且保留 EXIF）。
    二进制不可用时跳过——Pillow 重存 JPEG 是有损的，不算。
  - 其余类型（webp/heic/avif 等）没有纯 Python 的无损重压手段，原样放行。

失败、无 Pillow、压缩后反而变大——一律返回原 spool / 原 sha / 原 size，
上传主流程不受影响。压缩后内容变了，调用方需用返回的新 sha 与 size
重走去重与台账（同家庭同原图压缩结果确定，去重依然成立）。
"""
import hashlib
import logging
import shutil
import subprocess
from io import BytesIO
from tempfile import SpooledTemporaryFile

logger = logging.getLogger(__name__)

_SPOOL_MAX = 8 * 1024 * 1024        # 与 file_service 一致：小图内存缓冲，大图落临时盘
_MAX_COMPRESS_BYTES = 64 * 1024 * 1024  # 超过 64MB 的图不重压，避免解压峰值内存
_JPEGTRAN_TIMEOUT = 30              # 秒；异常大图直接放弃压缩走原图

_pillow_ok: bool | None = None
_jpegtran_bin: str | None = None
_jpegtran_checked = False


def _has_pillow() -> bool:
    global _pillow_ok
    if _pillow_ok is None:
        try:
            import PIL  # noqa: F401
            _pillow_ok = True
        except ImportError:
            logger.warning("Pillow 未安装，图片无损压缩跳过")
            _pillow_ok = False
    return _pillow_ok


def _jpegtran() -> str | None:
    global _jpegtran_bin, _jpegtran_checked
    if not _jpegtran_checked:
        _jpegtran_bin = shutil.which("jpegtran")
        _jpegtran_checked = True
        if not _jpegtran_bin:
            logger.warning("jpegtran 不可用，JPEG 无损压缩跳过")
    return _jpegtran_bin


def _recompress(data: bytes, content_type: str) -> bytes | None:
    """按类型无损重压；返回更小的字节，无收益或失败返回 None。"""
    try:
        if content_type == "image/jpeg":
            return _jpegtran_lossless(data)
        if content_type in ("image/png", "image/gif"):
            return _pillow_lossless(data, content_type)
    except Exception as exc:  # 压缩失败绝不阻断上传
        logger.warning("图片无损压缩失败（%s）：%s", content_type, exc)
    return None


def _pillow_lossless(data: bytes, content_type: str) -> bytes | None:
    if not _has_pillow():
        return None
    from PIL import Image

    fmt = "PNG" if content_type == "image/png" else "GIF"
    im = Image.open(BytesIO(data))
    if getattr(im, "n_frames", 1) > 1:  # 动图：单帧重存会丢动画
        return None
    buf = BytesIO()
    im.save(buf, fmt, optimize=True)
    out = buf.getvalue()
    return out if 0 < len(out) < len(data) else None


def _jpegtran_lossless(data: bytes) -> bytes | None:
    binary = _jpegtran()
    if not binary:
        return None
    proc = subprocess.run(
        [binary, "-copy", "all", "-optimize", "-progressive"],
        input=data, capture_output=True, timeout=_JPEGTRAN_TIMEOUT)
    if proc.returncode != 0 or not proc.stdout:
        logger.warning("jpegtran 退出码 %s：%s", proc.returncode,
                       proc.stderr[:200].decode("utf-8", "replace"))
        return None
    out = proc.stdout
    return out if len(out) < len(data) else None


def compress_image(spool, content_type: str, sha: str, size: int):
    """图片字节无损重压：返回 (spool, sha, size)，未压缩时原样返回入参。

    压缩成功时旧 spool 已关闭、游标已归零，调用方按新 sha/size 继续
    去重与落存储即可（finally 里 close 新 spool 的语义不变）。
    """
    if content_type not in ("image/png", "image/gif", "image/jpeg"):
        return spool, sha, size
    if size > _MAX_COMPRESS_BYTES:
        return spool, sha, size
    if content_type == "image/jpeg" and not _jpegtran():
        return spool, sha, size
    if content_type != "image/jpeg" and not _has_pillow():
        return spool, sha, size

    spool.seek(0)
    data = spool.read()
    out = _recompress(data, content_type)
    if not out:
        spool.seek(0)
        return spool, sha, size

    new_spool = SpooledTemporaryFile(max_size=_SPOOL_MAX)
    new_spool.write(out)
    new_spool.seek(0)
    spool.close()
    logger.info("图片无损压缩 %s：%d → %d 字节", content_type, size, len(out))
    return new_spool, hashlib.sha256(out).hexdigest(), len(out)
