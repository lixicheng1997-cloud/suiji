<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <view class="elder-wrap" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 40rpx)' }">
      <!-- 顶部：返回普通模式胶囊按钮 -->
      <view class="elder-exit" hover-class="hover-press" :hover-stay-time="80" @click="onExit">
        <image class="exit-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
        <text>返回普通模式</text>
      </view>

      <!-- 大标题：宝宝名 + 今天怎么样 -->
      <text class="elder-title">{{ babyName }}今天怎么样？</text>

      <!-- 4 条大字行卡：依次 rise 错峰入场 -->
      <view class="elder-rows">
        <view class="elder-row">
          <sj-icon name="01-feeding" :size="92" />
          <text class="row-txt">{{ feedText }}</text>
          <text class="row-val ok">正常</text>
        </view>
        <view class="elder-row">
          <sj-icon name="02-sleep" :size="92" />
          <text class="row-txt">{{ sleepText }}</text>
          <text class="row-val ok">正常</text>
        </view>
        <view class="elder-row">
          <sj-icon name="03-milestone" :size="92" />
          <text class="row-txt">{{ milestoneText }}</text>
          <text class="row-val ok">正常</text>
        </view>
        <view class="elder-row">
          <sj-icon name="34-fn-vaccine" :size="92" />
          <text class="row-txt">{{ vaccineText }}</text>
          <text class="row-val" :class="vaccineOverdue ? 'bad' : 'ok'">{{ vaccineOverdue ? '别忘了' : '安心' }}</text>
        </view>
      </view>

      <!-- 底部：打电话给妈妈（绿色通栏大按钮） -->
      <view class="elder-call" hover-class="hover-press" :hover-stay-time="80" @click="onCall">
        <text>打电话给妈妈</text>
      </view>
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'

export default {
  data() {
    return {
      baby: api.getBaby() || { name: '宝宝' },
      todayStats: api.getTodayStats(),
      vaccines: api.getVaccines(),
      statusBarHeight: 20
    }
  },

  computed: {
    /* 标题里的宝宝名（无档案时回退「宝宝」） */
    babyName() {
      return (this.baby && this.baby.name) || '宝宝'
    },
    /* 喝奶行：feeding 项 num（如「6 次」）取数字，缺省 0 */
    feedText() {
      const s = this.todayStats.find(x => x.type === 'feeding')
      const m = s && String(s.num).match(/\d+(\.\d+)?/)
      return '喝奶 ' + (m ? m[0] : '0') + ' 次'
    },
    /* 睡眠行：sleep 项按数据原样展示「{num} {label}」 */
    sleepText() {
      const s = this.todayStats.find(x => x.type === 'sleep')
      return s ? s.num + ' ' + s.label : '睡眠 0 h'
    },
    /* 里程碑行：milestone 项 num（如「3 条」） */
    milestoneText() {
      const s = this.todayStats.find(x => x.type === 'milestone')
      return '里程碑 ' + (s ? s.num : '0 条')
    },
    /* 疫苗行：有逾期未接种剂次时红字提醒 */
    vaccineOverdue() {
      return this.vaccines.some(v => v.status === 'overdue')
    },
    vaccineText() {
      return this.vaccineOverdue ? '有疫苗逾期了' : '本周没有到期'
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  /* 每次进入本页刷新：宝宝档案 / 今日统计 / 疫苗状态 */
  onShow() {
    this.refresh()
  },

  methods: {
    refresh() {
      const b = api.getBaby()
      if (b) this.baby = b
      this.todayStats = api.getTodayStats()
      this.vaccines = api.getVaccines()
    },
    /* 返回普通模式：栈空（直进本页）时回首页 */
    onExit() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },
    /* 呼叫家长手机号：家长档案暂无手机号字段时引导去「我的 → 编辑」填写 */
    onCall() {
      const p = api.getParentInfo() || {}
      const phone = String(p.phone || p.mobile || p.tel || '').trim()
      if (!phone) {
        this.$refs.ntf.show({ type: 'warn', message: '还没有妈妈手机号，请到「我的 → 编辑」填写' })
        return
      }
      uni.makePhoneCall({ phoneNumber: phone, fail: () => { /* 用户取消拨号 */ } })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 长辈模式大字版：奶油暖底 + 特粗大字行卡（对齐 v2 .elder-mode） */

.page {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  position: relative;
  z-index: 0;
  min-height: 100vh;
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
}
.elder-wrap {
  display: flex;
  flex-direction: column;
  gap: 28rpx;
  padding-left: 40rpx;
  padding-right: 40rpx;
  padding-bottom: 52rpx;
  box-sizing: border-box;
}

/* ---------- 返回普通模式胶囊 ---------- */
.elder-exit {
  align-self: flex-start;
  display: flex;
  align-items: center;
  gap: 8rpx;
  background: var(--sj-surface);
  border: 4rpx solid var(--sj-line);
  border-radius: var(--sj-r-pill);
  padding: 16rpx 32rpx;
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.elder-exit text { font-size: 30rpx; font-weight: 800; color: var(--sj-sub); line-height: 1; }
.exit-ic { width: 34rpx; height: 34rpx; flex: none; }

/* ---------- 大标题 ---------- */
.elder-title {
  font-family: var(--sj-font-display);
  font-size: 48rpx;
  font-weight: 900;
  color: var(--sj-ink);
  margin: 8rpx 0 4rpx;
}

/* ---------- 大字行卡 ---------- */
.elder-rows { display: flex; flex-direction: column; gap: 28rpx; }
.elder-row {
  display: flex;
  align-items: center;
  gap: 24rpx;
  background: var(--sj-surface);
  border: 5rpx solid var(--sj-line);
  border-radius: 32rpx;
  padding: 32rpx;
  box-shadow: var(--sj-sh-sm);
  animation: rise 0.5s cubic-bezier(.22,.8,.3,1) backwards;
}
/* 依次上移淡入入场（对齐 v2 nth-child 错峰） */
.elder-row:nth-child(1) { animation-delay: 50ms; }
.elder-row:nth-child(2) { animation-delay: 120ms; }
.elder-row:nth-child(3) { animation-delay: 190ms; }
.elder-row:nth-child(4) { animation-delay: 260ms; }
.row-txt { flex: 1; min-width: 0; font-size: 38rpx; font-weight: 800; color: var(--sj-ink); }
.row-val { flex: none; font-size: 36rpx; font-weight: 900; }
.row-val.ok { color: var(--sj-ok); }
.row-val.bad { color: var(--sj-bad); }
@keyframes rise {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: none; }
}

/* ---------- 打电话大按钮 ---------- */
.elder-call {
  margin-top: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--sj-ok);
  border-radius: 32rpx;
  padding: 32rpx 0;
  box-shadow: var(--sj-sh-md);
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.elder-call text { font-size: 36rpx; font-weight: 900; color: #fff; line-height: 1; }
.elder-call:active { transform: scale(0.96); }
</style>
