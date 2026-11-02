<!--
  sj-tabbar · v2 悬浮底部导航（森林绘本 Kawaii）
  设计还原：suiji-ui-v2 styles.css .tabbar/.tab（悬浮圆角胶囊、激活态 primary-deep + tabJump 弹性动画）。
  用法：tab 页根节点内放置 <sj-tabbar active="home" />；组件挂载时自动隐藏原生 tabBar。
  图标走 sj-icon 主题 png（10-tab-home…13-tab-me），随 bear/duck 实时换肤。
-->
<template>
  <view class="sj-tabbar">
    <view class="stb" hover-class="stb-hover" :hover-stay-time="120" v-for="t in tabs" :key="t.key" @click="go(t)">
      <view class="stb-ic" :class="{ on: t.key === active, jump: t.key === active && bounce === t.key }">
        <sj-icon :name="t.png" :size="68" />
      </view>
      <text class="stb-tx" :class="{ on: t.key === active }">{{ t.label }}</text>
    </view>
  </view>
</template>

<script>
/* 与 v2 设计一致的四个页签：时光轴 / 成长 / 家庭 / 我的 */
const TABS = [
  { key: 'home', png: '10-tab-home', label: '时光轴', url: '/pages/index/index' },
  { key: 'grow', png: '11-tab-growth', label: '成长', url: '/pages/grow/grow' },
  { key: 'family', png: '12-tab-family', label: '家庭', url: '/pages/family/family' },
  { key: 'me', png: '13-tab-me', label: '我的', url: '/pages/me/me' }
]

export default {
  name: 'SjTabbar',
  props: {
    /* 当前页 key：home | grow | family | me */
    active: { type: String, required: true }
  },
  data() {
    return { tabs: TABS, bounce: '' }
  },
  mounted() {
    /* 隐藏原生 tabBar，保留 pages.json 配置以维持 tab 页路由语义 */
    uni.hideTabBar({ animation: false, fail: () => {} })
  },
  methods: {
    go(t) {
      if (t.key !== this.active) {
        uni.switchTab({ url: t.url })
        return
      }
      /* 点击当前页签：重播 tabJump 弹性动画 */
      this.bounce = ''
      this.$nextTick(() => { this.bounce = t.key })
      setTimeout(() => { if (this.bounce === t.key) this.bounce = '' }, 520)
    }
  }
}
</script>

<style scoped>
.sj-tabbar {
  position: fixed;
  left: 20rpx;
  right: 20rpx;
  bottom: calc(20rpx + env(safe-area-inset-bottom));
  /* #ifdef MP-WEIXIN */
  /* 微信端整体下沉贴近 App 端观感：固定间隙 20rpx→8rpx，
   * env(safe-area-inset-bottom) 保留（iPhone Home 条避让，与 App 端同公式） */
  bottom: calc(8rpx + env(safe-area-inset-bottom));
  /* #endif */
  height: 144rpx;
  display: flex;
  background: rgba(255, 255, 255, 0.94);
  border: 2rpx solid var(--sj-line);
  border-radius: 52rpx;
  box-shadow: 0 -12rpx 48rpx rgba(180, 110, 60, 0.10);
  z-index: 40;
}
.stb {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4rpx;
  border-radius: 40rpx;
}
/* 安卓适配：animation/transition 简写内不用 var()（部分 webview 解析失败会丢弃整条声明），
   keyframes 位移用 px（rpx 在 keyframes 中不保证被编译转换）。1rpx = 0.5px。 */
.stb-ic {
  width: 68rpx;
  height: 68rpx;
  transition: transform 0.3s cubic-bezier(.34,1.56,.64,1);
}
.stb-hover .stb-ic { transform: translateY(-3px); }
/* 选中态：放大并持续上下浮动（可超出底栏） */
.stb-ic.on { animation: sjTabPop 0.45s cubic-bezier(.34,1.56,.64,1), sjTabFloat 1.5s ease-in-out 0.45s infinite; }
.stb-ic.jump { animation: sjTabJump 0.5s cubic-bezier(.34,1.56,.64,1), sjTabFloat 1.5s ease-in-out 0.5s infinite; }
@keyframes sjTabPop {
  0% { transform: scale(1); }
  40% { transform: scale(1.5) translateY(-6px) rotate(-8deg); }
  70% { transform: scale(1.24) translateY(-3px); }
  100% { transform: scale(1.32) translateY(-4px); }
}
@keyframes sjTabFloat {
  0%, 100% { transform: scale(1.32) translateY(-4px); }
  50% { transform: scale(1.44) translateY(-6.5px); }
}
@keyframes sjTabJump {
  0% { transform: scale(1); }
  35% { transform: scale(1.28) translateY(-6px) rotate(-6deg); }
  70% { transform: scale(0.94) translateY(1px); }
  100% { transform: scale(1); }
}
.stb-tx {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--sj-faint);
  transition: color 0.25s;
}
.stb-tx.on { color: var(--sj-primary-deep); }
</style>
