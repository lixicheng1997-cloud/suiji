"""生成新颖范式示例试听页 novel-preview/index.html。

6 个方向各 2 条（点击代表 / 成就代表），响度已按 RMS 对齐便于横向比较。
音频走相对路径，file:// 双击可试听；数据与包络内联。
"""

import json
import os
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NOV = os.path.join(ROOT, "novel-samples")

CSS = """
:root{
  --bg:#f5f3f0; --card:#fffdfa; --line:#e7e0d6; --ink:#2b2723; --muted:#8c8178;
  --accent:#7a6aa8; --tap:#5c7f6f; --win:#b4714a;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.6 "PingFang SC","Microsoft YaHei","Hiragino Sans GB",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased}
header{position:sticky;top:0;z-index:10;background:rgba(245,243,240,.94);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:18px 28px 14px}
h1{margin:0 0 4px;font-size:19px;letter-spacing:.02em}
h1 small{font-weight:400;color:var(--muted);font-size:13px;margin-left:10px}
.sub{margin:0;color:var(--muted);font-size:13px}
.controls{display:flex;align-items:center;gap:14px;margin-top:12px;flex-wrap:wrap}
.controls label{font-size:13px;color:var(--muted)}
input[type=range]{width:180px;accent-color:var(--accent);vertical-align:middle}
button{font:inherit;font-size:13px;color:var(--ink);background:var(--card);
  border:1px solid var(--line);border-radius:8px;padding:5px 12px;cursor:pointer}
button:hover{background:#fff;border-color:#d8cec0}
.note{margin-top:10px;font-size:12.5px;color:var(--muted);background:#eee9f3;
  border:1px solid var(--line);border-radius:8px;padding:8px 12px;line-height:1.7}
.note b{color:#5c534b}
main{padding:8px 28px 60px}
section{margin-top:22px;background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:16px 18px}
.sthead{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px}
h2{font-size:16px;margin:0}
.tag{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:1px 9px}
.sdesc{margin:6px 0 0;font-size:13px}
.sfit{margin:4px 0 0;font-size:12.5px;color:var(--muted)}
.sfit b{color:var(--tap)}
.sfit .caution{color:#a06a4a}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));gap:12px;margin-top:14px}
.card{position:relative;background:#fff;border:1px solid var(--line);border-radius:12px;
  padding:13px 14px 11px;cursor:pointer;overflow:hidden;transition:border-color .15s,box-shadow .15s}
.card:hover{border-color:#d9cfc0;box-shadow:0 2px 10px rgba(90,70,50,.06)}
.card:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.card.playing{border-color:var(--accent);box-shadow:0 2px 14px rgba(122,106,168,.16)}
.card::after{content:"";position:absolute;left:0;bottom:0;height:2px;width:calc(var(--p,0)*100%);
  background:var(--accent);opacity:.9;transition:width .06s linear}
.head{display:flex;align-items:center;gap:9px}
.badge{font:600 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em;
  color:#fff;border-radius:5px;padding:4px 6px;flex:none}
.badge.tap{background:var(--tap)} .badge.win{background:var(--win)}
h3{margin:0;font-size:14.5px;font-weight:600}
.play{margin-left:auto;font-size:11px;color:var(--muted);border:1px solid var(--line);
  border-radius:999px;padding:1px 8px;flex:none}
.card.playing .play{color:#fff;background:var(--accent);border-color:var(--accent)}
.wave{margin:9px 0 8px;color:#cfc4b6}
.wave svg{display:block;width:100%;height:34px}
.wave svg path{fill:currentColor}
.card.playing .wave{color:var(--accent)}
.meta{display:flex;flex-wrap:wrap;gap:4px 12px;margin:0;padding:0;list-style:none;
  font:11.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}
.meta b{font-weight:600;color:#5c534b}
footer{margin:40px 28px 0;padding-top:14px;border-top:1px solid var(--line);
  color:var(--muted);font-size:12px;line-height:1.8}
code{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;background:#eee9f3;padding:1px 5px;border-radius:4px}
"""

JS = """
const cards=[...document.querySelectorAll('.card')];
const audio=new Audio();audio.preload='none';
const vol=document.getElementById('vol'),volLabel=document.getElementById('volLabel');
const night=document.getElementById('night');
let current=null,queue=[];
function setVol(v){audio.volume=v/100;volLabel.textContent=v+'%';
  night.setAttribute('aria-pressed',v<=25?'true':'false');}
function clearCard(){if(current){current.classList.remove('playing');current.style.setProperty('--p',0);}current=null;}
function stop(){audio.pause();clearCard();queue=[];}
function start(card){audio.pause();clearCard();current=card;card.style.setProperty('--p',0);
  audio.src=card.dataset.src;card.classList.add('playing');
  audio.play().catch(()=>card.classList.remove('playing'));}
function play(card){if(current===card&&!audio.paused){stop();return;}queue=[];start(card);}
audio.addEventListener('timeupdate',()=>{if(!current||!audio.duration)return;
  current.style.setProperty('--p',audio.currentTime/audio.duration);});
audio.addEventListener('ended',()=>{clearCard();if(queue.length)setTimeout(()=>start(queue.shift()),140);});
cards.forEach(c=>{c.tabIndex=0;c.addEventListener('click',()=>play(c));
  c.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();play(c);}});});
document.querySelectorAll('[data-seq]').forEach(btn=>{
  btn.addEventListener('click',()=>{const g=btn.dataset.seq;
    const list=cards.filter(c=>c.dataset.dir===g);stop();queue=list.slice(1);
    if(list.length)start(list[0]);});});
vol.addEventListener('input',()=>setVol(+vol.value));
night.addEventListener('click',()=>{const v=night.getAttribute('aria-pressed')==='true'?80:20;
  vol.value=v;setVol(v);});
document.addEventListener('keydown',e=>{if(e.key==='Escape')stop();});
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
    return f"""      <article class="card" data-dir="{it['dir']}" data-src="{src}"
               aria-label="播放 {it['title']} {it['role_label']}">
        <div class="head">
          <span class="badge {it['role']}">{it['role_label']}</span>
          <h3>{it['title']}</h3>
          <span class="play">▶</span>
        </div>
        <div class="wave">{wave_svg(env)}</div>
        <ul class="meta">
          <li><b>{it['duration_ms']:.0f}</b> ms</li>
          <li>峰值 <b>{it['peak_dbfs']:.1f}</b> dBFS</li>
          <li><b>{it['lufs']:.1f}</b> LUFS</li>
        </ul>
      </article>"""


def main():
    man = json.load(open(os.path.join(NOV, "manifest.json"), encoding="utf-8"))
    directions = man["directions"]
    items = man["items"]

    sections = []
    for d in directions:
        cards = []
        for it in [x for x in items if x["dir"] == d["key"]]:
            p = os.path.join(NOV, "wav", it["file"])
            src = f"../novel-samples/wav/{it['file']}"
            cards.append(card_html(it, src, envelope(p)))
        sections.append(f"""    <section>
      <div class="sthead">
        <h2>{d['name']}</h2><span class="tag">{d['key']}</span>
      </div>
      <p class="sdesc">{d['desc']}</p>
      <p class="sfit"><b>适合：</b>{d['fit']}　<span class="caution">注意：{d['caution']}</span></p>
      <div class="controls" style="margin-top:10px">
        <button data-seq="{d['key']}">依次试听这两条</button>
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
<title>岁记 · 新颖音效范式示例</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>岁记 · 新颖音效范式示例<small>6 个方向 · 各 2 条小示例</small></h1>
  <p class="sub">前面几套都是"敲一个乐音"，这批换了声音材质与动态范式；挑中方向后我再按它全量重做。</p>
  <div class="controls">
    <label for="vol">试听音量</label>
    <input id="vol" type="range" min="0" max="100" value="80" step="1">
    <span id="volLabel" style="font:13px ui-monospace,monospace;color:var(--muted);width:38px">80%</span>
    <button id="night" aria-pressed="false">夜间 20%</button>
  </div>
  <div class="note">
    <b>怎么听：</b>每类左边是点击代表、右边是成就代表；响度已按 RMS 对齐，比较音色差异而不是音量。
    这些是纯合成示意，若选定拟物 / 自然材质方向，也可以改用生成式真实采样（泡泡纸、软胶、水声等），质感会更真。
  </div>
</header>
<main>
{chr(10).join(sections)}
</main>
<footer>
  示例母版 WAV 在 <code>novel-samples/wav/</code>；参数见 <code>novel-samples/manifest.json</code>。<br>
  重新生成：<code>python novel-samples/render_novel.py</code> 后 <code>python novel-preview/build_novel_preview.py</code>
</footer>
<script>{JS}</script>
</body>
</html>"""

    out = os.path.join(HERE, "index.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"生成 {out}（{len(items)} 条，{len(html) / 1024:.0f}KB）")


if __name__ == "__main__":
    main()
