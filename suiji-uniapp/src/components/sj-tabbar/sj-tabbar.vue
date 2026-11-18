<!--
  sj-tabbar · v2 悬浮底部导航（森林绘本 Kawaii）
  设计还原：suiji-ui-v2 styles.css .tabbar/.tab（悬浮圆角胶囊、激活态 primary-deep 静态放大，无回弹/浮动动画）。
  用法：tab 页根节点内放置 <sj-tabbar active="home" />；组件挂载时自动隐藏原生 tabBar。
  图标走 sj-icon 主题 png（10-tab-home…13-tab-me），随 bear/duck 实时换肤。
-->
<template>
  <view class="sj-tabbar">
    <view
      class="stb"
      :class="{ 'stb-pending': t.key === pending }"
      hover-class="stb-hover"
      :hover-stay-time="120"
      v-for="t in tabs"
      :key="t.key"
      @click="go(t)"
    >
      <view class="stb-ic" :class="{ on: t.key === active || t.key === pending }">
        <!-- 「我的」形象占画布更满、观感更大，放大 128rpx 并随容器底部对齐 -->
        <sj-icon :name="t.png" :size="t.key === 'me' ? 80 : 80" />
      </view>
      <text class="stb-tx" :class="{ on: t.key === active || t.key === pending }">{{ t.label }}</text>
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
    return { tabs: TABS, pending: '' }
  },
  watch: {
    /* 目标页已渲染（本页 active 落位时另一页接管高亮）或切回本页：清掉乐观高亮 */
    active() { this.clearPending() }
  },
  beforeUnmount() {
    this.clearPending()
  },
  mounted() {
    /* 隐藏原生 tabBar，保留 pages.json 配置以维持 tab 页路由语义 */
    uni.hideTabBar({ animation: false, fail: () => {} })
  },
  methods: {
    /* 微信端 switchTab 要切 webview + 目标页首帧渲染，空窗数百毫秒；
     * 点按瞬间乐观高亮目标页签，空窗期内不再呈现「点了没反应」 */
    go(t) {
      if (t.key === this.active || t.key === this.pending) return
      this.pending = t.key
      /* 兜底清除：切走后本页 webview 隐藏、active 不会变化，靠超时归位；
         若切 tab 失败留在本页，同样由超时恢复正确高亮 */
      clearTimeout(this._pt)
      this._pt = setTimeout(() => { this.pending = '' }, 1200)
      uni.switchTab({
        url: t.url,
        fail: () => this.clearPending()
      })
    },
    clearPending() {
      clearTimeout(this._pt)
      this._pt = null
      this.pending = ''
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
  /* 奶油→主题浅色渐变底：色值全走 --sj-* 令牌，bear/duck 切换实时换肤；
   * 深色端点放到 120%，浅色只染胶囊下半段，不喧宾夺主 */
  background: linear-gradient(160deg, var(--sj-cream) 30%, var(--sj-primary-soft) 120%);
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
  gap: 0;
  border-radius: 40rpx;
}
.stb-ic {
  width: 80rpx;
  height: 80rpx;
  /* 底部对齐：更大的「我的」图标（128rpx）底边与其他图标底边齐平，顶部自然冒出 */
  display: flex;
  align-items: flex-end;
  justify-content: center;
  transition: transform 0.3s cubic-bezier(.34,1.56,.64,1);
}
.stb-hover .stb-ic { transform: translateY(-3px); }
/* 乐观高亮期间压暗非目标页签文字，强化「已接收点击」的反馈 */
.stb-pending .stb-tx { color: var(--sj-sub); }
/* 激活态：图标向上跃出胶囊上边缘（弹性缓动自带回弹过冲），
 * 轻投影让跃出部分与页面内容分离；hover 仅微抬不跃出 */
.stb-ic.on {
  transform: translateY(-40rpx) scale(1.4);
  /* 双层暖色投影：近层收形、远层晕染，加重跃出图标的暖意 */
  filter: drop-shadow(0 8rpx 8rpx rgba(200, 115, 45, 0.30))
          drop-shadow(0 14rpx 20rpx rgba(232, 74, 111, 0.20));
}
.stb-tx {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--sj-faint);
  transition: color 0.25s, transform 0.3s cubic-bezier(.34,1.56,.64,1);
}
.stb-tx.on {
  color: var(--sj-primary-deep);
  /* 激活态文字上移量 = 图标弹出位移(40) − 缩放引起的下缘扩张(0.35×112/2≈19.6)，
     使选中的图文视觉间距与未选中态完全一致 */
  transform: translateY(-20rpx);
}
</style>
