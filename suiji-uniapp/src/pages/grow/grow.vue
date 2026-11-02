<template>
  <view class="page" :class="swipeClass" :style="themeVars" @touchstart="onTabTouchStart" @touchend="onTabTouchEnd">
    <sj-bg />
    <!-- 时间范围 chips（本地切换） -->
    <view class="range-chips">
      <view
        v-for="(r, i) in rangeChips"
        :key="r"
        class="rchip"
        :class="{ active: growRange === i }"
        hover-class="hover-press"
        :hover-stay-time="80"
        @click="growRange = i"
      >
        <text>{{ r }}</text>
      </view>
    </view>

    <!-- 早产矫正提示条（真实数据：胎龄 <37 周才按矫正年龄计算；足月不显示） -->
    <view class="preterm-bar" v-if="pretermText">
      <text>{{ pretermText }}</text>
    </view>

    <!-- 指标切换：体重 / 身高 / 头围 -->
    <view class="metric-tabs">
      <view
        v-for="k in metricKeys"
        :key="k"
        class="metric-tab"
        :class="{ active: growMetric === k }"
        hover-class="hover-press"
        :hover-stay-time="80"
        @click="growMetric = k"
      >
        <text>{{ GROW[k].label }}</text>
      </view>
    </view>

    <!-- 生长曲线卡（v2 grow-card：绘本白卡 + 主题色曲线，SVG data-uri 渲染） -->
    <view class="grow-card">
      <view class="gc-head">
        <text class="gc-title">{{ curMetric.label }}曲线</text>
        <text class="gc-sub">对照 WHO P3–P97 · {{ rangeChips[growRange] }}</text>
      </view>
      <image class="gc-curve" mode="widthFix" :src="chartSrc" />
      <view class="gc-foot">
        <text v-for="l in legend" :key="l.t" class="lg-item">
          <text class="lg-swatch" :style="{ background: l.c }" />{{ l.t }}
        </text>
      </view>
    </view>

    <!-- 当前值三卡（取各曲线最新点 + 百分位徽标） -->
    <view class="now-row">
      <view class="now-card" v-for="n in nowCards" :key="n.label">
        <text class="nc-val">{{ n.val }}</text>
        <text class="nc-label">{{ n.label }}</text>
        <text class="nc-p50">{{ n.p }}</text>
      </view>
    </view>

    <!-- 趋势卡（真实数据评估，走向随曲线实测点变化；合规红线：小字文案必须原样保留） -->
    <view class="trend-card">
      <text v-if="trendText" class="tc-text">{{ trendText }}</text>
      <text class="tc-note">趋势描述仅供参考，不构成医学结论 · 标准来源：WHO 儿童生长标准（2006）</text>
    </view>

    <!-- 成长对比与纪念（P31/P32/P33 + AI 日记，v2 entry-grid 双列卡） -->
    <view class="entry-grid">
      <view
        class="entry-card"
        :class="{ 'entry-disabled': c.disabled }"
        v-for="c in entryCards"
        :key="c.url"
        :hover-class="c.disabled ? 'none' : 'hover-press'"
        :hover-stay-time="80"
        @click="goPage(c)"
      >
        <view class="ec-icon" :style="{ background: c.tint }">
          <sj-icon :name="c.png" :size="72" />
        </view>
        <text class="ec-title">{{ c.title }}</text>
        <text class="ec-sub">{{ c.sub }}</text>
      </view>
    </view>

    <!-- 里程碑 · 5 大领域（v2 ms-chip 双行卡：图标 + 名称/状态，达成绿 / 待解锁弱化；
         达成的里程碑可点击直达纪念卡页并预选该里程碑） -->
    <block v-for="g in domainGroups" :key="g.d">
      <view class="ms-domain"><text>{{ g.d }}</text></view>
      <view class="ms-grid">
        <view
          class="ms-chip"
          :class="ms.done ? 'done' : 'todo'"
          v-for="ms in g.items"
          :key="ms.name"
          :hover-class="ms.done ? 'hover-press' : ''"
          :hover-stay-time="80"
          @click="goMsCard(ms)"
        >
          <sj-icon name="03-milestone" :size="52" />
          <view class="ms-txt">
            <text class="ms-name">{{ ms.name }}</text>
            <text class="ms-st">{{ ms.done ? ms.month : '待解锁' }}</text>
          </view>
        </view>
      </view>
    </block>

    <!-- 测量记录 -->
    <view class="section-title"><text>测量记录</text></view>
    <view class="info-card">
      <view class="field-row" v-for="r in measures" :key="r.date">
        <view class="fr-left">
          <text class="fr-date">{{ r.date }}</text>
          <text class="m-age">{{ r.age }}</text>
        </view>
        <view class="fr-right">
          <text class="time-val">{{ msVals(r) }}</text>
        </view>
      </view>
    </view>

    <!-- 录入测量 -->
    <view class="add-measure-btn" hover-class="hover-press" :hover-stay-time="80" @click="goMeasure">
      <text>+ 录入测量</text>
    </view>

    <view class="scroll-end"><text>· 晚于参考区间仅中性展示，可咨询儿保医生 ·</text></view>

    <!-- v2 悬浮底部导航（自动隐藏原生 tabBar） -->
    <sj-tabbar active="grow" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import tabSwipe, { pullRefresh } from '@/utils/tabSwipe.js'
import { palette } from '@/theme/theme.js'

/* growRange 索引 → 时间范围：近6月 / 近3月 / 近7天 / 全部（week=true 时曲线按天粒度出图） */
const RANGES = [
  { chip: '近6月', months: 6, week: false },
  { chip: '近3月', months: 3, week: false },
  { chip: '近7天', months: 7 / 30.4375, week: true },
  { chip: '全部', months: 0, week: false }
]

export default {
  mixins: [tabSwipe],
  /* 下拉刷新（Vue3 生命周期必须顶层声明，混入 methods 里的不会触发）：重拉 bootstrap 后走 tabAfterPull */
  onPullDownRefresh() { pullRefresh(this) },
  data() {
    const baby = api.getBaby()
    return {
      GROW: api.getGrowth(RANGES[0].months, RANGES[0].week),
      latest: api.getLatest(),
      measures: api.getMeasures(),
      milestones: api.getMilestones(),
      growMetric: 'weight',
      metricKeys: ['weight', 'height', 'head'],
      growRange: 0,
      rangeChips: RANGES.map(r => r.chip),
      domains: ['大运动', '精细动作', '语言', '认知', '社交'],
      babyName: (baby && baby.name) || '宝宝',
      /* 出生胎龄（周）：驱动早产矫正提示条（reload 随宝宝档案刷新） */
      gestWeeks: Number((baby && baby.gestational_weeks) || 0),
      /* v2 entry-grid：功能入口双列卡（图标走 v2 png 库） */
      entryCards: [
        { png: '20-fn-diary', tint: '#FDE9F2', title: 'AI 成长日记', sub: '基于本周记录自动生成', url: '/pages/diary/diary' },
        { png: '31-fn-compare', tint: '#E4F3FB', title: '同月龄对比', sub: '不使用人脸识别', url: '/pages/compare/compare' },
        { png: '32-fn-card', tint: '#FFF3C4', title: '纪念卡', sub: '百日 / 周岁 / 里程碑 · 一键生成', url: '/pages/card/card' },
        { png: '33-fn-video', tint: '#E2F5EA', title: '成长视频制作', sub: '30–90 秒 · 手机里制作不上传', url: '/pages/video/video', disabled: true }
      ]
    }
  },

  watch: {
    /* 切换时间范围：按对应月数重新取曲线数据 */
    growRange() {
      this.reload()
    }
  },

  onShow() {
    this.reload()
  },

  computed: {
    curMetric() {
      return this.GROW[this.growMetric]
    },

    /* 当前主题色板（曲线/图例随 bear/duck 换肤） */
    tc() {
      return palette(this.__theme)
    },

    /* 图例色块：运行时取主题色 */
    legend() {
      return [
        { t: '参考带', c: this.tc['primary'] },
        { t: 'P50', c: this.tc['sub'] },
        { t: this.babyName, c: this.tc['primary-deep'] }
      ]
    },

    /* 早产矫正提示：胎龄 <37 周才按矫正年龄计算（40 周足月基准，与曲线 ageMonths / 服务端 corrected_age_flag 同口径）；空串=足月不显示 */
    pretermText() {
      return this.gestWeeks > 0 && this.gestWeeks < 37
        ? '已按矫正年龄计算（胎龄 ' + this.gestWeeks + ' 周）'
        : ''
    },

    /* 趋势评估（真实数据）：baby 与 p50 同长度按索引对齐，取窗口内首/末实测点
       相对 P50 的偏差（baby/p50-1）变化判断走向：变化 ≤5% 视为基本平行，
       否则上升/回落；实测点不足 2 个时无法评估，返回空串隐藏整句（合规小字保留） */
    trendText() {
      const m = this.curMetric
      const idx = []
      for (let i = 0; i < m.baby.length; i++) {
        if (m.baby[i] != null && m.p50[i] > 0) idx.push(i)
      }
      if (idx.length < 2) return ''
      const dev = i => m.baby[i] / m.p50[i] - 1
      const delta = dev(idx[idx.length - 1]) - dev(idx[0])
      const chip = this.rangeChips[this.growRange]
      const win = chip === '全部' ? '全程' : chip
      const dir = Math.abs(delta) <= 0.05 ? '与 P50 参考线基本平行'
        : delta > 0 ? '较 P50 参考线呈上升趋势' : '较 P50 参考线有所回落'
      return win + m.label + '曲线' + dir + '。'
    },

    /* 当前值三卡：各指标最新值 + 百分位徽标 */
    nowCards() {
      return this.metricKeys.map(k => ({
        val: this.latest[k].value,
        label: this.GROW[k].label + '（' + this.GROW[k].unit + '）',
        p: this.latest[k].p
      }))
    },

    /* 里程碑按 5 大领域分组；用户自定义的里程碑（不在预置领域内）追加「自定义」分组 */
    domainGroups() {
      const groups = this.domains.map(d => ({ d, items: this.milestones.filter(x => x.domain === d) }))
      const custom = this.milestones.filter(x => !this.domains.includes(x.domain))
      if (custom.length) groups.push({ d: '自定义', items: custom })
      return groups
    },

    /* 生长曲线 SVG：坐标映射逻辑不变，配色改为当前主题（data-uri 无法用 CSS 变量，取十六进制）
       （viewBox 320×170 为 SVG 独立坐标系，内部尺寸不做 ×2 换算） */
    chartSrc() {
      const m = this.curMetric
      const t = this.tc
      const n = m.months
      const W = 320, H = 170, PL = 26, PR = 6, PT = 8, PB = 20
      const x = i => PL + (i * (W - PL - PR)) / n
      const y = v => PT + (1 - (v - m.min) / (m.max - m.min)) * (H - PT - PB)
      /* Catmull-Rom → 三次贝塞尔：折线转光滑曲线（tension 1/6，过点拟合） */
      const seg = pts => {
        let d = ''
        for (let i = 0; i < pts.length - 1; i++) {
          const p0 = pts[i - 1] || pts[i]
          const p1 = pts[i]
          const p2 = pts[i + 1]
          const p3 = pts[i + 2] || p2
          d += `C${(p1[0] + (p2[0] - p0[0]) / 6).toFixed(1)},${(p1[1] + (p2[1] - p0[1]) / 6).toFixed(1)} ` +
            `${(p2[0] - (p3[0] - p1[0]) / 6).toFixed(1)},${(p2[1] - (p3[1] - p1[1]) / 6).toFixed(1)} ` +
            `${p2[0].toFixed(1)},${p2[1].toFixed(1)}`
        }
        return d
      }
      /* null（范围过滤后的缺点）分段：每段独立起笔画光滑曲线 */
      const line = arr => {
        const segs = []
        let pts = []
        arr.forEach((v, i) => {
          if (v == null) {
            if (pts.length > 1) segs.push(`M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}` + seg(pts))
            pts = []
          } else pts.push([x(i), y(v)])
        })
        if (pts.length > 1) segs.push(`M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}` + seg(pts))
        return segs.join(' ')
      }
      /* 参考带：P97 上缘 + P3 下缘（反向）闭合，两缘均走光滑曲线 */
      const top = m.p97.map((v, i) => [x(i), y(v)])
      const bot = m.p3.map((v, i) => [x(i), y(v)]).reverse()
      const band = `M${top[0][0].toFixed(1)},${top[0][1].toFixed(1)}` + seg(top) +
        `L${bot[0][0].toFixed(1)},${bot[0][1].toFixed(1)}` + seg(bot) + 'Z'
      const grid = [m.min, (m.min + m.max) / 2, m.max].map(v =>
        `<line x1="${PL}" y1="${y(v).toFixed(1)}" x2="${W - PR}" y2="${y(v).toFixed(1)}" stroke="${t.line}" stroke-width="1"/>` +
        `<text x="${PL - 4}" y="${(y(v) + 3).toFixed(1)}" text-anchor="end" font-size="8" fill="${t.faint}">${v}</text>`).join('')
      let lastIdx = -1
      m.baby.forEach((v, i) => { if (v != null) lastIdx = i })
      const dots = m.baby.map((v, i) => v == null ? '' :
        `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="${i === lastIdx ? 5 : 3}" fill="#fff" stroke="${t['primary-deep']}" stroke-width="2"/>`).join('')
      /* X 轴刻度：窗口视图（近7天/近N月）用数据侧 labels（'10.23'/'4月'）；全部视图回落月龄 'N月' */
      const xLabels = Array.from({ length: n + 1 }, (_, i) =>
        `<text x="${x(i).toFixed(1)}" y="${H - 6}" text-anchor="middle" font-size="8" fill="${t.faint}">${m.labels ? m.labels[i] : i + '月'}</text>`).join('')
      const svg =
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${m.label}生长曲线">` +
        grid +
        `<path d="${band}" fill="${t['primary']}" opacity=".16"/>` +
        `<path d="${line(m.p97)}" fill="none" stroke="${t['primary']}" stroke-width="1.2" stroke-dasharray="3 3" opacity=".55"/>` +
        `<path d="${line(m.p3)}" fill="none" stroke="${t['primary']}" stroke-width="1.2" stroke-dasharray="3 3" opacity=".55"/>` +
        `<path d="${line(m.p50)}" fill="none" stroke="${t.sub}" stroke-width="1.4" stroke-dasharray="5 4"/>` +
        `<path d="${line(m.baby)}" fill="none" stroke="${t['primary-deep']}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>` +
        dots + xLabels +
        `</svg>`
      return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
    }
  },

  methods: {
    /* 下拉刷新：tabSwipe 已重拉 bootstrap，这里按缓存重算曲线 */
    tabAfterPull() { this.reload() },
    /* 每次回到本页刷新：曲线 / 当前值 / 测量 / 里程碑 / 宝宝名 */
    reload() {
      const baby = api.getBaby()
      if (baby) {
        this.babyName = baby.name
        this.gestWeeks = Number(baby.gestational_weeks) || 0
      }
      this.GROW = api.getGrowth(RANGES[this.growRange].months, RANGES[this.growRange].week)
      this.latest = api.getLatest()
      this.measures = api.getMeasures()
      this.milestones = api.getMilestones()
    },
    /* 测量值紧凑串：只拼实际存在的指标，缺项不占位，避免过长换行 */
    msVals(r) {
      const p = []
      if (r.h) p.push(r.h + 'cm')
      if (r.w) p.push(r.w + 'kg')
      if (r.c) p.push(r.c + 'cm')
      return p.length ? p.join(' · ') : '—'
    },
    goPage(c) {
      if (c.disabled) {
        uni.showToast({ title: '功能暂未开放', icon: 'none' })
        return
      }
      uni.navigateTo({ url: c.url })
    },
    goMeasure() {
      uni.navigateTo({ url: '/pages/editor/editor?type=measure' })
    },
    /* 达成的里程碑 → 纪念卡页（里程碑卡型 + 预选该里程碑）；待解锁不响应 */
    goMsCard(ms) {
      if (!ms.done) return
      uni.navigateTo({ url: '/pages/card/card?type=milestone&ms=' + encodeURIComponent(ms.id) })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 默认导航栏 Tab 页：无自定义顶栏，左右安全边距 32rpx，底部留安全区 */
.page {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  position: relative;
  z-index: 0;
  min-height: 100vh;
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
  padding: 24rpx 32rpx 48rpx;
  box-sizing: border-box;
}

/* ---------- 时间范围 chips ---------- */
.range-chips { display: flex; gap: 16rpx; margin-bottom: 20rpx; }
.rchip {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  color: var(--sj-sub);
  font-size: 24rpx;
  font-weight: 700;
  padding: 10rpx 28rpx;
  border-radius: var(--sj-r-pill);
  transition: all 0.2s;
}
.rchip.active { background: var(--sj-primary-soft); border-color: transparent; color: var(--sj-primary-deep); }

/* ---------- 早产矫正提示条 ---------- */
.preterm-bar {
  display: flex;
  align-items: center;
  gap: 12rpx;
  font-size: 23rpx;
  color: #8A6A1E;
  background: #FFF3D6;
  border: 2rpx dashed #F0CE7A;
  border-radius: var(--sj-r-sm);
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
}
.pb-tag {
  font-size: 20rpx;
  background: rgba(0, 0, 0, 0.07);
  color: #8A6A1E;
  border-radius: var(--sj-r-pill);
  padding: 2rpx 16rpx;
  margin-left: auto;
}

/* ---------- 指标切换 ---------- */
.metric-tabs { display: flex; gap: 16rpx; margin-bottom: 28rpx; }
.metric-tab {
  flex: 1;
  border: 3rpx solid var(--sj-line);
  background: var(--sj-surface);
  color: var(--sj-sub);
  font-size: 26rpx;
  font-weight: 700;
  padding: 16rpx 0;
  border-radius: var(--sj-r-md);
  text-align: center;
  transition: all 0.25s;
}
.metric-tab.active {
  color: var(--sj-primary-deep);
  border-color: var(--sj-primary);
  background: var(--sj-primary-soft);
  box-shadow: var(--sj-sh-sm);
}

/* ---------- 曲线卡（v2 grow-card） ---------- */
.grow-card {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 28rpx 32rpx;
  box-shadow: var(--sj-sh-sm);
  margin-bottom: 24rpx;
}
.gc-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12rpx; }
.gc-title { font-size: 29rpx; font-weight: 800; color: var(--sj-ink); }
.gc-sub { font-size: 22rpx; color: var(--sj-sub); }
.gc-curve { width: 100%; display: block; }
.gc-foot { display: flex; gap: 28rpx; padding-top: 12rpx; }
.lg-item { display: flex; align-items: center; font-size: 21rpx; color: var(--sj-sub); }
.lg-swatch { width: 28rpx; height: 6rpx; border-radius: 6rpx; margin-right: 8rpx; }

/* ---------- 当前值三卡 ---------- */
.now-row { display: flex; gap: 20rpx; margin-bottom: 24rpx; }
.now-card {
  flex: 1;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 24rpx;
  box-shadow: var(--sj-sh-sm);
  text-align: center;
  display: flex;
  flex-direction: column;
}
.nc-val { font-size: 36rpx; font-weight: 800; color: var(--sj-primary-deep); }
.nc-label { font-size: 21rpx; color: var(--sj-sub); }
.nc-p50 {
  align-self: center;
  margin-top: 8rpx;
  font-size: 20rpx;
  font-weight: 700;
  color: #B47714;
  background: #FFF3D6;
  padding: 2rpx 16rpx;
  border-radius: var(--sj-r-pill);
}

/* ---------- 趋势卡 ---------- */
.trend-card {
  background: #FFF8F3;
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 24rpx 28rpx;
  margin-bottom: 24rpx;
}
.tc-text { display: block; font-size: 24rpx; line-height: 1.6; color: var(--sj-ink); }
.tc-note { display: block; margin-top: 12rpx; font-size: 20rpx; color: var(--sj-faint); }

/* ---------- 功能入口双列卡（v2 entry-grid） ---------- */
.entry-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20rpx; margin-bottom: 32rpx; }
.entry-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 28rpx;
  box-shadow: var(--sj-sh-sm);
}
.entry-card:active { transform: scale(0.96); }
.entry-card.entry-disabled { opacity: 0.5; }
.entry-card.entry-disabled:active { transform: none; }
.ec-icon {
  width: 80rpx;
  height: 80rpx;
  border-radius: 24rpx;
  padding: 4rpx;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8rpx;
}
/* 图标图片圆角与外圈曲线平行（同心）：外半径 24 - 内边距 4 = 20rpx */
.ec-icon .sj-icon { border-radius: 20rpx; }
.ec-title { font-size: 27rpx; font-weight: 800; color: var(--sj-ink); }
.ec-sub { font-size: 22rpx; color: var(--sj-sub); }

/* ---------- 里程碑（v2 ms-chip） ---------- */
.ms-domain {
  display: flex;
  align-items: center;
  gap: 16rpx;
  font-size: 28rpx;
  font-weight: 800;
  color: var(--sj-ink);
  margin: 24rpx 0 16rpx;
}
.ms-domain::before {
  content: "";
  width: 8rpx;
  height: 28rpx;
  border-radius: 8rpx;
  background: var(--sj-primary);
}
.ms-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16rpx; }
.ms-chip {
  display: flex;
  align-items: center;
  gap: 12rpx;
  min-width: 0;
  font-size: 24rpx;
  font-weight: 700;
  border-radius: var(--sj-r-sm);
  padding: 12rpx 20rpx 12rpx 12rpx;
  border: 2rpx solid var(--sj-line);
  background: var(--sj-cream);
  color: var(--sj-sub);
}
.ms-txt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2rpx; }
.ms-name { display: block; color: var(--sj-ink); overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.ms-st {
  display: block;
  font-size: 20rpx;
  font-weight: 600;
  color: var(--sj-faint);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.ms-chip.done { background: #E2F5EA; border-color: #BFE6CF; }
.ms-chip.done .ms-name { color: #2E7D4F; }
.ms-chip.done .ms-st { color: #2E7D4F; opacity: 0.75; }
.ms-chip.todo { opacity: 0.6; }

/* ---------- 测量记录 ---------- */
.section-title {
  display: flex;
  align-items: center;
  gap: 16rpx;
  font-size: 28rpx;
  font-weight: 800;
  color: var(--sj-ink);
  margin: 32rpx 0 20rpx;
}
.section-title::before {
  content: "";
  width: 8rpx;
  height: 28rpx;
  border-radius: 8rpx;
  background: var(--sj-primary);
}
.info-card {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  box-shadow: var(--sj-sh-sm);
  padding: 8rpx 28rpx;
  margin-bottom: 28rpx;
}
.field-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16rpx;
  padding: 22rpx 0;
  border-bottom: 2rpx dashed var(--sj-line);
}
.field-row:last-child { border-bottom: none; }
.fr-left { display: flex; align-items: baseline; flex: none; }
.fr-date { font-size: 26rpx; font-weight: 600; color: var(--sj-ink); white-space: nowrap; }
.m-age { font-size: 20rpx; color: var(--sj-faint); margin-left: 12rpx; white-space: nowrap; }
.fr-right { display: flex; align-items: baseline; justify-content: flex-end; flex: 1; min-width: 0; }
.time-val { font-size: 26rpx; font-weight: 700; color: var(--sj-primary-deep); flex: none; white-space: nowrap; }

/* ---------- 录入测量按钮 ---------- */
.add-measure-btn {
  width: 100%;
  box-sizing: border-box;
  border: 3rpx dashed var(--sj-primary);
  background: var(--sj-primary-soft);
  color: var(--sj-primary-deep);
  font-size: 26rpx;
  font-weight: 700;
  padding: 24rpx 0;
  border-radius: var(--sj-r-md);
  text-align: center;
  margin-bottom: 32rpx;
}

/* ---------- 底部 ---------- */
.scroll-end { text-align: center; font-size: 22rpx; color: var(--sj-faint); padding: 24rpx 0 200rpx; letter-spacing: 4rpx; }
</style>
