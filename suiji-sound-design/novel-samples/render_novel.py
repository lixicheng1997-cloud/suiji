"""新颖范式示例合成器 —— 跳出"敲一个乐音"的框架，按声音材质/动态分 6 类。

每类出 2 条：tap(点击代表) / win(成就代表)。示例级响度：win 比 tap 略响，
峰值软压 ≤ -0.5 dBFS；未定全量阶梯，仅记录时长 / 峰值 / LUFS 供试听比较。

范式清单：
  soft_pop 软胶泡泡  —— 材质瞬态：按压软胶 + 泡泡纸捏破，弱音高
  paper    纸沙翻动  —— 颗粒噪声：纸张摩擦细沙，柔和沙沙
  glass    玻璃冰晶  —— 高频脆裂泛音，清亮尾韵
  chip     8-bit 芯片 —— 方波复古电子，短促数字感
  water    水波氛围  —— 水滴 + 水纹环境铺底，治愈安静
  sweep    滤波扫频  —— 频段扫过的动态"嗖"，转场/开合
"""

import json
import math
import os
import wave

import numpy as np

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "wav")

_LETTERS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def freq(name):
    letter, rest = name[0].upper(), name[1:]
    acc = 0
    while rest and rest[0] in "#b":
        acc += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    midi = 12 * (int(rest) + 1) + _LETTERS[letter] + acc
    return 440.0 * 2 ** ((midi - 69) / 12)


def t_axis(dur):
    return np.arange(int(round(dur * SR))) / SR


def env_exp(t, tc):
    return np.exp(-t / max(tc, 1e-6))


def env_ad(t, a, d):
    e = np.clip(t / max(a, 1e-6), 0, 1)
    return np.where(t < a, e, 1.0) * env_exp(np.maximum(t - a, 0), d)


def _poly(c, zi):
    return c[0] + c[1] * zi + c[2] * zi ** 2


def _sos(b, a, x):
    n = len(x)
    if n == 0:
        return x
    b = np.asarray(b, float) / a[0]
    a = np.asarray(a, float) / a[0]
    zi = np.exp(-1j * 2 * np.pi * np.fft.rfftfreq(2 * n))
    h = _poly(b, zi) / _poly(a, zi)
    h[~np.isfinite(h)] = 0.0
    return np.fft.irfft(np.fft.rfft(x, 2 * n) * h, 2 * n)[:n]


def bi_lowpass(x, f0, q=0.7071):
    w0 = 2 * math.pi * min(f0, SR / 2 - 10) / SR
    cw, sw = math.cos(w0), math.sin(w0)
    al = sw / (2 * q)
    return _sos([(1 - cw) / 2, 1 - cw, (1 - cw) / 2], [1 + al, -2 * cw, 1 - al], x)


def bi_highpass(x, f0, q=0.7071):
    w0 = 2 * math.pi * min(f0, SR / 2 - 10) / SR
    cw, sw = math.cos(w0), math.sin(w0)
    al = sw / (2 * q)
    return _sos([(1 + cw) / 2, -(1 + cw), (1 + cw) / 2], [1 + al, -2 * cw, 1 - al], x)


def _bandpass(x, lo, hi):
    return bi_lowpass(x, hi) - bi_lowpass(x, lo)


def noise(seed, n):
    return np.random.RandomState(seed).uniform(-1, 1, n)


def reverb(x, mix=0.22, tail=1.2):
    n = len(x) + int(tail * SR)
    out = np.zeros(n)
    out[: len(x)] = x * (1 - mix)
    for d_ms, fb in ((37, 0.45), (53, 0.40), (79, 0.36), (113, 0.32)):
        d = int(d_ms / 1000 * SR)
        for i in range(d, n):
            out[i] += fb * out[i - d]
    return bi_lowpass(out, 2400)


# ---------------------------------------------------------------- 音色件

def _glide(f0, f1, dur, vel, det=1.0):
    t = t_axis(dur)
    f = f0 + (f1 - f0) * np.clip(t / max(dur * 0.3, 1e-6), 0, 1)
    phase = 2 * np.pi * np.cumsum(f) / SR
    return vel * np.sin(phase * det)


def pop(seed, base=170.0, dur=0.14, vel=1.0):
    """软胶按压：低频闷压正弦 + 低通噪声"噗"，起奏偏圆。"""
    t = t_axis(dur)
    y = np.sin(2 * np.pi * base * t) * env_exp(t, 0.05)
    n = noise(seed, len(t))
    y += 0.6 * bi_lowpass(n, 650) * env_ad(t, 0.006, 0.045)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def rustle(seed, dur=0.16, vel=1.0, lo=1500, hi=5200):
    """纸沙：中高频细沙噪声，包络轻起伏。"""
    t = t_axis(dur)
    n = noise(seed, len(t))
    y = _bandpass(n, lo, hi)
    mod = 0.65 + 0.35 * np.sin(2 * np.pi * 9 * t + seed)
    y *= mod * env_ad(t, 0.012, dur * 0.55)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def ice(f0, dur, vel=1.0, seed=0):
    """玻璃冰晶：3/5/7 次高频泛音列，快衰减、轻失谐。"""
    t = t_axis(dur)
    y = np.zeros_like(t)
    for ratio, amp in ((3.0, 0.55), (5.0, 0.28), (7.0, 0.12)):
        y += amp * np.sin(2 * np.pi * f0 * ratio * t) * env_exp(t, 0.10 / ratio)
    y += 0.20 * np.sin(2 * np.pi * f0 * t) * env_exp(t, 0.16)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def square(f0, dur, vel=1.0, det=1.0):
    """8-bit 方波短促音。"""
    t = t_axis(dur)
    phase = 2 * np.pi * np.cumsum(f0 * det) / SR
    return vel * np.sign(np.sin(phase)) * env_ad(t, 0.003, dur * 0.5)


def triangle(f0, dur, vel=1.0):
    t = t_axis(dur)
    phase = 2 * np.pi * f0 * t
    return vel * (2 / math.pi) * np.arcsin(np.sin(phase)) * env_exp(t, dur * 0.5)


def ripple(f0, dur, vel=1.0, seed=0):
    """水滴 + 水纹泛音：下扫起滴，二次泛音慢衰减。"""
    t = t_axis(dur)
    y = _glide(f0 * 1.7, f0, dur, 1.0)
    y += 0.30 * np.sin(2 * np.pi * f0 * 2 * t) * env_exp(t, dur * 0.6)
    n = noise(seed, len(t))
    y += 0.12 * _bandpass(n, 1800, 3600) * env_ad(t, 0.0006, 0.006)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def sweep(seed, dur=0.16, f_lo=900.0, f_hi=3200.0, vel=1.0):
    """扫频：正弦上滑 + 带通噪声跟频，频段由低到高"嗖"过去。"""
    t = t_axis(dur)
    y = _glide(f_lo, f_hi, dur, 0.8)
    n = noise(seed, len(t))
    bp = _bandpass(n, f_lo, f_hi)
    y += 0.5 * bp * env_ad(t, 0.01, dur * 0.6)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


# ---------------------------------------------------------------- 编排

def add_at(buf, start_s, seg):
    i = int(start_s * SR)
    n = min(len(seg), len(buf) - i)
    if n > 0:
        buf[i:i + n] += seg[:n]
    return buf


def gel(length):
    return np.zeros(int(length * SR))


def build_soft_pop():
    tap = pop(201, 170, 0.13, vel=0.9)
    win = gel(0.62)
    for i in range(5):
        add_at(win, i * 0.075, pop(210 + i, 160 + i * 14, 0.13,
                                   vel=0.85 - i * 0.12))
    return tap, win


def build_paper():
    tap = rustle(221, 0.15, vel=0.9)
    win = gel(0.55)
    add_at(win, 0.0, rustle(222, 0.20, vel=0.8))
    add_at(win, 0.24, rustle(223, 0.18, vel=0.6, lo=2200, hi=6000))
    n = noise(224, int(0.03 * SR))
    snap = _bandpass(n, 3000, 6500) * env_exp(np.arange(len(n)) / SR, 0.012)
    add_at(win, 0.40, 0.5 * snap)
    return tap, win


def build_glass():
    tap = ice(freq("D5"), 0.20, vel=0.9, seed=231)
    win = gel(0.72)
    for i, n in enumerate(("E5", "G#5", "B5", "E6")):
        add_at(win, i * 0.09, ice(freq(n), 0.45 - i * 0.05,
                                  vel=0.7 + i * 0.08, seed=232 + i))
    return tap, win


def build_chip():
    tap = square(freq("B4"), 0.12, vel=0.9)
    win = gel(0.60)
    for i, n in enumerate(("C5", "E5", "G5")):
        add_at(win, i * 0.09, square(freq(n), 0.16, vel=0.85))
    add_at(win, 0.0, triangle(freq("C4"), 0.5, vel=0.30))
    return tap, win


def build_water():
    tap = ripple(freq("D5"), 0.18, vel=0.9, seed=251)
    win = gel(0.95)
    for i, n in enumerate(("D5", "A4", "B4", "D5")):
        add_at(win, i * 0.13, ripple(freq(n), 0.4, vel=0.7 - i * 0.06, seed=252 + i))
    win = reverb(win, mix=0.20, tail=0.5)
    return tap, win


def build_sweep():
    tap = sweep(261, 0.13, vel=0.9)
    win = gel(0.55)
    add_at(win, 0.0, sweep(262, 0.22, 800, 3400, vel=0.85))
    add_at(win, 0.20, sweep(263, 0.18, 2600, 1100, vel=0.7))
    add_at(win, 0.36, square(freq("G4"), 0.16, vel=0.5))
    return tap, win


DIRECTIONS = [
    ("soft_pop", "软胶泡泡拟物", "按压软胶 + 泡泡纸捏破的材质瞬态，几乎无明确音高",
     "高频点击、想要俏皮手感的产品", "低频偏闷，夜间需压低音量"),
    ("paper", "纸沙翻动", "纸张摩擦的细沙颗粒噪声，柔和沙沙",
     "记录 / 备忘录质感、轻量反馈", "音高感弱，成就情绪撑不起来"),
    ("glass", "玻璃冰晶", "高频脆裂泛音 + 清亮尾韵，通透闪亮",
     "收藏点亮、成就高光时刻", "高频偏多，夜间和低端机要收着用"),
    ("chip", "8-bit 芯片音", "方波复古电子音，短促数字跳变感",
     "儿童向、轻快俏皮、带游戏感", "风格化强，需权衡是否贴合温馨育儿调性"),
    ("water", "水波氛围", "水滴 + 水纹环境铺底，治愈安静",
     "纪念场景、安静陪伴感", "点击音偏轻，辨识度一般"),
    ("sweep", "滤波扫频", "频段扫过的动态“嗖”，靠滤波而非音高表意",
     "面板开合、步进、转场反馈", "单独做确认音不够落定，需配落定音"),
]

BUILDERS = {
    "soft_pop": build_soft_pop, "paper": build_paper, "glass": build_glass,
    "chip": build_chip, "water": build_water, "sweep": build_sweep,
}

CEIL = 10 ** (-0.5 / 20)
SAT_THR = 0.80


def soft_clip(x):
    ax = np.abs(x)
    excess = np.maximum(ax - SAT_THR, 0.0)
    compressed = SAT_THR + excess / (1.0 + excess / (1.0 - SAT_THR))
    out = np.where(ax > SAT_THR, compressed, ax)
    return np.sign(x) * out


def krms(x):
    return math.sqrt(float(np.mean(x ** 2)) + 1e-18)


def lufs(x):
    return -0.691 + 20 * math.log10(krms(x) + 1e-12)


def quantize(x):
    rs = np.random.RandomState(len(x))
    d = (rs.uniform(-1, 1, len(x)) + rs.uniform(-1, 1, len(x))) / 2
    return np.clip(np.round(x * 32768 + d), -32768, 32767).astype(np.int16)


def write_wav(name, x):
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(x.tobytes())


def main():
    os.makedirs(OUT, exist_ok=True)
    np.random.seed(20261112)
    items = []

    target_rms = 0.14  # tap 统一 K 前 RMS 基准，win 上浮 1.5 dB
    for key, name, desc, fit, caution in DIRECTIONS:
        tap, win = BUILDERS[key]()
        for role, seg, rel in (("tap", tap, 0.0), ("win", win, 1.5)):
            # 按同一把 RMS 尺子对齐响度，避免方波/噪声峰均比不同导致音量不可比
            y = seg / (krms(seg) + 1e-12) * target_rms * 10 ** (rel / 20)
            y = soft_clip(y)
            yq = quantize(y)
            xf = yq.astype(float) / 32768
            fname = f"novel_{key}_{role}.wav"
            write_wav(fname, yq)
            items.append({
                "dir": key, "role": role, "file": fname,
                "title": name, "desc": desc, "fit": fit, "caution": caution,
                "role_label": "点击代表" if role == "tap" else "成就代表",
                "duration_ms": round(len(xf) / SR * 1000, 1),
                "peak_dbfs": round(20 * math.log10(np.max(np.abs(xf)) + 1e-12), 1),
                "lufs": round(lufs(xf), 1),
            })

    with open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({"directions": [{"key": k, "name": n, "desc": d, "fit": f, "caution": c}
                                  for k, n, d, f, c in DIRECTIONS],
                   "items": items}, fh, ensure_ascii=False, indent=2)

    for it in items:
        print(f"{it['dir']:<10} {it['role']:<4} {it['duration_ms']:>7.1f}ms "
              f"{it['peak_dbfs']:>7.1f}dB {it['lufs']:>6.1f} LUFS  {it['file']}")
    print(f"\n生成 {len(items)} 条 -> {OUT}")


if __name__ == "__main__":
    main()
