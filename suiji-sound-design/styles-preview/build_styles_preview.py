"""生成风格选型对比试听页 styles-preview/index.html。

数据内联（manifest + 包络），音频走相对路径，双击 file:// 即可试听。
- 每种风格 3 条示例：点击 / 保存成功 / 里程碑成就；
- 顶部标注风格特点、适合场景、需要注意的点；
- 对照当前线上卡林巴木质风（引用 synth-v11 成品）。
"""

import json
import os
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STY = os.path.join(ROOT, "styles")
V11 = os.path.join(ROOT, "synth-v11", "wav")

ROLE_BADGE = {"tap": "点击", "save": "保存", "win": "成就"}

CSS = """
:root{
  --bg:#f7f4ee; --card:#fffdf9; --line:#e8e1d6; --ink:#2b2723; --muted:#8c8178;
  --accent:#b4714a; --sel:#5c7f6f;
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
.note{margin-top:10px; font-size:12.5px; color:var(--muted); background:#f1ebe1;
  border:1px solid var(--line); border-radius:8px; padding:8px 12px; line-height:1.7}
.note b{color:#5c534b}
main{padding:8px 28px 60px}
section{margin-top:26px; background:var(--card); border:1px solid var(--line);
  border-radius:14px; padding:16px 18px}
section.ref{background:#f3eee6; border-style:dashed}
.sthead{display:flex; flex-wrap:wrap; align-items:baseline; gap:10px}
h2{font-size:16px; margin:0; letter-spacing:.02em}
.tag{font-size:11px; color:var(--muted); border:1px solid var(--line); border-radius:999px; padding:1px 9px}
.sdesc{margin:6px 0 0; font-size:13px; color:var(--ink)}
.sfit{margin:4px 0 0; font-size:12.5px; color:var(--muted)}
.sfit b{color:var(--sel)}
.sfit .caution{color:#a06a4a}
.grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(268px,1fr)); gap:12px; margin-top:14px}
.card{
  position:relative; background:#fff; border:1px solid var(--line);
  border-radius:12px; padding:13px 14px 11px; cursor:pointer; overflow:hidden;
  transition:border-color .15s, box-shadow .15s;
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
h3{margin:0; font-size:14.5px; font-weight:600; letter-spacing:.01em}
.play{margin-left:auto; font-size:11px; color:var(--muted); border:1px solid var(--line);
  border-radius:999px; padding:1px 8px; flex:none;}
.card.playing .play{color:#fff;background:var(--accent);border-color:var(--accent)}
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
function stop() { audio.pause(); clearCard(); queue = []; }
function start(card) {
  audio.pause(); clearCard();
  current = card; card.style.setProperty('--p', 0);
  audio.src = card.dataset.src;
  card.classList.add('playing');
  audio.play().catch(() => { card.classList.remove('playing'); });
}
function play(card) {
  if (current === card && !audio.paused) { stop(); return; }
  queue = []; start(card);
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
    stop(); queue = list.slice(1); start(list[0]);
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
    rel = it.get("rel_lufs")
    rel_s = "对照" if rel is None else ("0.0 dB" if rel == 0 else f"{rel:+.1f} dB")
    return f"""      <article class="card" data-group="{it['style']}" data-src="{src}"
               aria-label="播放 {it['title']}">
        <div class="head">
          <span class="badge">{ROLE_BADGE[it['role']]}</span>
          <h3>{it['title']}</h3>
          <span class="play">▶</span>
        </div>
        <div class="wave">{wave_svg(env)}</div>
        <ul class="meta">
          <li><b>{it['duration_ms']:.0f}</b> ms</li>
          <li><b>{rel_s}</b> 相对档</li>
          <li>峰值 <b>{it['peak_dbfs']:.1f}</b> dBFS</li>
          <li><b>{it['lufs']:.1f}</b> LUFS</li>
          <li>高频 <b>{it['hf_pct']:.2f}%</b></li>
        </ul>
      </article>"""


def main():
    man = json.load(open(os.path.join(STY, "manifest.json"), encoding="utf-8"))
    styles, items = man["styles"], man["items"]

    sections, missing = [], 0
    for st in styles:
        sid = st["key"]
        cards = []
        for it in items:
            if it["style"] != sid:
                continue
            if it.get("external"):
                p = os.path.join(V11, it["file"])
                src = f"../synth-v11/wav/{it['file']}"
            else:
                p = os.path.join(STY, "wav", it["file"])
                src = f"../styles/wav/{it['file']}"
            if not os.path.isfile(p):
                missing += 1
                continue
            cards.append(card_html(it, src, envelope(p)))
        if not cards:
            continue
        ref_cls = " ref" if sid == "kalimba" else ""
        sections.append(f"""    <section{ref_cls}>
      <div class="sthead">
        <h2>{st['name']}</h2>
        <span class="tag">{len(cards)} 条示例</span>
      </div>
      <p class="sdesc">{st['desc']}</p>
      <p class="sfit"><b>适合：</b>{st['fit']}　<span class="caution">注意：{st['caution']}</span></p>
      <div class="controls" style="margin-top:10px">
        <button data-seq="{sid}">依次试听这组</button>
      </div>
      <div class="grid">
{chr(10).join(cards)}
      </div>
    </section>""")

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>岁记 · 音效风格选型试听</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>岁记 · 音效风格选型<small>6 种候选 + 当前线上对照 · 每种 3 条示例</small></h1>
  <p class="sub">点击卡片试听同角色在不同风格下的差别；选定一种后，我再按该风格全量重做全部交互与成就音。</p>
  <div class="controls">
    <label for="vol">试听音量</label>
    <input id="vol" type="range" min="0" max="100" value="80" step="1">
    <span id="volLabel" style="font:13px ui-monospace,monospace;color:var(--muted);width:38px">80%</span>
    <button id="night" aria-pressed="false">夜间 20%</button>
  </div>
  <div class="note">
    <b>怎么听：</b>同一行对照「点击 · 主按钮 / 保存成功 / 里程碑成就」三个角色。示例只是风格示意，
    时长和编排在定稿全量重做时还会调整；响度按角色排档（点击 -1.5、保存 0、成就 +1.5），便于横向比较。
    底部虚线块是当前线上的卡林巴木质风，作为被替换的对照基准。
  </div>
</header>
<main>
{chr(10).join(sections)}
</main>
<footer>
  示例母版 WAV 在 <code>styles/wav/</code>，对照素材在 <code>synth-v11/wav/</code>；相对档为 K 加权 RMS，以「保存成功」为 0 dB。<br>
  重新生成：<code>python styles/render_styles.py</code> 后 <code>python styles-preview/build_styles_preview.py</code>
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
