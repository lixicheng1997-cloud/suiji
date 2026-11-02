/* ================================================================
   岁记 · 官网内嵌真机原型交互（移植自 suiji-ui-v2/app.js）
   只负责 #phoneScreen 手机壳内部；站点层交互在 site.js
   ================================================================ */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ---------- 双主题换肤（全站 60 枚图标同步替换） ---------- */
function applyTheme(t, animate) {
  document.body.dataset.theme = t;
  $$('img[data-ic]').forEach((img, i) => {
    img.src = `assets/icons/${t}/${img.dataset.ic}.png`;
    if (animate && !REDUCED) {
      img.classList.remove('ic-pop'); void img.offsetWidth;
      img.style.animationDelay = (i % 14) * 0.025 + 's';
      img.classList.add('ic-pop');
    }
  });
  $$('[data-set-theme]').forEach(b =>
    b.classList.toggle('active', b.dataset.setTheme === t));
}

/* ---------- 彩带 ---------- */
const PALETTE = ['#F7A15C', '#FFD85C', '#FF8FAB', '#8FA8DC', '#5FC08C', '#A994D8', '#6FBDE0'];
function confettiIn(layer, count) {
  if (!layer) return;
  for (let i = 0; i < count; i++) {
    const b = document.createElement('i');
    b.className = 'confetti-bit';
    b.style.left = Math.random() * 100 + '%';
    b.style.background = PALETTE[i % PALETTE.length];
    b.style.animationDelay = (Math.random() * .35).toFixed(2) + 's';
    const s = 6 + Math.random() * 7;
    b.style.width = s + 'px';
    b.style.height = s * (Math.random() > .5 ? 1.4 : 1) + 'px';
    layer.appendChild(b);
    setTimeout(() => b.remove(), 2000);
  }
}
function burstConfetti() { confettiIn($('#confetti'), 26); }

/* ---------- 机内 Toast ---------- */
let toastTimer;
function toast(msg) {
  const el = $('#toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 1900);
}

/* ---------- 爱心粒子 ---------- */
const HEART_SVG = '<svg viewBox="0 0 24 24"><path d="M12 21s-7-4.6-9.5-9C.7 8.6 2.6 5 6 5c2 0 3.2 1 4 2.2C10.8 6 12 5 14 5c3.4 0 5.3 3.6 3.5 7-2.5 4.4-9.5 9-9.5 9Z"/></svg>';
function spawnHearts(container, x, y, n) {
  if (REDUCED || !container) return;
  for (let i = 0; i < n; i++) {
    const h = document.createElement('span');
    h.className = 'heart-bit';
    h.innerHTML = HEART_SVG;
    const s = 14 + Math.random() * 10;
    h.style.cssText = `left:${x + Math.random() * 44 - 22}px;top:${y + Math.random() * 16 - 8}px;width:${s}px;height:${s}px;animation-delay:${(i * .09).toFixed(2)}s;color:${i % 2 ? 'var(--blush)' : 'var(--c-mood)'}`;
    container.appendChild(h);
    setTimeout(() => h.remove(), 1700);
  }
}

/* ================================================================
   手机壳交互
   ================================================================ */
const PHONE = (() => {
  const api = { go() {}, switchTab() {}, celebrate() {}, burst() {}, toast() {} };
  const screen = $('#phoneScreen');
  if (!screen) return api;

  const screens = $$('#phoneScreen .scr');
  const TABS = ['home', 'growth', 'family', 'me'];
  /* 二级页 → 归属 Tab / 页面标题 */
  const SUB = {
    record: 'home', curve: 'growth', milestone: 'growth', diary: 'growth',
    vaccine: 'me', privacy: 'me'
  };
  const LABEL = {
    home: 'P01 · 时光轴首页', record: 'P09 · 添加记录（10 类动态表单）',
    growth: 'P02 · 成长中心', curve: 'P13 · 生长曲线', milestone: 'P12 · 里程碑清单',
    diary: 'P16 · AI 成长日记', family: 'P03 · 家庭中心', vaccine: 'P21 · 疫苗时间表',
    me: 'P04 · 我的', privacy: 'P26 · 我的数据 · 隐私看板'
  };
  const owner = n => TABS.includes(n) ? n : SUB[n];
  let curTab = 'home', curScr = 'home';

  function paint(name) {
    $$('.sj-demo-nav [data-goto], .wv-demo-nav [data-goto]').forEach(b =>
      b.classList.toggle('on', b.dataset.goto === name));
    const lb = $('#sjPhoneLabel') || $('#wvPhoneLabel');
    if (lb) lb.textContent = LABEL[name] || '';
  }

  function switchTab(name) {
    if (!$('#phoneScreen .scr[data-scr="' + name + '"]')) name = 'home';
    const fromLeft = TABS.indexOf(name) >= 0
      ? TABS.indexOf(name) < TABS.indexOf(curTab)
      : TABS.indexOf(owner(name)) < TABS.indexOf(curTab);
    curScr = name;
    curTab = owner(name) || curTab;
    screens.forEach(s => {
      const on = s.dataset.scr === name;
      s.classList.remove('scr-in-l');
      s.classList.toggle('scr-active', on);
      if (on) {
        s.scrollTop = 0;
        if (fromLeft) { void s.offsetWidth; s.classList.add('scr-in-l'); }
      }
    });
    $$('#tabbar .tab').forEach(t => {
      const on = t.dataset.tab === curTab;
      t.classList.remove('tab-active');
      if (on) { void t.offsetWidth; t.classList.add('tab-active'); }
    });
    paint(name);
  }
  function go(name) { switchTab(name); }

  $$('#tabbar .tab').forEach(t =>
    t.addEventListener('click', () => switchTab(t.dataset.tab)));
  /* 机内入口卡片 / 返回键也走同一套导航 */
  $$('#phoneScreen [data-goto]').forEach(el =>
    el.addEventListener('click', () => switchTab(el.dataset.goto)));

  /* ---------- P08 记录面板（含把手拖拽下滑关闭） ---------- */
  const sheet = $('#sheet'), mask = $('#sheetMask');
  function openSheet() {
    sheet.style.transform = ''; sheet.classList.remove('dragging');
    sheet.classList.add('show'); mask.classList.add('show');
  }
  function closeSheet() {
    sheet.classList.remove('show'); mask.classList.remove('show');
    sheet.style.transform = ''; sheet.classList.remove('dragging');
  }
  $('#fab').addEventListener('click', openSheet);
  $('#sheetClose').addEventListener('click', closeSheet);
  mask.addEventListener('click', closeSheet);

  $$('.sheet-handle').forEach(handle => {
    let dragStart = null, dragDy = 0;
    const panel = handle.parentElement;
    handle.addEventListener('pointerdown', e => {
      dragStart = e.clientY; dragDy = 0;
      panel.classList.add('dragging');
      handle.setPointerCapture(e.pointerId);
    });
    handle.addEventListener('pointermove', e => {
      if (dragStart === null) return;
      dragDy = Math.max(0, e.clientY - dragStart);
      panel.style.transform = `translateY(${dragDy}px)`;
    });
    handle.addEventListener('pointerup', () => {
      if (dragStart === null) return;
      dragStart = null;
      if (dragDy > 80) {
        if (panel.id === 'vinput') closeVoice();
        else closeSheet();
      }
      panel.classList.remove('dragging');
      panel.style.transform = '';
    });
  });

  /* ---------- 新记录插入闭环 ---------- */
  const TILE_NAME = {
    feeding: '喂奶', sleep: '睡眠', milestone: '里程碑', measure: '测量', poop: '便便',
    temp: '体温', med: '用药', photo: '照片', mood: '文字心情', voice: '语音'
  };
  const REC_DESC = {
    喂奶: '母乳亲喂 · 计时结束', 睡眠: '入睡 · 计时开始', 照片: '已保存 1 张新照片',
    测量: '身高体重已记录', 便便: '金黄色糊状 · 性状正常', 体温: '腋温 36.8 ℃ · 正常',
    用药: '剂量已记录', 文字心情: '一句话已保存'
  };
  function addRecord(name, tile, descHTML) {
    const ic = tile.querySelector('img').dataset.ic;
    const cs = getComputedStyle(tile);
    const now = new Date();
    const card = document.createElement('div');
    card.className = 'rec-card flash-new';
    card.style.setProperty('--rc', cs.getPropertyValue('--tc').trim());
    card.style.setProperty('--rs', cs.getPropertyValue('--tcs').trim());
    card.innerHTML = `<img class="rec-ic" data-ic="${ic}" src="assets/icons/${document.body.dataset.theme}/${ic}.png" alt=""><div class="rec-info"><b>${name}</b><span>${descHTML || REC_DESC[name] || '刚刚记录'}</span></div><time>${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}</time>`;
    if (name === '语音速记') card.addEventListener('click', () => playVoice(card));
    const tl = $('#timeline');
    tl.insertBefore(card, tl.firstChild);
    switchTab('home');
    const cnt = $('#recCount');
    cnt.textContent = parseInt(cnt.textContent, 10) + 1;
    cnt.classList.remove('count-bump'); void cnt.offsetWidth; cnt.classList.add('count-bump');
    toast(`已记录 · ${name}`);
  }

  $$('.sheet .tile').forEach(tile => {
    tile.addEventListener('click', () => {
      const name = tile.dataset.name;
      closeSheet();
      if (name === '里程碑') openCelebrate('解锁新里程碑', '记录一个全新的「第一次」');
      else if (name === '语音') setTimeout(openVoice, 240);
      else addRecord(name, tile);
    });
  });

  /* ---------- 里程碑全屏庆祝 ---------- */
  const celebrate = $('#celebrate');
  function openCelebrate(title, sub) {
    $('#celTitle').textContent = title;
    $('#celSub').textContent = sub;
    celebrate.classList.add('show');
    confettiIn($('#celConfetti'), 30);
    const t = celebrate.querySelector('.cel-trophy img');
    t.style.animation = 'none'; void t.offsetWidth; t.style.animation = '';
  }
  function closeCelebrate() { celebrate.classList.remove('show'); }
  $('#milestoneCard').addEventListener('click', () =>
    openCelebrate('人生第一次爬行', '2026.10.26 · 安安 8 个月 12 天'));
  $('#msCrawl').addEventListener('click', () =>
    openCelebrate('爬行 · 本月达成', '连续爬过整个客厅，太棒了'));
  $('#celClose').addEventListener('click', closeCelebrate);
  celebrate.addEventListener('click', e => { if (e.target === celebrate) closeCelebrate(); });
  $('#celCard').addEventListener('click', () => {
    closeCelebrate();
    toast('纪念卡已生成，可分享给家人');
  });

  /* ---------- 同步云状态回写 ---------- */
  const syncChip = $('#syncChip'), syncTxt = $('#syncTxt');
  syncChip.addEventListener('click', () => {
    if (syncChip.classList.contains('spinning')) return;
    syncChip.classList.add('spinning');
    syncTxt.textContent = '同步中…';
    setTimeout(() => {
      syncChip.classList.remove('spinning');
      syncTxt.textContent = '已同步';
    }, 760);
  });

  /* ---------- 睡眠进行中实时计时 ---------- */
  let sleepSec = 42 * 60 + 15;
  setInterval(() => {
    sleepSec++;
    const p = n => String(n).padStart(2, '0');
    $('#sleepTimer').textContent =
      `${p(Math.floor(sleepSec / 3600))}:${p(Math.floor(sleepSec % 3600 / 60))}:${p(sleepSec % 60)}`;
  }, 1000);

  /* ---------- 亲喂计时 ---------- */
  let feedSec = 12 * 60 + 45;
  const feedTimer = $('#feedTimer');
  setInterval(() => {
    if (!feedTimer || curScr !== 'record') return;
    feedSec++;
    const p = n => String(n).padStart(2, '0');
    feedTimer.textContent = `${p(Math.floor(feedSec / 60))}:${p(feedSec % 60)}`;
  }, 1000);

  /* ---------- 状态栏真实时钟 ---------- */
  function tickClock() {
    const d = new Date();
    $('#sbClock').textContent = d.getHours() + ':' + String(d.getMinutes()).padStart(2, '0');
  }
  tickClock(); setInterval(tickClock, 20000);

  /* ---------- 语音卡播放波形 ---------- */
  function playVoice(card) {
    card.classList.add('play');
    toast('播放语音 · 「咿呀呀」');
    setTimeout(() => card.classList.remove('play'), 1800);
  }
  $('#voiceCard').addEventListener('click', () => playVoice($('#voiceCard')));

  /* ---------- P08b 语音输入三态 ---------- */
  const vinput = $('#vinput'), vMask = $('#vMask');
  const viWave = $('#viWave'), viTimer = $('#viTimer'), viLive = $('#viLiveTxt');
  const VI_LINES = ['安安突然指着窗外', '「咿呀呀」叫了好几声', '，还回头冲我笑'];
  let viSec = 0, viTick = null, viAnim = null, viType = null;
  const viFmt = s => Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
  for (let i = 0; i < 26; i++) viWave.appendChild(document.createElement('i'));
  for (let i = 0; i < 22; i++) {
    const b = document.createElement('i');
    b.style.setProperty('--h', (6 + Math.random() * 20).toFixed(0) + 'px');
    $('#viThumb').appendChild(b);
  }
  function viClear() { [viTick, viAnim, viType].forEach(id => id && clearInterval(id)); viTick = viAnim = viType = null; }
  function openVoice() {
    viClear(); viSec = 0;
    vinput.dataset.state = 'idle';
    vinput.classList.add('show'); vMask.classList.add('show');
  }
  function closeVoice() {
    vinput.classList.remove('show'); vMask.classList.remove('show'); viClear();
  }
  vMask.addEventListener('click', closeVoice);

  $('#viMic').addEventListener('click', () => {
    vinput.dataset.state = 'rec';
    viTimer.textContent = '0:00'; viLive.textContent = '';
    let li = 0, ci = 0, out = '';
    viType = setInterval(() => {
      if (li >= VI_LINES.length) return;
      out += VI_LINES[li][ci++];
      viLive.textContent = out;
      if (ci >= VI_LINES[li].length) { li++; ci = 0; }
    }, 150);
    const bars = [...viWave.children];
    let hs = bars.map(() => 6 + Math.random() * 10);
    viAnim = setInterval(() => {
      hs = hs.map(h => { const t = 4 + Math.random() * 44; return h + (t - h) * .4; });
      bars.forEach((b, i) => b.style.height = hs[i].toFixed(1) + 'px');
    }, 110);
    viTick = setInterval(() => {
      viSec++;
      viTimer.textContent = viFmt(viSec);
      if (viSec >= 60) viFinish();
    }, 1000);
  });
  function viFinish() {
    viClear();
    vinput.dataset.state = 'done';
    const dur = viFmt(Math.max(1, viSec));
    $('#viDur').textContent = dur;
    $('#viTrans').textContent = (viLive.textContent.trim() || '「咿呀呀」叫了几声') + ' · ' + dur;
    $('#viPlayRow').classList.remove('playing');
  }
  $('#viStop').addEventListener('click', viFinish);
  $('#viFinish').addEventListener('click', viFinish);
  $('#viCancel').addEventListener('click', () => { closeVoice(); toast('已取消录音'); });
  $('#viRedo').addEventListener('click', () => { vinput.dataset.state = 'idle'; });
  $('#viPlay').addEventListener('click', () => $('#viPlayRow').classList.toggle('playing'));
  $('#viSave').addEventListener('click', () => {
    const tile = $('.tile[data-name="语音"]');
    const dur = $('#viDur').textContent;
    const t = viLive.textContent.trim() || '「咿呀呀」叫了几声';
    closeVoice();
    addRecord('语音速记', tile,
      `${t.slice(0, 16)} · ${dur} <span class="wave"><i></i><i></i><i></i><i></i><i></i></span>`);
  });

  /* ---------- 宝宝档案切换 ---------- */
  const babyChip = $('#babyChip'), babyMenu = $('#babyMenu');
  babyChip.addEventListener('click', e => {
    e.stopPropagation();
    babyMenu.classList.toggle('show');
  });
  document.addEventListener('click', () => babyMenu.classList.remove('show'));
  $$('.bm-item').forEach(item => item.addEventListener('click', e => {
    e.stopPropagation();
    if (item.dataset.baby === '__add') {
      babyMenu.classList.remove('show');
      toast('添加宝宝档案（演示）');
      return;
    }
    $$('.bm-item').forEach(i => i.classList.remove('bm-on'));
    item.classList.add('bm-on');
    const nm = $('#babyName');
    nm.innerHTML = item.dataset.baby + '<b>' + item.dataset.age + '</b>';
    nm.classList.remove('swap'); void nm.offsetWidth; nm.classList.add('swap');
    $$('#sheet h3 span, #vinput h3 span, #phoneScreen [data-scr="record"] .pg-back span:last-child').forEach(el =>
      el.textContent = item.dataset.baby + ' · ' + item.dataset.short);
    babyMenu.classList.remove('show');
    toast('已切换到 ' + item.dataset.baby + ' 的档案');
  }));

  /* ---------- 机内长辈模式 ---------- */
  $('#elderEntry').addEventListener('click', () => $('#elderMode').classList.add('show'));
  $('#elderExit').addEventListener('click', () => $('#elderMode').classList.remove('show'));
  $('#elderCall').addEventListener('click', () => toast('正在呼叫妈妈…（演示）'));

  /* ---------- P09 动态表单 / 胶囊 / 开关 ---------- */
  $$('.pg-type').forEach(t => t.addEventListener('click', () => {
    $$('.pg-type').forEach(x => x.classList.remove('on'));
    t.classList.add('on');
    $$('.pg-form').forEach(f => f.classList.toggle('on', f.dataset.f === t.dataset.t));
  }));
  $$('#phoneScreen .pg-chips:not(#pgTypes)').forEach(group => {
    group.addEventListener('click', e => {
      const it = e.target.closest('i');
      if (!it || it.classList.contains('pg-type')) return;
      group.querySelectorAll('i').forEach(x => x.classList.remove('on'));
      it.classList.add('on');
    });
  });
  $$('#phoneScreen .pg-seg').forEach(seg => {
    seg.addEventListener('click', e => {
      const it = e.target.closest('i');
      if (!it) return;
      seg.querySelectorAll('i').forEach(x => x.classList.remove('on'));
      it.classList.add('on');
    });
  });
  $$('#phoneScreen .pg-sw').forEach(sw => sw.addEventListener('click', () => sw.classList.toggle('on')));
  $$('#phoneScreen .pg-ck').forEach(ck => ck.addEventListener('click', () => {
    ck.classList.toggle('on');
    ck.textContent = ck.classList.contains('on') ? '✓' : '+';
  }));
  const backfill = $('#pgBackfill');
  if (backfill) backfill.addEventListener('click', e => {
    const sw = backfill.querySelector('.pg-sw');
    if (e.target !== sw) sw.classList.toggle('on');
  });
  const pgSave = $('#pgSave');
  if (pgSave) pgSave.addEventListener('click', () => {
    const act = $$('.pg-type.on')[0];
    const nm = TILE_NAME[act ? act.dataset.t : ''] || (act ? act.textContent : '记录');
    const tile = $(`.sheet .tile[data-name="${nm}"]`) || $('.sheet .tile');
    addRecord(nm, tile);
    burstConfetti();
  });

  /* ---------- 演示按钮统一 toast ---------- */
  $$('#phoneScreen [data-cutoast]').forEach(el =>
    el.addEventListener('click', () => toast(el.dataset.cutoast)));

  /* ---------- 重播首页动效 ---------- */
  const replay = $('#wvReplay');
  if (replay) replay.addEventListener('click', () => {
    switchTab('home');
    screens.forEach(s => s.classList.remove('scr-in-l'));
    const home = $('#phoneScreen .scr[data-scr="home"]');
    void home.offsetWidth;
    home.classList.add('scr-in-l');
    toast('已重播首页入场动效');
  });
  const celBtn = $('#wvCelebrateBtn');
  if (celBtn) celBtn.addEventListener('click', () => {
    switchTab('home');
    openCelebrate('人生第一次爬行', '2026.10.26 · 安安 8 个月 12 天');
  });

  switchTab('home');

  api.go = go;
  api.switchTab = switchTab;
  api.celebrate = openCelebrate;
  api.burst = burstConfetti;
  api.toast = toast;
  api.openSheet = openSheet;
  api.addRecord = addRecord;
  return api;
})();
