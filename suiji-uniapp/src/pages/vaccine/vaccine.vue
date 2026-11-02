<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回钮 + 标题 + 两枚操作胶囊：一键全部提醒 / 新建时间表） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">疫苗时间表</text>
      <view class="ph-chip" hover-class="hover-press" :hover-stay-time="80" @click="toggleAllRemind">
        <text>{{ allRemindOn ? '关闭全部提醒' : '开启全部提醒' }}</text>
      </view>
      <view class="ph-chip" hover-class="hover-press" :hover-stay-time="80" @click="goNewSchedule">
        <text>+ 新建时间表</text>
      </view>
    </view>

    <!-- 时间表内容区 -->
    <view class="content">
      <!-- 统计摘要（v2 白卡：display 字族大数字 primary-deep） -->
      <view class="v-summary">
        <text class="vs-num">{{ doneCount }} <text class="vs-label">已接种</text></text>
        <text class="vs-sep">/</text>
        <text class="vs-num">{{ pendingCount }} <text class="vs-label">待接种</text></text>
        <text class="vs-note">共 {{ vaccines.length }} 剂 · 按出生日期排期</text>
      </view>

      <!-- 逾期提示（v2 pg-hint.bad：红系虚线提示条） -->
      <view v-if="overdueCount" class="v-alert">
        <text>有 {{ overdueCount }} 剂已逾期，建议尽快到接种单位补种。</text>
      </view>

      <!-- 剂次列表（v2 pg-vrow：白底 line 边 28rpx 圆角；本周到龄行高亮，状态胶囊三态） -->
      <view
        class="v-row"
        v-for="v in vaccines"
        :key="v.id"
        :class="v.status + (v.status === 'pending' && v.days_left <= 7 ? ' due' : '')"
      >
        <!-- 左侧圆点：一键标记 / 取消完成接种 -->
        <view
          class="v-dot"
          :class="{ ok: v.done }"
          hover-class="hover-press"
          :hover-stay-time="80"
          @click="toggleDone(v)"
        >
          <text v-if="v.done" class="dot-mark">✓</text>
        </view>

        <!-- 疫苗图标（v2 34-fn-vaccine 双主题绘本图标） -->
        <sj-icon class="v-ic" name="34-fn-vaccine" :size="56" />

        <view class="v-info" hover-class="hover-press" :hover-stay-time="80" @click="onRow(v)">
          <text class="v-name">{{ v.n }} · {{ v.dose }}</text>
          <text class="v-meta">{{ v.age }} · {{ v.tip }}</text>
          <!-- 预期接种时间：点日期可自定义（已接种剂次不再改排期） -->
          <view class="v-plan">
            <text class="v-meta">计划 </text>
            <text
              v-if="!v.done"
              class="v-date-val"
              hover-class="hover-press"
              :hover-stay-time="80"
              @click.stop="openDateSheet(v, 'plan')"
            >{{ v.plan_text || '待定' }} ▾</text>
            <text v-else class="v-meta">{{ v.plan_text || '待定' }}</text>
            <text class="v-custom-tag" v-if="v.plan_custom">自定义</text>
          </view>
          <text class="v-meta sub" v-if="v.done">接种 {{ v.done_date || '—' }} · {{ v.org || '机构未填' }}</text>
          <text class="v-meta sub" v-else>{{ v.remind ? '提醒已开启' : '提醒未开启' }}</text>
        </view>

        <view class="v-acts">
          <!-- 状态胶囊：sj-tag 语义变体（已接种 ok / 本周到龄 soft / 逾期 err / 其余弱化浅底） -->
          <sj-tag size="mini" v-bind="vTagProps(v)" />
          <!-- 右侧铃铛：一键开启 / 关闭该剂次提醒（sj-tag chip 选中态） -->
          <sj-tag
            class="v-bell"
            :class="{ dim: v.done }"
            size="mini"
            variant="chip"
            :pressable="!v.done"
            :active="v.remind && !v.done"
            :text="v.done ? '已接种' : (v.remind ? '提醒中' : '设提醒')"
            @click="toggleRemind(v)"
          />
        </view>
      </view>

      <!-- 合规文案（一字不动） -->
      <view class="scroll-end"><text>· 时间表以国家免疫规划为准，仅作记录与提醒，不构成医学建议 ·</text></view>
    </view>

    <!-- 日期选择：直开 sj-datetime-picker 滚轮面板（无中间 sj-modal），滚轮「确定」即保存 -->
    <sj-datetime-picker ref="dtp" mode="date" :title="ds.title" :value="ds.date" :max="ds.max" @change="onDateChange">
      <view class="dtp-ghost" />
    </sj-datetime-picker>

    <!-- 行操作面板（sj-popup 底部弹层替代 ActionSheet：点选项收起后再分发操作） -->
    <sj-popup
      v-model:show="asShow"
      mode="bottom"
      :title="asTitle"
      bar-icon="67-ctl-popup"
      left-text="取消"
      right-text=""
    >
      <view class="as-list">
        <view
          v-for="item in asItems"
          :key="item"
          class="as-item"
          hover-class="hover-press"
          :hover-stay-time="80"
          @click="pickAction(item)"
        >
          <text class="as-item__name">{{ item }}</text>
        </view>
      </view>
    </sj-popup>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import { now, dayKey } from '@/domain/shared/date.js'

export default {
  data() {
    return {
      /* 内置时间表（按时间顺序）+ 各剂次状态，由 api.getVaccines 派生 */
      vaccines: [],
      /* 日期面板：{ id, mode:'plan'|'done', title, confirmText, sub, date } */
      dateSheet: null,
      /* 行操作面板（sj-popup）：显隐 / 当前剂次 / 选项文案列表 */
      asShow: false,
      asVaccine: null,
      asItems: [],
      statusBarHeight: 20
    }
  },

  computed: {
    doneCount() {
      return this.vaccines.filter(v => v.done).length
    },
    pendingCount() {
      return this.vaccines.filter(v => !v.done).length
    },
    overdueCount() {
      return this.vaccines.filter(v => v.status === 'overdue').length
    },
    allRemindOn() {
      const pend = this.vaccines.filter(v => !v.done)
      return pend.length > 0 && pend.every(v => v.remind)
    },
    /* 滚轮面板取数：未选剂次时给空壳兜底，避免模板报错 */
    ds() {
      return this.dateSheet || { title: '', date: '', max: '' }
    },
    /* 行操作面板标题：当前剂次「名称 · 剂次」 */
    asTitle() {
      return this.asVaccine ? this.asVaccine.n + ' · ' + this.asVaccine.dose : ''
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  onShow() {
    this.refresh()
  },

  methods: {
    /* 状态胶囊 → sj-tag 变体（ok/soft/err 自带设计稿配色；其余走 pill 自定义浅底） */
    vTagProps(v) {
      if (v.status === 'done') return { variant: 'ok', text: v.status_text }
      if (v.status === 'overdue') return { variant: 'err', text: v.status_text }
      if (v.status === 'pending' && v.days_left <= 7) return { variant: 'soft', text: v.status_text }
      return { variant: 'pill', bg: '#FFF8F0', color: '#C7B6A8', text: v.status_text }
    },

    refresh() {
      this.vaccines = api.getVaccines()
    },

    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    /* 顶栏「+ 新建时间表」→ 国家免疫规划选择页（P22） */
    goNewSchedule() {
      uni.navigateTo({ url: '/pages/vaccine-new/vaccine-new' })
    },

    /* 日期面板：mode='plan' 自定义预期接种时间 / mode='done' 自定义完成时间（默认当前日期） */
    openDateSheet(v, mode) {
      const today = dayKey(now())
      this.dateSheet = {
        id: v.id,
        mode,
        title: mode === 'plan' ? '预期接种时间' : (v.done ? '接种日期' : '完成接种时间'),
        date: mode === 'plan' ? (v.plan_date || v.plan_default || today) : (v.done_date || today),
        /* 实际接种不能填到未来；预期日期允许排在未来 */
        max: mode === 'plan' ? '' : today
      }
      /* value prop 下一帧才生效，nextTick 后再开面板，保证滚轮初始定位到当前日期 */
      this.$nextTick(() => this.$refs.dtp.open())
    },

    /* 滚轮「确定」：直接保存（取消不触发 change，无需处理） */
    async onDateChange(e) {
      const s = this.dateSheet
      this.dateSheet = null
      if (!s) return
      try {
        if (s.mode === 'plan') {
          await api.setVaccinePlanDate(s.id, e.detail.value)
          this.$refs.ntf.show({ type: 'ok', message: '预期接种时间已更新' })
        } else {
          await api.setVaccineDone(s.id, true, e.detail.value)
          this.$refs.ntf.show({ type: 'ok', message: '已标记完成并关闭提醒' })
        }
      } catch (err) {
        ui.error(err, '操作失败')
      }
      this.refresh()
    },

    /* 一键标记完成接种 / 取消完成（完成时先选完成时间，默认当前日期） */
    toggleDone(v) {
      const next = !v.done
      if (next) {
        this.openDateSheet(v, 'done')
        return
      }
      api.setVaccineDone(v.id, false)
        .catch(e => ui.error(e, '操作失败'))
        .finally(() => this.refresh())
      this.$refs.ntf.show({ type: 'ok', message: '已恢复为待接种' })
    },

    /* 一键开启 / 关闭该剂次提醒（已接种剂次不再提醒） */
    toggleRemind(v) {
      if (v.done) {
        this.$refs.ntf.show({ type: 'warn', message: '已完成接种，无需提醒' })
        return
      }
      api.setVaccineRemind(v.id, !v.remind)
        .catch(e => ui.error(e, '操作失败'))
        .finally(() => this.refresh())
      this.$refs.ntf.show({ type: 'ok', message: v.remind ? '已关闭提醒' : '已开启提醒' })
    },

    /* 全部待接种剂次一键开启 / 关闭提醒 */
    toggleAllRemind() {
      const on = !this.allRemindOn
      api.setAllVaccineRemind(on)
        .catch(e => ui.error(e, '操作失败'))
        .finally(() => this.refresh())
      this.$refs.ntf.show({ type: 'ok', message: on ? '已开启全部待接种提醒' : '已关闭全部待接种提醒' })
    },

    /* 行操作：弹出 sj-popup 选项面板（预期接种时间 / 接种日期 / 机构 / 批号） */
    onRow(v) {
      this.asVaccine = v
      this.asItems = v.done
        ? ['取消已完成', '修改接种日期', '填写接种机构', '填写批号']
        : ['标记为已完成', '修改预期接种时间']
            .concat(v.plan_custom ? ['恢复默认接种时间'] : [])
            .concat([v.remind ? '关闭提醒' : '开启提醒'])
      this.asShow = true
    },

    /* 面板选项：先收起弹层，再按文案分发原有操作 */
    async pickAction(pick) {
      const v = this.asVaccine
      this.asShow = false
      if (!v) return
      if (pick === '标记为已完成') return this.toggleDone(v)
      if (pick === '修改预期接种时间') return this.openDateSheet(v, 'plan')
      if (pick === '恢复默认接种时间') {
        try {
          await api.setVaccinePlanDate(v.id, '')
          this.$refs.ntf.show({ type: 'ok', message: '已恢复为按出生日期排期' })
        } catch (e) {
          ui.error(e, '操作失败')
        }
        this.refresh()
        return
      }
      if (pick === '修改接种日期') return this.openDateSheet(v, 'done')
      if (pick === '取消已完成') {
        try {
          await api.setVaccineDone(v.id, false)
        } catch (e) {
          ui.error(e, '操作失败')
        }
        this.refresh()
        return
      }
      if (pick === '开启提醒' || pick === '关闭提醒') return this.toggleRemind(v)
      const field = pick === '修改接种日期' ? 'done_date' : pick === '填写接种机构' ? 'org' : 'lot'
      const label = pick === '修改接种日期' ? '接种日期' : pick === '填写接种机构' ? '接种机构' : '疫苗批号'
      ui.showModal({
        title: pick,
        icon: '34-fn-vaccine',
        editable: true,
        placeholderText: v[field] || (field === 'done_date' ? '如 2026-10-22' : ''),
        success: async r => {
          if (!r.confirm) return
          const val = (r.content || '').trim()
          if (!val) {
            this.$refs.ntf.show({ type: 'warn', message: label + '不能为空' })
            return
          }
          /* 接种日期手输走文本框：不校验会存进 "10.22" 这类值，plan/done 比较与提醒全乱 */
          if (field === 'done_date' && !/^\d{4}-\d{2}-\d{2}$/.test(val)) {
            this.$refs.ntf.show({ type: 'warn', message: '请按 2026-10-22 的格式填写' })
            return
          }
          /* org/lot 落服务端 varchar(64)：中文机构名 3 字节/字，超长直接拦下（截断会让人以为存进去了） */
          if (field !== 'done_date' && val.length > 20) {
            this.$refs.ntf.show({ type: 'warn', message: label + '最多 20 个字' })
            return
          }
          try {
            await api.markVaccine(v.id, { [field]: val })
            this.refresh()
            this.$refs.ntf.show({ type: 'ok', message: label + '已更新' })
          } catch (e) {
            ui.error(e, '更新失败')
          }
        }
      })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 页面底：v2 奶油色；正文圆润字族 */
.page {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  position: relative;
  z-index: 0;
  min-height: 100vh;
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
  font-family: var(--sj-font-body);
}

/* ---------- 顶栏（v2 pg-back：sticky 奶油渐隐 + 圆形返回钮 + 操作胶囊） ---------- */
.pg-back {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding-left: 32rpx;
  padding-right: 32rpx;
  padding-bottom: 24rpx;
  position: sticky;
  top: 0;
  z-index: 10;
  background: linear-gradient(var(--sj-cream) 82%, transparent);
}
.bk {
  width: 68rpx;
  height: 68rpx;
  border-radius: 50%;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--sj-ink);
  box-shadow: var(--sj-sh-sm);
  flex: none;
}
.bk:active { transform: scale(0.92); }
.bk-ic { width: 36rpx; height: 36rpx; }
.pg-title {
  flex: 1;
  min-width: 0;
  font-family: var(--sj-font-display);
  font-size: 40rpx;
  font-weight: 900;
  color: var(--sj-ink);
}
/* 顶栏操作胶囊（v2 primary-soft 软底小钮） */
.ph-chip {
  flex: none;
  font-size: 22rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  padding: 10rpx 24rpx;
  border-radius: var(--sj-r-pill);
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.ph-chip:active { transform: scale(0.94); }

/* ---------- 内容区 ---------- */
.content { padding: 0 32rpx 48rpx; }

/* 统计摘要（v2 白卡：line 边 r-md + sh-sm） */
.v-summary {
  display: flex;
  align-items: baseline;
  gap: 16rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  box-shadow: var(--sj-sh-sm);
  padding: 28rpx 32rpx;
  margin-bottom: 20rpx;
}
.vs-num { font-family: var(--sj-font-display); font-size: 48rpx; font-weight: 900; color: var(--sj-primary-deep); line-height: 1.2; }
.vs-label { font-size: 22rpx; font-weight: 500; color: var(--sj-sub); }
.vs-sep { font-size: 28rpx; color: var(--sj-faint); }
.vs-note { margin-left: auto; font-size: 20rpx; color: var(--sj-faint); }

/* 逾期提示（v2 pg-hint.bad 红系语义） */
.v-alert {
  font-size: 23rpx;
  color: #B04A4A;
  line-height: 1.6;
  background: #FDF0F0;
  border: 2rpx dashed #F3C4C4;
  border-radius: 24rpx;
  padding: 16rpx 24rpx;
  margin-bottom: 20rpx;
}

/* 剂次行（v2 pg-vrow：白底 line 边 28rpx 圆角） */
.v-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: 28rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
  box-shadow: var(--sj-sh-sm);
}
/* 本周到龄高亮行：primary 描边 + 奶油暖底 */
.v-row.due { border-color: var(--sj-primary); background: var(--sj-cream); }
/* 逾期行：bad 红系描边 */
.v-row.overdue { border-color: var(--sj-bad); }
/* 完成圆点：一键标记（开=ok 绿底） */
.v-dot {
  width: 52rpx;
  height: 52rpx;
  flex: none;
  border-radius: 50%;
  border: 4rpx solid var(--sj-line);
  background: var(--sj-surface);
  display: flex;
  align-items: center;
  justify-content: center;
}
.v-dot.ok { background: var(--sj-ok); border-color: transparent; }
.v-dot:active { transform: scale(0.92); }
.dot-mark { font-size: 26rpx; color: #fff; font-weight: 700; line-height: 1; }
.v-ic { flex: none; }
.v-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4rpx; }
.v-name { font-size: 26rpx; font-weight: 800; color: var(--sj-ink); }
/* 预期接种时间：日期可点改（primary-soft 软底胶囊） */
.v-plan { display: flex; align-items: center; gap: 8rpx; }
.v-date-val {
  font-size: 21rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  border-radius: var(--sj-r-pill);
  padding: 4rpx 20rpx;
}
.v-date-val:active { transform: scale(0.96); }
/* 自定义排期标记（gold/duck 软底） */
.v-custom-tag {
  font-size: 18rpx;
  font-weight: 700;
  color: #B47714;
  background: var(--sj-duck-soft);
  border-radius: var(--sj-r-pill);
  padding: 4rpx 16rpx;
}
.v-meta { font-size: 21rpx; color: var(--sj-sub); line-height: 1.5; }
.v-meta.sub { font-size: 20rpx; color: var(--sj-faint); }

/* 右侧操作区 */
.v-acts { flex: none; display: flex; flex-direction: column; align-items: flex-end; gap: 10rpx; }
/* 状态胶囊与提醒铃铛：外观由 sj-tag（ok/soft/err/pill、chip 选中态）提供 */
.v-bell.dim { opacity: 0.5; }

/* ---------- 日期选择：直开滚轮面板，占位触发器零尺寸（弹层 fixed 定位不受影响） ---------- */
.dtp-ghost { width: 0; height: 0; }

/* ---------- 行操作面板（sj-popup 底部弹层内：选项行，line 分隔） ---------- */
.as-list { padding: 8rpx 0 calc(20rpx + env(safe-area-inset-bottom)); }
.as-item {
  display: flex;
  align-items: center;
  padding: 28rpx 40rpx;
  border-bottom: 2rpx solid var(--sj-line);
}
.as-item:last-child { border-bottom: none; }
.as-item__name { font-size: 28rpx; font-weight: 700; color: var(--sj-ink); }

/* 底部说明（合规文案） */
.scroll-end {
  text-align: center;
  font-size: 22rpx;
  color: var(--sj-faint);
  padding: 24rpx 0 16rpx;
  letter-spacing: 4rpx;
}
</style>
