<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回钮 + 显示字族标题） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">新建时间表</text>
    </view>

    <view class="content">
      <!-- 说明条（v2 pg-hint：cream 底虚线边；合规文案一字不动） -->
      <view class="pg-hint">
        <text>已为你预选国家免疫规划疫苗（一类免费），可调整月龄后一键生成时间表。</text>
      </view>

      <!-- 规划疫苗清单：整行点击切换选中（v2 白底行 + sj-checkbox 勾选方框） -->
      <view
        class="vp-item"
        v-for="(v, i) in VACCINE_PROGRAM"
        :key="i"
        :class="{ off: !sel[i] }"
        hover-class="hover-press"
        :hover-stay-time="80"
        @click="toggle(i)"
      >
        <!-- 勾选框本体（u-checkbox 内部 tap.stop，点击不冒泡到行；行点击仍走 toggle） -->
        <sj-checkbox class="vp-ck" :checked="sel[i]" @change="v => (sel[i] = v)" />
        <view class="vp-main">
          <view class="vp-name-row">
            <text class="vp-name">{{ v.n }}</text>
            <text class="vp-dose">{{ v.doses.length }} 剂</text>
          </view>
          <!-- 月龄排期胶囊（v2 chips 中性态） -->
          <view class="vp-ages">
            <text class="vp-age" v-for="(d, j) in v.doses" :key="j">{{ d }}</text>
          </view>
        </view>
      </view>

      <view class="scroll-end"><text>· 时间表以国家免疫规划为准，仅作记录与提醒，不构成医学建议 ·</text></view>

      <!-- 一键生成（v2 pg-btn：primary 渐变主按钮） -->
      <sj-button
        class="pg-btn"
        block
        size="lg"
        :loading="busy"
        :text="'生成时间表（已选 ' + totalDoses + ' 剂）'"
        @click="onGen"
      />
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import { VACCINE_PROGRAM } from '@/utils/mock.js'
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'

export default {
  data() {
    return {
      VACCINE_PROGRAM,
      /* 默认全选（参照原型 state.vprog） */
      sel: VACCINE_PROGRAM.map(() => true),
      /* 生成中：sj-button 自截重复点击 + 转圈 */
      busy: false,
      statusBarHeight: 20
    }
  },

  computed: {
    selectedIdx() {
      return this.sel.map((on, i) => (on ? i : -1)).filter(i => i >= 0)
    },
    totalDoses() {
      return VACCINE_PROGRAM.reduce((s, v, i) => s + (this.sel[i] ? v.doses.length : 0), 0)
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  methods: {
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    toggle(i) {
      this.sel[i] = !this.sel[i]
    },

    async onGen() {
      /* 一次生成要同步 20+ 行剂次，重复点击会把提醒状态来回翻转 */
      if (this.busy) return
      /* 一个都没勾 = 关闭全部待接种提醒，容易被当成「没点到」而误触，先确认一次 */
      if (!this.selectedIdx.length) {
        const yes = await ui.confirm({
          title: '未勾选任何疫苗',
          content: '生成后将关闭全部待接种提醒，确定继续？',
          danger: true
        })
        if (!yes) return
      }
      this.busy = true
      try {
        const res = await api.generateVaccineSchedule(this.selectedIdx)
        /* 先提示再返回：横幅在本页 ntf 实例展示，延迟返回让其完整可见（对齐 editor.vue 模式） */
        this.$refs.ntf.show({ type: 'ok', message: '已生成 · ' + res.count + ' 剂提醒已更新' })
        setTimeout(() => uni.navigateBack(), 1600)
      } catch (e) {
        ui.error(e, '生成失败，请重试')
      } finally {
        this.busy = false
      }
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
.content { padding: 0 32rpx 48rpx; }

/* 说明条（v2 pg-hint：cream 底 + 虚线 line 边） */
.pg-hint {
  font-size: 23rpx;
  color: var(--sj-sub);
  background: var(--sj-cream);
  border: 2rpx dashed var(--sj-line);
  border-radius: 24rpx;
  padding: 16rpx 24rpx;
  margin-bottom: 24rpx;
  line-height: 1.5;
}

/* 规划疫苗行（v2 pg-vrow 观感：白底 line 边 28rpx 圆角） */
.vp-item {
  display: flex;
  gap: 24rpx;
  align-items: flex-start;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: 28rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 16rpx;
  box-shadow: var(--sj-sh-sm);
}
.vp-item.off { opacity: 0.5; }
/* sj-checkbox 与名称行的视觉对齐（原自绘勾选框 margin-top 语义保留） */
.vp-ck { margin-top: 4rpx; }
.vp-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 14rpx; }
.vp-name-row { display: flex; align-items: center; gap: 12rpx; }
.vp-name { font-size: 27rpx; font-weight: 800; color: var(--sj-ink); }
/* 剂数徽章（gold/duck 软底语义） */
.vp-dose {
  flex: none;
  font-size: 20rpx;
  font-weight: 800;
  color: #B47714;
  background: var(--sj-duck-soft);
  border-radius: var(--sj-r-pill);
  padding: 4rpx 16rpx;
}
/* 月龄排期胶囊（v2 chips 中性态：白底 line 边 pill） */
.vp-ages { display: flex; flex-wrap: wrap; gap: 12rpx; }
.vp-age {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--sj-sub);
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-pill);
  padding: 6rpx 18rpx;
}

/* 底部说明（合规文案） */
.scroll-end {
  text-align: center;
  font-size: 22rpx;
  color: var(--sj-faint);
  padding: 24rpx 0 16rpx;
  letter-spacing: 4rpx;
}
/* 主按钮：外观由 sj-button（block size=lg）统一提供，此处仅保留布局 */
.pg-btn { display: flex; }
</style>
