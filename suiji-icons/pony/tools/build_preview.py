#!/usr/bin/env python3
"""扫描 pony 产物目录，生成 preview-pony.html（可重复执行）。"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LABELS = {
    "01-feeding": "喂养", "02-sleep": "睡眠", "03-milestone": "里程碑", "04-photo": "照片",
    "05-measure": "测量", "06-poop": "便便", "07-temp": "体温", "08-med": "用药",
    "09-text-mood": "心情", "09-voice": "语音",
    "10-tab-home": "时光轴", "11-tab-growth": "成长", "12-tab-family": "家庭", "13-tab-me": "我的",
    "20-fn-diary": "日记", "21-fn-remind": "提醒", "22-fn-backup": "备份", "23-fn-privacy": "隐私",
    "24-fn-search": "搜索", "25-fn-notify": "通知", "26-fn-export": "导出", "27-fn-trash": "回收站",
    "28-fn-invite": "邀请", "29-fn-babies": "多宝宝", "30-fn-elder": "长辈模式", "31-fn-compare": "成长对比",
    "32-fn-card": "成长卡片", "33-fn-video": "视频", "34-fn-vaccine": "疫苗", "35-fn-audit": "操作审计",
}

TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>岁记 · pony 小马图标库预览</title>
<style>
  :root { --ink:#5B4636; --sub:#9C8878; --line:#F1E2D2; --primary:#F58FB6; --deep:#D9628F; }
  * { box-sizing:border-box; }
  body { margin:0; padding:32px 28px 64px; font-family:"PingFang SC","Microsoft YaHei",sans-serif; color:var(--ink);
         background:radial-gradient(circle at 18% 8%, #FFF3F7 0%, #FFF8F0 45%, #F6F1FF 100%); }
  h1 { margin:0 0 6px; font-size:26px; letter-spacing:.5px; }
  .lead { margin:0 0 22px; color:var(--sub); font-size:13px; }
  .chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:26px; }
  .chip { display:flex; align-items:center; gap:7px; padding:6px 12px; border-radius:999px; background:#fff;
          border:1px solid var(--line); font-size:12px; box-shadow:0 4px 14px rgba(214,158,99,.10); }
  .dot { width:14px; height:14px; border-radius:50%; }
  section { background:rgba(255,255,255,.82); border:1px solid var(--line); border-radius:22px; padding:20px 22px; margin-bottom:22px;
            box-shadow:0 14px 40px rgba(180,110,60,.08); }
  h2 { margin:0 0 4px; font-size:17px; }
  .hint { margin:0 0 16px; color:var(--sub); font-size:12px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(128px,1fr)); gap:14px; }
  .cell { border-radius:16px; padding:12px 8px 10px; text-align:center; background:#fff; border:1px solid var(--line); }
  .checker { background-image:linear-gradient(45deg,#F3EDE7 25%,transparent 25%),linear-gradient(-45deg,#F3EDE7 25%,transparent 25%),
             linear-gradient(45deg,transparent 75%,#F3EDE7 75%),linear-gradient(-45deg,transparent 75%,#F3EDE7 75%);
             background-size:14px 14px; background-position:0 0,0 7px,7px -7px,-7px 0; }
  .cell img { width:88px; height:88px; object-fit:contain; display:block; margin:0 auto 8px; }
  .name { font-size:11px; color:var(--sub); word-break:break-all; }
  .label { font-size:13px; font-weight:600; margin-bottom:2px; }
  .tabs { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:16px; }
  .tabcard { border-radius:18px; border:1px solid var(--line); background:#fff; padding:14px; text-align:center; }
  .tabcard img { width:96px; height:96px; }
  .play { font-size:11px; color:var(--deep); margin-top:6px; }
  .mock { margin-top:18px; padding:18px 0 12px; border-radius:26px; background:rgba(255,255,255,.94);
          border:2px solid var(--line); box-shadow:0 -10px 40px rgba(180,110,60,.10); display:flex; }
  .mock .t { flex:1; display:flex; flex-direction:column; align-items:center; gap:4px; cursor:pointer; }
  .mock .t img { width:56px; height:56px; transition:transform .3s cubic-bezier(.34,1.56,.64,1); }
  .mock .t span { font-size:12px; font-weight:700; color:var(--sub); }
  .mock .t.on img { transform:scale(1.28) translateY(-6px); }
  .mock .t.on span { color:var(--deep); }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th,td { text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); }
  th { color:var(--sub); font-weight:600; font-size:12px; }
  code { background:#FBF3EA; padding:2px 6px; border-radius:6px; font-size:12px; }
</style>
</head>
<body>
<h1>岁记 · pony 小马图标库</h1>
<p class="lead">第三套 IP：奶粉小马 + 薰衣草鬃毛 · 纯透明无底板 · 全量统一画布 · 底部导航 APNG 动图</p>
<div class="chips">
  <div class="chip"><span class="dot" style="background:#FFD9E4"></span>身体 #FFD9E4</div>
  <div class="chip"><span class="dot" style="background:#C6A8F0"></span>鬃毛 #C6A8F0</div>
  <div class="chip"><span class="dot" style="background:#A8D8F0"></span>鬃毛尾 #A8D8F0</div>
  <div class="chip"><span class="dot" style="background:#7A4A5C"></span>描边 #7A4A5C</div>
  <div class="chip"><span class="dot" style="background:#F58FB6"></span>primary #F58FB6</div>
  <div class="chip"><span class="dot" style="background:#D9628F"></span>primary-deep #D9628F</div>
</div>

<section>
  <h2>① 记录类别图标 ×10</h2>
  <p class="hint">对应 <code>utils/mock.js</code> 的 TYPES.png，源文件 <code>1024/*.png</code>，App 用 <code>512/*.png</code>。</p>
  <div class="grid">__TYPES__</div>
</section>

<section>
  <h2>② 底部导航（静帧）×4</h2>
  <p class="hint">与 bear / duck 同名的 <code>10-tab-home…13-tab-me</code>，可直接被 <code>&lt;sj-icon&gt;</code> 消费。</p>
  <div class="grid">__TABS__</div>
</section>

<section>
  <h2>③ 底部导航（动态 APNG）×4</h2>
  <p class="hint">每个 4 帧循环（170ms/帧），256×256、约 100KB/张。鼠标悬停切换静帧↔动图对比。</p>
  <div class="tabs">__ANIM__</div>
  <div class="mock" id="mock">__MOCK__</div>
  <p class="hint" style="margin-top:10px">上为悬浮胶囊底栏还原：点击页签可切换激活态（放大上浮），激活页签播放 APNG。</p>
</section>

<section>
  <h2>④ 功能入口图标 ×16</h2>
  <p class="hint">设置页 / 工具格的 <code>20-fn-* … 35-fn-*</code>。</p>
  <div class="grid">__FNS__</div>
</section>

<section>
  <h2>⑤ 规格与产物</h2>
  <table>
    <tr><th>产物</th><th>尺寸</th><th>数量</th><th>用途</th></tr>
    <tr><td><code>1024/</code></td><td>1024×1024 RGBA 透明</td><td>30</td><td>源图 / 大屏展示 / 二次编辑</td></tr>
    <tr><td><code>512/</code></td><td>512×512 RGBA 透明</td><td>30</td><td>App 直接投放（与 bear/duck 同规格）</td></tr>
    <tr><td><code>tab-anim/frames/</code></td><td>512×512 单帧</td><td>16</td><td>帧轮播兜底（小程序端不支持 APNG 时）</td></tr>
    <tr><td><code>tab-anim/apng/</code></td><td>512×512 4 帧</td><td>4</td><td>无损母版</td></tr>
    <tr><td><code>tab-anim/apng-256/</code></td><td>256×256 4 帧 · 128 色</td><td>4</td><td>App 投放用动图</td></tr>
    <tr><td><code>tab-anim/sprites/</code></td><td>2048×512 横向雪碧图</td><td>4</td><td>CSS steps() 动画方案</td></tr>
    <tr><td><code>raw/</code></td><td>1024×1024 白底</td><td>34</td><td>生成原图留档（可重跑管线）</td></tr>
  </table>
</section>

<script>
document.querySelectorAll('.tabcard img').forEach(function (img) {
  var anim = img.getAttribute('data-anim'), still = img.getAttribute('data-still');
  img.addEventListener('mouseenter', function () { img.src = still; });
  img.addEventListener('mouseleave', function () { img.src = anim; });
});
var TABS = __TABJSON__;
var mock = document.getElementById('mock');
TABS.forEach(function (t, i) {
  var d = document.createElement('div');
  d.className = 't' + (i === 0 ? ' on' : '');
  d.innerHTML = '<img src="tab-anim/apng-256/' + t.k + '.png" alt="' + t.l + '"><span>' + t.l + '</span>';
  d.onclick = function () { mock.querySelectorAll('.t').forEach(function (x) { x.classList.remove('on'); }); d.classList.add('on'); };
  mock.appendChild(d);
});
</script>
</body>
</html>
"""


def card(name, src, size="88px"):
    return (
        f'<div class="cell checker"><img src="{src}/{name}.png" width="{size}" height="{size}" alt="{name}">'
        f'<div class="label">{LABELS.get(name, name)}</div><div class="name">{name}</div></div>'
    )


def main():
    stills = sorted(os.path.splitext(f)[0] for f in os.listdir(os.path.join(ROOT, "512")))
    types = [n for n in stills if n[:2] in {"01", "02", "03", "04", "05", "06", "07", "08", "09"}]
    tabs = [n for n in stills if n[0] == "1" and "-tab-" in n]
    fns = [n for n in stills if n.startswith("2") or n.startswith("3")]
    anim = sorted(os.path.splitext(f)[0] for f in os.listdir(os.path.join(ROOT, "tab-anim", "apng-256")))

    anim_html = "".join(
        f'<div class="tabcard"><img src="tab-anim/apng-256/{a}.png" '
        f'data-anim="tab-anim/apng-256/{a}.png" data-still="512/{a}.png" alt="{a}">'
        f'<div class="label">{LABELS.get(a, a)}</div>'
        f'<div class="name">{a}.png · 4 帧</div><div class="play">悬停看静帧</div></div>'
        for a in anim
    )
    tab_json = json.dumps([{"k": a, "l": LABELS.get(a, a)} for a in anim], ensure_ascii=False)
    html = (
        TPL.replace("__TYPES__", "".join(card(n, "512") for n in types))
        .replace("__TABS__", "".join(card(n, "512") for n in tabs))
        .replace("__ANIM__", anim_html)
        .replace("__MOCK__", "")
        .replace("__FNS__", "".join(card(n, "512") for n in fns))
        .replace("__TABJSON__", tab_json)
    )
    out = os.path.join(ROOT, "preview-pony.html")
    with open(out, "w", encoding="utf-8") as fp:
        fp.write(html)
    print(f"生成 {out}（类型 {len(types)} · tab {len(tabs)} · 动图 {len(anim)} · 功能 {len(fns)}）")


if __name__ == "__main__":
    main()
