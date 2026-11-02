import os, json

ROOT = "D:/project/traeData/suiji"
OUT = os.path.join(ROOT, "suiji-icons/ctl-v2")
manifest = json.load(open(os.path.join(OUT, "manifest.json"), encoding="utf8"))

GROUPS = [
    ("01 基础控件", ["40-ctl-btn-confirm", "41-ctl-btn-add", "42-ctl-tag", "43-ctl-tag-filter",
                     "44-ctl-badge-dot", "45-ctl-avatar", "46-ctl-loading"]),
    ("02 表单控件", ["47-ctl-input", "48-ctl-clear", "49-ctl-search-voice", "50-ctl-switch",
                     "51-ctl-checkbox", "52-ctl-radio", "53-ctl-slider", "54-ctl-numberbox",
                     "55-ctl-rate", "56-ctl-segment", "57-ctl-picker", "58-ctl-upload"]),
    ("03 导航控件", ["59-ctl-nav-back", "60-ctl-nav-more", "61-ctl-tabs", "62-ctl-steps", "63-ctl-cell"]),
    ("04 反馈控件", ["64-ctl-modal-warn", "65-ctl-modal-info", "66-ctl-modal-ok", "67-ctl-popup",
                     "68-ctl-toast", "69-ctl-empty", "70-ctl-skeleton", "71-ctl-progress", "72-ctl-ring"]),
    ("05 日期时间", ["73-ctl-calendar", "74-ctl-calendar-range"]),
]
LABEL = {
    "40-ctl-btn-confirm": ("按钮 · 主要/确认", "u-button"), "41-ctl-btn-add": ("按钮 · 新增", "u-button"),
    "42-ctl-tag": ("标签", "u-tag"), "43-ctl-tag-filter": ("标签 · 筛选", "u-tag"),
    "44-ctl-badge-dot": ("徽标红点", "u-badge"), "45-ctl-avatar": ("头像", "u-avatar"),
    "46-ctl-loading": ("加载中", "u-loading-icon"), "47-ctl-input": ("输入框 / 多行文本", "u-input"),
    "48-ctl-clear": ("输入框 · 清除", "u-input"), "49-ctl-search-voice": ("搜索 · 语音", "u-search"),
    "50-ctl-switch": ("开关", "u-switch"), "51-ctl-checkbox": ("复选框", "u-checkbox"),
    "52-ctl-radio": ("单选框", "u-radio"), "53-ctl-slider": ("滑块", "u-slider"),
    "54-ctl-numberbox": ("步进器", "u-number-box"), "55-ctl-rate": ("评分", "u-rate"),
    "56-ctl-segment": ("分段器", "u-subsection"), "57-ctl-picker": ("选择器", "u-picker"),
    "58-ctl-upload": ("图片上传", "u-upload"), "59-ctl-nav-back": ("导航 · 返回", "u-navbar"),
    "60-ctl-nav-more": ("导航 · 更多", "u-navbar"), "61-ctl-tabs": ("选项卡", "u-tabs"),
    "62-ctl-steps": ("步骤条", "u-steps"), "63-ctl-cell": ("单元格列表", "u-cell"),
    "64-ctl-modal-warn": ("对话框 · 危险", "u-modal"), "65-ctl-modal-info": ("对话框 · 信息", "u-modal"),
    "66-ctl-modal-ok": ("对话框 · 成功", "u-modal"), "67-ctl-popup": ("底部面板", "u-popup"),
    "68-ctl-toast": ("轻提示 / 通知栏", "u-toast"), "69-ctl-empty": ("空状态", "u-empty"),
    "70-ctl-skeleton": ("骨架屏", "u-skeleton"), "71-ctl-progress": ("线性进度", "u-line-progress"),
    "72-ctl-ring": ("环形进度", "u-circle-progress"), "73-ctl-calendar": ("日历 · 单选", "u-calendar"),
    "74-ctl-calendar-range": ("日历 · 区间", "u-calendar"),
}
bg = {(m["ip"], m["name"]): m["bg"] for m in manifest}
ips = {m["ip"] for m in manifest}
names = {m["name"] for m in manifest}

rows = []
for g, items in GROUPS:
    cards = []
    for n in items:
        if n not in names:
            continue
        title, comp = LABEL[n]
        figs = []
        for ip in ("bear", "duck"):
            if (ip, n) not in bg:
                continue
            figs.append(
                '<figure><div class="ic"><img src="rail/%s/%s.jpg" alt="%s" loading="lazy"></div>'
                '<figcaption>%s <b>%s</b></figcaption></figure>' % (ip, n, title, ip, bg[(ip, n)]))
        cards.append(
            '<article class="card"><div class="icons">%s</div>'
            '<div class="meta"><div class="row1"><span class="label">%s</span>'
            '<span class="file">%s.jpg</span></div><div class="scene"><code>&lt;%s&gt;</code></div></div></article>'
            % ("".join(figs), title, n, comp))
    rows.append('<section class="group"><div class="group-head"><h2>%s</h2><span>%d 个控件</span></div>'
                '<div class="grid">%s</div></section>' % (g, len([i for i in items if i in names]), "".join(cards)))

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>岁记 · 控件图标 ctl-v2 · 小熊 / 小鸭</title>
<style>
  :root { --bg:#FFF8F0; --surface:#fff; --border:#F3E4D3; --text:#5B4636; --sub:#9C8878;
          --primary:#F7A15C; --r-lg:24px; --r-pill:999px; --sh:0 2px 8px rgba(180,110,60,.10); }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:"PingFang SC","HarmonyOS Sans SC","MiSans","Microsoft YaHei",sans-serif;
         color:var(--text); background:radial-gradient(1100px 560px at 12% -8%, rgba(247,161,92,.14), transparent 60%),
         radial-gradient(900px 480px at 96% 108%, rgba(95,192,140,.14), transparent 55%), var(--bg);
         padding:40px 24px 64px; }
  .wrap { max-width:1120px; margin:0 auto; }
  header { text-align:center; margin-bottom:26px; }
  header h1 { font-size:26px; font-weight:800; }
  header p { font-size:13.5px; color:var(--sub); margin-top:10px; line-height:1.9; }
  header p b { color:var(--primary); }
  .chips { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-top:14px; }
  .chip { font-size:11.5px; font-weight:700; color:var(--sub); background:var(--surface);
          border:1px solid var(--border); border-radius:var(--r-pill); padding:6px 14px; }
  .group { margin-bottom:32px; }
  .group-head { display:flex; align-items:baseline; gap:10px; margin-bottom:12px; }
  .group-head h2 { font-size:17px; font-weight:800; }
  .group-head span { font-size:12px; color:var(--sub); }
  .grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }
  @media (max-width:900px){ .grid{grid-template-columns:repeat(2,1fr);} }
  @media (max-width:580px){ .grid{grid-template-columns:1fr;} }
  .card { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-lg);
          padding:13px; box-shadow:var(--sh); }
  .icons { display:flex; gap:9px; }
  .icons figure { flex:1; min-width:0; }
  .ic { width:100%; aspect-ratio:1/1; border-radius:var(--r-lg); overflow:hidden; background:#FDF6EE; }
  .ic img { width:100%; height:100%; object-fit:cover; display:block; }
  figcaption { text-align:center; font-size:10.5px; color:var(--sub); margin-top:5px; font-weight:700; }
  figcaption b { font-family:Consolas,monospace; font-weight:400; margin-left:3px; }
  .meta { margin-top:9px; }
  .row1 { display:flex; align-items:center; gap:8px; }
  .label { font-size:14px; font-weight:800; }
  .file { font-size:10px; color:var(--sub); margin-left:auto; font-family:Consolas,monospace; }
  .scene { font-size:11.5px; color:var(--sub); margin-top:4px; }
  code { font-family:Consolas,monospace; background:#FFF1E2; color:#B47714; padding:1px 6px; border-radius:6px; }
  footer { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-lg);
           padding:20px 24px; box-shadow:var(--sh); font-size:12.5px; color:var(--sub); line-height:1.9; }
  footer b { color:var(--text); }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>岁记 · 控件图标 <b>ctl-v2</b></h1>
  <p>为 <b>components.html</b> 的 uview-plus 控件补齐的配套图标 · 小熊「岁岁」× 小鸭「叽叽」双 IP 同构<br>
     满版平涂底色 · 无外框 · 角色占幅约 55% · 与 bear-v2 / duck-v2 现有 30 张同一画风与画布规格</p>
  <div class="chips"><span class="chip">原图 1920×1920 JPG</span><span class="chip">rail/ 预览方图</span>
    <span class="chip">png512/ 512×512 圆角 PNG（半径 115，与现有 assets 一致）</span>
    <span class="chip">编号段 40–74</span></div>
</header>
%BODY%
<footer>
  <b>目录</b> src1920/ 1920 原图 · rail/ 预览方图 · png512/ 可直接引用的圆角透明 PNG（对应 suiji-ui-v2/assets/icons 用法）<br>
  <b>接入</b> 把 png512/bear 与 png512/duck 分别拷入 assets/icons/bear、assets/icons/duck 即可按 data-ic 现有机制换肤；本目录为纯新增，未改动 suiji-icons/bear-v2、duck-v2 与 suiji-ui-v2 的任何既有文件。
</footer>
</div>
</body>
</html>
""".replace("%BODY%", "".join(rows))

open(os.path.join(OUT, "preview.html"), "w", encoding="utf8").write(html)
print("preview.html written,", len([m for m in manifest]), "files in manifest")
