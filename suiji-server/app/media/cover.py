"""视频封面抽帧：后台任务把视频首帧附近一帧压成 400px JPEG。

与图片缩略图同一哲学：请求线程只落原图，封面交给后台线程池；抽帧失败静默跳过，
下载端点在 meta 无 cover_key 时回退原图 / 前端占位，不阻断上传主流程。

ffmpeg 来源优先级：环境变量 ``FFMPEG_BIN`` → imageio-ffmpeg 自带静态二进制
（包内 ``binaries/ffmpeg-*``）→ PATH 里的 ``ffmpeg``。均不可用时封面任务直接跳过。
静态包不带 ffprobe：视频时长沿用前端上报并写入 ``meta.duration``，这里不做容器解析。
"""
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# 单次抽帧硬超时：只解码首帧附近 GOP，正常百毫秒级；兜底防损坏视频挂住 worker
_TIMEOUT_SECONDS = 30

# imageio-ffmpeg 二进制按平台命名 ffmpeg-<platform>-<arch>-<ver>；优先匹配本平台，
# 避免同目录混入其他平台二进制时误选（跨平台可执行文件在本机无法运行）。
_PLATFORM_PREFIX = {
    "win32": "ffmpeg-win-",
    "darwin": "ffmpeg-darwin-",
}.get(sys.platform, "ffmpeg-linux-")

_bin: str | None = None
_bin_resolved = False


def find_ffmpeg() -> str | None:
    """定位可用的 ffmpeg 可执行文件；解析结果缓存，找不到返回 None。"""
    global _bin, _bin_resolved
    if _bin_resolved:
        return _bin
    _bin_resolved = True

    env = os.getenv("FFMPEG_BIN", "").strip()
    if env and Path(env).exists():
        _bin = env
        return _bin

    # imageio-ffmpeg 静态二进制：binaries/ 目录按平台命名 ffmpeg-<platform>-*
    try:
        import imageio_ffmpeg

        binaries_dir = Path(imageio_ffmpeg.__file__).parent / "binaries"
        if binaries_dir.is_dir():
            candidates = sorted(binaries_dir.glob(_PLATFORM_PREFIX + "*"))
            if not candidates:  # 平台前缀未命中时再宽松回退任意 ffmpeg-*
                candidates = sorted(binaries_dir.glob("ffmpeg-*"))
            for cand in candidates:
                if cand.is_file():
                    try:
                        os.chmod(cand, 0o755)
                    except OSError:
                        pass
                    _bin = str(cand)
                    return _bin
    except Exception:
        # imageio_ffmpeg 未安装 / 版本异常都不应阻断回退到 PATH 里的 ffmpeg
        pass

    _bin = shutil.which("ffmpeg")
    return _bin


def extract_cover(video: bytes, width: int = 400, quality: int = 5,
                  seek: float = 0.3) -> bytes | None:
    """从视频字节抽一帧压成 JPEG。成功返回 JPEG 字节；不可用 / 失败返回 None。

    先取 ``seek`` 偏移处一帧（避开片头黑帧），失败退回 0s 再试一次。
    """
    exe = find_ffmpeg()
    if not exe or not video:
        return None

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    try:
        tmp.write(video)
        tmp.close()
        for offset in (seek, 0.0):
            jpeg = _run_ffmpeg(exe, tmp.name, offset, width, quality)
            if jpeg:
                return jpeg
        return None
    except Exception as exc:  # noqa: BLE001 - 抽帧失败只降级，不影响上传
        logger.warning("视频封面抽帧失败：%s", exc)
        return None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _run_ffmpeg(exe: str, src: str, seek: float, width: int, quality: int) -> bytes | None:
    """调 ffmpeg 抽单帧并编码为 mjpeg 管道输出；无有效 JPEG 输出返回 None。"""
    cmd = [
        exe, "-hide_banner", "-loglevel", "error",
        "-ss", f"{seek:.2f}", "-i", src,
        "-frames:v", "1",
        "-vf", f"scale={width}:-2",
        "-q:v", str(quality),
        "-f", "image2pipe", "-vcodec", "mjpeg", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=_TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("ffmpeg 调用失败（seek=%s）：%s", seek, exc)
        return None

    if proc.returncode != 0 or not proc.stdout:
        logger.warning("ffmpeg 抽帧无输出（seek=%s，rc=%s）：%s",
                       seek, proc.returncode,
                       (proc.stderr or b"")[:200].decode("utf-8", "replace"))
        return None

    # 只认 JPEG 字节（FFD8FF 开头）：避免把错误页 / 空帧存成封面对象
    if not proc.stdout[:3] == b"\xff\xd8\xff":
        logger.warning("ffmpeg 输出非 JPEG（seek=%s，%d 字节）", seek, len(proc.stdout))
        return None
    return proc.stdout
