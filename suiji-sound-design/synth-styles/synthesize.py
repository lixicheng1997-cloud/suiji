"""岁记交互音效 · 风格化全量合成器（bubble / drop 两套）。

沿用 v1.1 的全量清单、响度阶梯口径与红线，只替换音色层：
  - bubble 软合成气泡：圆润正弦 + 二次泛音，音头轻上滑，现代轻快；
  - drop   水滴气泡：频率下扫 + 快衰减，短促水滴感。

处理链与 v1.1 一致：定型(100Hz HP + 3.5kHz -7dB 搁架 + 裁尾 + 淡变)
  -> 高频占比校验 -> 全表统一响度基准定标(PLR 反推)
  -> 分段软压(阈值以下线性透明) -> TPDF 抖动 1LSB -> 16bit PCM。
固定随机种子，同一素材重跑字节一致。
"""

import json
import math
import os
import re
import wave

import numpy as np

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
STYLES = ["bubble", "drop"]

# ---------------------------------------------------------------- 基础工具

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
    rise = np.where(t < a, e, 1.0)
    return rise * env_exp(np.maximum(t - a, 0), d)


def _poly(coeffs, zi):
    return coeffs[0] + coeffs[1] * zi + coeffs[2] * zi ** 2


def sos_df2(b, a):
    b = np.asarray(b, float) / a[0]
    a = np.asarray(a, float) / a[0]
    return np.array([b[0], b[1], b[2], a[0], a[1], a[2]])


def sosfilt_df2(sos, x):
    n = len(x)
    if n == 0:
        return x
    b, a = sos[0:3], sos[3:6]
    zi = np.exp(-1j * 2 * np.pi * np.fft.rfftfreq(2 * n))
    h = _poly(b, zi) / _poly(a, zi)
    h[~np.isfinite(h)] = 0.0
    return np.fft.irfft(np.fft.rfft(x, 2 * n) * h, 2 * n)[:n]


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


def high_shelf(x, f0, gain_db, slope=1.0):
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
    return high_shelf(x, 1500, 4.0)


def kw_gain_db(f):
    skip = int(SR / f * 4)
    t = np.arange(int(SR / f * 8)) / SR
    y = k_weight(np.sin(2 * np.pi * f * t))[skip:]
    return 20 * math.log10(np.sqrt(np.mean(y ** 2) * 2) + 1e-12)


K_CAL = 10 ** (kw_gain_db(997.9) / 20)


def krms(x):
    w = k_weight(x) / K_CAL
    return math.sqrt(float(np.mean(w ** 2)) + 1e-18)


def _bandpass(x, lo, hi):
    return bi_lowpass(x, hi) - bi_lowpass(x, lo)


# ---------------------------------------------------------------- 音色层

def _glide(f0, f1, dur, vel, det=1.0):
    t = t_axis(dur)
    f = f0 + (f1 - f0) * np.clip(t / max(dur * 0.3, 1e-6), 0, 1)
    phase = 2 * np.pi * np.cumsum(f) / SR
    return vel * np.sin(phase * det)


def bubble_tone(f0, dur, vel=1.0, decay=0.12, seed=0):
    """软合成气泡：圆润正弦 + 二次泛音 + 低频共鸣，音头轻上滑。"""
    t = t_axis(dur)
    y = _glide(f0, f0 * 1.04, dur, 1.0)
    y += 0.28 * np.sin(2 * np.pi * f0 * 1.004 * t) * env_exp(t, decay)
    y += 0.10 * np.sin(2 * np.pi * f0 * 0.5 * t) * env_exp(t, 0.05)
    y *= env_ad(t, 0.004, decay)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def bubble_mellow(f0, dur, vel=1.0, seed=0):
    """闷质感气泡：低通短音，用于拦截 / 失败 / 暂停，无上行。"""
    t = t_axis(dur)
    y = np.sin(2 * np.pi * f0 * t) * env_exp(t, dur * 0.32)
    y += 0.20 * np.sin(2 * np.pi * f0 * 1.5 * t) * env_exp(t, 0.09)
    y = bi_lowpass(y, 1600)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def drop_tone(f0, dur, vel=1.0, decay=0.09, seed=0):
    """水滴：频率下扫 + 快衰减，短促气泡感。"""
    rs = np.random.RandomState(seed or int(f0) % 9973)
    t = t_axis(dur)
    y = _glide(f0 * 1.7, f0, dur, 1.0)
    n = rs.uniform(-1, 1, len(t))
    y += 0.18 * _bandpass(n, 1800, 3600) * env_ad(t, 0.0006, 0.006)
    y *= env_exp(t, decay)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


def drop_mellow(f0, dur, vel=1.0, seed=0):
    """闷质感水滴：低通低频短滴，用于拦截 / 失败 / 暂停。"""
    t = t_axis(dur)
    y = _glide(f0 * 1.3, f0 * 0.85, dur, 1.0)
    y = bi_lowpass(y, 1400)
    y *= env_exp(t, dur * 0.30)
    return y / (np.max(np.abs(y)) + 1e-9) * vel


TONE = {"bubble": bubble_tone, "drop": drop_tone}
MELLOW = {"bubble": bubble_mellow, "drop": drop_mellow}


def tone(style, f0, dur, vel=1.0, decay=0.12, seed=0):
    return TONE[style](f0, dur, vel, decay, seed)


def mellow(style, name, dur, vel=1.0, seed=0):
    return MELLOW[style](freq(name), dur, vel, seed)


def win_pad(style, chord, dur, vel=0.16, seed=5):
    """里程碑垫音层（按风格适配）。

    bubble：和弦长音正弦群慢起 + 根音上扬滑音，柔和托底；
    drop：薄垫音 + 高音水花泛音，不做人群嘈杂 / 掌声。
    """
    t = t_axis(dur)
    rs = np.random.RandomState(seed)
    y = np.zeros_like(t)
    for name in chord:
        f = freq(name)
        y += 0.30 * np.sin(2 * np.pi * f * 1.002 * t)
        y += 0.22 * np.sin(2 * np.pi * f * 0.998 * t)
    if style == "bubble":
        f0 = freq(chord[0])
        y += 0.26 * _glide(f0, f0 * 1.18, dur, 1.0)
        y = bi_lowpass(y, 2200)
    else:
        f0 = freq(chord[-1])
        y += 0.16 * np.sin(2 * np.pi * f0 * 2.0 * t) * env_exp(t, 0.18)
        y = bi_lowpass(y, 2000)
    a = int(0.15 * SR)
    r = int(0.40 * SR)
    env = np.ones_like(t)
    env[:a] = np.linspace(0, 1, a)
    env[-r:] *= np.linspace(1, 0, r)
    y *= env
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
    b = min(max(int(fo * SR), 16), int(n * 0.35))
    if a > 1:
        x[:a] *= np.linspace(0, 1, a)
    if b > 1:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def tail_level_db(x, win=0.012):
    k = max(1, int(win * SR))
    return 20 * math.log10(float(np.max(np.abs(x[-k:]))) + 1e-12)


CEIL = 10 ** (-0.5 / 20)
HF_BUDGET = 0.12
SAT_THR = 0.80
GLOBAL_GAIN_DB = 3.2


def shape(x, tail_ms=12, gate_db=-60):
    x = bi_highpass(x, 100)
    x = high_shelf(x, 3500, -7)
    gate = 10 ** (gate_db / 20)
    nz = np.abs(x) > gate
    if nz.any():
        x = x[: int(np.max(np.nonzero(nz))) + int(tail_ms / 1000 * SR)]
    loud_end = tail_level_db(x) > -30
    return fade(x, fo=0.12 if loud_end else 0.045)


def check_hf(sid, x):
    r = hf_ratio(x)
    if r > HF_BUDGET:
        raise ValueError(f"{sid} 高频占比 {r * 100:.1f}% 超过 {HF_BUDGET * 100:.1f}% 预算")
    return r


def plr(x):
    return np.max(np.abs(x)) / (krms(x) + 1e-12)


def soft_clip(x):
    ax = np.abs(x)
    excess = np.maximum(ax - SAT_THR, 0.0)
    compressed = SAT_THR + excess / (1.0 + excess / (1.0 - SAT_THR))
    out = np.where(ax > SAT_THR, compressed, ax)
    return np.sign(x) * out


def quantize(x):
    rs = np.random.RandomState(len(x))
    d = (rs.uniform(-1, 1, len(x)) + rs.uniform(-1, 1, len(x))) / 2
    return np.clip(np.round(x * 32768 + d), -32768, 32767).astype(np.int16)


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


def ms(x):
    return len(x) / SR * 1000


def normalize(x):
    return x / (np.max(np.abs(x)) + 1e-9)


def lufs(x):
    return -0.691 + 20 * math.log10(krms(x) + 1e-12)


TITLES = {
    "S-01": "面板展开", "S-02": "选中类型", "S-03": "保存成功", "S-04": "校验拦截",
    "S-05": "保存失败", "S-06": "快门", "S-08": "危险确认", "S-09": "恢复成功",
    "S-10": "切换宝宝", "S-11": "开关拨动", "S-12": "主按钮", "S-13": "次级按钮",
    "S-14": "返回收起", "S-15": "弹层打开", "S-16": "弹层关闭", "S-17": "标签选中",
    "S-18": "收藏点亮", "S-19": "新增条目", "S-20": "删除滑出", "S-21": "步进 +",
    "S-22": "步进 -", "S-23": "缩略图选中", "S-24": "Toast 提示", "S-25": "复制成功",
    "S-26": "输入聚焦",
    "T-01": "计时开始", "T-02": "计时暂停", "T-03": "计时恢复", "T-04": "计时结束",
    "E-01": "里程碑达成", "E-03": "数据点落位", "E-04": "日记生成", "E-05": "日记基础版",
    "E-06": "日记归档", "E-07": "纪念卡", "E-08": "视频完成", "E-09": "导出完成",
    "E-10": "家人加入", "E-11": "首次记录", "E-12": "满 7 天纪念",
}

# ---------------------------------------------------------------- 清单编排

def build(style):
    """返回 [(id, 文件, 相对响度dB, 波形, 中文场景)]；响度以 S-03 为 0dB 基准。"""
    o = []

    # --- S 组 · 基础交互 -------------------------------------------------
    o.append(("S-01", "suiji_s01_fab_open.wav", -5.0,
              tone(style, freq("D4"), 0.30, decay=0.16, seed=101), "点击 FAB，记录类型面板展开"))
    o.append(("S-02", "suiji_s02_type_pick.wav", -6.0,
              tone(style, freq("F#4"), 0.24, decay=0.16, seed=102), "面板内选中记录类型"))

    s03a = gel(0.62)
    add_at(s03a, 0.0, tone(style, freq("G4"), 0.34, decay=0.16, seed=103))
    add_at(s03a, 0.075, tone(style, freq("B4"), 0.50, vel=0.92, decay=0.16, seed=104))
    o.append(("S-03_v1", "suiji_s03_save_ok_v1.wav", 0.0, s03a, "记录保存成功(服务端确认后)"))
    s03b = gel(0.62)
    add_at(s03b, 0.0, tone(style, freq("A4"), 0.34, decay=0.16, seed=105))
    add_at(s03b, 0.075, tone(style, freq("C#5"), 0.50, vel=0.92, decay=0.16, seed=106))
    o.append(("S-03_v2", "suiji_s03_save_ok_v2.wav", 0.0, s03b, "记录保存成功(变体2，随机交替)"))

    o.append(("S-04", "suiji_s04_field_block.wav", -4.0,
              mellow(style, "A2", 0.24), "表单校验拦截(数值超范围/时间早于出生)"))

    s05 = gel(0.50)
    add_at(s05, 0.0, mellow(style, "E3", 0.26))
    add_at(s05, 0.10, mellow(style, "C3", 0.30, vel=0.9))
    o.append(("S-05", "suiji_s05_save_fail.wav", -4.0, s05, "保存失败/无网络(中性，非错误蜂鸣)"))

    s06 = gel(0.36)
    add_at(s06, 0.0, tone(style, freq("A3"), 0.30, seed=107))
    add_at(s06, 0.055, tone(style, freq("D5"), 0.18, vel=0.35, decay=0.10, seed=107))
    o.append(("S-06", "suiji_s06_shutter.wav", 0.0, s06, "拍照完成，照片进入预览"))

    s08 = gel(0.52)
    add_at(s08, 0.0, mellow(style, "A2", 0.30))
    add_at(s08, 0.085, mellow(style, "G2", 0.34, vel=0.85))
    o.append(("S-08", "suiji_s08_danger_confirm.wav", -0.5, s08, "危险操作二次确认(删除/改角色/注销)"))

    s09 = gel(0.62)
    add_at(s09, 0.0, tone(style, freq("A3"), 0.34, decay=0.16, seed=108))
    add_at(s09, 0.075, tone(style, freq("E4"), 0.48, vel=0.9, decay=0.16, seed=109))
    o.append(("S-09", "suiji_s09_restore.wav", -4.0, s09, "回收站恢复成功(纯五度落定)"))

    s10 = gel(0.80)
    for i, n in enumerate(("D4", "E4", "G4", "A4")):
        add_at(s10, i * 0.05, tone(style, freq(n), 0.34 - i * 0.05,
                                   vel=0.62 + i * 0.1, decay=0.16, seed=110 + i))
    o.append(("S-10", "suiji_s10_baby_switch.wav", -2.5, s10, "宝宝档案切换完成(上行刮奏)"))

    t = t_axis(0.16)
    rs = np.random.RandomState(21)
    n = rs.uniform(-1, 1, len(t))
    s11 = (bi_lowpass(n, 2400) - bi_lowpass(n, 1100)) * env_ad(t, 0.0004, 0.014)
    s11 += 0.25 * np.sin(2 * np.pi * (1200 if style == "bubble" else 1000) * t) * env_exp(t, 0.012)
    o.append(("S-11", "suiji_s11_switch_toggle.wav", -8.0, s11, "提醒/可见性开关拨动"))

    s12 = gel(0.24)
    add_at(s12, 0.0, tone(style, freq("D4"), 0.20, seed=120))
    add_at(s12, 0.045, tone(style, freq("A4"), 0.16, vel=0.45, decay=0.10, seed=121))
    o.append(("S-12", "suiji_s12_btn_primary.wav", -1.5, s12, "主按钮点击(确认/提交/下一步)"))

    o.append(("S-13", "suiji_s13_btn_secondary.wav", -5.5,
              tone(style, freq("E4"), 0.18, decay=0.12, seed=122), "次级按钮/列表项点击"))

    s14 = gel(0.26)
    add_at(s14, 0.0, tone(style, freq("A4"), 0.16, decay=0.12, seed=123))
    add_at(s14, 0.06, tone(style, freq("E4"), 0.18, vel=0.85, decay=0.12, seed=124))
    o.append(("S-14", "suiji_s14_back_collapse.wav", -5.0, s14, "返回/面板收起(下行轻滑)"))

    o.append(("S-15", "suiji_s15_panel_open.wav", -4.0,
              tone(style, freq("C5"), 0.22, decay=0.14, seed=125), "弹窗/底部弹层打开(轻上扬)"))
    o.append(("S-16", "suiji_s16_panel_close.wav", -5.0,
              tone(style, freq("E4"), 0.18, decay=0.12, seed=126), "弹窗/弹层关闭(轻下落)"))

    s17 = gel(0.22)
    add_at(s17, 0.0, tone(style, freq("D4"), 0.14, decay=0.10, seed=127))
    add_at(s17, 0.05, tone(style, freq("E4"), 0.16, vel=0.85, decay=0.10, seed=128))
    o.append(("S-17", "suiji_s17_tag_pick.wav", -5.0, s17, "标签/筛选条件选中"))

    s18 = gel(0.28)
    add_at(s18, 0.0, tone(style, freq("G4"), 0.16, decay=0.12, seed=129))
    add_at(s18, 0.06, tone(style, freq("D5"), 0.22, vel=0.9, decay=0.14, seed=130))
    o.append(("S-18", "suiji_s18_favorite.wav", -3.0, s18, "收藏/星星点亮(小上行两音)"))

    o.append(("S-19", "suiji_s19_add_item.wav", -3.5,
              tone(style, freq("A4"), 0.18, decay=0.12, seed=131), "新增条目(加号按钮，小上拨)"))

    s20 = gel(0.24)
    add_at(s20, 0.0, tone(style, freq("A3"), 0.16, seed=132))
    add_at(s20, 0.05, mellow(style, "F3", 0.16, vel=0.8))
    o.append(("S-20", "suiji_s20_item_delete.wav", -4.0, s20, "条目删除滑出(下行轻点)"))

    o.append(("S-21", "suiji_s21_step_up.wav", -5.0,
              tone(style, freq("B4"), 0.12, seed=133), "数字步进 +(上拨)"))
    o.append(("S-22", "suiji_s22_step_down.wav", -5.0,
              tone(style, freq("E3"), 0.12, seed=134), "数字步进 -(下拨)"))
    o.append(("S-23", "suiji_s23_thumb_pick.wav", -5.5,
              tone(style, freq("D5"), 0.16, decay=0.10, seed=135), "缩略图/图片选中"))

    s24 = gel(0.22)
    add_at(s24, 0.0, tone(style, freq("G4"), 0.14, vel=0.7, decay=0.10, seed=136))
    add_at(s24, 0.05, tone(style, freq("A4"), 0.16, vel=0.65, decay=0.10, seed=137))
    o.append(("S-24", "suiji_s24_toast.wav", -6.5, s24, "Toast 轻提示弹出(极轻双音)"))

    o.append(("S-25", "suiji_s25_copy_ok.wav", -4.5,
              tone(style, freq("C5"), 0.18, decay=0.12, seed=138), "复制成功(单音轻点)"))
    o.append(("S-26", "suiji_s26_focus.wav", -7.0,
              tone(style, freq("B4"), 0.12, vel=0.6, decay=0.08, seed=139), "输入框聚焦(极轻提示，可关)"))

    # --- T 组 · 计时 -----------------------------------------------------
    o.append(("T-01", "suiji_t01_timer_start.wav", -1.5,
              tone(style, freq("A4"), 0.45, decay=0.18, seed=140), "母乳/睡眠计时开始(此后全程无声)"))
    t02 = gel(0.46)
    add_at(t02, 0.0, mellow(style, "A3", 0.24))
    add_at(t02, 0.07, mellow(style, "E3", 0.28, vel=0.9))
    o.append(("T-02", "suiji_t02_timer_pause.wav", -2.5, t02, "计时暂停(下行，材质变闷)"))
    t03 = gel(0.46)
    add_at(t03, 0.0, mellow(style, "E3", 0.24))
    add_at(t03, 0.07, mellow(style, "A3", 0.28, vel=0.9))
    o.append(("T-03", "suiji_t03_timer_resume.wav", -2.5, t03, "计时恢复(上行，与暂停一听即辨)"))

    t04 = gel(1.00)
    for i, n in enumerate(("C5", "G4", "E4")):
        add_at(t04, i * 0.11, tone(style, freq(n), 0.55 - i * 0.1,
                                    vel=0.95 - i * 0.05, decay=0.20, seed=141 + i))
    add_at(t04, 0.33, mellow(style, "A4", 0.45, vel=0.16))
    o.append(("T-04", "suiji_t04_timer_end.wav", -5.0, t04, "计时结束(夜间为纯振动，此为发声版)"))

    # --- E 组 · 成就/情感 ------------------------------------------------
    scales = {
        "v1": ("G4", "A4", "B4", "D5", "E5"),
        "v2": ("A4", "B4", "C#5", "E5", "F#5"),
        "v3": ("D4", "F#4", "A4", "B4", "D5"),
        "v4": ("E4", "G4", "A4", "B4", "E5"),
        "v5": ("C4", "D4", "E4", "G4", "A4"),
    }
    spacing = {"v1": 0.085, "v2": 0.10, "v3": 0.078, "v4": 0.11, "v5": 0.092}
    cheer_chord = {
        "v1": ("G4", "B4", "D5"),
        "v2": ("A4", "C#5", "E5"),
        "v3": ("D4", "A4", "D5"),
        "v4": ("E4", "B4", "E5"),
        "v5": ("C4", "G4", "C5"),
    }
    for k, sc in scales.items():
        buf = gel(1.90)
        for i, n in enumerate(sc):
            add_at(buf, i * spacing[k], tone(style, freq(n), 0.85 - i * 0.06,
                                               vel=0.62 + i * 0.07, decay=0.26, seed=150 + i))
        add_at(buf, 0.34, win_pad(style, cheer_chord[k], 1.30, vel=0.16, seed=160 + int(k[1])))
        tt = t_axis(1.4)
        air = np.random.RandomState(len(sc)).uniform(-1, 1, len(tt))
        air = bi_lowpass(air, 2200) * env_ad(tt, 0.12, 0.45)
        add_at(buf, 0.30, 0.05 * air)
        o.append((f"E-01_{k}", f"suiji_e01_milestone_{k}.wav", +1.5, buf,
                  f"里程碑首次达成 变体{k[-1]}(琶音+风格欢呼垫音，随机播放)"))

    o.append(("E-03", "suiji_e03_curve_point.wav", -9.0,
              tone(style, freq("D5"), 0.26, vel=0.8, decay=0.16, seed=170), "生长曲线新数据点落位"))

    e04 = gel(0.75)
    add_at(e04, 0.0, tone(style, freq("E4"), 0.45, decay=0.18, seed=171))
    add_at(e04, 0.09, tone(style, freq("B4"), 0.60, vel=0.9, decay=0.18, seed=172))
    o.append(("E-04", "suiji_e04_journal_ready.wav", -3.0, e04, "AI 日记生成成功，进入待确认"))

    t = t_axis(0.45)
    f = freq("G4")
    e05 = np.sin(2 * np.pi * f * t) * env_exp(t, 0.14)
    e05 += 0.18 * np.sin(2 * np.pi * f * 1.5 * t) * env_exp(t, 0.07)
    e05 = bi_lowpass(e05, 2000)
    o.append(("E-05", "suiji_e05_journal_basic.wav", -5.0, e05, "AI 降级基础版(中性，禁止失败音)"))

    e06 = gel(0.85)
    for i, n in enumerate(("A4", "F#4", "D4")):
        add_at(e06, i * 0.135, tone(style, freq(n), 0.6 - i * 0.05, decay=0.20, seed=173 + i))
    e06 = reverb(e06, mix=0.24, tail=0.45)
    o.append(("E-06", "suiji_e06_journal_archive.wav", -2.0, e06, "AI 日记归档(落印感，带轻混响尾)"))

    e07v = {
        "v1": ("百日 100 天", ("D5", "A4", "F#4", "D4"), 0.15),
        "v2": ("周岁 1 岁", ("E5", "B4", "G4", "E4"), 0.165),
    }
    for k, (label, seq, sp) in e07v.items():
        buf = gel(1.15)
        for i, n in enumerate(seq):
            add_at(buf, i * sp, tone(style, freq(n), 0.6 - i * 0.06,
                                      vel=0.8 + i * 0.03, decay=0.20, seed=180 + i))
        o.append((f"E-07_{k}", f"suiji_e07_card_{k}.wav", -1.5, buf,
                  f"纪念卡生成完成 {label}(纪念而非庆祝)"))

    e08 = gel(0.85)
    add_at(e08, 0.0, tone(style, freq("F4"), 0.5, decay=0.18, seed=185))
    add_at(e08, 0.1, tone(style, freq("C4"), 0.65, vel=0.9, decay=0.18, seed=186))
    o.append(("E-08", "suiji_e08_video_done.wav", -4.0, e08, "成长视频合成完成(过程中无进度音)"))

    e09 = gel(0.75)
    add_at(e09, 0.0, tone(style, freq("E4"), 0.4, decay=0.16, seed=187))
    add_at(e09, 0.085, tone(style, freq("A3"), 0.55, vel=0.88, decay=0.16, seed=188))
    o.append(("E-09", "suiji_e09_pdf_export_done.wav", -4.0, e09, "PDF 成长档案导出完成"))

    e10 = gel(1.05)
    for i, n in enumerate(("D5", "E5")):
        add_at(e10, i * 0.11, tone(style, freq(n), 0.4, vel=0.85, decay=0.20, seed=190 + i))
    for i, n in enumerate(("G4", "A4")):
        add_at(e10, 0.40 + i * 0.11, tone(style, freq(n), 0.6, vel=0.92, decay=0.20, seed=192 + i))
    o.append(("E-10", "suiji_e10_member_joined.wav", -0.5, e10, "家人成功加入家庭空间(呼应式欢迎动机)"))

    e11 = gel(0.66)
    for i, n in enumerate(("C5", "E5", "G5")):
        add_at(e11, i * 0.08, tone(style, freq(n), 0.34 - i * 0.04,
                                    vel=0.8 - i * 0.05, decay=0.18, seed=195 + i))
    o.append(("E-11", "suiji_e11_first_record.wav", -1.0, e11, "首次记录达成(新手小庆祝，弱于里程碑)"))

    e12 = gel(0.95)
    for i, n in enumerate(("A4", "F#4", "D4")):
        add_at(e12, i * 0.12, tone(style, freq(n), 0.4, decay=0.18, seed=198 + i))
    add_at(e12, 0.40, tone(style, freq("E4"), 0.45, vel=0.8, decay=0.18, seed=201))
    e12 = reverb(e12, mix=0.18, tail=0.35)
    o.append(("E-12", "suiji_e12_week_streak.wav", -1.5, e12, "连续记录满 7 天(温和纪念，非激励音)"))

    return [(i, f, r, x, s) for (i, f, r, x, s) in o]


# ---------------------------------------------------------------- 主流程

def write_wav(out_dir, name, x):
    with wave.open(os.path.join(out_dir, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(x.tobytes())


def run_style(style):
    out_dir = os.path.join(HERE, f"wav-{style}")
    os.makedirs(out_dir, exist_ok=True)
    np.random.seed(20261112)

    specs = build(style)
    shaped = []
    for sid, fn, rel, x, scene in specs:
        y = shape(normalize(x))
        check_hf(sid, y)
        shaped.append((sid, fn, rel, y, scene))

    ref = min(CEIL / (plr(x) * 10 ** (rel / 20)) for _, _, rel, x, _ in shaped)
    g = 10 ** (GLOBAL_GAIN_DB / 20)

    results = []
    for sid, fn, rel, x, scene in shaped:
        y = x / krms(x) * ref * 10 ** (rel / 20) * g
        y = soft_clip(y)
        y = quantize(y)
        xf = y.astype(float) / 32768
        write_wav(out_dir, fn, y)
        results.append({
            "id": sid, "file": fn, "scene": scene, "target_rel_db": rel,
            "title": TITLES[re.sub(r"_v\d+$", "", sid)],
            "duration_ms": round(ms(xf), 1),
            "peak_dbfs": round(20 * math.log10(np.max(np.abs(xf)) + 1e-12), 1),
            "lufs": round(lufs(xf), 1),
            "plr_db": round(20 * math.log10(plr(x)), 1),
            "rel_lufs_vs_s03": round(20 * math.log10(krms(xf) / (ref * g) + 1e-12), 2),
            "hf_energy_pct_above_3k5": round(hf_ratio(xf) * 100, 2),
        })

    man = {
        "project": "岁记 Baby Growth Log",
        "style": style,
        "sample_rate": SR, "bit_depth": 16, "channels": 1,
        "reference": "rel_lufs_vs_s03 以 S-03(保存成功)为 0dB 基准",
        "acceptance": {
            "hf_ratio_limit_pct": 12.0, "peak_limit_dbfs": -0.5,
            "ladder_tolerance_db": 1.0,
        },
        "items": results,
    }
    with open(os.path.join(HERE, f"manifest-{style}.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)

    bad = 0
    for r in results:
        flag = (r["hf_energy_pct_above_3k5"] > 12 or r["peak_dbfs"] > -0.5
                or abs(r["rel_lufs_vs_s03"] - r["target_rel_db"]) > 1.0)
        bad += flag
        mark = "!" if flag else " "
        print(f"{mark}{r['id']:<10} {r['duration_ms']:>7.1f}ms "
              f"{r['peak_dbfs']:>7.1f}dB {r['lufs']:>6.1f} "
              f"实测 {r['rel_lufs_vs_s03']:>5.1f}/{r['target_rel_db']:>5.1f}dB "
              f"高频 {r['hf_energy_pct_above_3k5']:>6.2f}%  {r['file']}")
    print(f"\n[{style}] 基准 ref={ref:.4f}，{len(results)} 条，超差 {bad} 条 -> {out_dir}\n")
    return results


def main():
    for style in STYLES:
        run_style(style)


if __name__ == "__main__":
    main()
