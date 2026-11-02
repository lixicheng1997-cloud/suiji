<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回钮 + 显示字族标题） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">提醒设置</text>
    </view>

    <view class="content">
      <!-- 通知权限提示条：App 端系统通知被关闭时显示，提醒只会进消息中心 -->
      <view class="auth-warn" v-if="notifyOff" hover-class="hover-press" :hover-stay-time="80" @click="openNotifySettings">
        <sj-icon name="25-fn-notify" :size="44" />
        <view class="aw-text">
          <text class="aw-title">系统通知已关闭</text>
          <text class="aw-desc">提醒将只在消息中心可见 · 点击前往系统设置</text>
        </view>
        <text class="aw-go">前往 ›</text>
      </view>

      <!-- 提醒类型 · 独立开关（v2 P23：set-group 标题在卡内 + set-row + pg-sw 开=ok 绿底） -->
      <view class="set-group">
        <text class="sg-title">提醒类型</text>
        <view
          class="set-row"
          v-for="row in rows"
          :key="row.k"
          hover-class="hover-press"
          :hover-stay-time="80"
          @click="toggleRow(row.k)"
        >
          <view class="sr-icon">
            <sj-icon :name="row.icon" :size="56" />
          </view>
          <view class="sr-label">
            <text>{{ row.label }}</text>
            <text class="sr-desc">{{ row.desc }}</text>
          </view>
          <sj-switch class="row-sw" :checked="r[row.k]" @click.stop @change="setRow(row.k, $event)" />
        </view>
      </view>

      <!-- 提醒时间：set-group 同框；picker 只包右侧时刻文本（同 editor/baby 页 dt-field 模式），行框由页面自排 -->
      <view class="set-group">
        <text class="sg-title">提醒时间</text>
        <view class="set-row">
          <view class="sr-icon">
            <sj-icon name="21-fn-remind" :size="56" />
          </view>
          <text class="sr-label">每日提醒时刻</text>
          <sj-datetime-picker class="time-pick" mode="time" :value="r.time" @change="onTimeChange">
            <text class="sr-val time-val" hover-class="hover-press" :hover-stay-time="80">{{ r.time }} ▾</text>
          </sj-datetime-picker>
        </view>
      </view>

      <!-- 合规文案（一字不动） -->
      <view class="pg-hint">提醒仅提供时间提示，不构成医学建议 · 推送权限跟随系统设置</view>
    </view>

    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import { play } from '@/utils/sound.js'

export default {
  data() {
    return {
      statusBarHeight: 20,
      /* 提醒开关集合：vaccine/checkup/anniversary/quiet/msg/time */
      r: api.getRemind(),
      pendingCount: 0,
      /* 最近一剂待接种（refresh 派生），驱动疫苗行副标题 */
      nextDose: null,
      /* 系统通知权限被关闭（仅 App 端可能为 true），驱动提示条 */
      notifyOff: false
    }
  },

  /* 开关行配置：图标用 v2 主题图标名（sj-icon 解析 bear/duck 双主题）；疫苗行副标题随真实排期动态生成 */
  computed: {
    rows() {
      const d = this.nextDose
      return [
        { k: 'vaccine', icon: '34-fn-vaccine', label: '疫苗接种提醒', desc: d ? '下一剂：' + d.n + ' ' + d.dose + ' · ' + d.plan_text : '暂无待接种剂次' },
        { k: 'checkup', icon: '05-measure', label: '体检与月龄发育提示', desc: '体检节点提醒 · 附月龄发育观察要点' },
        { k: 'anniversary', icon: '32-fn-card', label: '纪念日提醒（百日 · 周岁）', desc: '提前 3 天与当天提醒 · 直达日记生成' },
        { k: 'quiet', icon: '02-sleep', label: '免打扰时段', desc: '22:00 – 07:00 不推送' },
        { k: 'msg', icon: '25-fn-notify', label: '消息通知', desc: '家人记录宝宝时即时提醒 · 关闭后不弹窗，历史仍在消息中心查看' }
      ]
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  onShow() {
    /* 未读由「消息中心」消费：提醒设置页不再清空通知账本 */
    this.refresh()
    /* 通知权限状态：App 端系统通知被关时展示引导条 */
    const st = api.notifyAuthStatus()
    this.notifyOff = st.supported && !st.enabled
  },

  methods: {
    refresh() {
      this.r = api.getRemind()
      const pending = api.getVaccines().filter(v => !v.done && v.plan_date)
      this.pendingCount = pending.length
      this.nextDose = pending.slice().sort((a, b) => (a.plan_date < b.plan_date ? -1 : 1))[0] || null
    },

    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    toggleRow(k) {
      this.r = api.setRemind({ [k]: !this.r[k] })
      play('S11') // 提醒开关拨动音效
    },

    /* sj-switch 适配器：以事件新值直写持久化（与 toggleRow 同效，不改原方法） */
    setRow(k, v) {
      this.r = api.setRemind({ [k]: v })
      play('S11') // 提醒开关拨动音效
    },

    onTimeChange(e) {
      this.r = api.setRemind({ time: e.detail.value })
    },

    openNotifySettings() {
      api.openNotifySettings()
    },

    go(url) {
      uni.navigateTo({ url })
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

/* ---------- 顶栏（v2 pg-back：sticky 奶油渐隐 + 圆形返回钮） ---------- */
.pg-back {
  display: flex;
  align-items: center;
  gap: 20rpx;
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
  font-family: var(--sj-font-display);
  font-size: 40rpx;
  font-weight: 900;
  color: var(--sj-ink);
}

/* ---------- 内容区 ---------- */
.content { padding: 8rpx 32rpx 48rpx; }

/* 通知权限提示条（v2 卡片风格：surface 底 + line 边，主色强调） */
.auth-warn {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
  box-shadow: var(--sj-sh-sm);
  color: var(--sj-primary-deep);
}
.auth-warn:active { background: var(--sj-cream); }
.aw-text { flex: 1; min-width: 0; }
.aw-title { display: block; font-size: 25rpx; font-weight: 800; color: var(--sj-ink); }
.aw-desc { display: block; font-size: 21rpx; color: var(--sj-sub); margin-top: 4rpx; line-height: 1.5; }
.aw-go { font-size: 23rpx; font-weight: 800; color: var(--sj-primary-deep); flex: none; }

/* 设置分组（v2 set-group：白卡 line 边 r-md，组标题在卡内） */
.set-group {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 12rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: var(--sj-sh-sm);
}
.sg-title {
  display: block;
  font-size: 24rpx;
  font-weight: 800;
  color: var(--sj-faint);
  padding: 16rpx 4rpx 8rpx;
}
.set-row {
  display: flex;
  align-items: center;
  gap: 24rpx;
  padding: 22rpx 4rpx;
  border-top: 2rpx dashed var(--sj-line);
}
.set-row:first-of-type { border-top: none; }
.set-row:active { background: var(--sj-cream); }
.sr-icon {
  width: 68rpx;
  height: 68rpx;
  border-radius: 20rpx;
  background: var(--sj-cream);
  padding: 6rpx;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
/* 图标图片圆角与外圈曲线平行（同心）：外半径 20 - 内边距 6 = 14rpx */
.sr-icon .sj-icon { border-radius: 14rpx; }
.sr-label { flex: 1; min-width: 0; font-size: 27rpx; font-weight: 600; color: var(--sj-ink); }
.sr-desc {
  display: block;
  font-size: 21rpx;
  font-weight: 400;
  color: var(--sj-sub);
  margin-top: 4rpx;
  line-height: 1.5;
}
.sr-val { font-size: 23rpx; color: var(--sj-sub); flex: none; max-width: 280rpx; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.sr-chev { width: 30rpx; height: 30rpx; flex: none; opacity: 0.5; }

/* 开关改用 sj-switch 封装（外观对齐 v2 pg-sw）：行内不收缩 */
.row-sw { flex: none; }

/* 提醒时间行：picker 作行尾弹性项不收缩，时刻文本随 sr-val 居右（根 inline-flex 收缩到文本宽，无需覆写） */
.time-pick { flex: none; }
.time-val { color: var(--sj-primary-deep); font-weight: 900; }

/* 提示文案行（v2 pg-hint：cream 底 + 虚线边） */
.pg-hint {
  font-size: 23rpx;
  color: var(--sj-sub);
  background: var(--sj-cream);
  border: 2rpx dashed var(--sj-line);
  border-radius: 24rpx;
  padding: 16rpx 24rpx;
  margin-top: 8rpx;
  line-height: 1.5;
}
</style>
