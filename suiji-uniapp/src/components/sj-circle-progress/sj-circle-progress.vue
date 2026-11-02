<template>
  <view class="sj-rp" :style="ringStyle">
    <!-- 白芯：v2 .cu-ring::before inset 9px → strokeWidth×2 rpx -->
    <view class="sj-rp-core" :style="coreStyle" />
    <view class="sj-rp-center">
      <!-- 默认 slot 可替换中心内容；缺省显示百分比文本 -->
      <slot>
        <text class="sj-rp-text">{{ clamped }}%</text>
      </slot>
    </view>
  </view>
</template>

<script>
/**
 * 岁记 · 环形进度（easycom 自动注册）
 * 外观严格对齐 v2 .cu-ring（components.html L580-591「进度条/环形进度」；
 * styles.css L796-798，px×2→rpx）：74px→148rpx 圆 + 9px→18rpx 环宽白芯 +
 * conic-gradient 进度弧（自顶部顺时针）+ 中心 display 字体 primary-deep 900 百分比。
 * 选型说明：本机 node_modules 的 uview-plus u-circle-progress 为官方标注
 * 「TODO: 待完善」的半成品 —— percentage prop 未接入渲染、环色写死灰/绿、尺寸固定 100px，
 * 无法表达百分比与主题渐变，故按设计稿 conic-gradient 方案自绘（纯视觉组件、无交互内核损失）。
 * 渐变环：primary→primary-deep 扫过进度弧（随主题换肤，走 var(--sj-*) 令牌级联）。
 * 用法：<sj-circle-progress :percent="72" />
 *       <sj-circle-progress :percent="45" :size="90" :stroke-width="12">
 *         <text>自定义中心</text>
 *       </sj-circle-progress>
 */
export default {
  name: 'SjCircleProgress',
  props: {
    /* 进度百分比 0-100 */
    percent: { type: Number, default: 0 },
    /* 直径（px，×2 转 rpx；默认 74 → 148rpx 对齐 v2 .cu-ring） */
    size: { type: Number, default: 74 },
    /* 环宽（px，×2 转 rpx；默认 9 → 18rpx 对齐 v2 ::before inset） */
    strokeWidth: { type: Number, default: 9 }
  },
  computed: {
    /* 钳制到 0-100，防止非法值破坏 conic-gradient 色标 */
    clamped() {
      return Math.min(100, Math.max(0, Math.round(this.percent)))
    },
    /* 进度弧：主色起、primary-deep 止（扫过 percent），余量走 --sj-line 轨道 */
    ringStyle() {
      const p = this.clamped
      return {
        width: this.size * 2 + 'rpx',
        height: this.size * 2 + 'rpx',
        background:
          `conic-gradient(var(--sj-primary) 0%, var(--sj-primary-deep) ${p}%, ` +
          `var(--sj-line) ${p}%, var(--sj-line) 100%)`
      }
    },
    /* 白芯内缩 = 环宽（四边分开写，兼容小程序 WXSS 不支持 inset 简写） */
    coreStyle() {
      const v = this.strokeWidth * 2 + 'rpx'
      return { top: v, right: v, bottom: v, left: v }
    }
  }
}
</script>

<style lang="scss" scoped>
/* 环体：全圆 + 相对定位承托白芯与中心内容（v2 .cu-ring） */
.sj-rp {
  position: relative;
  border-radius: 50%;
  flex: none;
}
/* 白芯（v2 ::before：inset 9px 圆） */
.sj-rp-core {
  position: absolute;
  border-radius: 50%;
  background: var(--sj-surface);
}
/* 中心内容层 */
.sj-rp-center {
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* 百分比文本：v2 .cu-ring b（display 字体 16px→32rpx / primary-deep / 特粗） */
.sj-rp-text {
  font-family: var(--sj-font-display);
  font-size: 32rpx;
  font-weight: 900;
  color: var(--sj-primary-deep);
}
</style>
