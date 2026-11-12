"""生成双风格全量对比试听页 full-preview/index.html。

两套风格各 46 条：bubble 软合成气泡 / drop 水滴气泡。
顶部切换风格，下方按 S 交互 / T 计时 / E 成就分组；点卡片试听，可整组连播。
音频走相对路径（file:// 可直接打开），数据与包络内联。
"""

import json
import os
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STY_DIR = os.path.join(ROOT, "synth-styles")

STYLE_META = {
    "bubble": ("软合成气泡风", "圆润正弦 + 二次泛音，音头轻上滑，现代轻快"),
    "drop": ("水滴气泡风", "频率下扫 + 快衰减，短促水滴感，轻快可爱"),
}

GROUPS = {
    "S": ("交互与点击", "主按钮、列表项、选择、保存、拦截、开合等即时反馈"),
    "T": ("计时", "开始 / 暂停 / 恢复 / 结束"),
    "E": ("成就与情感", "里程碑欢呼、纪念、归档、导出、家人加入等低频高价值事件"),
}

CSS = """
:root{
  --bg:#f7f4ee; --card:#fffdf9; --line:#e8e1d6; --ink:#2b2723; --muted:#8c8178;
  --accent:#b4714a; --s:#b4714a; --t:#5c7f6f; --e:#8a6a9c;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.6 "PingFang SC","Microsoft YaHei","Hiragino Sans GB",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased}
header{position:sticky;top:0;z-index:10;background:rgba(247,244,238,.94);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:18px 28px 14px}
h1{margin:0 0 4px;font-size:19px;letter-spacing:.02em}
h1 small{font-weight:400;color:var(--muted);font-size:13px;margin-left:10px}
.sub{margin:0;color:var(--muted);font-size:13px}
.tabs{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
.tab{font:inherit;font-size:13.5px;color:var(--ink);background:var(--card);
  border:1px solid var(--line);border-radius:999px;padding:6px 16px;cursor:pointer}
.tab[aria-pressed=true]{background:var(--ink);color:#fff;border-color:var(--ink)}
.controls{display:flex;align-items:center;gap:14px;margin-top:12px;flex-wrap:wrap}
.controls label{font-size:13px;color:var(--muted)}
input[type=range]{width:180px;accent-color:var(--accent);vertical-align:middle}
button{font:inherit;font-size:13px;color:var(--ink);background:var(--card);
  border:1px solid var(--line);border-radius:8px;padding:5px 12px;cursor:pointer}
button:hover{background:#fff;border-color:#d8cec0}
button[aria-pressed=true]{background:var(--ink);color:#fff;border-color:var(--ink)}
.note{margin-top:10px;font-size:12.5px;color:var(--muted);background:#f1ebe1;
  border:1px solid var(--line);border-radius:8px;padding:8px 12px;line-height:1.7}
.note b{color:#5c534b}
main{padding:8px 28px 60px}
section{margin-top:26px}
h2{font-size:14px;letter-spacing:.08em;margin:0 0 2px;display:flex;align-items:baseline;gap:10px}
h2 .dot{width:8px;height:8px;border-radius:50%;display:inline-block}
h2 span{font-weight:400;color:var(--muted);font-size:12px;letter-spacing:0}
.gdesc{margin:0 0 14px;color:var(--muted);font-size:12.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));gap:12px}
.card{position:relative;background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:13px 14px 11px;cursor:pointer;overflow:hidden;transition:border-color .15s,box-shadow .15s}
.card:hover{border-color:#d9cfc0;box-shadow:0 2px 10px rgba(90,70,50,.06)}
.card:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.card.playing{border-color:var(--accent);box-shadow:0 2px 14px rgba(180,113,74,.16)}
.card::after{content:"";position:absolute;left:0;bottom:0;height:2px;width:calc(var(--p,0)*100%);
  background:var(--accent);opacity:.9;transition:width .06s linear}
.head{display:flex;align-items:center;gap:9px}
.badge{font:600 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em;
  color:#fff;background:var(--accent);border-radius:5px;padding:4px 6px;flex:none}
.gS .badge{background:var(--s)} .gT .badge{background:var(--t)} .gE .badge{background:var(--e)}
h3{margin:0;font-size:14.5px;font-weight:600;letter-spacing:.01em}
.play{margin-left:auto;font-size:11px;color:var(--muted);border:1px solid var(--line);
  border-radius:999px;padding:1px 8px;flex:none}
.card.playing .play{color:#fff;background:var(--accent);border-color:var(--accent)}
.scene{margin:7px 0 0;font-size:12.5px;color:var(--muted);line-height:1.45;min-height:36px}
.wave{margin:9px 0 8px;color:#cfc4b6}
.wave svg{display:block;width:100%;height:34px}
.wave svg path{fill:currentColor}
.card.playing .wave{color:var(--accent)}
.meta{display:flex;flex-wrap:wrap;gap:4px 12px;margin:0;padding:0;list-style:none;
  font:11.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}
.meta b{font-weight:600;color:#5c534b}
footer{margin:40px 28px 0;padding-top:14px;border-top:1px solid var(--line);
  color:var(--muted);font-size:12px;line-height:1.8}
code{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;background:#efe9df;padding:1px 5px;border-radius:4px}
"""

JS = """
const cards = [...document.querySelectorAll('.card')];
const audio = new Audio();
audio.preload = 'none';
const vol = document.getElementById('vol');
const volLabel = document.getElementById('volLabel');
const night = document.getElementById('night');
let current = null, queue = [], curStyle = 'bubble';

function setVol(v){audio.volume=v/100;volLabel.textContent=v+'%';
  night.setAttribute('aria-pressed', v<=25?'true':'false');}
function clearCard(){if(current){current.classList.remove('playing');current.style.setProperty('--p',0);}current=null;}
function stop(){audio.pause();clearCard();queue=[];}
function visibleCards(){return cards.filter(c=>c.dataset.style===curStyle);}
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
    const list=visibleCards().filter(c=>c.dataset.group===g);
    stop();queue=list.slice(1);if(list.length)start(list[0]);});});

document.querySelectorAll('.tab').forEach(t=>{
  t.addEventListener('click',()=>{stop();curStyle=t.dataset.style;
    document.querySelectorAll('.tab').forEach(x=>x.setAttribute('aria-pressed',x===t?'true':'false'));
    cards.forEach(c=>c.style.display=c.dataset.style===curStyle?'':'none');});});

vol.addEventListener('input',()=>setVol(+vol.value));
night.addEventListener('click',()=>{const v=night.getAttribute('aria-pressed')==='true'?80:20;
  vol.value=v;setVol(v);});
document.addEventListener('keydown',e=>{if(e.key==='Escape')stop();});
setVol(+vol.value);
cards.forEach(c=>{if(c.dataset.style!==curStyle)c.style.display='none';});
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
    d = "M" + "L".join(top) + "L" + "L" + "L".join(reversed(bot)) + "Z"
    return f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true"><path d="{d}"/></svg>'


def card_html(style, it, src, env):
    g = it["id"][0]
    rel = it["target_rel_db"]
    rel_s = "0.0 dB" if rel == 0 else f"{rel:+.1f} dB"
    return f"""      <article class="card g{g}" data-group="{g}" data-style="{style}" data-src="{src}"
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
          <li><b>{it['lufs']:.1f}</b> LUFS</li>
          <li>高频 <b>{it['hf_energy_pct_above_3k5']:.2f}%</b></li>
        </ul>
      </article>"""


def main():
    by_style = {}
    total = 0
    for style in STYLE_META:
        man = json.load(open(os.path.join(STY_DIR, f"manifest-{style}.json"), encoding="utf-8"))
        by_style[style] = man["items"]
        total += len(man["items"])

    sections_html = []
    for g, (name, desc) in GROUPS.items():
        cards = []
        for style in STYLE_META:
            for it in by_style[style]:
                if it["id"][0] != g:
                    continue
                p = os.path.join(STY_DIR, f"wav-{style}", it["file"])
                src = f"../synth-styles/wav-{style}/{it['file']}"
                cards.append(card_html(style, it, src, envelope(p)))
        sections_html.append(f"""    <section>
      <h2><i class="dot" style="background:var(--{g.lower()})"></i>{name}
        <span>{len(by_style['bubble']) and len([c for c in cards if 'bubble' in c])} 条 / 风格</span></h2>
      <p class="gdesc">{desc}</p>
      <div class="controls" style="margin:-6px 0 12px">
        <button data-seq="{g}">依次试听当前风格这组</button>
      </div>
      <div class="grid">
{chr(10).join(cards)}
      </div>
    </section>""")

    tabs = "".join(
        f'<button class="tab" data-style="{s}" aria-pressed="{"true" if s == "bubble" else "false"}">'
        f"{meta[0]}</button>"
        for s, meta in STYLE_META.items()
    )

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>岁记 · 双风格全量音效对比</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>岁记 · 双风格全量音效对比<small>每套 {len(by_style['bubble'])} 条 · 共 {total} 条</small></h1>
  <p class="sub">顶部切换两种风格，同一条目位置不变，便于直接 A/B 对比；点卡片试听，Esc 停止。</p>
  <div class="tabs">{tabs}</div>
  <div class="controls">
    <label for="vol">试听音量</label>
    <input id="vol" type="range" min="0" max="100" value="80" step="1">
    <span id="volLabel" style="font:13px ui-monospace,monospace;color:var(--muted);width:38px">80%</span>
    <button id="night" aria-pressed="false">夜间 20%</button>
  </div>
  <div class="note">
    <b>两套风格共用同一响度阶梯：</b>以「保存成功」为 0 dB 基准，点击 -1.5~-9、成就 +1.5；
    峰值 ≤ -0.5 dBFS，时长 &lt;2s，高频占比 ≤12%。本页为试听母版 WAV，定稿后再转 ogg/mp3 接入。
  </div>
</header>
<main>
{chr(10).join(sections_html)}
</main>
<footer>
  素材目录 <code>synth-styles/wav-bubble/</code>、<code>synth-styles/wav-drop/</code>；参数见对应 <code>manifest-*.json</code>。<br>
  重新生成：<code>python synth-styles/synthesize.py</code> 后 <code>python full-preview/build_full_preview.py</code>
</footer>
<script>{JS}</script>
</body>
</html>"""

    out = os.path.join(HERE, "index.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"生成 {out}（{total} 条卡片，{len(html) / 1024:.0f}KB）")


if __name__ == "__main__":
    main()
