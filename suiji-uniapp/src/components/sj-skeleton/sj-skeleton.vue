<template>
  <view class="sj-sk">
    <!-- 占位渲染与 shimmer 节奏交给 uview-plus u-skeleton（loading=false 时渲染默认 slot 真实内容） -->
    <u-skeleton
      :loading="loading"
      :rows="rows"
      :rowsHeight="rowsHeight"
      :avatar="avatar"
      :animate="animate"
      :title="false"
    >
      <slot />
    </u-skeleton>
  </view>
</template>

<script>
/**
 * 岁记 · 骨架屏（uview-plus u-skeleton 封装，easycom 自动注册）
 * 外观严格对齐 v2 .pg-skel（components.html L572-578「骨架屏：暖米底+高光扫过」；
 * styles.css L641-643，px×2→rpx）：骨架条暖米系渐变
 * linear-gradient(100deg,#FBF2E6 30%,#FFF8F0 50%,#FBF2E6 70%) + 2rpx --sj-line 描边，
 * 圆角 --r-md 20px→40rpx、条高 64px→128rpx（设计稿为"与卡片布局一致的节奏"粗条，
 * 非库默认 18px 细线；rowsHeight prop 传入，可覆写成数组做 64/44/88 混合节奏）、
 * 条间距 gap 10px→20rpx，shimmer 1.4s linear 无限循环（库默认冷灰与 400% 节奏经命名空间覆盖）。
 * 库 title 占位默认开启，设计稿为纯条状节奏，故固定 title=false；
 * animate 开关透传库（关闭时静态暖米底）。
 * 用法：<sj-skeleton :loading="busy" :rows="3">
 *         <view>…真实内容…</view>
 *       </sj-skeleton>
 */
export default {
  name: 'SjSkeleton',
  props: {
    /* true 显示骨架占位，false 渲染默认 slot 内容 */
    loading: { type: Boolean, default: true },
    /* 骨架条行数 */
    rows: { type: Number, default: 3 },
    /* 骨架条高度：默认 v2 卡条节奏 128rpx；可传数组混合（如 ['128rpx','88rpx','176rpx']） */
    rowsHeight: { type: [String, Number, Array], default: '128rpx' },
    /* 是否显示头像占位（圆形） */
    avatar: { type: Boolean, default: false },
    /* 是否开启 shimmer 动画 */
    animate: { type: Boolean, default: true }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：不破坏页面 flex 布局 */
.sj-sk {
  display: block;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-sk 命名空间覆盖 u-skeleton 内部节点 ============
 * 库骨架块背景走 --up-skeleton-* 变量（默认冷灰），此处统一覆盖为 v2 暖米系。 */
.sj-sk {
  .u-skeleton__wrapper__content__rows,
  .u-skeleton__wrapper__content__title {
    /* v2 .pg-skel i：暖米高光扫过 + 1px→2rpx line 描边 + 圆角 --r-md 40rpx */
    background: linear-gradient(100deg, #FBF2E6 30%, #FFF8F0 50%, #FBF2E6 70%) !important;
    background-size: 200% 100% !important;
    border: 2rpx solid var(--sj-line);
    border-radius: 40rpx !important;
  }
  /* 条间距 = v2 .pg-skel gap 10px→20rpx（库默认 12px 偏大） */
  .u-skeleton__wrapper__content__rows {
    margin-bottom: 20rpx !important;
  }
  /* 头像占位：同暖米系，保持圆形 */
  .u-skeleton__wrapper__avatar {
    background: linear-gradient(100deg, #FBF2E6 30%, #FFF8F0 50%, #FBF2E6 70%) !important;
    background-size: 200% 100% !important;
    border: 2rpx solid var(--sj-line);
    border-radius: 100px !important;
  }
  /* shimmer：对齐 v2 @keyframes shimmer（to{background-position:-200% 0}）1.4s linear */
  .animate {
    animation: sjSkelShimmer 1.4s linear infinite !important;
  }
}

@keyframes sjSkelShimmer {
  to {
    background-position: -200% 0;
  }
}
</style>
