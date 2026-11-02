<template>
  <view class="page" :class="swipeClass" :style="themeVars" @touchstart="onTabTouchStart" @touchend="onTabTouchEnd">
    <!-- 应用内氛围背景：奶油底 + 漂浮光斑（全应用共用 sj-bg） -->
    <sj-bg />

    <view class="content">
      <!-- 顶栏 appbar：宝宝切换 chip（点击弹 sj-modal 列表）+ 同步状态 chip（搜索/消息保留为圆形图标按钮） -->
      <view class="appbar" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
        <view class="baby-chip" hover-class="hover-press" @click="babyModalShow = true">
          <image class="baby-avatar" :src="avatar || ('/static/icons/ctl/' + __theme + '/128/45-ctl-avatar.png')" :mode="avatar ? 'aspectFill' : 'aspectFit'" />
          <view class="baby-name">
            <text>{{ baby.name }}</text>
            <text class="baby-age">{{ baby.age }}</text>
          </view>
          <image class="chev" src="/static/icons/chevron-down.svg" />
        </view>
        <view class="bar-right">
          <view class="icon-btn" hover-class="hover-press" @click="onSearch">
            <image class="ic17" src="/static/icons/search.svg" />
          </view>
          <view class="icon-btn" hover-class="hover-press" @click="onBell">
            <image class="ic17" src="/static/icons/bell.svg" />
            <view v-if="unread" class="badge-num"><text>{{ unread > 99 ? '99+' : unread }}</text></view>
          </view>
        </view>
      </view>

      <!-- 今日问候条：吉祥物探头 + 陪伴记录数 -->
      <view class="today-strip">
        <view class="today-txt">
          <text class="tt-hello">{{ greeting }}，{{ baby.name }}</text>
          <text class="tt-sub">今天已记录 <text class="cnt">{{ todayCount }}</text> 条 · {{ cheerText }}</text>
        </view>
        <view class="peek-wrap">
          <sj-mascot :size="104" />
        </view>
      </view>

      <!-- 当日统计胶囊行 -->
      <view class="day-summary">
        <view class="ds-chip" v-for="s in todayStats" :key="s.label">
          <view class="ds-ic" :style="{ background: TYPES[s.type].color }">
            <sj-icon :name="TYPES[s.type].png" :size="40" />
          </view>
          <text class="ds-txt">{{ s.num }} {{ s.label }}</text>
        </view>
      </view>

      <!-- 时光轴（按日分组，date-row 分隔 + rec-card 新布局） -->
      <view class="timeline">
        <view class="day-group" v-for="g in groups" :key="g.day">
          <view class="date-row">
            <view class="dr-line" />
            <text class="dr-label">{{ g.day }}</text>
            <text class="dr-count">{{ g.total }} 条</text>
            <view class="dr-line" />
          </view>

          <!-- 左滑删除包装：卡片左移露出底层红色删除块。
               不用 v-memo（微信小程序编译器不支持，会导致 build:mp-weixin 失败） -->
          <view class="rec-swipe" v-for="e in g.items" :key="g.day + e.time + e.id">
            <view class="swipe-del" :class="{ 'del-show': swipeX(e) !== 0 }" hover-class="hover-press" :hover-stay-time="80" @click.stop="onSwipeDelete(e)">删除</view>
            <view
              class="rec-card"
              :class="{ 'rec-milestone': e.type === 'milestone', 'rec-ongoing': e.badge === 'ongoing', 'swipe-on': swipeX(e) !== 0 }"
              :style="[cardStyle(e), swipeStyle(e)]"
              @touchstart="onSwipeStart($event, e)"
              @touchmove="onSwipeMove($event, e)"
              @touchend.stop="onSwipeEnd($event, e)"
              @touchcancel.stop="onSwipeEnd($event, e)"
              @mousedown="onSwipeStart($event, e)"
              @mousemove="onSwipeMove($event, e)"
              @mouseup="onSwipeEnd($event, e)"
              @mouseleave="onSwipeEnd($event, e)"
              @click="onEntry(e)"
            >
            <view class="rec-ic" :style="{ background: TYPES[e.type].tint }">
              <sj-icon :name="TYPES[e.type].png" :size="76" />
            </view>
            <view class="rec-info">
              <view class="rec-title">
                <text>{{ e.title }}</text>
                <view v-if="e.badge === 'ongoing'" class="zzz"><text>z</text><text>z</text><text>z</text></view>
                <text v-else-if="e.badge" class="badge" :class="e.badge">{{ BADGES[e.badge] }}</text>
              </view>
              <view class="rec-meta">
                <block v-if="e.badge === 'ongoing'">
                  <view class="og-dot" />
                  <text class="og-txt">进行中 {{ sleepTimerText }}</text>
                </block>
                <block v-else>
                  <text>{{ e.meta || TYPES[e.type].label }}</text>
                  <text v-if="e.creator || e.creator_id">· {{ whoOf(e) }}</text>
                </block>
              </view>
              <!-- 语音：紧凑播放条替代原装饰波形（点击只播放，不冒泡进详情） -->
              <view v-if="e.voice" class="rec-voice">
                <sj-voice-play
                  compact
                  :segments="e.voice.segments"
                  :url="e.voice.url"
                  :duration="e.voice.duration"
                  :wave="e.voice.wave"
                />
              </view>
              <text v-if="e.note" class="rec-note">{{ e.note }}</text>
            </view>
            <image v-if="e.photo" class="rec-photo" :src="e.photo" mode="aspectFill" lazy-load />
            <!-- 里程碑右侧：时间与"庆祝一下"按钮上下错行；点按钮只弹庆祝，点卡片其余区域进详情 -->
            <view v-if="e.type === 'milestone'" class="ms-side">
              <text class="rec-time">{{ e.time }}</text>
              <text class="ms-badge" hover-class="hover-press" :hover-stay-time="80" @click.stop="openCelebrate(e)">庆祝一下</text>
            </view>
            <text v-else class="rec-time">{{ e.time }}</text>
            </view>
          </view>
        </view>

        <!-- 空态 -->
        <view v-if="!groups.length" class="empty">
          <sj-mascot :size="200" />
          <text class="empty-text">还没有记录{{ '\n' }}点右下角 + 记一笔吧</text>
        </view>
        <!-- 触底分页提示：还有更多→下箭头（加载中弹跳）；全部加载完→对勾（到底啦） -->
        <view v-else class="scroll-end">
          <image class="se-ic" :class="{ bounce: loadingMore }" :src="scrollEndIcon" />
          <text>{{ loadingMore ? '正在加载更多…' : hasMore ? '上拉加载更多' : '· 已经到底啦 ·' }}</text>
        </view>
      </view>
    </view>

    <!-- P08 记录面板遮罩 -->
    <view class="sheet-mask" :class="{ show: sheetOpen }" @click="closeSheet" />

    <!-- P08 快速记录底部面板（6 高频磁贴 + 更多 4 类 + 取消） -->
    <view class="sheet" :class="{ open: sheetOpen }">
      <view class="sheet-handle" />
      <view class="sheet-head">
        <text class="sh-title">记录此刻</text>
        <text class="sh-sub">{{ baby.name }} · {{ baby.age }}</text>
      </view>
      <view class="sheet-grid">
        <view
          class="tile"
          v-for="(k, i) in sheetTypes"
          :key="k"
          :style="{ background: TYPES[k].tint, animationDelay: sheetOpen ? i * 55 + 'ms' : '0ms' }"
          hover-class="hover-press"
          @click="pickType(k)"
        >
          <sj-icon :name="TYPES[k].png" :size="96" />
          <text class="t-label">{{ TYPES[k].label }}</text>
        </view>
      </view>
      <view class="sheet-more">
        <view
          class="tile-sm"
          v-for="k in moreTypes"
          :key="k"
          :style="{ background: TYPES[k].tint }"
          hover-class="hover-press"
          @click="pickType(k)"
        >
          <sj-icon :name="TYPES[k].png" :size="52" />
          <text>{{ TYPES[k].label }}</text>
        </view>
      </view>
    </view>

    <!-- 悬浮记录按钮 + 呼吸光环 -->
    <view class="fab-ring" v-if="!sheetOpen" />
    <view class="fab" :class="{ open: sheetOpen }" hover-class="hover-press" @click="toggleSheet">
      <image class="fab-ic" src="/static/icons/plus-white.svg" mode="aspectFit" />
    </view>

    <!-- 里程碑全屏庆祝弹层（彩带 + 奖杯弹跳） -->
    <view class="celebrate" :class="{ show: cel.show }" v-if="cel.show" @click="closeCelebrate">
      <view class="confetti-layer">
        <view
          class="confetti-bit"
          v-for="(b, i) in cel.bits"
          :key="i"
          :style="{ left: b.left + '%', background: b.color, borderRadius: b.round ? '50%' : '6rpx', animationDelay: b.delay + 's', animationDuration: b.dur + 's', width: b.w + 'rpx', height: b.h + 'rpx' }"
        />
      </view>
      <view class="cel-card" @click.stop>
        <view class="cel-trophy"><sj-icon name="03-milestone" :size="184" /></view>
        <text class="cel-title">{{ cel.title }}</text>
        <text class="cel-sub">{{ cel.sub }}</text>
        <view class="cel-btns">
          <sj-button class="cel-main" block text="生成纪念卡" @click="onCelCard" />
          <sj-button class="cel-ghost" block variant="ghost" text="收下啦" @click="closeCelebrate" />
        </view>
      </view>
    </view>

    <!-- 宝宝切换对话框：仅展示各宝宝头像 + 名字 + 年龄，点行即切换 -->
    <sj-modal v-model:show="babyModalShow" title="切换宝宝" confirmText="关闭">
      <scroll-view scroll-y class="baby-switch-list">
        <view
          class="bs-row"
          v-for="b in babyList"
          :key="b.id"
          :class="{ 'bs-row--on': b.id === baby.id }"
          hover-class="hover-press"
          @click="pickBaby(b)"
        >
          <image class="bs-avatar" :src="b.avatarSrc || ('/static/icons/ctl/' + __theme + '/128/45-ctl-avatar.png')" :mode="b.avatarSrc ? 'aspectFill' : 'aspectFit'" />
          <text class="bs-name">{{ b.name }}</text>
          <text class="bs-age">{{ b.age }}</text>
        </view>
      </scroll-view>
    </sj-modal>

    <!-- v2 悬浮底部导航（自动隐藏原生 tabBar） -->
    <sj-tabbar active="home" />
    <sj-ui-host />
  </view>
</template>

<script>
import { TYPES, BADGES } from '@/utils/mock.js'
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import tabSwipe, { pullRefresh } from '@/utils/tabSwipe.js'
import { palette } from '@/theme/theme.js'
import { play } from '@/utils/sound.js'

/* 左滑删除：露出的删除块宽度（rpx→px），与模板 .swipe-del 宽度一致 */
const SWIPE_DEL_PX = uni.upx2px(150)
/* 高频 touchmove 合帧用：小程序等无 rAF 环境退化为 16ms 定时 */
const raf = typeof requestAnimationFrame === 'function' ? requestAnimationFrame : cb => setTimeout(cb, 16)
const caf = typeof cancelAnimationFrame === 'function' ? cancelAnimationFrame : clearTimeout

/* 彩带粒子颜色（马卡龙色板，与 v2 confetti 一致） */
const CONFETTI_COLORS = ['#F7A15C', '#FF8FAB', '#F5B32C', '#8FA8DC', '#5FC08C', '#A994D8', '#6FBDE0']

export default {
  mixins: [tabSwipe],
  /* 下拉刷新（Vue3 生命周期必须顶层声明，混入 methods 里的不会触发）：重拉 bootstrap 后走 tabAfterPull */
  onPullDownRefresh() { pullRefresh(this) },
  /* 上滑触底：加载下一页时光轴（触底距离见 pages.json onReachBottomDistance） */
  onReachBottom() { this.loadMore() },
  data() {
    return {
      TYPES,
      BADGES,
      baby: api.getBaby() || { name: '宝宝', age: '' },
      todayStats: api.getTodayStats(),
      /* 时光轴服务端游标分页（专用接口 /entries/timeline，数据量大不再读全量缓存）：
         items=已加载的扁平 view item（occurred_at 倒序），cursor=下一页游标 */
      items: [],
      cursor: '',
      hasMore: false,
      /* 服务端 day_totals（{ 'YYYY-MM-DD': 全天真实条数 }）：日期行显示全天数，跨页天不再只算已加载部分 */
      dayTotals: {},
      pageSize: 10,
      loadingMore: false,
      /* 消息中心未读通知数（待办不计入，驱动顶栏铃铛角标） */
      unread: 0,
      sheetOpen: false,
      /* 宝宝切换对话框显隐 */
      babyModalShow: false,
      statusBarHeight: 20,
      /* 同步状态 chip：refresh 期间为 syncing */
      syncing: false,
      /* 进行中睡眠实时计时（秒），无进行中记录时为 -1 */
      sleepElapsed: -1,
      sleepTimer: null,
      /* 里程碑庆祝弹层 */
      cel: { show: false, title: '', sub: '', bits: [] },
      /* 时光轴左滑删除状态：同一时刻只有一张卡处于拖拽/展开态 */
      swipe: { id: '', x: 0, openId: '', sx: 0, sy: 0, moved: false },
      /* 家长信息勾选的常用记录类别（onShow 刷新时重读，驱动快速记录面板排序，见 computed sortedTypes） */
      parentCats: []
    }
  },

  computed: {
    /* 快速记录面板类别顺序：家长信息勾选的常用类别排最前（按勾选先后），
       未勾选的按 TYPES 原顺序殿后；note 为 mood 历史别名，不参与面板 */
    sortedTypes() {
      const all = Object.keys(TYPES).filter(k => k !== 'note')
      const picked = this.parentCats.filter(k => all.indexOf(k) > -1)
      const rest = all.filter(k => this.parentCats.indexOf(k) === -1)
      return picked.concat(rest)
    },
    /* 前 6 类走大磁贴区 */
    sheetTypes() {
      return this.sortedTypes.slice(0, 6)
    },
    /* 其余归入"更多"小磁贴区 */
    moreTypes() {
      return this.sortedTypes.slice(6)
    },
    /* 宝宝自定义头像（/files 文件 URL 解析为带 token 直链；未设置留空，模板回退本地图标占位） */
    avatar() {
      return api.fileSrc((this.baby && this.baby.avatar) || '')
    },
    /* 宝宝切换列表：仅头像 + 名字 + 年龄 */
    babyList() {
      return api.getBabies().map(b => ({
        id: b.id,
        name: b.name,
        age: b.age,
        is_active: b.is_active,
        avatarSrc: api.fileSrc(b.avatar || '')
      }))
    },
    /* 同步图标：App 端不支持内联 svg，描边色烘焙进 data URI（同步中转主题深橙） */
    syncSrc() {
      const c = palette(this.themeName)
      const stroke = this.syncing ? c['primary-deep'] : '#5FC08C'
      const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="' + stroke + '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/><path d="M12 12v6"/><path d="m9.5 14.5 2.5-2.5 2.5 2.5"/></svg>'
      return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
    },
    /* 按时段问候（v2 today-strip 文案） */
    greeting() {
      const h = new Date().getHours()
      if (h < 6) return '夜深了'
      if (h < 11) return '早上好'
      if (h < 13) return '中午好'
      if (h < 18) return '下午好'
      return '晚上好'
    },
    /* 问候尾缀贴当前主题 IP：小熊→蜂蜜梗；小鸭→"鸭"谐音梗 */
    cheerText() {
      return this.__theme === 'duck' ? '继续加油鸭' : '今天也甜甜的'
    },
    /* 今日记录总条数（bootstrap 缓存派生） */
    todayCount() {
      return api.getTodayCount()
    },
    /* 已加载记录按日分组（服务端返回 occurred_at 倒序：新日在前、日内最新在前）。
       date-row 条数：优先取服务端 day_totals（该日全天真实条数，跨页天也准确），
       无对应值（如刚删改尚未重拉）时退回该日已加载条数 */
    groups() {
      const map = {}
      const out = []
      let i = 0
      for (const e of this.items) {
        if (!map[e.day]) { map[e.day] = { day: e.day, dk: e.dk, items: [], total: 0 }; out.push(map[e.day]) }
        map[e.day].items.push({ ...e, _i: i++ })
        map[e.day].total++
      }
      for (const g of out) {
        if (this.dayTotals[g.dk] !== undefined) g.total = this.dayTotals[g.dk]
      }
      return out
    },
    /* 底部提示卡通图标（ctl 控制图标库，按状态取语义）：
       加载中→46-loading；还有更多→60-more；到底啦→66-ok（完成对勾） */
    scrollEndIcon() {
      const base = '/static/icons/ctl/' + this.__theme + '/'
      if (this.loadingMore) return base + '192/46-ctl-loading.png'
      if (this.hasMore) return base + '56/60-ctl-nav-more.png'
      return base + '64/66-ctl-modal-ok.png'
    },
    /* 进行中睡眠计时文本 hh:mm:ss */
    sleepTimerText() {
      if (this.sleepElapsed < 0) return ''
      const s = this.sleepElapsed
      const p = n => String(n).padStart(2, '0')
      return p(Math.floor(s / 3600)) + ':' + p(Math.floor(s / 60) % 60) + ':' + p(s % 60)
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
    /* 铃铛角标实时刷新：订阅未读变化（轮询拉到新通知/已读操作时回调），onUnload 退订 */
    this._offUnread = api.onUnreadChange(n => { this.unread = n })
  },

  onShow() {
    this.refresh()
  },

  onHide() {
    this.stopSleepTimer()
  },

  onUnload() {
    this.stopSleepTimer()
    if (this._offUnread) { this._offUnread(); this._offUnread = null }
  },

  methods: {
    /* 下拉刷新：tabSwipe 已重拉 bootstrap，这里复用本页刷新链路 */
    tabAfterPull() { return this.refresh() },
    /* 每次回到本页刷新：档案 / 今日概览 / 时光轴（记录会增删改） */
    async refresh() {
      this.syncing = true
      const b = api.getBaby()
      if (b) this.baby = b
      this.todayStats = api.getTodayStats()
      /* 常用记录类别：家长信息页保存后回本页即生效（setting 缓存非响应式，这里显式重读） */
      this.parentCats = (api.getParentInfo().cats || []).slice()
      /* 铃铛角标：消息中心未读通知数（待办不计入） */
      this.unread = api.getUnreadTotal()
      try {
        /* 专用分页接口拉第一页（服务端游标分页，不读全量缓存） */
        const p = await api.fetchTimeline({ limit: this.pageSize })
        this.items = p.items
        this.cursor = p.next_cursor
        this.hasMore = p.has_more
        this.dayTotals = p.day_totals || {}
      } catch (e) { /* 保留当前列表 */ }
      this.syncing = false
      this.syncSleepTimer()
    },
    /* 同步 chip：轻点重新拉取 */
    onSync() {
      if (!this.syncing) this.refresh()
    },
    /* 触底加载下一页：按游标请求 /entries/timeline */
    loadMore() {
      if (this.loadingMore || !this.hasMore) return
      this.loadingMore = true
      api.fetchTimeline({ cursor: this.cursor, limit: this.pageSize }).then(p => {
        this.items = this.items.concat(p.items)
        this.cursor = p.next_cursor
        this.hasMore = p.has_more
        this.dayTotals = Object.assign({}, this.dayTotals, p.day_totals)
        this.loadingMore = false
      }).catch(() => { this.loadingMore = false })
    },
    /* 记录人展示：与宝宝关系在前、昵称在后（「妈妈 · 小熊妈妈」）；按 creator_id 解析成员 */
    whoOf(e) {
      return api.creatorLabel(e)
    },
    /* rec-card 左描边色 + 入场错峰延迟（错峰上限 10 张，触底加载的新卡片不排长队） */
    cardStyle(e) {
      return {
        /* 未知/历史 type 不能让渲染函数抛错，否则整条时光轴白屏 */
        borderLeftColor: (TYPES[e.type] || TYPES.note).color,
        animationDelay: (Math.min(e._i, 9) * 60 + 200) + 'ms'
      }
    },
    /* ---------- 进行中睡眠实时计时 ---------- */
    findOngoing() {
      /* 进行中睡眠从 bootstrap 缓存查找（不受时光轴分页影响，原始行含 occurred_at） */
      return api.getOngoingSleep()
    },
    syncSleepTimer() {
      this.stopSleepTimer()
      const og = this.findOngoing()
      if (!og) { this.sleepElapsed = -1; return }
      const start = new Date(String(og.occurred_at).replace(' ', 'T')).getTime()
      /* occurred_at 畸形时 start 是 NaN：Math.max(0, NaN) 仍是 NaN，计时文案会常驻 NaN:NaN:NaN */
      if (!isFinite(start)) { this.sleepElapsed = -1; return }
      const tick = () => {
        const s = Math.max(0, Math.floor((Date.now() - start) / 1000))
        this.sleepElapsed = s
      }
      tick()
      this.sleepTimer = setInterval(tick, 1000)
    },
    stopSleepTimer() {
      if (this.sleepTimer) { clearInterval(this.sleepTimer); this.sleepTimer = null }
    },
    /* ---------- 里程碑庆祝 ---------- */
    openCelebrate(e) {
      const d = new Date()
      const dateTxt = d.getFullYear() + '.' + String(d.getMonth() + 1).padStart(2, '0') + '.' + String(d.getDate()).padStart(2, '0')
      this.cel = {
        show: true,
        title: e.title || '达成里程碑',
        sub: dateTxt + ' · ' + this.baby.name + ' ' + this.baby.age,
        /* 来源记录 id：「生成纪念卡」跳卡页时预选该里程碑 */
        entryId: e.id,
        /* 48 片彩带：圆点 / 长条混合，尺寸更大、错峰飘落、循环播放 */
        bits: Array.from({ length: 48 }, (_, i) => {
          const size = 16 + Math.floor(Math.random() * 18)
          const strip = i % 3 === 0
          return {
            left: Math.round(Math.random() * 98),
            color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
            delay: Math.round(Math.random() * 80) / 100,
            dur: 1.5 + Math.round(Math.random() * 90) / 100,
            round: i % 5 === 1,
            w: strip ? 10 + Math.floor(Math.random() * 8) : size,
            h: strip ? Math.round(size * 1.8) : size
          }
        })
      }
    },
    closeCelebrate() {
      this.cel.show = false
    },
    onCelCard() {
      this.cel.show = false
      /* 直达纪念卡页：主动选中「里程碑纪念卡」并预选刚庆祝的这条里程碑 */
      uni.navigateTo({ url: '/pages/card/card?type=milestone&entry=' + encodeURIComponent(this.cel.entryId || '') })
    },
    /* ---------- 快速记录面板 ---------- */
    /* 记录面板 / 庆祝弹层展开时禁用左右滑页（覆盖 tabSwipe 默认实现） */
    tabSwipeAllowed() {
      return !this.sheetOpen && !this.cel.show
    },
    toggleSheet() {
      this.sheetOpen = !this.sheetOpen
      /* 仅面板展开时播音效，收起不播 */
      if (this.sheetOpen) play('S01')
    },
    closeSheet() {
      this.sheetOpen = false
    },
    pickType(k) {
      /* 选中记录类型时播音效 */
      play('S02')
      this.sheetOpen = false
      uni.navigateTo({ url: '/pages/editor/editor?type=' + k })
    },
    /* ---------- 顶栏与时光轴交互 ---------- */
    /* 宝宝切换 sj-modal：点行切换当前宝宝（档案入口已移除） */
    pickBaby(b) {
      this.babyModalShow = false
      if (b && !b.is_active && b.id !== this.baby.id) {
        api.setActiveBaby(b.id)
        /* ensureVaccineSchedule 变异步：从服务端刷新该宝宝疫苗/里程碑后再刷新页面 */
        api.ensureVaccineSchedule().then(() => this.refresh())
      }
    },
    /* 顶栏搜索 → 搜索页（P34） */
    onSearch() {
      uni.navigateTo({ url: '/pages/search/search' })
    },
    /* 顶栏铃铛 → 消息中心（通知 / 待办 · 已读未读） */
    onBell() {
      uni.navigateTo({ url: '/pages/notify/notify' })
    },
    onEntry(e) {
      /* 刚完成一次拖拽：H5 松手会合成 click，400ms 内忽略，防止把刚展开的卡立刻收回 */
      if (Date.now() - (this._swipeEndAt || 0) < 400) return
      /* 已左滑展开的卡片：点击先收回，不进详情 */
      if (this.swipe.openId === e.id) { this.swipe.openId = ''; return }
      /* 所有类型统一 → 记录详情；里程碑庆祝由卡片右侧"庆祝一下"按钮触发 */
      uni.navigateTo({ url: '/pages/detail/detail?id=' + e.id })
    },

    /* ---------- 时光轴左滑删除 ---------- */
    /* 当前应展示的横向位移（px）：拖拽中卡实时跟手，展开卡固定露出删除块 */
    swipeX(e) {
      if (this.swipe.id === e.id) return this.swipe.x
      return this.swipe.openId === e.id ? -SWIPE_DEL_PX : 0
    },
    swipeStyle(e) {
      const x = this.swipeX(e)
      const pressed = this.swipe.id === e.id
      const s = {}
      /* 按下即接管 transform（含缩放反馈），拖拽起点不再从 hover-press 缩放跳回原尺寸 */
      if (x || pressed) s.transform = 'translateX(' + x + 'px)' + (pressed ? ' scale(0.97)' : '')
      /* 拖拽期间关掉 transition 保证跟手，松手回弹动画由 .rec-card 自带 */
      if (pressed && this.swipe.moved) s.transition = 'none'
      return s
    },
    onSwipeStart(ev, e) {
      /* 触屏取 touches[0]，桌面 H5 鼠标事件直接带 clientX/Y */
      const t = (ev.touches && ev.touches[0]) || ev
      if (this.swipe.openId && this.swipe.openId !== e.id) this.swipe.openId = ''
      this.swipe.id = e.id
      this.swipe.sx = t.clientX
      this.swipe.sy = t.clientY
      this.swipe.moved = false
      this.swipe.x = this.swipe.openId === e.id ? -SWIPE_DEL_PX : 0
    },
    onSwipeMove(ev, e) {
      if (this.swipe.id !== e.id) return
      const t = (ev.touches && ev.touches[0]) || ev
      const dx = t.clientX - this.swipe.sx
      const dy = t.clientY - this.swipe.sy
      if (!this.swipe.moved) {
        /* 起手先判定方向：纵向为主让位给页面滚动，不劫持 */
        if (Math.abs(dx) < 6) return
        if (Math.abs(dy) > Math.abs(dx)) return
        this.swipe.moved = true
      }
      const base = this.swipe.openId === e.id ? SWIPE_DEL_PX : 0
      /* 只记最新位移，一帧最多触发一次响应式更新（touchmove 可达 100Hz+） */
      this._pendingX = Math.max(-SWIPE_DEL_PX, Math.min(0, dx - base))
      if (this._rafId) return
      this._rafId = raf(() => { this._rafId = 0; this.swipe.x = this._pendingX })
    },
    onSwipeEnd(ev, e) {
      if (this.swipe.id !== e.id) return
      if (this._rafId) { caf(this._rafId); this._rafId = 0 }
      if (this.swipe.moved) {
        /* 卡片上的横向拖拽归左滑删除管：阻止 touchend 冒泡到页面根节点，
         * 避免同一次手势被 tabSwipe 判定为切页滑动；其他位置滑动不受影响 */
        if (ev && ev.stopPropagation) ev.stopPropagation()
        const x = this._pendingX !== undefined ? this._pendingX : this.swipe.x
        if (x < -SWIPE_DEL_PX / 2) this.swipe.openId = e.id
        else if (this.swipe.openId === e.id) this.swipe.openId = ''
        this._swipeEndAt = Date.now()
      }
      this._pendingX = undefined
      this.swipe.id = ''
      this.swipe.x = 0
    },
    onSwipeDelete(e) {
      ui.showModal({
        title: '删除记录',
        content: '确定删除「' + e.title + '」吗？删除后 30 天内可在回收站找回。',
        confirmText: '删除',
        danger: true,
        success: res => {
          if (!res.confirm) return
          api.deleteEntry(e.id)
            .then(() => { this.swipe.openId = ''; this.refresh() })
            .catch(err => ui.error(err, '删除失败'))
        }
      })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 原生 tabBar 在 webview 之外，fixed 元素 bottom 值已按「距 tab 栏上沿」换算 */

.page {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  z-index: 0;
  position: relative;
  min-height: 100vh;
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
}

/* 不要给 .content 加 z-index：会形成层叠上下文，把内部弹层（sj-picker/sj-popup 的 fixed 层）
   困在这一层，压不过页面级 z-index:40 的 sj-tabbar；背景沉底靠 .page 的层叠上下文即可 */
.content { position: relative; padding: 0 32rpx; }

/* ---------- 顶栏 appbar ---------- */
.appbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 24rpx;
}
.baby-chip {
  display: flex;
  align-items: center;
  gap: 16rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-pill);
  padding: 10rpx 24rpx 10rpx 10rpx;
  box-shadow: var(--sj-sh-sm);
}
.baby-chip:active { transform: scale(0.96); }
.baby-avatar {
  width: 68rpx;
  height: 68rpx;
  border-radius: 50%;
  background: var(--sj-primary-soft);
  flex: none;
}
.baby-name { display: flex; flex-direction: column; }
.baby-name text:first-child { font-size: 28rpx; font-weight: 800; line-height: 1.15; color: var(--sj-ink); }
.baby-age { font-size: 20rpx; font-weight: 600; color: var(--sj-sub); margin-top: 2rpx; }

/* ---------- 宝宝切换对话框列表（sj-modal 默认 slot） ---------- */
.baby-switch-list { max-height: 520rpx; width: 100%; }
.bs-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 16rpx 20rpx;
  border-radius: 28rpx;
  border: 2rpx solid var(--sj-line);
  background: rgba(255, 253, 251, 0.9);
}
.bs-row--on { border-color: var(--sj-primary); background: var(--sj-primary-soft); }
.bs-avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  background: var(--sj-primary-soft);
  flex: none;
}
.bs-name { font-size: 28rpx; font-weight: 800; color: var(--sj-ink); }
.bs-age { font-size: 22rpx; font-weight: 600; color: var(--sj-sub); margin-left: auto; }
.chev { width: 30rpx; height: 30rpx; flex: none; }
.bar-right { display: flex; align-items: center; gap: 14rpx; }
.icon-btn {
  position: relative;
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.88);
  border: 2rpx solid var(--sj-line);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--sj-sh-sm);
  flex: none;
}
.icon-btn:active { transform: scale(0.92); }
.ic17 { width: 36rpx; height: 36rpx; }
.badge-num {
  position: absolute;
  top: 2rpx;
  right: 2rpx;
  min-width: 30rpx;
  height: 30rpx;
  padding: 0 8rpx;
  box-sizing: border-box;
  border-radius: var(--sj-r-pill);
  background: var(--sj-bad);
  border: 3rpx solid #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.badge-num text { font-size: 18rpx; font-weight: 800; color: #fff; line-height: 1; }
.sync-chip {
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 22rpx;
  font-weight: 700;
  color: var(--sj-ok);
  background: #E2F5EA;
  border-radius: var(--sj-r-pill);
  padding: 12rpx 22rpx;
  transition: all 0.3s;
}
.sync-chip text { line-height: 1; }
.ic-sync { width: 30rpx; height: 30rpx; flex: none; }
.sync-chip.spinning { color: var(--sj-primary-deep); background: var(--sj-primary-soft); }
.sync-chip.spinning .ic-sync { animation: spin 0.72s cubic-bezier(.22,.8,.3,1) infinite; }
@keyframes spin { to { transform: rotate(720deg); } }

/* ---------- 今日问候条 ---------- */
.today-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, #FFE8DB, #FFF2DE);
  border: 2rpx solid #FFDCC0;
  border-radius: var(--sj-r-md);
  padding: 28rpx 32rpx;
  margin-bottom: 24rpx;
}
.today-txt { display: flex; flex-direction: column; gap: 6rpx; }
.tt-hello { font-size: 30rpx; font-weight: 800; color: var(--sj-ink); }
.tt-sub { font-size: 24rpx; color: var(--sj-sub); }
.cnt { font-weight: 900; color: var(--sj-primary-deep); }
.peek-wrap { flex: none; animation: peek 3s ease-in-out infinite; transform-origin: bottom center; }
@keyframes peek {
  0%, 100% { transform: translateY(0) rotate(0); }
  50% { transform: translateY(-6px) rotate(4deg); }
}

/* ---------- 当日统计胶囊 ---------- */
.day-summary { display: flex; gap: 16rpx; margin-bottom: 28rpx; flex-wrap: wrap; }
.ds-chip {
  display: flex;
  align-items: center;
  gap: 10rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-pill);
  padding: 8rpx 20rpx 8rpx 8rpx;
}
.ds-chip:active { transform: scale(0.95); }
.ds-ic {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  padding: 4rpx;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
/* 图标图片圆角与外圈曲线平行（同心）：外半径 24 - 内边距 4 = 20rpx（即图片整圆） */
.ds-ic .sj-icon { border-radius: 50%; }
.ds-txt { font-size: 23rpx; font-weight: 700; color: var(--sj-ink); }

/* ---------- 时光轴 ---------- */
.timeline { display: flex; flex-direction: column; padding-bottom: 300rpx; }
.day-group { margin-bottom: 8rpx; }
.date-row { display: flex; align-items: center; gap: 20rpx; margin: 12rpx 0 20rpx; }
.dr-line { flex: 1; height: 2rpx; border-radius: 2rpx; background: var(--sj-line); }
.dr-label { font-size: 24rpx; font-weight: 700; color: var(--sj-faint); flex: none; }
.dr-count {
  font-size: 20rpx; font-weight: 700; color: var(--sj-sub);
  background: var(--sj-surface); border: 2rpx solid var(--sj-line);
  padding: 2rpx 14rpx; border-radius: var(--sj-r-pill); flex: none;
}

.rec-card {
  display: flex;
  align-items: center;
  gap: 24rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-left: 8rpx solid var(--sj-primary);
  border-radius: var(--sj-r-md);
  padding: 24rpx 28rpx;
  margin-bottom: 20rpx;
  box-shadow: var(--sj-sh-sm);
  animation: cardIn 0.5s cubic-bezier(.22,.8,.3,1) backwards;
}
.rec-card:active { transform: scale(0.97); }
/* 左滑删除：间距收在包装层上，删除块与卡片严格等高对齐；
 * 卡片底是半透明 surface，收起态必须隐藏删除块，否则红色会从卡片底下透出来 */
.rec-swipe { position: relative; margin-bottom: 20rpx; }
.rec-swipe .rec-card { margin-bottom: 0; }
.swipe-del {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 150rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #EF7A7A, #D95A5A);
  border-radius: var(--sj-r-md);
  color: #fff;
  font-size: 27rpx;
  font-weight: 800;
  letter-spacing: 2rpx;
  box-shadow: var(--sj-sh-sm);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.18s ease-out;
}
.swipe-del.del-show { opacity: 1; pointer-events: auto; }
/* 展开/回弹动画（拖拽跟手时由内联 transition:none 覆盖） */
.rec-card { transition: transform 0.18s ease-out; }
/* 拖拽/展开中的卡片提升为合成层，transform 逐帧更新不触发重排 */
.rec-card.swipe-on, .rec-card:active { will-change: transform; }
.rec-ic {
  width: 88rpx;
  height: 88rpx;
  border-radius: 28rpx;
  padding: 6rpx;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
/* 图标图片圆角与外圈曲线平行（同心）：外半径 28 - 内边距 6 = 22rpx */
.rec-ic .sj-icon { border-radius: 22rpx; }
.rec-info { flex: 1; min-width: 0; }
.rec-title { display: flex; align-items: center; gap: 12rpx; }
.rec-title text:first-child { font-size: 28rpx; font-weight: 800; color: var(--sj-ink); }
.rec-meta {
  display: flex;
  align-items: center;
  gap: 10rpx;
  font-size: 23rpx;
  color: var(--sj-sub);
  margin-top: 6rpx;
  white-space: nowrap;
  overflow: hidden;
}
.rec-note {
  display: block;
  font-size: 22rpx;
  color: var(--sj-sub);
  margin-top: 8rpx;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.rec-photo {
  width: 96rpx;
  height: 96rpx;
  border-radius: 20rpx;
  flex: none;
  border: 4rpx solid #fff;
  box-shadow: var(--sj-sh-sm);
}
.rec-time { font-size: 23rpx; font-weight: 700; color: var(--sj-faint); flex: none; }

/* 里程碑卡：金色绘本底 + 庆祝角标 */
.rec-milestone {
  background: linear-gradient(135deg, rgba(255, 248, 227, 0.82), rgba(255, 243, 196, 0.82));
  border-color: #F5D888;
  border-left-color: var(--sj-c-milestone);
}
.ms-badge {
  font-size: 21rpx;
  font-weight: 800;
  color: #B47714;
  background: var(--sj-surface);
  border-radius: var(--sj-r-pill);
  padding: 8rpx 20rpx;
  box-shadow: var(--sj-sh-sm);
  flex: none;
}
/* 里程碑右侧竖排：时间在上、庆祝按钮在下 */
.ms-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10rpx;
  flex: none;
}

/* 进行中睡眠卡：虚线描边 + zzz + 实时计时 */
.rec-ongoing { border-left-style: dashed; }
.zzz { display: flex; gap: 2rpx; align-items: flex-end; }
.zzz text {
  font-style: normal;
  font-weight: 900;
  font-size: 22rpx;
  color: var(--sj-c-sleep);
  animation: zfloat 2.2s infinite;
}
.zzz text:nth-child(2) { animation-delay: 0.4s; font-size: 26rpx; }
.zzz text:nth-child(3) { animation-delay: 0.8s; font-size: 30rpx; }
@keyframes zfloat {
  0% { opacity: 0; transform: translateY(4px); }
  30% { opacity: 1; }
  100% { opacity: 0; transform: translateY(-10px); }
}
.og-dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background: var(--sj-c-sleep);
  flex: none;
  animation: dotPulse 1.4s infinite;
}
.og-txt { font-weight: 700; color: var(--sj-c-sleep); }
@keyframes dotPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.35; transform: scale(0.7); }
}

/* 语音播放条（组件内自绘波形，这里只负责在卡片里占一行） */
.rec-voice { margin-top: 12rpx; flex: none; }

/* 徽标（补记 / P50 等非里程碑类型） */
.badge { font-size: 20rpx; font-weight: 700; padding: 4rpx 16rpx; border-radius: var(--sj-r-pill); }
.badge.backfill { color: var(--sj-faint); border: 2rpx dashed var(--sj-faint); }
.badge.ongoing { background: #E9EEFB; color: var(--sj-c-sleep); }
.badge.p50 { background: var(--sj-tint-measure); color: var(--sj-c-measure); }

/* 空态 / 收尾 */
.empty { text-align: center; padding: 96rpx 40rpx; display: flex; flex-direction: column; align-items: center; gap: 24rpx; }
.empty-text { font-size: 26rpx; color: var(--sj-sub); line-height: 1.7; }
.scroll-end {
  display: flex; align-items: center; justify-content: center; gap: 12rpx;
  font-size: 22rpx; color: var(--sj-faint); padding: 24rpx 0 16rpx; letter-spacing: 4rpx;
}
.se-ic { width: 44rpx; height: 44rpx; flex: none; }
/* 加载中：卡通图标上下弹跳 */
.se-ic.bounce { animation: seBounce 0.8s ease-in-out infinite; }
@keyframes seBounce {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(8rpx) scale(1.08); }
}

@keyframes cardIn {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to { opacity: 1; transform: none; }
}

/* ---------- P08 遮罩 + 底部面板 ---------- */
.sheet-mask {
  position: fixed; left: 0; top: 0; right: 0; bottom: 0; z-index: 50;
  background: var(--sj-mask);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s;
}
.sheet-mask.show { opacity: 1; pointer-events: auto; }

.sheet {
  position: fixed; left: 32rpx; right: 32rpx; bottom: 24rpx; z-index: 66;
  background: #FFFDF9;
  border-radius: 60rpx 60rpx 48rpx 48rpx;
  padding: 20rpx 36rpx 36rpx;
  box-shadow: var(--sj-sh-lg);
  transform: translateY(120%);
  transition: transform 0.5s cubic-bezier(.34,1.56,.64,1);
}
.sheet.open { transform: translateY(0); }
.sheet-handle { width: 88rpx; height: 10rpx; border-radius: 6rpx; background: var(--sj-line); margin: 4rpx auto 24rpx; }
.sheet-head { display: flex; align-items: baseline; gap: 16rpx; margin-bottom: 28rpx; }
.sh-title { font-family: var(--sj-font-display); font-size: 34rpx; font-weight: 900; color: var(--sj-ink); }
.sh-sub { font-size: 22rpx; font-weight: 600; color: var(--sj-sub); }
.sheet-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20rpx; }
.tile {
  border-radius: var(--sj-r-md);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  padding: 28rpx 8rpx 24rpx;
  opacity: 0;
}
.sheet.open .tile { animation: tilePop 0.38s cubic-bezier(.34,1.56,.64,1) both; }
.tile:active { transform: scale(0.92); }
.t-label { font-size: 26rpx; font-weight: 800; color: var(--sj-ink); }
@keyframes tilePop {
  from { opacity: 0; transform: scale(0.5) translateY(8px); }
  to { opacity: 1; transform: none; }
}
.sheet-more { display: flex; align-items: center; gap: 16rpx; margin-top: 24rpx; }
.sm-label { font-size: 22rpx; font-weight: 800; color: var(--sj-faint); flex: none; letter-spacing: 2rpx; }
.tile-sm {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  border-radius: var(--sj-r-pill);
  padding: 16rpx 8rpx;
  font-size: 23rpx;
  font-weight: 700;
  color: var(--sj-ink);
}
.tile-sm:active { transform: scale(0.92); }
.tile-sm text { line-height: 1; }
/* 取消按钮：外观由 sj-button ghost 提供，这里只留面板内的位置 */
.sheet-close { margin-top: 28rpx; }

/* ---------- FAB ---------- */
.fab {
  position: fixed; right: 48rpx; bottom: 210rpx; z-index: 70;
  width: 120rpx; height: 120rpx; border-radius: 50%;
  background: linear-gradient(145deg, var(--sj-primary), var(--sj-primary-deep));
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 20rpx 48rpx rgba(224, 126, 51, 0.45);
  transition: transform 0.3s cubic-bezier(.34,1.56,.64,1);
  animation: fabIn 0.6s 0.5s cubic-bezier(.34,1.56,.64,1) backwards;
}
.fab:active { transform: scale(0.92); }
.fab-ic { width: 52rpx; height: 52rpx; transition: transform 0.35s cubic-bezier(.34,1.56,.64,1); }
.fab.open { transform: rotate(45deg); }
.fab.open .fab-ic { transform: rotate(-45deg); }
.fab-ring {
  position: fixed; right: 48rpx; bottom: 210rpx; z-index: 65;
  width: 120rpx; height: 120rpx; border-radius: 50%;
  border: 4rpx solid rgba(247, 161, 92, 0.4);
  pointer-events: none;
  animation: fabBreath 2s infinite;
}
@keyframes fabIn {
  from { opacity: 0; transform: scale(0.4); }
  to { opacity: 1; transform: none; }
}
@keyframes fabBreath {
  0% { transform: scale(0.9); opacity: 0.8; }
  70% { transform: scale(1.25); opacity: 0; }
  100% { opacity: 0; }
}

/* ---------- 里程碑庆祝弹层 ---------- */
.celebrate {
  position: fixed; left: 0; top: 0; right: 0; bottom: 0; z-index: 80;
  display: flex; align-items: center; justify-content: center;
  background: rgba(58, 38, 28, 0.66);
  animation: fadeIn 0.3s;
}
.confetti-layer { position: absolute; left: 0; top: 0; right: 0; bottom: 0; pointer-events: none; overflow: hidden; z-index: 2; }
.confetti-bit {
  position: absolute; top: -80rpx;
  /* 循环飘落：末帧在屏幕外淡出，重启无跳变；时长/延迟由内联样式逐片覆盖 */
  animation: fallCel 1.8s linear infinite;
  will-change: transform;
}
@keyframes fallCel {
  0% { transform: translate3d(0, -60rpx, 0) rotate(0deg); opacity: 1; }
  20% { transform: translate3d(44rpx, 22vh, 0) rotate(220deg); }
  45% { transform: translate3d(-36rpx, 48vh, 0) rotate(430deg); }
  70% { transform: translate3d(36rpx, 74vh, 0) rotate(640deg); }
  88% { transform: translate3d(-20rpx, 100vh, 0) rotate(820deg); opacity: 1; }
  100% { transform: translate3d(-20rpx, 112vh, 0) rotate(900deg); opacity: 0; }
}
.cel-card {
  position: relative; z-index: 3;
  width: 80%; max-width: 560rpx;
  background: linear-gradient(165deg, #FFFBEF, #FFF3D9);
  border: 4rpx solid #F5D888;
  border-radius: var(--sj-r-lg);
  padding: 52rpx 40rpx 44rpx;
  text-align: center;
  box-shadow: var(--sj-sh-lg);
  /* 入场弹跳 + 持续金色光晕呼吸 */
  animation: celIn 0.6s cubic-bezier(.34,1.56,.64,1), celGlow 1.8s 0.6s ease-in-out infinite;
  display: flex; flex-direction: column; align-items: center;
}
.cel-trophy {
  /* 入场旋转 + 循环弹跳，配金色光晕 */
  animation: trophySpin 0.9s cubic-bezier(.34,1.56,.64,1), trophyBounce 1.5s 0.9s ease-in-out infinite;
  filter: drop-shadow(0 0 28rpx rgba(245, 179, 44, 0.85));
}
.cel-title {
  display: block; font-family: var(--sj-font-display); font-size: 40rpx; font-weight: 900; color: var(--sj-ink); margin-top: 20rpx;
  animation: titlePop 0.5s 0.25s cubic-bezier(.34,1.56,.64,1) backwards;
}
.cel-sub { display: block; font-size: 24rpx; color: var(--sj-sub); margin-top: 4rpx; }
.cel-btns { display: flex; gap: 20rpx; margin-top: 36rpx; width: 100%; }
/* 庆祝弹层两颗按钮：外观（渐变主按钮 / ghost 描边按钮）由 sj-button 提供，此处只分配宽度 */
.cel-main { flex: 1.4; }
.cel-ghost { flex: 1; }
@keyframes celIn {
  from { opacity: 0; transform: scale(0.35) rotate(-6deg) translateY(40px); }
  to { opacity: 1; transform: none; }
}
@keyframes celGlow {
  0%, 100% { box-shadow: var(--sj-sh-lg), 0 0 70rpx rgba(245, 179, 44, 0.5); }
  50% { box-shadow: var(--sj-sh-lg), 0 0 150rpx rgba(245, 179, 44, 0.9); }
}
@keyframes trophySpin {
  0% { transform: scale(0) rotate(-70deg); }
  60% { transform: scale(1.3) rotate(14deg); }
  100% { transform: scale(1) rotate(0); }
}
@keyframes trophyBounce {
  0%, 100% { transform: translateY(0) scale(1); }
  30% { transform: translateY(-16rpx) scale(1.1); }
  60% { transform: translateY(0) scale(0.96); }
}
@keyframes titlePop {
  from { opacity: 0; transform: scale(0.5) translateY(14px); }
  to { opacity: 1; transform: none; }
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
</style>
