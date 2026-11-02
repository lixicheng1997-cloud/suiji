/* ================================================================
   岁记官网 v4 · 站点层交互
   依赖 phone.js 已暴露的全局：$ / $$ / REDUCED / applyTheme /
   confettiIn / spawnHearts / burstConfetti / PHONE
   ================================================================ */
(function () {
  "use strict";

  const CFG = window.SUIJI_CONFIG || {};
  const DL = CFG.download || {};

  /* ============================================================
     1. Toast
     ============================================================ */
  let toastTimer;
  function toast(msg) {
    const el = $("#sjToast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 2200);
  }

  /* ============================================================
     2. 主题切换（小熊 / 小鸭）：配色 + 全站图标 + 背景
     ============================================================ */
  function setTheme(t, animate) {
    applyTheme(t, animate);
    document.body.dataset.theme = t;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", t === "duck" ? "#FFF6D9" : "#FFF8F0");
    const btn = $("#sjThemeBtn");
    if (btn) btn.title = t === "duck" ? "切换到小熊主题" : "切换到小鸭主题";
    try { localStorage.setItem("suiji-theme-v4", t); } catch (e) {}
  }

  function bindTheme() {
    $$("[data-set-theme]").forEach(b => b.addEventListener("click", () => {
      const t = b.dataset.setTheme;
      if (document.body.dataset.theme === t) return;
      setTheme(t, true);
      confettiIn($("#sjConfetti"), 18);
      toast(t === "duck" ? "已切换到小鸭叽叽 · 奶油明黄" : "已切换到小熊岁岁 · 蜂蜜暖棕");
    }));
    let saved = null;
    try { saved = localStorage.getItem("suiji-theme-v4"); } catch (e) {}
    setTheme(saved === "duck" ? "duck" : "bear", false);
  }

  /* ============================================================
     3. 平台识别 + 下载
     ============================================================ */
  const UA = navigator.userAgent;
  const IS_IOS = /iPad|iPhone|iPod/.test(UA) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const IS_ANDROID = /Android/i.test(UA);
  const IS_WECHAT = /MicroMessenger/i.test(UA);
  const PLATFORM = IS_IOS ? "ios" : IS_ANDROID ? "android" : "pc";

  function fileUrl(store) {
    const u = (DL[store] || "").trim();
    if (!u) return "";
    if (/^https?:\/\//i.test(u)) return u;
    return new URL(u, location.href).href;
  }

  function detectDevice() {
    if (PLATFORM !== "pc") {
      const btn = $('[data-store="' + PLATFORM + '"]');
      if (btn) {
        const tag = document.createElement("span");
        tag.className = "sj-rec-tag";
        tag.textContent = "当前设备推荐";
        btn.appendChild(tag);
      }
      const auto = $('[data-store="auto"]');
      if (auto) {
        auto.dataset.store = PLATFORM;
        const url = fileUrl(PLATFORM);
        if (url) auto.dataset.href = url;
      }
    }
    // iOS 未上架 → 按钮文案标注
    const iosText = $("#sjIosBtnText");
    if (iosText && !DL.ios) iosText.textContent = "即将上架 · 订阅通知";
    const iosMeta = $("#sjMetaIos");
    if (iosMeta) {
      iosMeta.textContent = (DL.ios ? CFG.iosReq : CFG.iosReq + " · 上架中") +
        (IS_IOS ? " · 当前设备" : "");
    }
    const aMeta = $("#sjMetaAndroid");
    if (aMeta) {
      aMeta.textContent = CFG.androidReq + " · " + CFG.apkSize +
        (IS_ANDROID ? " · 当前设备" : "");
    }
  }

  function openStore(store) {
    if (store === "auto") store = PLATFORM;
    const url = fileUrl(store);
    if (!url) {
      toast(store === "ios"
        ? "iOS 版正在上架 App Store，扫码可订阅上架通知"
        : "下载地址尚未配置");
      return;
    }
    if (store === "ios") {
      // iOS 走商店链接，不做本地下载
      window.open(url, "_blank", "noopener");
      return;
    }
    const a = document.createElement("a");
    a.href = url;
    a.download = "suiji-" + (CFG.version || "1.0.0") + ".apk";
    document.body.appendChild(a);
    a.click();
    a.remove();
    toast("开始下载 Android 安装包 v" + (CFG.version || "1.0.0"));
    confettiIn($("#sjConfetti"), 16);
  }

  function bindDownload() {
    $$("[data-store]").forEach(b => b.addEventListener("click", () => openStore(b.dataset.store)));
    $$(".sj-copy").forEach(btn => btn.addEventListener("click", async () => {
      const url = fileUrl(btn.dataset.copy) || (CFG.siteUrl || location.href);
      try {
        await navigator.clipboard.writeText(url);
        toast("下载链接已复制，发给家人就能直接装");
      } catch (e) {
        const t = document.createElement("textarea");
        t.value = url;
        document.body.appendChild(t);
        t.select();
        try { document.execCommand("copy"); toast("下载链接已复制"); }
        catch (e2) { toast("复制失败，可长按地址栏手动复制"); }
        t.remove();
      }
    }));
  }

  /* ============================================================
     3.1 扫码进入的自动下载（二维码指向 ?download=apk）
     ============================================================ */
  function showWxHint() {
    if ($("#sjWxHint")) return;
    const d = document.createElement("div");
    d.id = "sjWxHint";
    d.innerHTML =
      "<b>请在浏览器中打开下载</b>" +
      "<span>微信内无法直接下载安装包，点右上角 ··· 选择「在浏览器打开」即可下载 v" +
      (CFG.version || "1.0.0") + "</span>";
    document.body.appendChild(d);
    d.addEventListener("click", () => d.remove());
  }

  function handleScanDownload() {
    let p;
    try { p = new URLSearchParams(location.search); } catch (e) { return; }
    if (p.get("download") !== "apk") return;
    // 清掉 query，避免刷新重复触发；滚到下载区
    history.replaceState(null, "", location.pathname);
    const sec = $("#download");
    if (sec) sec.scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "start" });
    if (IS_WECHAT) { showWxHint(); return; }
    if (IS_ANDROID) setTimeout(() => openStore("android"), 500);
  }

  /* ============================================================
     4. 导航：滚动状态 / 进度条 / 当前区块 / 回顶
     ============================================================ */
  const NAV_SECTIONS = ["demo", "features", "flow", "guard", "faq", "download"];

  function bindScrollUI() {
    const nav = $("#sjNav"), bar = $("#sjProgress"), top = $("#sjTopBtn"), mob = $("#sjMobileDl");
    let raf = 0;
    function update() {
      raf = 0;
      const y = scrollY;
      const h = document.documentElement.scrollHeight - innerHeight;
      if (bar) bar.style.width = (h > 0 ? Math.min(100, y / h * 100) : 0) + "%";
      if (nav) nav.classList.toggle("stuck", y > 8);
      if (top) top.classList.toggle("show", y > innerHeight * 0.7);
      if (mob) mob.classList.toggle("show", y > innerHeight * 0.5);
      let active = "";
      NAV_SECTIONS.forEach(id => {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top <= 150) active = id;
      });
      $$(".sj-nav-links a").forEach(a =>
        a.classList.toggle("active", a.getAttribute("href") === "#" + active));
    }
    addEventListener("scroll", () => { if (!raf) raf = requestAnimationFrame(update); }, { passive: true });
    addEventListener("resize", () => { if (!raf) raf = requestAnimationFrame(update); });
    update();
    if (top) top.addEventListener("click", () =>
      scrollTo({ top: 0, behavior: REDUCED ? "auto" : "smooth" }));
  }

  /* ============================================================
     5. 移动端抽屉
     ============================================================ */
  function bindDrawer() {
    const burger = $("#sjBurger"), drawer = $("#sjDrawer"), mask = $("#sjDrawerMask");
    if (!burger || !drawer) return;
    function close() {
      drawer.classList.remove("open");
      burger.classList.remove("open");
      burger.setAttribute("aria-expanded", "false");
      drawer.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
    }
    burger.addEventListener("click", () => {
      const open = !drawer.classList.contains("open");
      drawer.classList.toggle("open", open);
      burger.classList.toggle("open", open);
      burger.setAttribute("aria-expanded", String(open));
      drawer.setAttribute("aria-hidden", String(!open));
      document.body.style.overflow = open ? "hidden" : "";
    });
    if (mask) mask.addEventListener("click", close);
    $$(".sj-drawer-panel a").forEach(a => a.addEventListener("click", close));
    addEventListener("keydown", e => { if (e.key === "Escape") close(); });
    addEventListener("resize", () => { if (innerWidth > 920) close(); });
  }

  /* ============================================================
     6. 滚动揭示
     ============================================================ */
  function bindReveal() {
    const els = $$(".sj-reveal");
    if (REDUCED || !("IntersectionObserver" in window)) {
      els.forEach(el => el.classList.add("in"));
      return;
    }
    const io = new IntersectionObserver(es => es.forEach(en => {
      if (!en.isIntersecting) return;
      en.target.classList.add("in");
      io.unobserve(en.target);
    }), { threshold: 0.08, rootMargin: "0px 0px -40px 0px" });
    els.forEach((el, i) => {
      el.style.transitionDelay = (i % 4) * 70 + "ms";
      io.observe(el);
    });
  }

  /* ============================================================
     7. 真机壳自适应缩放（受容器宽 + 视口高双重约束）
     ============================================================ */
  function bindPhoneScale() {
    const stage = $("#sjDemoStage");
    if (!stage) return;
    const fit = () => {
      const byW = (stage.clientWidth - 6) / 406;
      const byH = (innerHeight - 140) / 860;
      const s = Math.max(0.3, Math.min(1, byW, byH > 0 ? byH : 1));
      stage.style.setProperty("--sj-scale", s.toFixed(4));
    };
    fit();
    if ("ResizeObserver" in window) new ResizeObserver(fit).observe(stage);
    addEventListener("resize", fit);
    addEventListener("orientationchange", fit);
  }

  /* ============================================================
     8. 真机切页：功能卡 / 演示导航 / 流程步骤
     ============================================================ */
  function gotoScreen(name, scroll) {
    if (!PHONE || !PHONE.go) return;
    PHONE.go(name);
    const stage = $("#sjDemoStage");
    if (scroll && stage) {
      const r = stage.getBoundingClientRect();
      const visible = Math.min(r.bottom, innerHeight) - Math.max(r.top, 0);
      if (visible < r.height * 0.5) {
        stage.scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "center" });
      }
    }
  }

  function bindGoto() {
    // 功能卡 → 切真机
    $$(".sj-feat").forEach(c => c.addEventListener("click", () => {
      gotoScreen(c.dataset.goto, true);
      toast("已切换到「" + c.querySelector("h3").textContent + "」");
    }));
    // 演示导航
    $$("#sjDemoNav button").forEach(b => b.addEventListener("click", () => {
      gotoScreen(b.dataset.goto, false);
    }));
    // 流程步骤 → 切到记录录入
    $$(".sj-step").forEach(s => s.addEventListener("click", () => {
      gotoScreen("record", true);
      toast("点右下角「+」就能记一条");
    }));
    // 重播 / 庆祝
    const replay = $("#sjReplay");
    if (replay) replay.addEventListener("click", () => {
      gotoScreen("home", false);
      PHONE.burst && PHONE.burst();
      toast("已重播首页入场动效");
    });
    const cel = $("#sjCelebrate");
    if (cel) cel.addEventListener("click", () => {
      PHONE.celebrate && PHONE.celebrate("人生第一次爬行", "2026.10.26 · 安安 8 个月 12 天");
    });
  }

  /* ============================================================
     9. Hero 轻量手机：实时时钟 + FAB 新增记录
     ============================================================ */
  function bindHeroPhone() {
    const clock = $("#sjHeroClock");
    if (clock) {
      const tick = () => {
        const d = new Date();
        clock.textContent = d.getHours() + ":" + String(d.getMinutes()).padStart(2, "0");
      };
      tick();
      setInterval(tick, 20000);
    }

    const fab = $("#sjHeroFab");
    const list = $("#sjHeroTimeline");
    const count = $("#sjHeroCount");
    if (!fab || !list) return;

    const pool = [
      ["01-feeding", "喂奶 · 瓶喂 120ml", "妈妈记"],
      ["02-sleep", "小睡 · 40 分钟", "外婆记"],
      ["04-photo", "照片 · 日常抓拍", "爸爸记"],
      ["03-milestone", "里程碑 · 会爬了", "已达成"]
    ];
    let n = 0;
    fab.addEventListener("click", () => {
      const it = pool[n % pool.length];
      n++;
      const row = document.createElement("div");
      row.className = "sj-hp-row sj-new";
      row.innerHTML =
        '<img data-ic="' + it[0] + '" src="assets/icons/' + document.body.dataset.theme + "/" + it[0] + '.png" alt="">' +
        "<span><b>" + it[1] + "</b><small>刚刚</small></span><i>" + it[2] + "</i>";
      list.prepend(row);
      // 保持最多 4 条
      while (list.children.length > 4) list.lastElementChild.remove();
      if (count) {
        const c = parseInt(count.textContent.replace(/\D/g, ""), 10) || 0;
        count.textContent = "今日 " + (c + 1) + " 条";
      }
      confettiIn($("#sjConfetti"), 10);
      toast("已记下一条，自动进入时光轴");
    });

    // 手机 3D 跟随鼠标
    const frame = $(".sj-hp-frame");
    const visual = $(".sj-hero-visual");
    if (frame && visual && matchMedia("(pointer:fine)").matches && !REDUCED) {
      visual.addEventListener("pointermove", e => {
        const r = visual.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5;
        const y = (e.clientY - r.top) / r.height - 0.5;
        frame.style.transform =
          "perspective(1200px) rotateY(" + (x * 10).toFixed(2) + "deg) rotateX(" + (-y * 8).toFixed(2) + "deg)";
      });
      visual.addEventListener("pointerleave", () => { frame.style.transform = ""; });
    }
  }

  /* ============================================================
     10. 吉祥物彩蛋 + 眼睛跟随
     ============================================================ */
  function bindMascots() {
    const wrap = $("#sjMascots");
    if (!wrap) return;
    let taps = 0, timer = null;
    $$(".sj-mascot", wrap).forEach(m => m.addEventListener("click", e => {
      const r = wrap.getBoundingClientRect();
      spawnHearts(wrap, e.clientX - r.left, e.clientY - r.top, 5);
      taps++;
      clearTimeout(timer);
      timer = setTimeout(() => { taps = 0; }, 1200);
      if (taps >= 3) {
        taps = 0;
        confettiIn($("#sjConfetti"), 40);
        toast("岁岁和叽叽被你逗乐了");
      }
    }));
    const hero = $(".sj-hero");
    if (hero && !REDUCED) {
      hero.addEventListener("pointermove", e => {
        const r = hero.getBoundingClientRect();
        const dx = Math.max(-2.5, Math.min(2.5, (e.clientX - r.left - r.width / 2) / 120));
        const dy = Math.max(-2, Math.min(2, (e.clientY - r.top - r.height / 2) / 160));
        $$(".sj-eye-track").forEach(g => g.setAttribute("transform", "translate(" + dx + " " + dy + ")"));
      });
    }
  }

  /* ============================================================
     11. 鼠标光晕跟随
     ============================================================ */
  function bindCursorGlow() {
    if (!matchMedia("(pointer:fine)").matches || REDUCED) return;
    const glow = $("#sjCursorGlow");
    if (!glow) return;
    document.body.classList.add("sj-has-pointer");
    let x = 0, y = 0, tx = 0, ty = 0, raf = 0;
    addEventListener("pointermove", e => {
      tx = e.clientX; ty = e.clientY;
      if (!raf) raf = requestAnimationFrame(loop);
    }, { passive: true });
    function loop() {
      x += (tx - x) * 0.12;
      y += (ty - y) * 0.12;
      glow.style.transform = "translate3d(" + x.toFixed(1) + "px," + y.toFixed(1) + "px,0)";
      raf = (Math.abs(tx - x) > 0.4 || Math.abs(ty - y) > 0.4) ? requestAnimationFrame(loop) : 0;
    }
  }

  /* ============================================================
     12. 走马灯拖拽
     ============================================================ */
  function bindMarquee() {
    const track = $("#sjMarquee");
    if (!track) return;
    let down = false, startX = 0, startPos = 0, moved = false;
    track.addEventListener("pointerdown", e => {
      down = true; moved = false;
      startX = e.clientX;
      startPos = track.scrollLeft;
      track.classList.add("dragging");
    });
    track.addEventListener("pointermove", e => {
      if (!down) return;
      const dx = e.clientX - startX;
      if (Math.abs(dx) > 4) moved = true;
      // 视觉平移
      const cur = getComputedStyle(track).transform;
      const m = cur.match(/matrix\(([^)]+)\)/);
      const baseX = m ? parseFloat(m[1].split(",")[4]) : 0;
      track.style.transform = "translateX(" + (baseX + dx) + "px)";
      e.preventDefault();
    });
    const end = () => {
      if (!down) return;
      down = false;
      track.classList.remove("dragging");
      track.style.transform = "";
    };
    track.addEventListener("pointerup", end);
    track.addEventListener("pointerleave", end);
    track.addEventListener("click", e => { if (moved) e.preventDefault(); }, true);
  }

  /* ============================================================
     13. 二维码放大弹窗
     ============================================================ */
  function bindQrModal() {
    const modal = $("#sjModal"), img = $("#sjModalImg"), title = $("#sjModalTitle");
    if (!modal) return;
    function open(src, text) {
      img.src = src;
      title.textContent = text;
      modal.classList.add("open");
      modal.setAttribute("aria-hidden", "false");
    }
    function close() {
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
    }
    $$("[data-qr]").forEach(b => b.addEventListener("click", () => {
      const store = b.dataset.qr;
      const src = store === "android" ? DL.qrAndroid : DL.qrIos;
      const text = store === "android"
        ? "扫码下载 Android 版 v" + (CFG.version || "1.0.0")
        : "扫码订阅 iOS 上架通知";
      if (!src) { toast("二维码尚未生成"); return; }
      open(src, text);
    }));
    $("#sjModalMask").addEventListener("click", close);
    $("#sjModalClose").addEventListener("click", close);
    addEventListener("keydown", e => { if (e.key === "Escape") close(); });
  }

  /* ============================================================
     14. FAQ 手风琴（一次只开一条）
     ============================================================ */
  function bindFaq() {
    const items = $$(".sj-faq details");
    items.forEach(d => d.addEventListener("toggle", () => {
      if (!d.open) return;
      items.forEach(x => { if (x !== d) x.open = false; });
    }));
  }

  /* ============================================================
     15. 按钮涟漪
     ============================================================ */
  const RIP_SEL = ".sj-btn,.sj-feat,.sj-demo-nav button,.sj-dl-card,.sj-copy,.sj-qr,.sj-theme-btn";
  if (!REDUCED) {
    document.addEventListener("pointerdown", e => {
      const el = e.target.closest(RIP_SEL);
      if (!el) return;
      const r = el.getBoundingClientRect();
      const size = Math.max(r.width, r.height) * 2.1;
      const rip = document.createElement("span");
      rip.className = "sj-ripple";
      rip.style.cssText = "width:" + size + "px;height:" + size + "px;left:" +
        (e.clientX - r.left - size / 2) + "px;top:" + (e.clientY - r.top - size / 2) + "px";
      el.appendChild(rip);
      setTimeout(() => rip.remove(), 620);
    });
  }

  /* ============================================================
     16. 卡片 3D 倾斜（桌面端）
     ============================================================ */
  function bindTilt() {
    if (!matchMedia("(pointer:fine)").matches || REDUCED) return;
    $$(".sj-feat,.sj-dl-card").forEach(card => {
      card.addEventListener("pointermove", e => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5;
        const y = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform =
          "perspective(900px) translateY(-7px) rotateX(" + (-y * 5).toFixed(2) +
          "deg) rotateY(" + (x * 6).toFixed(2) + "deg)";
      });
      card.addEventListener("pointerleave", () => { card.style.transform = ""; });
    });
  }

  /* ============================================================
     17. 免责声明注入 + 首屏提示
     ============================================================ */
  function bindMisc() {
    const d = $("#sjDisclaimer");
    if (d && CFG.disclaimer) d.textContent = CFG.disclaimer;

    const stage = $("#sjDemoStage");
    if (stage && "IntersectionObserver" in window) {
      const io = new IntersectionObserver(es => es.forEach(en => {
        if (!en.isIntersecting) return;
        io.disconnect();
        setTimeout(() => { PHONE.toast && PHONE.toast("这是一台真的手机，随便点"); }, 700);
      }), { threshold: 0.35 });
      io.observe(stage);
    }
  }

  /* ============================================================
     启动
     ============================================================ */
  bindTheme();
  bindDownload();
  detectDevice();
  handleScanDownload();
  bindScrollUI();
  bindDrawer();
  bindReveal();
  bindPhoneScale();
  bindGoto();
  bindHeroPhone();
  bindMascots();
  bindCursorGlow();
  bindMarquee();
  bindQrModal();
  bindFaq();
  bindTilt();
  bindMisc();
})();
