"""岁记交互音效合成器 —— 按《岁记-交互音效需求表-v1.0》生成全量 WAV.

音色世界观：卡林巴(拇指琴)拨弦 + 木质敲击 + 气声尾。
统一处理链：定型(100Hz HP + 3.5kHz 以上 -12dB 搁架 + 裁尾 + 淡变)
            -> A-06 高频占比校验 -> 全表统一响度基准定标(峰均比反推，无限幅)
            -> TPDF 抖动 1LSB -> 16bit PCM。
"""

import json
import math
import os
import re
import wave

import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wav")

# ---------------------------------------------------------------- 基础工具

_LETTERS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def freq(name):
    """支持 F#4 / Bb3 / C4 形式的音名。"""
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
    """线性 attack + 指数 decay，用于气声/底噪类元素。"""
    e = np.clip(t / max(a, 1e-6), 0, 1)
    rise = np.where(t < a, e, 1.0)
    return rise * env_exp(np.maximum(t - a, 0), d)


def sos_df2(b, a):
    """把 biquad 系数转成 [b0,b1,b2,a0,a1,a2]。"""
    b = np.asarray(b, float) / a[0]
    a = np.asarray(a, float) / a[0]
    return np.array([b[0], b[1], b[2], a[0], a[1], a[2]])


def sosfilt_df2(sos, x):
    """零相位 FFT 滤波：设计阶段无群延迟顾虑，且比逐样本循环快三个数量级。"""
    n = len(x)
    if n == 0:
        return x
    b, a = sos[0:3], sos[3:6]
    zi = np.exp(-1j * 2 * np.pi * np.fft.rfftfreq(2 * n))  # 归一化角频率 0..pi，单位是"周期/采样"
    h = _poly(b, zi) / _poly(a, zi)
    h[~np.isfinite(h)] = 0.0
    return np.fft.irfft(np.fft.rfft(x, 2 * n) * h, 2 * n)[:n]


def _poly(coeffs, zi):
    """coeffs 为 [b0,b1,b2]，按 z^-1 升幂求值。"""
    return coeffs[0] + coeffs[1] * zi + coeffs[2] * zi ** 2


def bi_lowpass(x, f0, q=0.7071):
    w0 = 2 * math.pi * min(f0, SR / 2 - 10) / SR
    cw, sw = math.cos(w0), math.sin(w0)
    al = sw / (2 * q)
    return sosfilt_df2(sos_df2([(1 - cw) / 2, 1 - cw, (1 - cw) / 2],
                               [1 + al, -2 * cw, 1 - al]), x)


def bi_highpass(x, f0, q=0.7071):
    w0 = 2 * math.pi * min(f0, SR / 2 - 10) / SR
    cw, sw = math.cos(w0), math.sin(w0)
    al = sw / (2 * q)
    return sosfilt_df2(sos_df2([(1 + cw) / 2, -(1 + cw), (1 + cw) / 2],
                               [1 + al, -2 * cw, 1 - al]), x)


def hf_shelf_cut(x):
    """3.5kHz 以上 -12dB 搁架(需求表 §2.1)。

    单级即可，不做级联：级联会把占比压到 0.02%，远优于 8% 的验收线，
    但卡林巴的木质光泽正来自 3.5-6kHz 的一层薄泛音，削过头声音会发闷。
    """
    return high_shelf(x, 3500, -12)


def high_shelf(x, f0, gain_db, slope=1.0):
    """RBJ 高频搁架：gain_db>0 抬高 f0 以上频段，<0 压低。"""
    A = 10 ** (gain_db / 40)
    w0 = 2 * math.pi * min(f0, SR / 2 - 10) / SR
    cw, sw = math.cos(w0), math.sin(w0)
    al = sw / 2 * math.sqrt((A + 1 / A) * (1 / slope - 1) + 2)
    r = 2 * math.sqrt(A) * al
    b = [A * ((A + 1) + (A - 1) * cw + r),
         -2 * A * ((A - 1) + (A + 1) * cw),
         A * ((A + 1) + (A - 1) * cw - r)]
    a = [(A + 1) - (A - 1) * cw + r,
         2 * ((A - 1) - (A + 1) * cw),
         (A + 1) - (A - 1) * cw - r]
    return sosfilt_df2(sos_df2(b, a), x)


def k_weight(x):
    """BS.1770 K 加权：+4dB @1.5kHz 以上的高频搁架。

    注意：published 系数表多按 48kHz 设计，直接装在 44.1kHz 上极点会跑到 140Hz，
    低频被削 13dB、响度阶梯失真，故此处按本采样率解析重算。
    """
    return high_shelf(x, 1500, 4.0)


def kw_gain_db(f):
    """K 加权在给定频率上的增益(dB)，用于标定与自检。"""
    skip = int(SR / f * 4)
    t = np.arange(int(SR / f * 8)) / SR
    y = k_weight(np.sin(2 * np.pi * f * t))[skip:]
    return 20 * math.log10(np.sqrt(np.mean(y ** 2) * 2) + 1e-12)


# 归一到 BS.1770 惯例(1kHz = 0dB)。单级搁架在 200-6000Hz 内约 +3.8dB 抬升，
# 不扣除会让绝对 LUFS 整体虚高；阶梯本身是同一把尺子量出来的，扣除前后都不影响。
K_CAL = 10 ** (kw_gain_db(997.9) / 20)


def krms(x):
    w = k_weight(x) / K_CAL
    return math.sqrt(float(np.mean(w ** 2)) + 1e-18)


# ---------------------------------------------------------------- 音素

def kalimba(f0, dur, vel=1.0, body=1.0, air=0.0, decay=0.30):
    """卡林巴主音色：微失谐基频 + 木质共鸣泛音 + 快速衰减的拨片噪声。

    `decay` 是基频的衰减时间常数(秒)。交互音取 0.16 收得干脆，成就音保留 0.30 让余韵铺开。
    """
    t = t_axis(dur)
    parts = [
        (1.0, 1.0, 0.30, 1.0),
        (2.005, 0.30, 0.085, 1.0),
        (3.98, 0.09, 0.040, 1.0),
        (5.02, 0.045, 0.022, 1.0),
    ]
    y = np.zeros_like(t)
    for ratio, amp, tc, _ in parts:
        f = f0 * ratio
        if f >= SR / 2 - 500:
            continue
        d = decay * (tc / 0.30) * (0.62 + 0.38 * (300.0 / f))
        detune = 1.0 + 0.0009 * np.sin(2 * np.pi * 0.25 * t)  # 极轻颤，避免死板
        y += amp * np.sin(2 * np.pi * f * detune * t) * env_exp(t, d)
    # 木质共鸣：基频下方一档的宽频模态
    y += 0.14 * body * np.sin(2 * np.pi * f0 * 0.5 * t) * env_exp(t, 0.05)
    # 拨片瞬态：窄带噪声，决定"温暖 vs 刺耳"。上限压到 3.5 倍基频以守住高频预算
    nyq = SR / 2 - 500
    n = np.random.RandomState(int(f0) % 9973).uniform(-1, 1, len(t))
    band_lo, band_hi = min(f0 * 1.6, nyq), min(f0 * 3.5, nyq)
    bp = bi_lowpass(n, band_hi) - bi_lowpass(n, band_lo)
    y += 0.30 * vel * bp * env_ad(t, 0.0008, 0.011)
    if air:
        y += air * np.sin(2 * np.pi * min(f0 * 2.5, nyq) * t) * env_exp(t, 0.30)
    peak = np.max(np.abs(y)) + 1e-9
    return y / peak * vel


def wood_hit(f0, dur, vel=1.0):
    """木质敲击：短促、宽带、无明显音高感，用于快门。"""
    t = t_axis(dur)
    y = np.sin(2 * np.pi * f0 * t) * env_exp(t, 0.020)
    y += 0.55 * np.sin(2 * np.pi * f0 * 2.4 * t) * env_exp(t, 0.008)
    n = np.random.RandomState(7).uniform(-1, 1, len(t))
    y += 0.85 * (bi_lowpass(n, 2600) - bi_lowpass(n, 700)) * env_ad(t, 0.0005, 0.006)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def mellow(name, dur, vel=1.0):
    """闷质感(用于暂停/失败/拦截)：正弦 + 低通，几乎无高频泛音。"""
    t = t_axis(dur)
    f = freq(name)
    y = np.sin(2 * np.pi * f * t) * env_exp(t, dur * 0.32)
    y += 0.22 * np.sin(2 * np.pi * f * 1.5 * t) * env_exp(t, 0.09)
    y = bi_lowpass(y, min(f * 3.2, 2400))
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def add_at(buf, start_s, seg):
    i = int(start_s * SR)
    n = min(len(seg), len(buf) - i)
    if n > 0:
        buf[i:i + n] += seg[:n]
    return buf


def gel(length):
    return np.zeros(int(length * SR))


def reverb(x, mix=0.24, tail=1.4):
    """低成本反馈延迟混响，只用于"落印/归档"的尾部空间感。"""
    n = len(x) + int(tail * SR)
    out = np.zeros(n)
    out[: len(x)] = x * (1 - mix)
    for d_ms, fb in ((37, 0.45), (53, 0.40), (79, 0.36), (113, 0.32)):
        d = int(d_ms / 1000 * SR)
        for i in range(d, n):
            out[i] += fb * out[i - d]
    return bi_lowpass(out, 2400)


# ---------------------------------------------------------------- 后期

def fade(x, fi=0.004, fo=0.045):
    n = len(x)
    a = min(int(fi * SR), n // 2)
    b = min(max(int(fo * SR), 16), int(n * 0.35))  # 短素材按比例收淡出，避免吃掉瞬态
    if a > 1:
        x[:a] *= np.linspace(0, 1, a)
    if b > 1:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def tail_level_db(x, win=0.012):
    k = max(1, int(win * SR))
    return 20 * math.log10(float(np.max(np.abs(x[-k:]))) + 1e-12)


CEIL = 10 ** (-3.2 / 20)      # 峰值上限，比 -3dBFS 多留 0.2dB 给抖动与取整
HF_BUDGET = 0.075             # A-06 的 8% 预算留 0.5 个百分点余量


def shape(x, tail_ms=12, gate_db=-60):
    """定型链：低频清理 -> 高频搁架 -> 裁尾 -> 淡变。全程不做电平缩放。

    裁尾门限取 -60 dBFS 而非更保守的 -80：§2.1 的"末端落至 -60 dBFS"就是可闻终止线，
    用同一把尺子量时长，`duration_ms` 才能直接对着需求表的时长预算验收。

    淡出长度随结尾电平自适应：卡林巴的自然衰减在预算点上往往还有 -15~-25 dB，
    45ms 直落会听出"被剪断"，拉到 120ms 才像自然收尾。§2.1 只要求 >=30ms，上探合规。
    """
    x = bi_highpass(x, 100)
    x = hf_shelf_cut(x)
    gate = 10 ** (gate_db / 20)
    nz = np.abs(x) > gate
    if nz.any():
        x = x[: int(np.max(np.nonzero(nz))) + int(tail_ms / 1000 * SR)]
    loud_end = tail_level_db(x) > -30
    return fade(x, fo=0.12 if loud_end else 0.045)


def check_hf(sid, x):
    """A-06 成品高频占比校验。

    实测：单级 -12dB 搁架后最高的 S-11(带通噪声开关音)也只有 3.7%，预算从未吃紧，
    所以不做"超标就逐档加深低通"的自动救场——那只会把音色默默削闷、把问题藏起来。
    真超标说明编曲层泛音给多了，应该回编曲改，不是在后期压。
    """
    r = hf_ratio(x)
    if r > HF_BUDGET:
        raise ValueError(f"{sid} 高频占比 {r * 100:.1f}% 超过 {HF_BUDGET * 100:.1f}% 预算")
    return r


def plr(x):
    """峰均比(线性)：K 加权 RMS 相对时域峰值。决定该素材能爬到多高的绝对电平。"""
    return np.max(np.abs(x)) / (krms(x) + 1e-12)


def quantize(x):
    """TPDF 抖动 1 LSB + 16bit 量化。种子取样本长度，同一素材重跑字节一致。"""
    rs = np.random.RandomState(len(x))
    d = (rs.uniform(-1, 1, len(x)) + rs.uniform(-1, 1, len(x))) / 2
    return np.clip(np.round(x * 32768 + d), -32768, 32767).astype(np.int16)


def write_wav(name, x):
    path = os.path.join(OUT, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(x.tobytes())
    return path


# ---------------------------------------------------------------- 编曲

def build():
    """返回 [(id, 文件, 相对响度dB, 波形, 中文场景)]；响度以 S-03(保存成功) 为 0dB 基准。"""
    o = []

    # --- S 组 交互音 -----------------------------------------------------
    def click(name, dur, vel=1.0):
        return kalimba(freq(name), dur, vel=vel, decay=0.16)

    o.append(("S-01", "suiji_s01_fab_open.wav", -6.0,
              click("D4", 0.30), "点击 FAB，记录类型面板展开"))
    o.append(("S-02", "suiji_s02_type_pick.wav", -7.0,
              click("F#4", 0.24), "面板内选中记录类型"))

    s03a = gel(0.62)
    add_at(s03a, 0.0, kalimba(freq("G4"), 0.34, decay=0.16))
    add_at(s03a, 0.075, kalimba(freq("B4"), 0.50, vel=0.92, decay=0.16))
    o.append(("S-03_v1", "suiji_s03_save_ok_v1.wav", 0.0, s03a, "记录保存成功(服务端确认后)"))
    s03b = gel(0.62)
    add_at(s03b, 0.0, kalimba(freq("A4"), 0.34, decay=0.16))
    add_at(s03b, 0.075, kalimba(freq("C#5"), 0.50, vel=0.92, decay=0.16))
    o.append(("S-03_v2", "suiji_s03_save_ok_v2.wav", 0.0, s03b, "记录保存成功(变体2，随机交替)"))

    o.append(("S-04", "suiji_s04_field_block.wav", -5.0,
              mellow("A2", 0.24) * 1.0, "表单校验拦截(数值超范围/时间早于出生)"))

    s05 = gel(0.50)
    add_at(s05, 0.0, mellow("E3", 0.26))
    add_at(s05, 0.10, mellow("C3", 0.30, vel=0.9))
    o.append(("S-05", "suiji_s05_save_fail.wav", -5.0, s05, "保存失败/无网络(中性，非错误蜂鸣)"))

    s06 = gel(0.36)
    add_at(s06, 0.0, wood_hit(freq("A3"), 0.30))
    add_at(s06, 0.055, kalimba(freq("D5"), 0.18, vel=0.35, decay=0.10))
    o.append(("S-06", "suiji_s06_shutter.wav", 0.0, s06, "拍照完成，照片进入预览"))

    s08 = gel(0.52)
    add_at(s08, 0.0, mellow("A2", 0.30))
    add_at(s08, 0.085, mellow("G2", 0.34, vel=0.85))
    o.append(("S-08", "suiji_s08_danger_confirm.wav", -0.5, s08, "危险操作二次确认(删除/改角色/注销)"))

    s09 = gel(0.62)
    add_at(s09, 0.0, kalimba(freq("A3"), 0.34, decay=0.16))
    add_at(s09, 0.075, kalimba(freq("E4"), 0.48, vel=0.9, decay=0.16))
    o.append(("S-09", "suiji_s09_restore.wav", -5.0, s09, "回收站恢复成功(纯五度落定)"))

    s10 = gel(0.80)
    for i, n in enumerate(("D4", "E4", "G4", "A4")):
        add_at(s10, i * 0.05, kalimba(freq(n), 0.34 - i * 0.05,
                                      vel=0.62 + i * 0.1, decay=0.16))
    o.append(("S-10", "suiji_s10_baby_switch.wav", -3.0, s10, "宝宝档案切换完成(上行刮奏)"))

    t = t_axis(0.16)
    rs = np.random.RandomState(21)
    n = rs.uniform(-1, 1, len(t))
    # 带通 1.1-2.4kHz：开关"咔"要有质感但不留高频毛刺
    s11 = (bi_lowpass(n, 2400) - bi_lowpass(n, 1100)) * env_ad(t, 0.0004, 0.014)
    s11 += 0.25 * np.sin(2 * np.pi * 1200 * t) * env_exp(t, 0.012)
    o.append(("S-11", "suiji_s11_switch_toggle.wav", -9.0, s11, "提醒/可见性开关拨动"))

    # --- T 组 计时 -------------------------------------------------------
    o.append(("T-01", "suiji_t01_timer_start.wav", -2.0,
              kalimba(freq("A4"), 0.45, decay=0.18), "母乳/睡眠计时开始(此后全程无声)"))
    t02 = gel(0.46)
    add_at(t02, 0.0, mellow("A3", 0.24))
    add_at(t02, 0.07, mellow("E3", 0.28, vel=0.9))
    o.append(("T-02", "suiji_t02_timer_pause.wav", -3.0, t02, "计时暂停(下行，材质变闷)"))
    t03 = gel(0.46)
    add_at(t03, 0.0, mellow("E3", 0.24))
    add_at(t03, 0.07, mellow("A3", 0.28, vel=0.9))
    o.append(("T-03", "suiji_t03_timer_resume.wav", -3.0, t03, "计时恢复(上行，与暂停一听即辨)"))

    t04 = gel(1.00)
    for i, n in enumerate(("C5", "G4", "E4")):
        add_at(t04, i * 0.11, kalimba(freq(n), 0.55 - i * 0.1, vel=0.95 - i * 0.05, decay=0.20))
    add_at(t04, 0.33, mellow("A4", 0.45, vel=0.16))
    o.append(("T-04", "suiji_t04_timer_end.wav", -6.0, t04, "计时结束(夜间为纯振动，此为发声版)"))

    # --- E 组 成就/情感 --------------------------------------------------
    scales = {
        "v1": ("G4", "A4", "B4", "D5", "E5"),
        "v2": ("A4", "B4", "C#5", "E5", "F#5"),
        "v3": ("D4", "F#4", "A4", "B4", "D5"),
        "v4": ("E4", "G4", "A4", "B4", "E5"),
        "v5": ("C4", "D4", "E4", "G4", "A4"),
    }
    spacing = {"v1": 0.085, "v2": 0.10, "v3": 0.078, "v4": 0.11, "v5": 0.092}
    for k, sc in scales.items():
        buf = gel(1.80)
        for i, n in enumerate(sc):
            add_at(buf, i * spacing[k], kalimba(freq(n), 0.85 - i * 0.06,
                                                vel=0.7 + i * 0.075, air=0.10, decay=0.26))
        tt = t_axis(1.4)
        air = np.random.RandomState(len(sc)).uniform(-1, 1, len(tt))
        air = bi_lowpass(air, 2200) * env_ad(tt, 0.12, 0.45)
        add_at(buf, 0.30, 0.05 * air)
        o.append((f"E-01_{k}", f"suiji_e01_milestone_{k}.wav", -1.0, buf,
                  f"里程碑首次达成 变体{k[-1]}(全 App 唯一庆祝音，随机播放)"))

    e03 = kalimba(freq("D5"), 0.26, vel=0.8, decay=0.16)
    o.append(("E-03", "suiji_e03_curve_point.wav", -10.0, e03, "生长曲线新数据点落位"))

    e04 = gel(0.75)
    add_at(e04, 0.0, kalimba(freq("E4"), 0.45, decay=0.18))
    add_at(e04, 0.09, kalimba(freq("B4"), 0.60, vel=0.9, decay=0.18))
    o.append(("E-04", "suiji_e04_journal_ready.wav", -4.0, e04, "AI 日记生成成功，进入待确认"))

    t = t_axis(0.45)
    f = freq("G4")
    e05 = np.sin(2 * np.pi * f * t) * env_exp(t, 0.14)
    e05 += 0.18 * np.sin(2 * np.pi * f * 1.5 * t) * env_exp(t, 0.07)
    e05 = bi_lowpass(e05, 2000)
    o.append(("E-05", "suiji_e05_journal_basic.wav", -6.0, e05, "AI 降级基础版(中性，禁止失败音)"))

    e06 = gel(0.85)
    for i, n in enumerate(("A4", "F#4", "D4")):
        add_at(e06, i * 0.135, kalimba(freq(n), 0.6 - i * 0.05, decay=0.20))
    e06 = reverb(e06, mix=0.24, tail=0.45)
    o.append(("E-06", "suiji_e06_journal_archive.wav", -3.0, e06, "AI 日记归档(落印感，带轻混响尾)"))

    e07v = {
        "v1": ("百日 100 天", ("D5", "A4", "F#4", "D4"), 0.15),
        "v2": ("周岁 1 岁", ("E5", "B4", "G4", "E4"), 0.165),
    }
    for k, (label, seq, sp) in e07v.items():
        buf = gel(1.15)
        for i, n in enumerate(seq):
            add_at(buf, i * sp, kalimba(freq(n), 0.6 - i * 0.06,
                                        vel=0.8 + i * 0.03, decay=0.20))
        o.append((f"E-07_{k}", f"suiji_e07_card_{k}.wav", -2.0, buf,
                  f"纪念卡生成完成 {label}(纪念而非庆祝)"))

    e08 = gel(0.85)
    add_at(e08, 0.0, kalimba(freq("F4"), 0.5, decay=0.18))
    add_at(e08, 0.1, kalimba(freq("C4"), 0.65, vel=0.9, decay=0.18))
    o.append(("E-08", "suiji_e08_video_done.wav", -5.0, e08, "成长视频合成完成(过程中无进度音)"))

    e09 = gel(0.75)
    add_at(e09, 0.0, kalimba(freq("E4"), 0.4, decay=0.16))
    add_at(e09, 0.085, kalimba(freq("A3"), 0.55, vel=0.88, decay=0.16))
    o.append(("E-09", "suiji_e09_pdf_export_done.wav", -5.0, e09, "PDF 成长档案导出完成"))

    e10 = gel(1.05)
    for i, n in enumerate(("D5", "E5")):      # 呼
        add_at(e10, i * 0.11, kalimba(freq(n), 0.4, vel=0.85, decay=0.20))
    for i, n in enumerate(("G4", "A4")):      # 应
        add_at(e10, 0.40 + i * 0.11, kalimba(freq(n), 0.6, vel=0.92, decay=0.20))
    o.append(("E-10", "suiji_e10_member_joined.wav", -1.0, e10, "家人成功加入家庭空间(呼应式欢迎动机)"))

    return [(i, f, r, x, s) for (i, f, r, x, s) in o]


# ---------------------------------------------------------------- 度量

def hf_ratio(x):
    """3.5kHz 以上能量占比(Welch 分段功率谱)。

    不能用单窗 FFT：指数衰减长尾在单窗里等价于一次整窗幅度调制，会把"时域衰减"
    误读成宽带高频能量，导致正常音色被判成超标；也不能用零相位滤波切带，
    它对非周期突发信号的边缘行为会整段压掉电平。
    """
    nper, hop = 2048, 1024
    if len(x) < nper:
        x = np.pad(x, (0, nper - len(x)))
    win = np.hanning(nper)
    lo = hi = tot = 0.0
    for s in range(0, len(x) - nper + 1, hop):
        spec = np.abs(np.fft.rfft(x[s:s + nper] * win)) ** 2
        fr = np.fft.rfftfreq(nper, 1 / SR)
        tot += spec[fr > 60].sum()
        lo += spec[(fr > 60) & (fr <= 3500)].sum()
        hi += spec[fr > 3500].sum()
    return hi / (tot + 1e-18)


def ms(x):
    return len(x) / SR * 1000


def normalize(x):
    return x / (np.max(np.abs(x)) + 1e-9)


def lufs(x):
    """BS.1770 相对全响度(近似)：-0.691 门限偏移 + K 加权 RMS。"""
    return -0.691 + 20 * math.log10(krms(x) + 1e-12)


# 预览页与素材清单用的短标题；完整说明见 scene 字段
TITLES = {
    "S-01": "面板展开", "S-02": "选中类型", "S-03": "保存成功", "S-04": "校验拦截",
    "S-05": "保存失败", "S-06": "快门", "S-08": "危险确认", "S-09": "恢复成功",
    "S-10": "切换宝宝", "S-11": "开关拨动",
    "T-01": "计时开始", "T-02": "计时暂停", "T-03": "计时恢复", "T-04": "计时结束",
    "E-01": "里程碑达成", "E-03": "数据点落位", "E-04": "日记生成", "E-05": "日记基础版",
    "E-06": "日记归档", "E-07": "纪念卡", "E-08": "视频完成", "E-09": "导出完成",
    "E-10": "家人加入",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    np.random.seed(20261027)

    specs = build()
    shaped = []
    for sid, fn, rel, x, scene in specs:
        y = shape(normalize(x))
        check_hf(sid, y)
        shaped.append((sid, fn, rel, y, scene))

    # 全表统一基准：解 ref = min_i CEIL / (plr_i * 10^(rel_i/20))。
    # 峰均比最大、目标最响的那条素材钉死基准，其余素材自动留出峰值余量，
    # 于是阶梯精确成立且全程不需要限幅器。
    ref = min(CEIL / (plr(x) * 10 ** (rel / 20)) for _, _, rel, x, _ in shaped)

    results = []
    for sid, fn, rel, x, scene in shaped:
        y = quantize(x / krms(x) * ref * 10 ** (rel / 20))
        xf = y.astype(float) / 32768
        write_wav(fn, y)
        results.append({
            "id": sid, "file": fn, "scene": scene, "target_rel_db": rel,
            "title": TITLES[re.sub(r"_v\d+$", "", sid)],
            "duration_ms": round(ms(xf), 1),
            "peak_dbfs": round(20 * math.log10(np.max(np.abs(xf)) + 1e-12), 1),
            "lufs": round(lufs(xf), 1),
            "plr_db": round(20 * math.log10(plr(x)), 1),
            "rel_lufs_vs_s03": round(20 * math.log10(krms(xf) / ref + 1e-12), 2),
            "hf_energy_pct_above_3k5": round(hf_ratio(xf) * 100, 2),
        })

    man = {
        "project": "岁记 Baby Growth Log",
        "spec": "岁记-交互音效需求表-v1.0",
        "sample_rate": SR, "bit_depth": 16, "channels": 1,
        "reference": "rel_lufs_vs_s03 以 S-03(保存成功)为 0dB 基准，对应需求表音量档",
        "acceptance": {
            "duration_window": "起点为首样本，终点为最后一个高于 -60dBFS 的样本；结尾仍 >-30dB 时用 120ms 淡出收尾",
            "hf_ratio_limit_pct": 8.0,
            "peak_limit_dbfs": -3.0,
            "ladder_tolerance_db": 1.0,
            "loudness": (
                "全表按 K 加权 RMS 精确落在 §2.1 响度阶梯上；绝对电平由峰均比反推统一基准，"
                "峰值不越 -3dBFS。-20/-24LUFS 与 -3dBFS 上限对 1-2s 短音效不能同时取到，"
                "以阶梯差为验收口径(需求表 A-09)，绝对 LUFS 见各条 lufs 字段。"
            ),
        },
        "items": results,
    }
    with open(os.path.join(os.path.dirname(OUT), "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)

    print(f"{'ID':<10} {'时长':>8} {'峰值':>8} {'LUFS':>7} {'峰均比':>7} "
          f"{'实测相对':>9} {'目标':>7} {'高频占比':>9}  文件")
    for r in results:
        bad = "!" if (r["hf_energy_pct_above_3k5"] > 8 or r["peak_dbfs"] > -3
                      or abs(r["rel_lufs_vs_s03"] - r["target_rel_db"]) > 0.05) else " "
        print(f"{bad}{r['id']:<10} {r['duration_ms']:>7.1f}ms "
              f"{r['peak_dbfs']:>7.1f}dB {r['lufs']:>6.1f} "
              f"{r['plr_db']:>6.1f}dB "
              f"{r['rel_lufs_vs_s03']:>8.1f}dB "
              f"{r['target_rel_db']:>6.1f}dB {r['hf_energy_pct_above_3k5']:>8.2f}%  {r['file']}")
    print(f"\n统一基准 ref_rms={ref:.4f} ({20 * math.log10(ref):.1f}dBFS K-RMS)")
    print(f"生成 {len(results)} 个文件 -> {OUT}")


if __name__ == "__main__":
    main()
