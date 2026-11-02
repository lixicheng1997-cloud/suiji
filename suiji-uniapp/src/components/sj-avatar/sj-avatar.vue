<template>
  <view class="sj-av" :class="['sj-av--' + shape, ringClass, { 'is-overlap': overlap }]" :style="boxStyle">
    <image v-if="url" class="sj-av-img" :src="url" :mode="mode" />
    <template v-else>
      <image v-if="icon" class="sj-av-ic" :src="iconSrc" mode="aspectFit" />
      <!-- 无图无字回落：ctl-v2 45-ctl-avatar 角色占位切图 -->
      <image v-else-if="!text" class="sj-av-ic" :src="ctlSrc" mode="aspectFit" />
      <text v-else class="sj-av-tx" :style="txStyle">{{ initial }}</text>
    </template>
    <!-- 徽标位：与 sj-badge 同款数字/红点（家庭空间成员「+2」等） -->
    <view v-if="!hidden && (dot || shownValue)" class="sj-av-bd" :class="{ 'sj-av-bd--dot': dot }">
      <text v-if="!dot">{{ shownValue }}</text>
    </view>
  </view>
</template>

<script>
/**
 * 岁记 · 头像（easycom 自动注册 <sj-avatar>，对齐 v2 components.html「头像」卡 .cu-av）
 * 统一白描边 + 主题浅底（primary-soft）；shape circle | square（v2 组内 14px→28rpx 圆角方）；
 * ring 变体对应 v2 g2（腮红描边）/ g3（雾蓝描边），重叠组里区分成员；
 * 无图回落：icon 名（/static/icons/{name}.svg 或 sj-icon PNG 主题图标）或昵称首字；
 * 无图且无 icon 无 text 时回落 ctl-v2 45-ctl-avatar 角色占位切图（128rpx 规格，
 * scripts/cut-ctl-icons.py 生成到 /static/icons/ctl/{theme}/128/，按头像尺寸等比缩放）。
 * 尺寸 props 为 rpx，默认 88（设计契约 §4 宝宝头像 88×88）。
 * 用法：<sj-avatar :url="baby.avatarUrl" :size="88" />
 *       <sj-avatar icon="13-tab-me" themed ring="g2" />
 *       <sj-avatar text="安安" />   → 显示「安」
 *       <sj-avatar />               → 角色占位图
 */
export default {
  name: 'SjAvatar',
  props: {
    /* 图片地址（相册 / 云端头像） */
    url: { type: String, default: '' },
    /* 无图回落：文字（取首字） */
    text: { type: String, default: '' },
    /* 无图回落：图标名 */
    icon: { type: String, default: '' },
    /* icon 为主题 PNG（static/icons/{theme}/）而非公共 SVG */
    themed: { type: Boolean, default: false },
    /* rpx */
    size: { type: [Number, String], default: 88 },
    /* circle | square */
    shape: { type: String, default: 'circle' },
    /* '' | g2 | g3（v2 描边变体） */
    ring: { type: String, default: '' },
    /* image mode */
    mode: { type: String, default: 'aspectFill' },
    /* 重叠组内使用：左移 -24rpx 叠在前一个头像上（v2 .cu-avgrp） */
    overlap: { type: Boolean, default: false },
    /* 徽标 */
    value: { type: [Number, String], default: '' },
    dot: { type: Boolean, default: false },
    max: { type: Number, default: 99 },
    hidden: { type: Boolean, default: false }
  },
  computed: {
    sizeRpx() {
      const s = typeof this.size === 'number' ? this.size : Number(this.size) || 88
      return s + 'rpx'
    },
    boxStyle() {
      return { width: this.sizeRpx, height: this.sizeRpx }
    },
    ringClass() {
      return this.ring ? 'sj-av--' + this.ring : ''
    },
    iconSrc() {
      const theme = this.__theme || 'bear'
      return this.themed
        ? `/static/icons/${theme}/${this.icon}.png`
        : `/static/icons/${this.icon}.svg`
    },
    /* 无图无字回落的角色占位切图 */
    ctlSrc() {
      return `/static/icons/ctl/${this.__theme || 'bear'}/128/45-ctl-avatar.png`
    },
    initial() {
      return (this.text || '').trim().charAt(0)
    },
    txStyle() {
      const s = typeof this.size === 'number' ? this.size : Number(this.size) || 88
      return { fontSize: Math.round(s * 0.42) + 'rpx' }
    },
    shownValue() {
      if (this.value === '' || this.value === null) return ''
      if (typeof this.value === 'number' && this.value > this.max) return this.max + '+'
      return String(this.value)
    }
  }
}
</script>

<style lang="scss" scoped>
/* v2 .cu-av：44px→88rpx 圆、primary-soft 底、2px→4rpx 白描边、sh-sm 投影 */
.sj-av {
  position: relative;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: visible;
  background: var(--sj-primary-soft);
  border: 4rpx solid var(--sj-white);
  border-radius: var(--sj-r-pill);
  box-shadow: var(--sj-sh-sm);
  box-sizing: border-box;
}
.sj-av--square {
  border-radius: 28rpx;   /* v2 组内方形 14px→28rpx */
}
.sj-av--g2 { border-color: var(--sj-blush-soft); }  /* v2 .cu-av.g2 */
.sj-av--g3 { border-color: #E9EEFB; }              /* v2 .cu-av.g3 雾蓝 */
.sj-av.is-overlap { margin-left: -24rpx; }         /* v2 .cu-avgrp 相邻左叠 -12px→-24rpx */
.sj-av-img {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  display: block;
}
.sj-av-ic {
  width: 62%;
  height: 62%;
}
.sj-av-tx {
  font-weight: 900;
  color: var(--sj-primary-deep);
  line-height: 1;
}
/* 徽标（v2 .cu-bd i：bad 底白字，dot 模式只点不字） */
.sj-av-bd {
  position: absolute;
  top: -6rpx;
  right: -6rpx;
  min-width: 30rpx;
  height: 30rpx;
  padding: 0 6rpx;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--sj-r-pill);
  background: var(--sj-bad);
  border: 3rpx solid var(--sj-white);
  z-index: 2;
}
.sj-av-bd text {
  font-size: 18rpx;
  font-weight: 900;
  color: #fff;
  line-height: 1;
}
.sj-av-bd--dot {
  min-width: 18rpx;
  width: 18rpx;
  height: 18rpx;
  padding: 0;
}
</style>
