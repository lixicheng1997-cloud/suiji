"""把 synth/wav 的成品转成 Android 交付用的 Ogg Vorbis(需求表 §2.1)。

Android SoundPool 从 API 21 起支持 ogg/vorbis 解码，同等音质下体积约为 WAV 的 1/8，
29 条素材从 1.76MB 降到 222KB，进 APK 才划算。

优先用 libsndfile(python-soundfile) 在进程内编码，不依赖外部二进制；
装不上再退回 ffmpeg。两条路都没有就明确报错退出——不静默跳过，
避免交付里混进"以为转了其实没转"的空目录。
"""

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WAV = os.path.join(HERE, "wav")
OGG = os.path.join(HERE, "ogg")
QUALITY = "5"  # ffmpeg 回退路线用 libvorbis -q:a，约 160kbps 单声道


def via_soundfile(jobs):
    import soundfile as sf
    for src, dst in jobs:
        x, sr = sf.read(src, dtype="int16")
        sf.write(dst, x, sr, format="OGG", subtype="VORBIS")


def via_ffmpeg(jobs, ff):
    for src, dst in jobs:
        subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
                        "-c:a", "libvorbis", "-q:a", QUALITY, "-ac", "1",
                        "-ar", "44100", dst], check=True, capture_output=True)


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    for p in (r"C:\Program Files\ffmpeg\bin\ffmpeg.exe", r"C:\ffmpeg\bin\ffmpeg.exe",
              os.path.expanduser(r"~\scoop\shims\ffmpeg.exe")):
        if os.path.isfile(p):
            return p
    return None


def main():
    os.makedirs(OGG, exist_ok=True)
    man = json.load(open(os.path.join(HERE, "manifest.json"), encoding="utf-8"))
    jobs = [(os.path.join(WAV, it["file"]),
             os.path.join(OGG, os.path.splitext(it["file"])[0] + ".ogg"))
            for it in man["items"]]

    try:
        via_soundfile(jobs)
        backend = "libsndfile"
    except ImportError:
        ff = find_ffmpeg()
        if not ff:
            print("转码不可用：既没有 python-soundfile，也找不到 ffmpeg。", file=sys.stderr)
            print("  pip install soundfile          # 推荐，无需外部程序", file=sys.stderr)
            print("  winget install Gyan.FFmpeg     # 或装 ffmpeg", file=sys.stderr)
            return 1
        via_ffmpeg(jobs, ff)
        backend = "ffmpeg"

    done = [p for _, p in jobs if os.path.getsize(p) > 0]
    total = sum(os.path.getsize(p) for p in done)
    src_total = sum(os.path.getsize(s) for s, _ in jobs)
    print(f"[{backend}] 转码 {len(done)}/{len(jobs)} 条 -> {OGG}")
    print(f"体积 {src_total / 1024 / 1024:.2f}MB -> {total / 1024:.0f}KB "
          f"(压缩比 {src_total / max(total, 1):.1f}x)")
    return 0 if len(done) == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
