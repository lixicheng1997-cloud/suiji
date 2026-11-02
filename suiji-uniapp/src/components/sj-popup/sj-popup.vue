<template>
  <view class="sj-pop" :class="'sj-pop--' + mode">
    <!-- 遮罩/滑入动画/圆角交给 uview-plus u-popup，容器内容与头部条自组（同 sj-modal 选型） -->
    <u-popup
      :show="show"
      :mode="mode"
      :round="radius"
      :zoom="zoom"
      :overlay="overlay"
      :overlayStyle="maskStyle"
      :closeOnClickOverlay="closeOnClickOverlay"
      :duration="duration"
      :zIndex="zIndex"
      :safeAreaInsetBottom="safeAreaInsetBottom"
      :safeAreaInsetTop="safeAreaInsetTop"
      bgColor=""
      @open="$emit('open')"
      @close="onOverlayClose"
    >
      <view class="pop-panel">
        <!-- 把手条（v2 底部面板「•••」把手，双主题同值；center 模式不显示） -->
        <view v-if="showHandle" class="pop-handle">
          <view class="pop-handle__bar" />
        </view>
        <!-- 头部条（v2 .cu-pick .pk-bar：取消 · 标题 · 关闭，2rpx 虚线分隔，
             标题 primary-deep、两侧按钮 sub 色） -->
        <view v-if="showBar" class="pop-bar">
          <view class="pop-bar__side" @click="onLeft">
            <text v-if="leftText" class="pop-bar__btn" hover-class="pop-bar__btn--press" :hover-stay-time="80">{{ leftText }}</text>
          </view>
          <view class="pop-bar__mid">
            <!-- 标题前置图标：ctl-v2 去底切图（bar-icon 传切图名时显示，56rpx） -->
            <image v-if="barIconSrc" class="pop-bar__ic" :src="barIconSrc" mode="aspectFit" />
            <text class="pop-bar__title">{{ title }}</text>
          </view>
          <view class="pop-bar__side pop-bar__side--right" @click="onRight">
            <text v-if="rightText" class="pop-bar__btn" hover-class="pop-bar__btn--press" :hover-stay-time="80">{{ rightText }}</text>
          </view>
        </view>
        <slot />
      </view>
    </u-popup>
  </view>
</template>

<script>
/**
 * 岁记 · 弹出面板（uview-plus u-popup 承载遮罩与动画 + 自组把手/头部条，easycom 自动注册）
 * 外观 1:1 对齐 v2 components.html 04 反馈区「底部面板 <u-popup>」卡
 * （styles.css L802-804 .cu-pick/.pk-bar，px×2→rpx）：
 * mode=bottom + 圆角 24→48rpx（top/left/right 向按对应边收口）+ 把手条；
 * 头部条 padding 24/32rpx、26rpx/800 sub 字、2rpx 虚线 line 分隔，标题 primary-deep；
 * 遮罩 --sj-mask（暖可可半透）、面板为 .94 暖白磨砂近实底（叠在遮罩上不能再透，故不随 --sj-surface 半透化）；
 * 入场缓动覆盖为 --sj-spring（同 sj-modal）。
 * 头部两侧文案置 ''（且 title 为空）即隐藏头部条；center 模式默认不带把手。
 * bar-icon：传 ctl-v2 切图名（如 '67-ctl-popup'）时标题前置 56rpx 角色切图，
 * scripts/cut-ctl-icons.py 生成到 /static/icons/ctl/{theme}/56/，随主题换肤。
 * 注意：调用处不要放在带有 z-index / transform / filter 的容器里（会形成层叠上下文，
 * fixed 弹层被关在该层内，压不过页面级浮层如 z-index:40 的 sj-tabbar）。
 * 用法：<sj-popup v-model:show="typeShow" title="选择记录类型" bar-icon="67-ctl-popup"
 *        @cancel/@close 收起>
 *         <view>…记录类型磁贴…</view>
 *       </sj-popup>
 */
import { POPUP_MASK_STYLE } from '@/theme/theme.js'

export default {
  name: 'SjPopup',
  props: {
    /* 显隐（v-model:show） */
    show: { type: Boolean, default: false },
    /* 弹出方向：bottom | top | left | right | center */
    mode: { type: String, default: 'bottom' },
    /* 头部条标题（'' = 只显示两侧按钮时仍占位，标题为空可配 showBar） */
    title: { type: String, default: '' },
    /* 标题前置 ctl-v2 切图名（'' = 无图标） */
    barIcon: { type: String, default: '' },
    /* 头部左侧按钮文案（'' = 不显示），点击 emit cancel 并关闭 */
    leftText: { type: String, default: '取消' },
    /* 头部右侧按钮文案（'' = 不显示），点击 emit close 并关闭 */
    rightText: { type: String, default: '关闭' },
    /* 顶部把手条（center 模式忽略） */
    handle: { type: Boolean, default: true },
    /* 是否显示遮罩 */
    overlay: { type: Boolean, default: true },
    /* 点击遮罩是否关闭 */
    closeOnClickOverlay: { type: Boolean, default: true },
    /* 动画时长 ms */
    duration: { type: [String, Number], default: 300 },
    /* 层级 */
    zIndex: { type: [String, Number], default: 10075 },
    /* iPhone X 底部安全区留白 */
    safeAreaInsetBottom: { type: Boolean, default: true },
    /* 顶部状态栏留白（mode=top 时按需开启） */
    safeAreaInsetTop: { type: Boolean, default: false },
    /* center 模式缩放动画 */
    zoom: { type: Boolean, default: true },
    /* 圆角（设计稿 24px→48rpx；传 '' 走直角） */
    round: { type: [String, Number], default: '' }
  },
  emits: ['update:show', 'open', 'close', 'cancel'],
  computed: {
    /* 当前主题下的标题前置切图（彩色绘本图，不走 color 重染） */
    barIconSrc() {
      if (!this.barIcon) return ''
      return `/static/icons/ctl/${this.__theme}/56/${this.barIcon}.png`
    },
    /* 遮罩内联样式（同 sj-modal：--sj-mask 值经 overlayStyle 下发） */
    maskStyle() {
      return POPUP_MASK_STYLE
    },
    radius() {
      if (this.round === '') return this.mode === 'left' || this.mode === 'right' ? 0 : '48rpx'
      return this.round
    },
    showHandle() {
      return this.handle && this.mode !== 'center'
    },
    showBar() {
      return !!(this.title || this.leftText || this.rightText)
    }
  },
  methods: {
    /* 头部按钮点击后由本组件负责关闭（emit update:show false） */
    onLeft() {
      if (!this.leftText) return
      this.$emit('update:show', false)
      this.$emit('cancel')
    },
    onRight() {
      if (!this.rightText) return
      this.$emit('update:show', false)
      this.$emit('close')
    },
    /* 点遮罩关闭或外部置 show=false：统一对外发 close */
    onOverlayClose() {
      this.$emit('update:show', false)
      this.$emit('close')
    }
  }
}
</script>

<style lang="scss" scoped>
/* 弹层包裹：u-popup 根为 fixed 弹窗，此层不占布局（同 sj-modal） */
.sj-pop {
  width: 0;
  height: 0;
}
/* 面板主体（v2 .cu-pick：白底、顶部圆角由 u-popup contentStyle 处理） */
.pop-panel {
  display: flex;
  flex-direction: column;
}
/* 把手条（v2 顶部面板「•••」：居中小胶囊） */
.pop-handle {
  display: flex;
  justify-content: center;
  padding: 20rpx 0 4rpx;
}
.pop-handle__bar {
  width: 72rpx;
  height: 8rpx;
  border-radius: var(--sj-r-pill);
  background: var(--sj-faint);
}
/* 头部条（v2 .pk-bar：flex 两端 + 居中标题，2rpx 虚线分隔） */
.pop-bar {
  display: flex;
  align-items: center;
  padding: 20rpx 32rpx;
  font-size: 26rpx;
  font-weight: 800;
  color: var(--sj-sub);
  border-bottom: 2rpx dashed var(--sj-line);
}
/* 两侧等宽占位，保证标题始终居中；文案为空仍保留位置 */
.pop-bar__side {
  flex: 1;
  display: flex;
}
.pop-bar__side--right {
  justify-content: flex-end;
}
/* 标题区：前置图标 + 标题整体居中 */
.pop-bar__mid {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
}
.pop-bar__ic {
  width: 56rpx;
  height: 56rpx;
  margin-right: 12rpx;
  flex: none;
}
.pop-bar__btn {
  padding: 8rpx 12rpx;
  transition: transform 0.2s var(--sj-spring);
}
.pop-bar__btn--press {
  opacity: 0.55;
}
.pop-bar__title {
  color: var(--sj-primary-deep);
  text-align: center;
}
</style>

<style lang="scss">
/* 非 scoped：uview-plus 内部节点对齐 v2 规范（命名空间 .sj-pop） */
.sj-pop {
  /* 面板：.94 暖白磨砂近实底（压住遮罩与页面内容，避免玻璃叠玻璃） */
  .u-popup__content {
    background: rgba(255, 253, 251, 0.94) !important;
    overflow: hidden;
  }
  /* 入场缓动对齐 v2 弹性曲线（bottom/top 滑入） */
  .u-transition {
    transition-timing-function: var(--sj-spring) !important;
  }
  /* center 模式：卡片投影对齐 v2 md-card（sh-lg） */
  &.sj-pop--center .u-popup__content {
    box-shadow: var(--sj-sh-lg);
  }
}
</style>
