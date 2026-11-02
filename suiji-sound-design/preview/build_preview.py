"""生成可离线打开的音效预览页 preview/index.html。

数据全部内联（manifest + 每条素材的包络），只有音频文件走相对路径，
所以直接双击 index.html 就能听，不需要起本地服务器（file:// 下 fetch 会被 CORS 拦）。

页面既是验收工具也是设计讨论的载体：
- 点卡片即听，一次只响一条，方便 A/B 比较；
- 每组可"依次试听"，用于 A-04 情绪预算盲听（29 条连续过一遍）；
- 音量可调，"夜间 20%"预设对应 A-02 的实测音量。
"""

import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SYNTH = os.path.join(ROOT, "synth")

GROUPS = {
    "S": ("交互音 · S 组", "点击、选择、保存、拦截等即时反馈"),
    "T": ("计时 · T 组", "开始 / 暂停 / 恢复 / 结束，靠音区与材质区分"),
    "E": ("成就与情感 · E 组", "里程碑、归档、导出等低频高价值事件"),
}

CSS = """
:root{
  --bg:#f7f4ee; --card:#fffdf9; --line:#e8e1d6; --ink:#2b2723; --muted:#8c8178;
  --accent:#b4714a; --s:#b4714a; --t:#5c7f6f; --e:#8a6a9c;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.6 "PingFang SC","Microsoft YaHei","Hiragino Sans GB",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;
}
header{
  position:sticky; top:0; z-index:10; background:rgba(247,244,238,.94);
  backdrop-filter:blur(8px); border-bottom:1px solid var(--line);
  padding:18px 28px 14px;
}
h1{margin:0 0 4px; font-size:19px; letter-spacing:.02em}
h1 small{font-weight:400; color:var(--muted); font-size:13px; margin-left:10px}
.sub{margin:0; color:var(--muted); font-size:13px}
.controls{display:flex; align-items:center; gap:14px; margin-top:12px; flex-wrap:wrap}
.controls label{font-size:13px; color:var(--muted)}
input[type=range]{width:180px; accent-color:var(--accent); vertical-align:middle}
button{
  font:inherit; font-size:13px; color:var(--ink); background:var(--card);
  border:1px solid var(--line); border-radius:8px; padding:5px 12px; cursor:pointer;
  transition:background .15s,border-color .15s;
}
button:hover{background:#fff; border-color:#d8cec0}
button[aria-pressed=true]{background:var(--ink); color:#fff; border-color:var(--ink)}
main{padding:8px 28px 60px}
section{margin-top:26px}
h2{
  font-size:14px; letter-spacing:.08em; margin:0 0 2px;
  display:flex; align-items:baseline; gap:10px;
}
h2 .dot{width:8px;height:8px;border-radius:50%;display:inline-block}
h2 span{font-weight:400;color:var(--muted);font-size:12px;letter-spacing:0}
.gdesc{margin:0 0 14px; color:var(--muted); font-size:12.5px}
.grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(268px,1fr)); gap:12px}
.card{
  position:relative; background:var(--card); border:1px solid var(--line);
  border-radius:12px; padding:13px 14px 11px; cursor:pointer; overflow:hidden;
  transition:border-color .15s, box-shadow .15s, transform .12s;
}
.card:hover{border-color:#d9cfc0; box-shadow:0 2px 10px rgba(90,70,50,.06)}
.card:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
.card.playing{border-color:var(--accent); box-shadow:0 2px 14px rgba(180,113,74,.16)}
.card::after{
  content:""; position:absolute; left:0; bottom:0; height:2px; width:calc(var(--p,0)*100%);
  background:var(--accent); opacity:.9; transition:width .06s linear;
}
.head{display:flex; align-items:center; gap:9px}
.badge{
  font:600 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace; letter-spacing:.04em;
  color:#fff; background:var(--accent); border-radius:5px; padding:4px 6px; flex:none;
}
.gS .badge{background:var(--s)} .gT .badge{background:var(--t)} .gE .badge{background:var(--e)}
h3{margin:0; font-size:15.5px; font-weight:600; letter-spacing:.01em}
.play{
  margin-left:auto; font-size:11px; color:var(--muted); border:1px solid var(--line);
  border-radius:999px; padding:1px 8px; flex:none;
}
.card.playing .play{color:#fff;background:var(--accent);border-color:var(--accent)}
.scene{margin:7px 0 0; font-size:12.5px; color:var(--muted); line-height:1.45; min-height:36px}
.wave{margin:9px 0 8px; color:#cfc4b6}
.wave svg{display:block; width:100%; height:34px}
.wave svg path{fill:currentColor}
.card.playing .wave{color:var(--accent)}
.meta{display:flex; flex-wrap:wrap; gap:4px 12px; margin:0; padding:0; list-style:none;
  font:11.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--muted)}
.meta b{font-weight:600; color:#5c534b}
footer{margin:40px 28px 0; padding-top:14px; border-top:1px solid var(--line);
  color:var(--muted); font-size:12px; line-height:1.8}
code{font:12px ui-monospace,SFMono-Regular,Menlo,monospace; background:#efe9df;
  padding:1px 5px; border-radius:4px}
"""

JS = """
const cards = [...document.querySelectorAll('.card')];
const audio = new Audio();
audio.preload = 'none';
const vol = document.getElementById('vol');
const volLabel = document.getElementById('volLabel');
const night = document.getElementById('night');
let current = null, queue = [];

function setVol(v) {
  audio.volume = v / 100;
  volLabel.textContent = v + '%';
  night.setAttribute('aria-pressed', v <= 25 ? 'true' : 'false');
}

function clearCard() {
  if (current) { current.classList.remove('playing'); current.style.setProperty('--p', 0); }
  current = null;
}

function stop() {
  audio.pause();
  clearCard();
  queue = [];
}

// start 只负责发一声，不动 queue；play 是用户点卡片的入口，会打断队列。
// 旧版 play 内部先调 stop() 把 queue 清空，导致"依次试听"永远只响第一条。
function start(card) {
  audio.pause();
  clearCard();
  current = card;
  card.style.setProperty('--p', 0);
  audio.src = card.dataset.src;
  card.classList.add('playing');
  audio.play().catch(() => {
    card.classList.remove('playing');
    card.querySelector('.play').textContent = '无法播放';
  });
}

function play(card) {
  if (current === card && !audio.paused) { stop(); return; }
  queue = [];
  start(card);
}

audio.addEventListener('timeupdate', () => {
  if (!current || !audio.duration) return;
  current.style.setProperty('--p', audio.currentTime / audio.duration);
});
audio.addEventListener('ended', () => {
  clearCard();
  if (queue.length) setTimeout(() => start(queue.shift()), 140);
});

cards.forEach(c => {
  c.tabIndex = 0;
  c.addEventListener('click', () => play(c));
  c.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); play(c); }
  });
});

document.querySelectorAll('[data-seq]').forEach(btn => {
  btn.addEventListener('click', () => {
    const g = btn.dataset.seq;
    const list = cards.filter(c => c.dataset.group === g);
    stop();
    queue = list.slice(1);
    start(list[0]);
  });
});

vol.addEventListener('input', () => setVol(+vol.value));
night.addEventListener('click', () => {
  const v = night.getAttribute('aria-pressed') === 'true' ? 80 : 20;
  vol.value = v; setVol(v);
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') stop(); });
setVol(+vol.value);
"""


def envelope(path, buckets=96):
    import wave
    with wave.open(path, "rb") as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
    edges = np.linspace(0, len(raw), buckets + 1).astype(int)
    env = np.array([np.max(np.abs(raw[edges[i]:edges[i + 1]])) if edges[i + 1] > edges[i] else 0.0
                    for i in range(buckets)], dtype=float)
    return env / (env.max() + 1e-9)


def wave_svg(env, w=210, h=34):
    mid = h / 2
    top, bot = [], []
    for i, a in enumerate(env):
        x = (i + 0.5) * w / len(env)
        y = a * (mid - 1.5)
        top.append(f"{x:.1f},{mid - y:.1f}")
        bot.append(f"{x:.1f},{mid + y:.1f}")
    d = "M" + "L".join(top) + "L" + "L".join(reversed(bot)) + "Z"
    return f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true"><path d="{d}"/></svg>'


def card_html(it, src, env):
    g = it["id"][0]
    rel = it["target_rel_db"]
    rel_s = "0.0 dB" if rel == 0 else f"{rel:+.1f} dB"
    return f"""      <article class="card g{g}" data-group="{g}" data-src="{src}"
               aria-label="播放 {it['title']}">
        <div class="head">
          <span class="badge">{it['id'].replace('_v', '·')}</span>
          <h3>{it['title']}</h3>
          <span class="play">▶</span>
        </div>
        <p class="scene">{it['scene']}</p>
        <div class="wave">{wave_svg(env)}</div>
        <ul class="meta">
          <li><b>{it['duration_ms']:.0f}</b> ms</li>
          <li><b>{rel_s}</b> 相对档</li>
          <li>峰值 <b>{it['peak_dbfs']:.1f}</b> dBFS</li>
          <li>高频 <b>{it['hf_energy_pct_above_3k5']:.2f}%</b></li>
        </ul>
      </article>"""


def main():
    man = json.load(open(os.path.join(SYNTH, "manifest.json"), encoding="utf-8"))
    items = man["items"]

    sections, missing = [], 0
    for g, (name, desc) in GROUPS.items():
        cards = []
        for it in items:
            if it["id"][0] != g:
                continue
            base = os.path.splitext(it["file"])[0]
            ogg = f"../synth/ogg/{base}.ogg"
            wav = f"../synth/wav/{it['file']}"
            if os.path.isfile(os.path.join(ROOT, "synth", "ogg", base + ".ogg")):
                src = ogg
            else:
                src = wav
            p = os.path.join(SYNTH, "wav", it["file"])
            if not os.path.isfile(p):
                missing += 1
                continue
            cards.append(card_html(it, src, envelope(p)))
        if cards:
            sections.append(f"""    <section>
      <h2><i class="dot" style="background:var(--{g.lower()})"></i>{name}
        <span>{len(cards)} 条</span></h2>
      <p class="gdesc">{desc}</p>
      <div class="controls" style="margin:-6px 0 12px">
        <button data-seq="{g}">依次试听整组</button>
      </div>
      <div class="grid">
{chr(10).join(cards)}
      </div>
    </section>""")

    total_s = sum(it["duration_ms"] for it in items) / 1000
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>岁记 · 音效预览</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>岁记 · 交互音效预览<small>v1.0 · {len(items) - missing} 条 · 共 {total_s:.1f} 秒</small></h1>
  <p class="sub">点击任意卡片试听，Esc 停止。响度档以 S-03「保存成功」为 0 dB 基准。</p>
  <div class="controls">
    <label for="vol">试听音量</label>
    <input id="vol" type="range" min="0" max="100" value="80" step="1">
    <span id="volLabel" style="font:13px ui-monospace,monospace;color:var(--muted);width:38px">80%</span>
    <button id="night" aria-pressed="false">夜间 20%</button>
  </div>
</header>
<main>
{chr(10).join(sections)}
</main>
<footer>
  相对档 = 以 S-03 为 0 dB 的 K 加权 RMS 阶梯；峰值与高频占比取自 <code>synth/manifest.json</code>。<br>
  音量滑杆只影响试听，不改变素材本身；验收请以 <code>review/audit.md</code> 的实测值为准。<br>
  重新生成：<code>python preview/build_preview.py</code>
</footer>
<script>{JS}</script>
</body>
</html>
"""
    out = os.path.join(HERE, "index.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"生成 {out}（{len(items) - missing} 条，{len(html) / 1024:.0f}KB）")
    if missing:
        print(f"警告：{missing} 条素材缺 wav，已跳过")


if __name__ == "__main__":
    main()
