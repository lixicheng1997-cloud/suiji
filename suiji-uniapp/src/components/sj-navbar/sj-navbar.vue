<template>
  <!-- v2 components.html「顶部导航」卡 .cu-nav：晨光奶橘渐变底 + 圆形返回钮 + 右侧图标区；
       落地形态对齐代码库各页 .pg-back（sticky 奶油渐隐 + statusBarHeight 内缩） -->
  <view class="sj-nb" :class="{ 'sj-nb--plain': !gradient }" :style="wrapStyle">
    <view v-if="back" class="sj-nb-bk" hover-class="hover-press" :hover-stay-time="80" @click="onBack">
      <image class="sj-nb-bk-ic" :src="backSrc" mode="aspectFit" />
    </view>
    <slot name="left" />
    <view class="sj-nb-title">
      <slot>
        <text class="sj-nb-tx">{{ title }}</text>
      </slot>
    </view>
    <view class="sj-nb-rt">
      <slot name="right" />
      <!-- 更多钮：ctl-v2 60 去底切图（more=true 时显示，页面 @more 自行处理） -->
      <view v-if="more" class="sj-nb-bk" hover-class="hover-press" :hover-stay-time="80" @click="$emit('more')">
        <image class="sj-nb-bk-ic" :src="moreSrc" mode="aspectFit" />
      </view>
    </view>
  </view>
</template>

<script>
/**
 * 岁记 · 顶部导航栏（easycom 自动注册 <sj-navbar>，对齐 v2「顶部导航」卡 + 各页 .pg-back 惯例）
 * 用于 navigationStyle: custom 页面：自动用 statusBarHeight（uni.getSystemInfoSync，勿依赖
 * --status-bar-height，小程序端为 0）做状态栏内缩；gradient 默认「晨光奶橘」渐变
 * （v2 .cu-nav linear-gradient(135deg,#FFE8DB,#FFF2DE)），plain 模式为白底（v2 第二示例）。
 * 右侧图标区走 #right 插槽（搜索 / 通知 + sj-badge 等页面自组）；more=true 追加
 * 圆形「更多」钮（ctl-v2 60 切图，点击 emit more）。
 * 返回/更多钮内为 ctl-v2 去底切图（59 举左向箭头指示牌 / 60 举三点指示牌，56rpx，
 * scripts/cut-ctl-icons.py 生成到 /static/icons/ctl/{theme}/56/），随主题换肤。
 * 用法：<sj-navbar title="成长曲线">
 *         <template #right>
 *           <image class="nav-ic" src="/static/icons/24-fn-search.png" />
 *         </template>
 *       </sj-navbar>
 * 非 tabs 页返回默认 uni.navigateBack()，可 @back 拦截（自行 preventDefault 语义：传 back=false 隐藏钮）。
 */
export default {
  name: 'SjNavbar',
  props: {
    /* 标题（也可用默认插槽自定义） */
    title: { type: String, default: '' },
    /* 是否显示圆形返回钮 */
    back: { type: Boolean, default: true },
    /* 晨光渐变（false = 白底 plain） */
    gradient: { type: Boolean, default: true },
    /* 右侧显示圆形「更多」钮（ctl-v2 60 切图） */
    more: { type: Boolean, default: false },
    /* 返回钮点击目标层级，0 = navigateBack */
    delta: { type: Number, default: 1 }
  },
  emits: ['back', 'more'],
  data() {
    /* 缓存状态栏高：getSystemInfoSync 每页重复调用有性能损耗，组件内取一次即可 */
    return { statusBarHeight: 0 }
  },
  computed: {
    wrapStyle() {
      return { paddingTop: 'calc(' + this.statusBarHeight + 'px + 8rpx)' }
    },
    /* 当前主题下的返回/更多钮切图（彩色绘本图，不走 color 重染） */
    backSrc() {
      return `/static/icons/ctl/${this.__theme}/56/59-ctl-nav-back.png`
    },
    moreSrc() {
      return `/static/icons/ctl/${this.__theme}/56/60-ctl-nav-more.png`
    }
  },
  mounted() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0
    } catch (e) {
      this.statusBarHeight = 0
    }
  },
  methods: {
    onBack() {
      this.$emit('back')
      uni.navigateBack({ delta: this.delta })
    }
  }
}
</script>

<style lang="scss" scoped>
/* v2 .cu-nav 14px→28rpx/900 标题；.pg-back 惯例：sticky + 奶油渐隐底 */
.sj-nb {
  position: -webkit-sticky;
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding-right: 32rpx;
  padding-bottom: 12rpx;
  background: linear-gradient(135deg, #FFE8DB, #FFF2DE);
}
.sj-nb--plain {
  background: var(--sj-surface);
}
.sj-nb-bk {
  flex: none;
  width: 64rpx;
  height: 64rpx;
  margin-left: 24rpx;
  border-radius: 50%;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
}
.sj-nb-bk-ic {
  width: 56rpx;
  height: 56rpx;
}
.sj-nb-title {
  min-width: 0;
}
.sj-nb-tx {
  font-size: 28rpx;
  font-weight: 900;
  color: var(--sj-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sj-nb-rt {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 16rpx;
}
</style>
