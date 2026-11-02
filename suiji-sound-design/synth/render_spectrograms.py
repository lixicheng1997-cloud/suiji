"""为每条音效渲染频谱瀑布图，供需求表 §A-06 高频占比与 §2.1 无削波的人工复核。"""

import json
import math
import os
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
WAV = os.path.join(HERE, "wav")
OUT = os.path.join(HERE, "..", "review")

CELL_W, SPEC_H, COLS, FMAX = 300, 150, 3, 8000.0
GAP = 210


def font(size, bold=False):
    for cand in (("msyh.ttc", "msyhbd.ttc")[1 if bold else 0], "simhei.ttf", "Deng.ttf"):
        try:
            return ImageFont.truetype(
                os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", cand), size)
        except OSError:
            continue
    return ImageFont.load_default()


def load(name):
    with wave.open(os.path.join(WAV, name), "rb") as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    return raw.astype(float) / 32768


def specgram(x, nper=1024, hop=96):
    """逐帧短时谱，纵轴 0-FMAX 自下而上。"""
    win = np.hanning(nper)
    fr = np.fft.rfftfreq(nper, 1 / SR)
    rows = []
    for s in range(0, max(1, len(x) - nper + 1), hop):
        seg = np.pad(x[s:s + nper], (0, max(0, nper - len(x) + s)))
        mag = np.abs(np.fft.rfft(seg * win))
        rows.append(20 * np.log10(np.interp(np.linspace(0, FMAX, SPEC_H), fr, mag) + 1e-7))
    m = np.array(rows)
    return (m - m.min()) / (m.max() - m.min() + 1e-9)


def centroid(x):
    n = min(len(x), 4096)
    seg = np.pad(x[:n] * np.hanning(n), (0, 4096 - n))
    mag = np.abs(np.fft.rfft(seg))
    fr = np.fft.rfftfreq(4096, 1 / SR)
    return float((fr * mag).sum() / (mag.sum() + 1e-12))


def main():
    os.makedirs(OUT, exist_ok=True)
    items = json.load(open(os.path.join(HERE, "manifest.json"), encoding="utf-8"))["items"]
    rows = math.ceil(len(items) / COLS)
    row_h = SPEC_H + GAP
    img = Image.new("RGB", (COLS * (CELL_W + 18) + 30, rows * row_h + 110), (246, 245, 242))
    d = ImageDraw.Draw(img)
    f14, f12, f11 = font(15, True), font(12), font(11)

    d.text((16, 10), "岁记音效 · 频谱复核图", fill=(35, 35, 42), font=f14)
    d.text((16, 34), "上：短时频谱 0–8kHz（越亮能量越强，橙线 = 3.5kHz 高频预算分界）"
                     "　中：波形包络　下：能量随时间分布", fill=(95, 95, 102), font=f12)

    for i, it in enumerate(items):
        cx = 18 + (i % COLS) * (CELL_W + 18)
        cy = 76 + (i // COLS) * row_h
        x = load(it["file"])
        s = specgram(x)
        im = Image.fromarray((np.clip(s, 0, 1) * 255).astype(np.uint8), "L").convert("RGB")
        img.paste(im.resize((CELL_W, SPEC_H)), (cx, cy))
        d = ImageDraw.Draw(img)
        d.line([(cx, cy + SPEC_H * (1 - 3500 / FMAX)),
                (cx + CELL_W, cy + SPEC_H * (1 - 3500 / FMAX))], fill=(228, 112, 66), width=2)
        over = it["hf_energy_pct_above_3k5"] > 8
        d.text((cx + 2, cy - 20),
               f"{it['id']}  {it['duration_ms']:.0f}ms  {it['rel_lufs_vs_s03']:+.1f}dB"
               f"  高频 {it['hf_energy_pct_above_3k5']:.2f}%",
               fill=(172, 42, 32) if over else (46, 94, 58), font=f12)
        d.text((cx + 2, cy + SPEC_H + 6), it["scene"], fill=(82, 82, 90), font=f11)

        wy = cy + SPEC_H + 26
        pk = max(np.max(np.abs(x)), 1e-6)
        for c in range(CELL_W):
            a0 = int(c / CELL_W * len(x))
            a1 = max(a0 + 1, int((c + 1) / CELL_W * len(x)))
            a = float(np.max(np.abs(x[a0:a1]))) / pk
            d.line([(cx + c, wy + 16 - a * 15), (cx + c, wy + 16 + a * 15)], fill=(56, 58, 68))

        eyc = wy + 40
        nb = 90
        env = np.array([math.sqrt(np.mean(x[int(k / nb * len(x)):max(int(k / nb * len(x)) + 1,
                                                                 int((k + 1) / nb * len(x)))] ** 2))
                        for k in range(nb)])
        env /= env.max() + 1e-9
        for k, v in enumerate(env):
            d.rectangle([cx + k / nb * CELL_W, eyc + 26 - v * 25,
                         cx + (k + 1) / nb * CELL_W, eyc + 26], fill=(122, 118, 132))
        d.text((cx + CELL_W - 58, eyc + 28), f"质心 {centroid(x) / 1000:.2f}kHz",
               fill=(120, 118, 128), font=f11)

    img.save(os.path.join(OUT, "spectrograms.png"))
    print("渲染 ->", os.path.abspath(os.path.join(OUT, "spectrograms.png")), img.size)


if __name__ == "__main__":
    main()
