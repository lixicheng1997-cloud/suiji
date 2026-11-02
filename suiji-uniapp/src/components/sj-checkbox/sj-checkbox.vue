<template>
  <view class="sj-ck" :class="{ 'sj-ck--bare': !label }">
    <!-- 交互行为交给 uview-plus u-checkbox（usedAlone 独立使用，无需 checkbox-group） -->
    <u-checkbox
      :checked="checked"
      :disabled="disabled"
      usedAlone
      shape="square"
      :size="22"
      :iconSize="13"
      :activeColor="activeColor"
      inactiveColor="#C7B6A8"
      iconColor="#FFFFFF"
      :label="label"
      labelColor="#5B4636"
      :labelSize="14"
      @change="onChange"
    />
  </view>
</template>

<script>
/**
 * 岁记 · 复选框（uview-plus u-checkbox 封装，easycom 自动注册）
 * 外观严格对齐 v2 .pg-ck（styles.css L591-592，px×2→rpx）：44×44rpx（size=22px）、
 * 圆角 14rpx、边框 4rpx solid --sj-faint(#C7B6A8)；选中 = primary 填充 + primary-deep 描边 + 白色✓（26rpx）。
 * primary/primary-deep 随主题换肤，故以 palette 十六进制经 activeColor 传入、经 var(--sj-primary-deep) 覆盖；
 * faint(#C7B6A8)/ink(#5B4636)/白 双主题相同，直接写死。
 * label 为空时只渲染方框（根节点带 .sj-ck--bare 去掉图标右间距，页面自行排文字）。
 * 用法：<sj-checkbox :checked="agree" label="我已阅读并同意" @change="agree = $event" />
 */
import { palette } from '@/theme/theme.js'

export default {
  name: 'SjCheckbox',
  props: {
    /* 当前选中状态（受控） */
    checked: { type: Boolean, default: false },
    /* 文案，可空（空时页面自行排文字） */
    label: { type: String, default: '' },
    /* 禁用（库拦截点击并弱化样式） */
    disabled: { type: Boolean, default: false }
  },
  emits: ['change'],
  computed: {
    /* 选中填充色取当前主题 primary（库 props 只接受静态色值，随换肤更新） */
    activeColor() {
      return palette(this.__theme)['primary']
    }
  },
  methods: {
    /* u-checkbox 的 change 首参即新布尔值（第二参 { name } 忽略），直接透传 */
    onChange(val) {
      this.$emit('change', val)
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：不破坏页面 flex 布局 */
.sj-ck {
  display: inline-flex;
  align-items: center;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-ck 命名空间覆盖 u-checkbox 内部类 ============
 * uview 内部节点 scoped 命不中；色值走 var(--sj-*) 令牌随页面根节点 themeVars 换肤。 */
.sj-ck {
  /* 去掉库默认的上下外边距，交由页面布局控制 */
  .u-checkbox {
    margin: 0 !important;
  }
  /* 方框：v2 .pg-ck 圆角 7px→14rpx、边框 2px→4rpx（库 square 默认 3px 圆角 / 1px 边） */
  .u-checkbox__icon-wrap--square {
    border-radius: 14rpx !important;
    border-width: 4rpx !important;
  }
  /* 选中态：库内联把边框也涂成 activeColor(primary)，按 v2 覆盖为 primary-deep 描边 */
  .u-checkbox__icon-wrap--checked {
    border-color: var(--sj-primary-deep) !important;
  }
  /* label：ink 特粗（颜色/字号已由 props 传入，字重库未提供 prop，此处覆盖） */
  .u-checkbox__label-wrap {
    font-weight: 700;
  }
  /* 无 label 时去掉方框右间距，避免空文本节点撑出缝隙 */
  &--bare .u-checkbox__icon-wrap {
    margin-right: 0 !important;
  }
}
</style>
