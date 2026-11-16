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

字节以文件形态进出，不再 `spool.read()` 整份进内存：一次请求要同时握住原图和
结果两份，48MP 照片就是 60MB 量级，9 张并发足以顶满 api 容器。
"""
import hashlib
import logging
import shutil
import subprocess
import tempfile
from tempfile import SpooledTemporaryFile

from ..core.config import settings

logger = logging.getLogger(__name__)

_SPOOL_MAX = 8 * 1024 * 1024        # 与 file_service 一致：小图内存缓冲，大图落临时盘
_JPEGTRAN_TIMEOUT = 30              # 秒；异常大图直接放弃压缩走原图
_CHUNK = 1024 * 1024

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


def _has_fd(spool) -> bool:
    """spool 是否已滚动到临时盘（有真实 fd 才能直接当子进程 stdin）。

    SpooledTemporaryFile 在内存态是 BytesIO，fileno() 抛 UnsupportedOperation。
    """
    try:
        spool.seek(0)
        spool.fileno()
        return True
    except Exception:
        return False


def _digest(spool) -> tuple[str, int]:
    """流式算 sha256 与字节数，结束后游标归零。"""
    d = hashlib.sha256()
    total = 0
    spool.seek(0)
    while True:
        chunk = spool.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        d.update(chunk)
    spool.seek(0)
    return d.hexdigest(), total


def _jpegtran_lossless(spool, size: int):
    """原图喂 stdin、结果落临时文件；无收益或失败返回 None（不抛，交给上层用原图）。

    只有 spool 已经落到临时盘（>8MB，有真实 fd）才能流式；子进程的 stdout
    也必须是一个真实文件描述符，SpooledTemporaryFile 的内存态没有 fd，fileno() 直接抛。
    """
    binary = _jpegtran()
    if not binary:
        return None
    args = [binary, "-copy", "all", "-optimize", "-progressive"]
    timeout = _JPEGTRAN_TIMEOUT
    if _has_fd(spool):
        out = tempfile.TemporaryFile()
        keep = False
        try:
            proc = subprocess.run(args, stdin=spool, stdout=out,
                                  stderr=subprocess.PIPE, timeout=timeout)
            if proc.returncode != 0 or out.tell() == 0:
                logger.warning("jpegtran 退出码 %s：%s", proc.returncode,
                               (proc.stderr or b"")[:200].decode("utf-8", "replace"))
                return None
            out.seek(0)
            sha, new_size = _digest(out)
            if new_size >= size:  # 压不动了：保留原图，别做无用功
                return None
            out.seek(0)
            keep = True
            return out, sha, new_size
        except Exception as exc:  # 压缩失败绝不阻断上传
            logger.warning("jpegtran 无损压缩失败：%s", exc)
            return None
        finally:
            if not keep:
                out.close()
    # 内存态小文件（≤8MB）：没有 fd 可交给子进程，退化成一次性管道
    try:
        spool.seek(0)
        proc = subprocess.run(args, input=spool.read(), capture_output=True, timeout=timeout)
        if proc.returncode != 0 or not proc.stdout:
            logger.warning("jpegtran 退出码 %s：%s", proc.returncode,
                           (proc.stderr or b"")[:200].decode("utf-8", "replace"))
            return None
        out = SpooledTemporaryFile(max_size=_SPOOL_MAX)
        out.write(proc.stdout)
        sha, new_size = _digest(out)
        if new_size >= size:
            out.close()
            return None
        return out, sha, new_size
    except Exception as exc:
        logger.warning("jpegtran 无损压缩失败：%s", exc)
        return None


def _pillow_lossless(spool, content_type: str, size: int):
    if not _has_pillow():
        return None
    from PIL import Image

    fmt = "PNG" if content_type == "image/png" else "GIF"
    out = None
    try:
        spool.seek(0)
        im = Image.open(spool)  # Pillow 收文件对象，不必先整份 read 成 bytes
        if getattr(im, "n_frames", 1) > 1:  # 动图：单帧重存会丢动画
            return None
        out = SpooledTemporaryFile(max_size=_SPOOL_MAX)
        im.save(out, fmt, optimize=True)
        sha, new_size = _digest(out)
        if new_size == 0 or new_size >= size:
            out.close()
            return None
        return out, sha, new_size
    except Exception as exc:  # 压缩失败绝不阻断上传
        if out is not None:
            try:
                out.close()
            except Exception:
                pass
        logger.warning("图片无损压缩失败（%s）：%s", content_type, exc)
        return None


def _within_budget(spool) -> bool:
    """重压的成本按像素走（实测 12MP 0.28s、48MP 1.2s），所以闸口用像素数而不是字节数：
    一张 48MP 的 JPEG 才 12MB，按字节根本拦不住。尺寸只读文件头、不解码，代价可忽略。

    读不出来（没装 Pillow、文件异常）一律放行：那种图本来就走不了 Pillow 分支，
    交给下面的分支各自兜底，不该由闸口把压缩能力再砍一刀。
    """
    if not _has_pillow():
        return True
    from PIL import Image

    try:
        spool.seek(0)
        with Image.open(spool) as im:
            w, h = im.size
        return w * h <= settings.compress_max_pixels
    except Exception as exc:
        logger.warning("读图尺寸失败，重压闸口放行：%s", exc)
        return True
    finally:
        spool.seek(0)


def compress_image(spool, content_type: str, sha: str, size: int):
    """图片字节无损重压：返回 (spool, sha, size)，未压缩时原样返回入参。

    压缩成功时旧 spool 已关闭、游标已归零，调用方按新 sha/size 继续
    去重与落存储即可（finally 里 close 新 spool 的语义不变）。
    """
    if content_type not in ("image/png", "image/gif", "image/jpeg"):
        return spool, sha, size
    # 超过 COMPRESS_MAX_PIXELS（默认 2000 万）的原图直接入库：多留约 10% 字节，
    # 换掉请求线程里秒级的排队——一次保存九张时这几秒是累加的。
    if not _within_budget(spool):
        return spool, sha, size
    if content_type == "image/jpeg":
        res = _jpegtran_lossless(spool, size)
    else:
        res = _pillow_lossless(spool, content_type, size)
    if not res:
        spool.seek(0)
        return spool, sha, size
    new_spool, new_sha, new_size = res
    spool.close()
    logger.info("图片无损压缩 %s：%d → %d 字节", content_type, size, new_size)
    return new_spool, new_sha, new_size
