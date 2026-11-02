<template>
  <view class="sj-bd">
    <!-- 宿主内容（图标/头像等）由页面放入默认插槽 -->
    <slot />
    <!-- 徽标本体交给 uview-plus u-badge：absolute + offset 定位到宿主右上角，
         key 随值变化重挂载以重播 v2 bump 弹性动画 -->
    <u-badge
      :key="String(value) + String(dot)"
      :value="value"
      :isDot="dot"
      :max="max"
      :show="visible"
      bgColor="#EF7A7A"
      color="#FFFFFF"
      absolute
      :offset="offset"
    />
  </view>
</template>

<script>
/**
 * 岁记 · 徽标红点（uview-plus u-badge 封装，easycom 自动注册）
 * 对齐 v2 设计稿 components.html L163-174（徽标红点区）+ styles.css L708-710（.cu-bd，px×2→rpx）：
 * 数字徽标 34rpx 高、min-width 34rpx、全圆角、底色 --sj-bad(#EF7A7A) 白字 20rpx 黑 900、
 * 内衬 0 8rpx、白描边 4rpx(2px)、位置 top -12rpx / right -20rpx（v2 -6px/-10px）；
 * dot 模式 18rpx 小圆点，位置 top -4rpx / right -6rpx（v2 -2px/-3px）；
 * 出现/变更时播放 bump 弹性放大（styles.css L445，scale 1→1.4→1 / .5s spring）。
 * bad 语义色与白描边双主题相同，直接写死；超过 max（默认 99）库自动显示「99+」。
 * value 为 0 且非 dot 时不显示（对齐库 showZero 语义），hidden 可强制隐藏。
 * 用法：<sj-badge :value="3"><image src="..."/></sj-badge> <sj-badge dot><view class="ico"/></sj-badge>
 */
export default {
  name: 'SjBadge',
  props: {
    /* 徽标内容：数字或字符串（如 12、'新'） */
    value: { type: [Number, String], default: 0 },
    /* 小圆点模式（弱提示「有新内容」） */
    dot: { type: Boolean, default: false },
    /* 数值上限，超出显示 max+ */
    max: { type: Number, default: 99 },
    /* 强制隐藏徽标（不影响宿主插槽） */
    hidden: { type: Boolean, default: false }
  },
  computed: {
    /* 可见性：hidden 或「非 dot 且数值为 0」时隐藏（Number('')===0，空串同样隐藏） */
    visible() {
      return !this.hidden && (this.dot || Number(this.value) !== 0)
    },
    /* 位置偏移 [top, right]：dot 与设计稿 .cu-bd i.dot 对齐，数字与 .cu-bd i 对齐 */
    offset() {
      return this.dot ? ['-4rpx', '-6rpx'] : ['-12rpx', '-20rpx']
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：为绝对定位徽标提供参照系，尺寸随宿主内容 */
.sj-bd {
  position: relative;
  display: inline-flex;
  align-items: center;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-bd 命名空间覆盖 u-badge 内部类 ============
 * 库 scoped 选择器带 [data-v]，关键覆盖以重复类名提权 + !important 稳定命中。 */
.sj-bd {
  /* 通用：v2 .cu-bd i 白描边 4rpx + 出现时 bump 弹性动画（key 重挂载重播） */
  .u-badge.u-badge {
    border: 4rpx solid #FFFFFF;
    box-sizing: border-box;
    animation: sj-bd-bump 0.5s cubic-bezier(.34,1.56,.64,1);
  }
  /* 数字徽标：34rpx 高全圆角胶囊，20rpx 白字黑 900，内衬 0 8rpx */
  .u-badge.u-badge--not-dot {
    min-width: 34rpx !important;
    height: 34rpx !important;
    border-radius: 999rpx !important;
    padding: 0 8rpx !important;
    font-size: 20rpx !important;
    line-height: 26rpx !important;
    font-weight: 900;
  }
  /* dot 模式：18rpx 圆点，去内衬 */
  .u-badge.u-badge--dot {
    width: 18rpx !important;
    height: 18rpx !important;
    border-radius: 999rpx !important;
    padding: 0 !important;
  }
}
/* bump：对齐 styles.css L445（0→40% scale(1.4)→100% scale(1)），
 * sj 前缀唯一命名防全局泄漏 */
@keyframes sj-bd-bump {
  0% { transform: scale(1); }
  40% { transform: scale(1.4); }
  100% { transform: scale(1); }
}
</style>
