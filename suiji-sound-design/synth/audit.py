"""按《岁记-交互音效需求表-v1.0》§七 验收标准做客观审计，输出 review/audit.md。

覆盖可机检的条目：A-06(高频占比)、A-09(响度阶梯)、§2.1(峰值/淡入淡出/裁尾)、
§六(变体必须互不相同)。A-01/A-02/A-03/A-04/A-05/A-07/A-08 属主观或真机项，
脚本只列出待人工签核。
"""

import json
import math
import os
import wave

import numpy as np

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
WAV = os.path.join(HERE, "wav")
OUT = os.path.join(HERE, "..", "review")

PEAK_CEIL_DB = -3.0
HF_CEIL_PCT = 8.0
LOUD_TOL_DB = 1.0


def load(name):
    with wave.open(os.path.join(WAV, name), "rb") as w:
        assert w.getnchannels() == 1 and w.getframerate() == SR and w.getsampwidth() == 2, name
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    return raw.astype(float) / 32768


def hf_pct(x):
    nper, hop = 2048, 1024
    if len(x) < nper:
        x = np.pad(x, (0, nper - len(x)))
    win = np.hanning(nper)
    fr = np.fft.rfftfreq(nper, 1 / SR)
    hi = tot = 0.0
    for s in range(0, len(x) - nper + 1, hop):
        m = np.abs(np.fft.rfft(x[s:s + nper] * win)) ** 2
        tot += m[fr > 60].sum()
        hi += m[fr > 3500].sum()
    return 100 * hi / (tot + 1e-18)


def headroom_db(x):
    """首样本相对峰值的电平，验证 §2.1 的 0-3ms 淡入（防咔哒）。"""
    return 20 * math.log10(abs(x[0]) / (np.max(np.abs(x)) + 1e-12) + 1e-12)


def tail_db(x):
    return 20 * math.log10(np.max(np.abs(x[-8:])) + 1e-12)


def corr(a, b):
    n = min(len(a), len(b))
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    return float((a * b).sum() / (np.sqrt((a ** 2).sum() * (b ** 2).sum()) + 1e-12))


def main():
    os.makedirs(OUT, exist_ok=True)
    items = json.load(open(os.path.join(HERE, "manifest.json"), encoding="utf-8"))["items"]
    by_id = {it["id"]: load(it["file"]) for it in items}

    fails, rows = [], []
    for it in items:
        x = by_id[it["id"]]
        peak = 20 * math.log10(np.max(np.abs(x)) + 1e-12)
        hf = hf_pct(x)
        dev = it["rel_lufs_vs_s03"] - it["target_rel_db"]
        checks = {
            "峰值<=-3dBFS": peak <= PEAK_CEIL_DB + 0.05,
            "高频<=8%": hf <= HF_CEIL_PCT,
            "响度偏差<=1dB": abs(dev) <= LOUD_TOL_DB,
            "淡入无跳变": headroom_db(x) < -40,
            "尾部收干净": tail_db(x) < -45,
        }
        bad = [k for k, v in checks.items() if not v]
        fails += [f"{it['id']}: {b}" for b in bad]
        rows.append((it["id"], it["file"], it["duration_ms"], it["rel_lufs_vs_s03"],
                     it["target_rel_db"], round(peak, 1), round(hf, 2), "PASS" if not bad else "FAIL"))

    # §六 变体差异性：同组变体不得是同一素材的复制
    groups = {"S-03": ["S-03_v1", "S-03_v2"],
              "E-01": [f"E-01_v{k}" for k in range(1, 6)],
              "E-07": ["E-07_v1", "E-07_v2"]}
    diff_notes = []
    for g, ids in groups.items():
        worst = 1.0
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                worst = min(worst, corr(by_id[ids[i]], by_id[ids[j]]))
        ok = worst < 0.85
        diff_notes.append((g, len(ids), round(worst, 3), ok))
        if not ok:
            fails.append(f"{g} 变体相关性 {worst:.2f} 过高，视为重复素材")

    lines = ["# 岁记音效 · 客观审计报告", "",
             f"素材 {len(items)} 条 ｜ 采样 {SR}Hz/16bit/单声道 ｜ "
             f"判定阈值：峰值 ≤{PEAK_CEIL_DB}dBFS、3.5kHz 以上能量 ≤{HF_CEIL_PCT}%、"
             f"响度对目标偏差 ≤{LOUD_TOL_DB}dB", "",
             "| ID | 文件 | 时长 | 实测相对 | 目标 | 峰值 | 高频占比 | 判定 |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    lines += ["", "## 变体差异性（需求表 §六）", "",
              "| 组 | 变体数 | 组内最大互相关 | 判定 |", "| --- | --- | --- | --- |"]
    for g, n, c, ok in diff_notes:
        lines.append(f"| {g} | {n} | {c} | {'PASS' if ok else 'FAIL'} |")
    lines += ["", "## 机检结论", "",
              f"- 未通过项：{len(fails)}", *[f"  - {f}" for f in fails], "",
              "## 需真机/人工签核的条目", "",
              "| 验收项 | 为何无法机检 | 建议做法 |", "| --- | --- | --- |",
              "| A-01 静音路径完整性 | 依赖系统 DND、TalkBack、应用内分档开关的联动 | "
              "四态各录一段屏幕录制，核对每条音效均有等价振动或视觉反馈 |",
              "| A-02 夜间压力测试 | 主观听感 + 真实卧室声学 | 23:40、媒体音量 20%、距人耳 1m，"
              "≥3 人评分 T-04 + S-03 + E-01 全链路，『不惊醒婴儿』≥4/5 |",
              "| A-03 时序穿帮 | 需断网/弱网/500 注入 | 与 NFR-06 联测，确认 S-03 绝不误播 |",
              "| A-04 情绪预算 | 语义判断 | 盲听除 E-01/E-07/E-10 外的全部素材，确认无庆祝语汇 |",
              "| A-05 医疗红线 | 属交互设计约束 | 复核体温≥38℃、低于 P3、晚于参考范围三场景无警示音 |",
              "| A-07 无骚扰性 | 需真实操作流 | 连续 20 次记录，检查叠音与重复触发 |",
              "| A-08 时长预算 | 需与埋点联测 | 对比开关音效前后的 G-01 P95 记录耗时 |", ""]

    with open(os.path.join(OUT, "audit.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"审计完成：{len(items)} 条素材，未通过 {len(fails)} 项 -> review/audit.md")
    for f in fails:
        print("  FAIL", f)


if __name__ == "__main__":
    main()
