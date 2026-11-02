<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回按钮 + display 标题） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">监护人同意</text>
      <view class="pg-title-spacer" />
    </view>

    <!-- 分项授权内容区（v2 P07：pg-field 行 + sj-checkbox 勾选 + pg-hint 留痕） -->
    <view class="content">
      <view class="pg-hint">
        <text>创建宝宝档案前，请阅读并逐项确认。同意与撤回分开勾选，撤回后对应功能立即停止使用相关数据。</text>
      </view>

      <!-- 逐项勾选（整行点击 toggle，逻辑不变） -->
      <view
        class="pg-field c-item"
        v-for="(c, i) in consents"
        :key="i"
        hover-class="hover-press"
        :hover-stay-time="80"
        @click="toggle(i)"
      >
        <!-- 勾选框本体（u-checkbox 内部 tap.stop，点击不冒泡到行；行点击仍走 toggle） -->
        <sj-checkbox class="c-ck" :checked="c.on" @change="v => (consents[i].on = v)" />
        <view class="c-info">
          <text class="c-title">{{ c.t }}<text v-if="c.req" class="c-req">必需</text></text>
          <text class="c-desc">{{ c.d }}</text>
        </view>
      </view>

      <!-- 同意留痕说明（v2 pg-hint.ok 绿色语义） -->
      <view class="pg-hint ok">
        <text>同意记录会保存：时间 · 政策版本 v1.0 · 操作账号</text>
      </view>

      <!-- 同意主按钮：校验 3 个必需项（逻辑不变） -->
      <sj-button
        class="pg-btn"
        block
        size="lg"
        text="同意并继续建档"
        @click="onAgree"
      />
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import { CONSENTS } from '@/utils/mock.js'
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'

/* 同意项下标 → 持久化键（与 seed.js consent 设置键序一致） */
const CONSENT_KEYS = ['privacy', 'child_rules', 'health', 'cloud_photo', 'ai_journal']

export default {
  data() {
    return {
      consents: CONSENTS.map(c => ({ ...c })),
      statusBarHeight: 20
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  onShow() {
    const saved = api.getConsent()
    if (saved) {
      CONSENT_KEYS.forEach((k, i) => {
        if (saved[k] !== undefined) this.consents[i].on = !!saved[k]
      })
    }
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
      this.consents[i].on = !this.consents[i].on
    },
    async onAgree() {
      if (!this.consents.filter(c => c.req).every(c => c.on)) {
        this.$refs.ntf.show({ type: 'warn', message: '请先勾选全部必需项' })
        return
      }
      const flags = {}
      CONSENT_KEYS.forEach((k, i) => { flags[k] = this.consents[i].on })
      api.saveConsent(flags)
      /* 建档变异步：无宝宝时 await 建档成功后再进首页，失败停留本页提示重试 */
      if (!api.getBaby()) {
        try {
          await api.onboardBaby({ name: '宝宝' })
        } catch (e) {
          ui.error(e, '建档失败，请检查网络后重试')
          return
        }
      }
      this.$refs.ntf.show({ type: 'ok', message: '已同意 · 宝宝档案创建完成' })
      uni.reLaunch({ url: '/pages/index/index' })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 页面底：v2 奶油色 */
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
.pg-title-spacer { width: 68rpx; flex: none; }

/* ---------- 内容区 ---------- */
.content { padding: 8rpx 32rpx 48rpx; }

/* 提示文案行（v2 pg-hint：cream 底 + 虚线边；ok 绿色语义变体） */
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
.pg-hint.ok { color: #2E7D4F; border-color: #BFE6CF; background: #EDF9F2; }

/* 字段行（v2 pg-field：毛玻璃面 + 半透高光描边 + 28rpx 圆角；玻璃配方见 App.vue --sj-glass*） */
.pg-field {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: var(--sj-glass);
  border: 2rpx solid var(--sj-glass-line);
  border-radius: 28rpx;
  box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
  padding: 20rpx 28rpx;
  font-size: 27rpx;
}

/* 同意分项（pg-field 行观感叠加） */
.c-item {
  align-items: flex-start;
  padding: 24rpx 28rpx;
  margin-bottom: 20rpx;
  box-shadow: var(--sj-sh-sm);
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.c-item:active { transform: scale(0.98); }

/* sj-checkbox 与标题行的视觉对齐（原自绘勾选框 margin-top 语义保留） */
.c-ck { margin-top: 4rpx; }

.c-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6rpx; }
.c-title { font-size: 27rpx; font-weight: 800; color: var(--sj-ink); }
.c-req {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--sj-bad);
  background: #FDF0F0;
  border-radius: var(--sj-r-pill);
  padding: 2rpx 16rpx;
  margin-left: 8rpx;
}
.c-desc { font-size: 22rpx; color: var(--sj-sub); line-height: 1.6; }
/* 主按钮：外观由 sj-button（block size=lg）统一提供，此处仅保留布局 */
.pg-btn { display: flex; }
/* 次按钮与主按钮的间距（原 .pg-btn.ghost 上的 margin-top） */
.pg-btn + .pg-btn { margin-top: 20rpx; }
</style>
