<template>
  <view class="sj-pg">
    <!-- 进度动画/宽度自适应交给 uview-plus u-line-progress（真实 prop 名为 percentage） -->
    <u-line-progress
      :percentage="percent"
      :height="barHeight"
      inactiveColor="#FFF8F0"
      :showText="false"
    />
  </view>
</template>

<script>
/**
 * 岁记 · 线性进度条（uview-plus u-line-progress 封装，easycom 自动注册）
 * 外观严格对齐 v2 .pg-prog（styles.css L610-612，px×2→rpx）：轨道高 10px→20rpx 全圆胶囊、
 * cream(#FFF8F0) 底 + 2rpx --sj-line 边；填充 primary→primary-deep 水平渐变 + pgGrow 入场动画
 * （1.2s --sj-smooth，width 0→目标）。
 * height prop 按 v2 设计 px 传入（默认 10，对齐轨道 20rpx），内部 ×2 换算 rpx 字符串传给库
 * （库 addUnit 对带单位字符串原样透传）。
 * 库的 activeColor 走内联 backgroundColor，无法承载渐变，
 * 故填充渐变经 .sj-pg 命名空间全局覆盖（var(--sj-primary) 随换肤）。
 * 用法：<sj-progress :percent="65" :height="10" />
 */
export default {
  name: 'SjProgress',
  props: {
    /* 进度百分比 0-100 */
    percent: { type: Number, default: 0 },
    /* 进度条高度，v2 设计 px 值（内部 ×2 → rpx；v2 轨道 10px → 默认 10） */
    height: { type: Number, default: 10 }
  },
  computed: {
    /* v2 设计 px × 2 → rpx，带单位字符串绕过库的默认 px 单位 */
    barHeight() {
      return this.height * 2 + 'rpx'
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：占满可用宽度 */
.sj-pg {
  width: 100%;
  display: flex;
  align-items: center;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-pg 命名空间覆盖 u-line-progress 内部类 ============ */
.sj-pg {
  /* 轨道：v2 .pg-prog 为 cream 底 + 1px(2rpx) line 边、全圆角胶囊；
   * 强制 content-box 使「轨道高 20rpx」指内容高度，边框外扩与设计稿盒模型一致 */
  .u-line-progress__background {
    box-sizing: content-box !important;
    border: 2rpx solid var(--sj-line) !important;
    border-radius: var(--sj-r-pill) !important;
  }
  /* 填充条：primary→primary-deep 水平渐变（!important 压过库内联 backgroundColor）；
   * top 内缩 2rpx 落在轨道描边之内；pgGrow 入场：keyframes 仅声明 from{width:0}，
   * 隐式 100% 取库内联目标宽度，实现 width 0→目标的 1.2s 生长动画 */
  .u-line-progress__line {
    top: 2rpx !important;
    background: linear-gradient(90deg, var(--sj-primary), var(--sj-primary-deep)) !important;
    animation: sjPgGrow 1.2s cubic-bezier(.22,.8,.3,1);
  }
}
/* v2 @keyframes pgGrow（命名空间前缀防全局泄漏） */
@keyframes sjPgGrow {
  from {
    width: 0;
  }
}
</style>
