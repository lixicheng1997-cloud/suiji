"""风格选型示例合成器 —— 为里程碑/点击音风格对比出样。

每种风格出 3 个角色：
  tap  主按钮点击（代表高频交互）
  save 保存成功（两音上行，主基准 0 dB）
  win  里程碑成就（琶音/落定，最响一档）

示例之间统一响度基准（save=0 dB，tap=-1.5，win=+1.5），便于横向试听比较；
峰值 ≤ -0.5 dBFS，分段软压阈值以下透明，不破坏相对阶梯。
当前线上的卡林巴木质风作为对照，直接引用 ../synth-v11 的成品，不重复合成。
"""

import json
import math
import os
import wave

import numpy as np

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "wav")

# ---------------------------------------------------------------- DSP 基础

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


def _sos_df2(b, a):
    b = np.asarray(b, float) / a[0]
    a = np.asarray(a, float) / a[0]
    return np.array([b[0], b[1], b[2], a[0], a[1], a[2]])


def _sosfilt(sos, x):
    n = len(x)
    if n == 0:
        return x
    b, a = sos[0:3], sos[3:6]
    zi = np.exp(-1j * 2 * np.pi * np.fft.rfftfreq(2 * n))
    h = (b[0] + b[1] * zi + b[2] * zi ** 2) / (a[0] + a[1] * zi + a[2] * zi ** 2)
    h[~np.isfinite(h)] = 0.0
    return np.fft.irfft(np.fft.rfft(x, 2 * n) * h, 2 * n)[:n]


def bi_lowpass(x, f0, q=0.7071):
    w0 = 2 * math.pi * min(f0, SR / 2 - 10) / SR
    cw, sw = math.cos(w0), math.sin(w0)
    al = sw / (2 * q)
    return _sosfilt(_sos_df2([(1 - cw) / 2, 1 - cw, (1 - cw) / 2],
                             [1 + al, -2 * cw, 1 - al]), x)


def bi_highpass(x, f0, q=0.7071):
    w0 = 2 * math.pi * min(f0, SR / 2 - 10) / SR
    cw, sw = math.cos(w0), math.sin(w0)
    al = sw / (2 * q)
    return _sosfilt(_sos_df2([(1 + cw) / 2, -(1 + cw), (1 + cw) / 2],
                             [1 + al, -2 * cw, 1 - al]), x)


def high_shelf(x, f0, gain_db, slope=1.0):
    A = 10 ** (gain_db / 40)
    w0 = 2 * math.pi * min(f0, SR / 2 - 10) / SR
    cw, sw = math.cos(w0), math.sin(w0)
    al = sw / 2 * math.sqrt((A + 1 / A) * (1 / slope - 1) + 2)
    r = 2 * math.sqrt(A) * al
    b = [A * ((A + 1) + (A - 1) * cw + r),
         -2 * A * ((A - 1) + (A + 1) * cw),
         A * ((A + 1) + (A - 1) * cw - r)]
    a = [(A + 1) - (A - 1) * cw + r, 2 * ((A - 1) - (A + 1) * cw),
         (A + 1) - (A - 1) * cw - r]
    return _sosfilt(_sos_df2(b, a), x)


def k_weight(x):
    return high_shelf(x, 1500, 4.0)


def krms(x):
    w = k_weight(x)
    return math.sqrt(float(np.mean(w ** 2)) + 1e-18)


def gel(length):
    return np.zeros(int(length * SR))


def add_at(buf, start_s, seg):
    i = int(start_s * SR)
    n = min(len(seg), len(buf) - i)
    if n > 0:
        buf[i:i + n] += seg[:n]
    return buf


def _bandpass(x, lo, hi):
    return bi_lowpass(x, hi) - bi_lowpass(x, lo)


# ---------------------------------------------------------------- 音色

def _glide(f0, f1, dur, vel, det=1.0):
    """频率在前段从 f0 滑到 f1，相位积分防爆音。"""
    t = t_axis(dur)
    f = f0 + (f1 - f0) * np.clip(t / max(dur * 0.3, 1e-6), 0, 1)
    phase = 2 * np.pi * np.cumsum(f) / SR
    return vel * np.sin(phase * det)


def bubble(f0, dur, vel=1.0, decay=0.12, seed=1):
    """软合成气泡：圆润正弦 + 二次泛音，音头轻上滑。"""
    t = t_axis(dur)
    y = _glide(f0, f0 * 1.04, dur, 1.0)
    y += 0.28 * np.sin(2 * 2 * np.pi * f0 * 1.004 * t) * env_exp(t, decay)
    y += 0.10 * np.sin(2 * np.pi * f0 * 0.5 * t) * env_exp(t, 0.05)
    y *= env_ad(t, 0.004, decay)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def marimba(f0, dur, vel=1.0, seed=2):
    """木琴：强二/四次泛音，快衰减，音高感明亮。"""
    t = t_axis(dur)
    y = np.sin(2 * np.pi * f0 * t) * env_exp(t, 0.13)
    y += 0.40 * np.sin(2 * np.pi * f0 * 2.0 * t) * env_exp(t, 0.06)
    y += 0.12 * np.sin(2 * np.pi * f0 * 4.0 * t) * env_exp(t, 0.025)
    n = np.random.RandomState(seed).uniform(-1, 1, len(t))
    y += 0.22 * _bandpass(n, 1500, 3200) * env_ad(t, 0.0006, 0.008)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def piano(f0, dur, vel=1.0, seed=3):
    """柔钢琴：递减泛音列 + 击弦短噪，低通收亮。"""
    t = t_axis(dur)
    parts = [(1.0, 1.0), (2.0, 0.5), (3.0, 0.25), (4.0, 0.12)]
    y = np.zeros_like(t)
    for ratio, amp in parts:
        y += amp * np.sin(2 * np.pi * f0 * ratio * t) * env_exp(t, 0.30 / ratio)
    n = np.random.RandomState(seed).uniform(-1, 1, len(t))
    y += 0.12 * _bandpass(n, 900, 2600) * env_ad(t, 0.001, 0.01)
    y = bi_lowpass(y, 3000)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def musicbox(f0, dur, vel=1.0, seed=4):
    """八音盒：高频泛音 + 轻颤音 + 细长尾韵，金属细密感。"""
    t = t_axis(dur)
    vib = 1.0 + 0.004 * np.sin(2 * np.pi * 5.5 * t)
    y = np.sin(2 * np.pi * f0 * vib * t) * env_exp(t, 0.26)
    y += 0.18 * np.sin(2 * np.pi * f0 * 3.0 * vib * t) * env_exp(t, 0.12)
    y += 0.08 * np.sin(2 * np.pi * f0 * 5.0 * t) * env_exp(t, 0.05)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def drop(f0, dur, vel=1.0, seed=5):
    """水滴：频率下扫 + 快衰减，短促气泡感。"""
    t = t_axis(dur)
    y = _glide(f0 * 1.7, f0, dur, 1.0)
    n = np.random.RandomState(seed).uniform(-1, 1, len(t))
    y += 0.18 * _bandpass(n, 1800, 3600) * env_ad(t, 0.0006, 0.006)
    y *= env_exp(t, 0.085)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def woodblock(f0, dur, vel=1.0, seed=6):
    """木质打击：低频短击 + 中带噪声，弱音高、克制中性。"""
    t = t_axis(dur)
    y = np.sin(2 * np.pi * f0 * 0.5 * t) * env_exp(t, 0.05)
    n = np.random.RandomState(seed).uniform(-1, 1, len(t))
    y += 0.7 * _bandpass(n, 500, 1800) * env_ad(t, 0.0005, 0.006)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


SYNTHS = {
    "bubble": bubble, "marimba": marimba, "piano": piano,
    "musicbox": musicbox, "drop": drop, "wood": woodblock,
}

# 各风格 save / win 的音符编排
SAVE_NOTES = {
    "bubble": ("G4", "B4"), "marimba": ("G4", "B4"), "piano": ("A4", "C#5"),
    "musicbox": ("A4", "C#5"), "drop": ("G4", "B4"), "wood": ("A3", "E4"),
}
WIN_NOTES = {
    "bubble": ("C5", "E5", "G5", "C6"),
    "marimba": ("G4", "A4", "B4", "D5", "E5"),
    "piano": ("E5", "G5", "B5", "E6"),
    "musicbox": ("E5", "G#5", "B5", "E6"),
    "drop": ("D5", "G5", "B5", "D6"),
    "wood": ("A3", "C4", "E4", "A4"),
}
TAP_NOTE = {
    "bubble": "D5", "marimba": "D5", "piano": "E4", "musicbox": "B5",
    "drop": "D5", "wood": "A3",
}

STYLES = [
    {"key": "bubble", "name": "软合成气泡风",
     "desc": "现代轻快、圆润 Q 弹，像主流系统 App 的提示音，干净中性。",
     "fit": "高频点击、年轻轻快的产品气质", "caution": "电子感偏强，温暖和怀旧感弱"},
    {"key": "marimba", "name": "木琴钟琴风",
     "desc": "明亮清脆的敲击旋律，音高明确，带童趣和阳光感。",
     "fit": "育儿 / 儿童向场景，辨识度高", "caution": "高频偏多，夜间或低端机需压低音量"},
    {"key": "piano", "name": "柔钢琴风",
     "desc": "柔和钢琴单双音，温暖经典、治愈百搭，最不容易出错。",
     "fit": "全场景通用，情绪稳妥", "caution": "辨识度一般，偏常规、少记忆点"},
    {"key": "musicbox", "name": "八音盒风",
     "desc": "细密金属齿轮音，带轻颤音和长尾韵，精致梦幻、纪念感强。",
     "fit": "里程碑、纪念卡等成就音", "caution": "做点击音会偏飘、偏长"},
    {"key": "drop", "name": "水滴气泡风",
     "desc": "短促水滴/气泡声，轻快可爱，几乎不占注意力。",
     "fit": "轻量点击、频繁交互", "caution": "成就音情绪偏轻，撑不起庆祝感"},
    {"key": "wood", "name": "木质打击风",
     "desc": "纯木块敲击、弱音高，极简克制，低调不打扰。",
     "fit": "夜间场景、追求安静克制", "caution": "缺少温度和记忆点，偏干涩"},
]

ROLE_REL = {"tap": -1.5, "save": 0.0, "win": 1.5}
ROLE_TITLE = {"tap": "点击 · 主按钮", "save": "保存成功", "win": "里程碑成就"}


def build_role(style, role, seed):
    fn = SYNTHS[style]
    if role == "tap":
        return fn(freq(TAP_NOTE[style]), 0.20, seed=seed)
    if role == "save":
        a, b = SAVE_NOTES[style]
        buf = gel(0.55)
        add_at(buf, 0.0, fn(freq(a), 0.30, seed=seed))
        add_at(buf, 0.075, fn(freq(b), 0.42, vel=0.92, seed=seed + 1))
        return buf
    # win：上行琶音
    notes = WIN_NOTES[style]
    spacing = 0.09 if len(notes) == 5 else 0.10
    buf = gel(1.15)
    for i, n in enumerate(notes):
        add_at(buf, i * spacing, fn(freq(n), 0.6 - i * 0.05,
                                     vel=0.72 + i * 0.07, seed=seed + i))
    return buf


# ---------------------------------------------------------------- 后期

CEIL = 10 ** (-0.5 / 20)
SAT_THR = 0.80
HF_BUDGET = 0.12


def shape(x, tail_ms=12, gate_db=-60):
    x = bi_highpass(x, 100)
    x = high_shelf(x, 3500, -7)
    gate = 10 ** (gate_db / 20)
    nz = np.abs(x) > gate
    if nz.any():
        x = x[: int(np.max(np.nonzero(nz))) + int(tail_ms / 1000 * SR)]
    loud_end = 20 * math.log10(float(np.max(np.abs(x[-max(1, int(0.012 * SR)):]))) + 1e-12) > -30
    a = min(int(0.004 * SR), len(x) // 2)
    b = min(max(int((0.12 if loud_end else 0.045) * SR), 16), int(len(x) * 0.35))
    if a > 1:
        x[:a] *= np.linspace(0, 1, a)
    if b > 1:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def plr(x):
    return np.max(np.abs(x)) / (krms(x) + 1e-12)


def soft_clip(x):
    ax = np.abs(x)
    excess = np.maximum(ax - SAT_THR, 0.0)
    compressed = SAT_THR + excess / (1.0 + excess / (1.0 - SAT_THR))
    return np.sign(x) * np.where(ax > SAT_THR, compressed, ax)


def quantize(x):
    rs = np.random.RandomState(len(x))
    d = (rs.uniform(-1, 1, len(x)) + rs.uniform(-1, 1, len(x))) / 2
    return np.clip(np.round(x * 32768 + d), -32768, 32767).astype(np.int16)


def write_wav(name, x):
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(x.tobytes())


def hf_ratio(x):
    nper, hop = 2048, 1024
    if len(x) < nper:
        x = np.pad(x, (0, nper - len(x)))
    win = np.hanning(nper)
    tot = hi = 0.0
    for s in range(0, len(x) - nper + 1, hop):
        spec = np.abs(np.fft.rfft(x[s:s + nper] * win)) ** 2
        fr = np.fft.rfftfreq(nper, 1 / SR)
        tot += spec[fr > 60].sum()
        hi += spec[fr > 3500].sum()
    return hi / (tot + 1e-18)


def lufs(x):
    return -0.691 + 20 * math.log10(krms(x) + 1e-12)


def main():
    os.makedirs(OUT, exist_ok=True)
    np.random.seed(20261112)

    items = []
    shaped = []
    seed = 300
    for st in STYLES:
        for role in ("tap", "save", "win"):
            raw = build_role(st["key"], role, seed)
            seed += 3
            y = shape(raw / (np.max(np.abs(raw)) + 1e-9))
            rel = ROLE_REL[role]
            shaped.append((st["key"], role, y, rel))
            items.append({"style": st["key"], "role": role, "rel": rel})

    ref = min(CEIL / (plr(x) * 10 ** (rel / 20)) for _, _, x, rel in shaped)

    for (style, role, x, rel), meta in zip(shaped, items):
        y = soft_clip(x / krms(x) * ref * 10 ** (rel / 20))
        yq = quantize(y)
        xf = yq.astype(float) / 32768
        fname = f"style_{style}_{role}.wav"
        write_wav(fname, yq)
        meta.update({
            "file": fname,
            "title": ROLE_TITLE[role],
            "duration_ms": round(len(xf) / SR * 1000, 1),
            "peak_dbfs": round(20 * math.log10(np.max(np.abs(xf)) + 1e-12), 1),
            "lufs": round(lufs(xf), 1),
            "rel_lufs": round(20 * math.log10(krms(xf) / ref + 1e-12), 2),
            "hf_pct": round(hf_ratio(xf) * 100, 2),
        })

    # 当前线上卡林巴风对照（引用 v11 成品）
    ref_map = [
        ("kalimba", "tap", "suiji_s12_btn_primary.wav", "点击 · 主按钮"),
        ("kalimba", "save", "suiji_s03_save_ok_v1.wav", "保存成功"),
        ("kalimba", "win", "suiji_e01_milestone_v1.wav", "里程碑成就"),
    ]
    v11 = os.path.join(HERE, "..", "synth-v11", "wav")
    for style, role, fn, title in ref_map:
        p = os.path.join(v11, fn)
        w = wave.open(p)
        xf = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768
        items.append({
            "style": style, "role": role, "rel": ROLE_REL[role], "file": fn,
            "external": True, "title": title,
            "duration_ms": round(len(xf) / SR * 1000, 1),
            "peak_dbfs": round(20 * math.log10(np.max(np.abs(xf)) + 1e-12), 1),
            "lufs": round(lufs(xf), 1), "hf_pct": round(hf_ratio(xf) * 100, 2),
        })

    styles_out = STYLES + [{"key": "kalimba", "name": "当前 · 卡林巴木质风",
                            "desc": "线上现有版本：拇指琴拨弦 + 木质敲击 + 气声尾，温润夜间感。",
                            "fit": "对照基准", "caution": "即本次想要换掉的风格"}]
    man = {"styles": styles_out, "items": items}
    with open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)

    print(f"{'style':<10} {'role':<6} {'时长':>8} {'峰值':>8} {'LUFS':>7} {'相对':>7}  高频")
    for m in items:
        print(f"{m['style']:<10} {m['role']:<6} {m['duration_ms']:>7.0f}ms "
              f"{m['peak_dbfs']:>7.1f}dB {m['lufs']:>6.1f} {m['rel_lufs'] if 'rel_lufs' in m else '-':>7} "
              f"{m['hf_pct']:>6.2f}%")
    print(f"\n生成 {len(items)} 条 -> {OUT}")


if __name__ == "__main__":
    main()
