/* ================================================================
   岁记 · 控件样式库 v1.0 · 交互逻辑
   ================================================================ */

/* ---------- 图标（与 suiji-prototype ICONS 同源，描边改 currentColor） ---------- */
const SW = 'xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
const ICONS = {
  search:      `<svg ${SW}><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`,
  bell:        `<svg ${SW}><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>`,
  chevronDown: `<svg ${SW}><path d="m6 9 6 6 6-6"/></svg>`,
  plus:        `<svg ${SW} stroke-width="2.4"><path d="M5 12h14"/><path d="M12 5v14"/></svg>`,
  moon:        `<svg ${SW}><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>`,
  camera:      `<svg ${SW}><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>`,
  sparkles:    `<svg ${SW}><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>`,
  image:       `<svg ${SW}><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/></svg>`,
  pencil:      `<svg ${SW}><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .624.625l4.353-1.32a2 2 0 0 0 .83-.497Z"/></svg>`,
  trash:       `<svg ${SW}><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>`,
  download:    `<svg ${SW}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/></svg>`,
  alert:       `<svg ${SW}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
  x:           `<svg ${SW}><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`,
  check:       `<svg ${SW} stroke-width="3"><path d="M20 6 9 17l-5-5"/></svg>`,
  cloud:       `<svg ${SW}><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>`,
  users:       `<svg ${SW}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`
};

const $  = (id) => document.getElementById(id);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/* ---------- 图标水合：[data-icon] ---------- */
$$("[data-icon]").forEach((el) => {
  el.innerHTML = ICONS[el.dataset.icon] || "";
  if (el.dataset.icColor) el.style.color = el.dataset.icColor;
  if (el.dataset.icSize) { el.style.width = el.dataset.icSize + "px"; el.style.height = el.dataset.icSize + "px"; }
});
/* 空状态插画图标着色 */
$$("[data-ic-size]").forEach((el) => { el.style.color = "var(--primary)"; });

/* ================================================================
   Toast
   ================================================================ */
const TOAST_ICON = { ok: "check", err: "alert", info: "sparkles" };
const TOAST_COLOR = { ok: "#8FD8A6", err: "#FF9B9B", info: "#FFC24B" };
function toast(kind, msg) {
  const area = $("toast-area");
  while (area.children.length >= 3) area.removeChild(area.firstChild);
  const t = document.createElement("div");
  t.className = "toast";
  t.innerHTML = `${ICONS[TOAST_ICON[kind] || "sparkles"]}<span>${msg}</span>`;
  t.querySelector("svg").style.color = TOAST_COLOR[kind] || "#FFC24B";
  area.appendChild(t);
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 320); }, 2200);
}

/* ================================================================
   浮层开关（data-open / data-close / 遮罩点击 / data-ok）
   ================================================================ */
function openOv(id) {
  const ov = $(id);
  ov.classList.add("show");
  if (id === "ov-date" || id === "ov-dt") syncPicker(ov);
  if (id === "ov-time" || id === "ov-dt") syncTimePicker(ov);
}
function closeOv(ov) { ov.classList.remove("show"); }

document.addEventListener("click", (e) => {
  const opener = e.target.closest("[data-open]");
  if (opener) { openOv(opener.dataset.open); return; }

  const okBtn = e.target.closest("[data-ok]");
  if (okBtn) { closeOv(okBtn.closest(".overlay")); toast("ok", okBtn.dataset.ok); return; }

  const closer = e.target.closest("[data-close]");
  if (closer) { closeOv(closer.closest(".overlay")); return; }

  if (e.target.classList && e.target.classList.contains("overlay")) { closeOv(e.target); return; }

  /* 下拉菜单外点关闭 */
  $$(".pick-wrap.open").forEach((w) => { if (!w.contains(e.target)) w.classList.remove("open"); });
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") $$(".overlay.show").forEach(closeOv);
});

/* Toast 触发按钮 */
$$("[data-toast]").forEach((b) => {
  b.addEventListener("click", () => { const [k, m] = b.dataset.toast.split("|"); toast(k, m); });
});

/* Loading 演示：2 秒后自动关闭 */
$$('[data-open="ov-loading"]').forEach((b) => {
  b.addEventListener("click", () => {
    setTimeout(() => { closeOv($("ov-loading")); toast("ok", "已保存"); }, 2000);
  });
});

/* 表单弹窗：空值禁用保存 */
const renameInput = $("dlg-rename"), renameOk = $("dlg-rename-ok");
renameInput.addEventListener("input", () => { renameOk.disabled = !renameInput.value.trim(); });
renameOk.addEventListener("click", () => { closeOv($("ov-form")); toast("ok", `空间已重命名为「${renameInput.value.trim()}」`); });

/* ================================================================
   滚轮选择器
   ================================================================ */
const ROW = 36;
const pad2 = (n) => String(n).padStart(2, "0");

function fillCol(list, values, labelFn) {
  list.innerHTML = values.map((v) => `<div class="pk-item" data-val="${v}">${labelFn(v)}</div>`).join("");
}
function markSel(list) {
  const i = Math.max(0, Math.min(list.children.length - 1, Math.round(list.scrollTop / ROW)));
  Array.from(list.children).forEach((el, j) => el.classList.toggle("sel", j === i));
  refreshTitle(list.closest(".picker"));
}

/* 标题实时回显已选值，滚轮高亮之外给用户第二确认 */
function refreshTitle(pk) {
  if (!pk) return;
  const title = pk.querySelector(".pk-title");
  if (!title) return;
  if (!title.dataset.base) title.dataset.base = title.textContent;
  const parts = [];
  if (pk.querySelector('[data-col="year"]')) parts.push(dateText(pk));
  if (pk.querySelector('[data-col="hour"]')) parts.push(timeText(pk));
  title.textContent = parts.length ? `${title.dataset.base} · ${parts.join(" ")}` : title.dataset.base;
}
function scrollToVal(list, val) {
  const i = Array.from(list.children).findIndex((el) => el.dataset.val === String(val));
  if (i >= 0) list.scrollTop = i * ROW;
  markSel(list);
}
function getSel(list) {
  const s = list.querySelector(".pk-item.sel");
  return s ? s.dataset.val : (list.firstChild ? list.firstChild.dataset.val : null);
}
function bindCol(list) {
  let t;
  list.addEventListener("scroll", () => {
    markSel(list);
    clearTimeout(t);
    t = setTimeout(() => { if (list.dataset.col === "year" || list.dataset.col === "month") refreshDays(list.closest(".pk-body")); }, 80);
  });
}

const TODAY = new Date();
function buildDateGroup(body) {
  const years = [], y0 = TODAY.getFullYear() - 6, y1 = TODAY.getFullYear() + 1;
  for (let y = y0; y <= y1; y++) years.push(y);
  const months = Array.from({ length: 12 }, (_, i) => i + 1);
  fillCol(body.querySelector('[data-col="year"]'), years, (v) => v + "年");
  fillCol(body.querySelector('[data-col="month"]'), months, (v) => v + "月");
  fillCol(body.querySelector('[data-col="day"]'), Array.from({ length: 31 }, (_, i) => i + 1), (v) => v + "日");
  $$("[data-col]", body).forEach(bindCol);
}
function refreshDays(body) {
  const y = +getSel(body.querySelector('[data-col="year"]'));
  const m = +getSel(body.querySelector('[data-col="month"]'));
  const n = new Date(y, m, 0).getDate();
  const dayList = body.querySelector('[data-col="day"]');
  const cur = +getSel(dayList);
  fillCol(dayList, Array.from({ length: n }, (_, i) => i + 1), (v) => v + "日");
  scrollToVal(dayList, Math.min(cur || 1, n));
}
function buildTimeGroup(body) {
  fillCol(body.querySelector('[data-col="hour"]'), Array.from({ length: 24 }, (_, i) => i), (v) => pad2(v) + "时");
  fillCol(body.querySelector('[data-col="minute"]'), Array.from({ length: 12 }, (_, i) => i * 5), (v) => pad2(v) + "分");
  $$("[data-col]", body).forEach(bindCol);
}

/* 初始化所有滚轮 */
$$('[data-picker]').forEach((pk) => {
  $$(".pk-body", pk).forEach((g) => {
    if (g.querySelector('[data-col="year"]')) buildDateGroup(g);
    else buildTimeGroup(g);
  });
});

function syncPicker(ov) { /* 定位到日期默认值 */
  $$(".pk-body", ov).filter((g) => g.querySelector('[data-col="year"]')).forEach((g) => {
    scrollToVal(g.querySelector('[data-col="year"]'), TODAY.getFullYear());
    scrollToVal(g.querySelector('[data-col="month"]'), TODAY.getMonth() + 1);
    refreshDays(g);
    scrollToVal(g.querySelector('[data-col="day"]'), TODAY.getDate());
  });
}
function syncTimePicker(ov) {
  $$(".pk-body", ov).filter((g) => g.querySelector('[data-col="hour"]')).forEach((g) => {
    scrollToVal(g.querySelector('[data-col="hour"]'), TODAY.getHours());
    scrollToVal(g.querySelector('[data-col="minute"]'), Math.floor(TODAY.getMinutes() / 5) * 5);
  });
}
function dateText(ov) {
  const g = $$(".pk-body", ov).find((b) => b.querySelector('[data-col="year"]'));
  return `${getSel(g.querySelector('[data-col="year"]'))}年${+getSel(g.querySelector('[data-col="month"]'))}月${+getSel(g.querySelector('[data-col="day"]'))}日`;
}
function timeText(ov) {
  const g = $$(".pk-body", ov).find((b) => b.querySelector('[data-col="hour"]'));
  return `${getSel(g.querySelector('[data-col="hour"]'))}:${getSel(g.querySelector('[data-col="minute"]'))}`;
}

/* 快捷定位与确定 */
document.addEventListener("click", (e) => {
  const act = e.target.closest("[data-pk]");
  if (!act) return;
  const ov = act.closest(".overlay");
  switch (act.dataset.pk) {
    case "today": syncPicker(ov); break;
    case "now": syncTimePicker(ov); break;
    case "dt-now": syncPicker(ov); syncTimePicker(ov); break;
    case "date-ok": closeOv(ov); toast("ok", `已选择 ${dateText(ov)}`); applyQuickTime(ov); break;
    case "time-ok": closeOv(ov); toast("ok", `已选择 ${timeText(ov)}`); break;
    case "dt-ok": closeOv(ov); toast("ok", `已选择 ${dateText(ov)} ${timeText(ov)}`); break;
  }
});

/* 组合选择器的分段切换 */
$$('[data-picker="dt"] .pk-seg .metric-tab').forEach((tab) => {
  tab.addEventListener("click", () => {
    const pk = tab.closest(".picker");
    $$(".metric-tab", pk).forEach((t) => t.classList.toggle("active", t === tab));
    $$(".pk-body", pk).forEach((g) => g.classList.toggle("hidden", g.dataset.group !== tab.dataset.tab));
  });
});

/* ================================================================
   快捷时间 / 月龄 chips
   ================================================================ */
function applyQuickTime(ov) {
  const active = $("#quick-time .qchip.active");
  if (active && active.dataset.val === "自定义") {
    $("#quick-time-val").textContent = `已选：${dateText(ov)} · 来自自定义日期`;
  }
}
$$("#quick-time .qchip").forEach((chip) => {
  chip.addEventListener("click", () => {
    if (chip.dataset.val === "自定义") return; /* 由 data-open 打开滚轮 */
    $$("#quick-time .qchip").forEach((c) => c.classList.toggle("active", c === chip));
    const now = `${pad2(TODAY.getHours())}:${pad2(TODAY.getMinutes())}`;
    $("#quick-time-val").textContent = `已选：${chip.dataset.val} ${now} · 自动填充当前时间`;
  });
});

/* 月龄 chips 生成 */
(function buildMAge() {
  const wrap = $("m-age-pick");
  const vals = ["0月", "1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月", "1岁+"];
  wrap.innerHTML = vals.map((v, i) => `<button class="qchip${i === 5 ? " active" : ""}">${v}</button>`).join("");
})();

/* 通用 chips 组：单选互斥 / 多选切换 */
$$(".qchips").forEach((group) => {
  group.addEventListener("click", (e) => {
    const chip = e.target.closest(".qchip");
    if (!chip) return;
    if (group.dataset.mode === "single") $$(".qchip", group).forEach((c) => c.classList.toggle("active", c === chip));
    else chip.classList.toggle("active");
  });
});

/* ================================================================
   表单控件
   ================================================================ */
/* 开关 */
$$("[data-switch]").forEach((s) => s.addEventListener("click", () => s.classList.toggle("on")));

/* 复选项 */
$$("[data-check]").forEach((item) => {
  item.addEventListener("click", () => item.querySelector(".c-check").classList.toggle("on"));
});

/* 单选组 */
$$("[data-radio]").forEach((group) => {
  group.addEventListener("click", (e) => {
    const item = e.target.closest(".check-item");
    if (!item) return;
    $$(".c-check", group).forEach((c) => c.classList.toggle("on", c === item.querySelector(".c-check")));
  });
});

/* 步进器 */
$$(".num-stepper").forEach((st) => {
  const input = st.querySelector(".ns-input");
  const step = parseFloat(st.dataset.step), min = parseFloat(st.dataset.min), max = parseFloat(st.dataset.max);
  const dec = +(st.dataset.dec || 0);
  const clamp = (v) => Math.min(max, Math.max(min, v));
  $$("[data-dir]", st).forEach((b) => {
    b.addEventListener("click", () => {
      const v = parseFloat(input.value) || 0;
      input.value = (clamp(v + step * (+b.dataset.dir))).toFixed(dec);
    });
  });
  input.addEventListener("change", () => { input.value = clamp(parseFloat(input.value) || min).toFixed(dec); });
});

/* 多行文本计数 */
const note = $("note-demo"), noteCount = $("note-count");
note.addEventListener("input", () => {
  noteCount.textContent = `${note.value.length}/200`;
  noteCount.classList.toggle("max", note.value.length >= 200);
});

/* 下拉选择 */
$$(".pick-wrap").forEach((w) => {
  w.querySelector("[data-drop]").addEventListener("click", () => w.classList.toggle("open"));
  $$(".pm-item", w).forEach((it) => {
    it.addEventListener("click", () => {
      $$(".pm-item", w).forEach((x) => x.classList.toggle("sel", x === it));
      w.querySelector(".ds-val").textContent = it.dataset.val;
      w.classList.remove("open");
    });
  });
});

/* 搜索栏 */
const searchBar = $("search-demo"), searchInput = searchBar.querySelector(".search-input");
searchInput.addEventListener("input", () => searchBar.classList.toggle("has-val", !!searchInput.value));
searchBar.querySelector("[data-clear]").addEventListener("click", () => {
  searchInput.value = ""; searchInput.focus(); searchBar.classList.remove("has-val");
});

/* 照片添加（上限 6） */
const photoWrap = $("photo-demo"), photoAdd = photoWrap.querySelector("[data-photo-add]");
function refreshAdd() { photoAdd.style.display = $$(".photo-thumb", photoWrap).length >= 6 ? "none" : "flex"; }
photoAdd.addEventListener("click", () => {
  const thumb = document.createElement("div");
  thumb.className = "photo-thumb";
  thumb.innerHTML = `${ICONS.image}<button class="pt-del">${ICONS.x}</button>`;
  thumb.querySelector(".image-svg, svg").style.color = "var(--primary)";
  thumb.querySelector(".pt-del").addEventListener("click", (e) => { e.stopPropagation(); thumb.remove(); refreshAdd(); });
  photoWrap.insertBefore(thumb, photoAdd);
  refreshAdd();
});

/* ================================================================
   进度条演示
   ================================================================ */
$$("[data-pg]").forEach((b) => {
  b.addEventListener("click", () => {
    const fill = $("pg-demo");
    const w = Math.min(100, (parseFloat(fill.style.width) || 0) + 20);
    fill.style.width = w + "%";
    $("pg-label").textContent = `已用 ${(w / 10).toFixed(1)} GB`;
    if (w >= 100) toast("err", "存储空间已满");
  });
});
