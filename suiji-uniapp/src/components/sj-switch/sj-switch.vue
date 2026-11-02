<template>
  <view class="sj-sw">
    <!-- 交互行为交给 uview-plus u-switch（点击切换/禁用拦截/滑动动画由库保证） -->
    <u-switch
      :modelValue="checked"
      :disabled="disabled"
      :activeColor="activeColor"
      inactiveColor="#F3E4D3"
      :size="24"
      @change="onChange"
    />
  </view>
</template>

<script>
/**
 * 岁记 · 开关（uview-plus u-switch 封装，easycom 自动注册）
 * 外观严格对齐 v2 .pg-sw（styles.css L582-585，px×2→rpx）：
 * 92×52rpx 全圆胶囊；关=--sj-line(#F3E4D3)、开=当前主题主色（经 palette 随换肤）。
 * 圆点 40rpx 白、top/left 6rpx、阴影 0 4rpx 12rpx rgba(120,70,30,.25)，开态 translateX(40rpx)；
 * 底色过渡 .25s、圆点走 --sj-spring 缓动。
 * u-switch 的 size 单位为 px（高度 = size + 2），size=24 → 高 26px = 52rpx；
 * 库宽公式 size*2+2=50px≠92rpx，经 .sj-sw 命名空间 !important 覆盖内联宽度精确命中；
 * 圆点为库 flex 右对齐 + 内联 transform，改绝对定位 + 状态类 transform 覆盖，与 v2 ::after 完全一致。
 * 关态底色双主题相同，直接写死；受控用法：父组件更新 checked，本组件仅 emit change(新布尔值)。
 * 用法：<sj-switch :checked="on" :disabled="lock" @change="on = $event" />
 */
import { palette } from '@/theme/theme.js'

export default {
  name: 'SjSwitch',
  props: {
    /* 当前开关状态（受控） */
    checked: { type: Boolean, default: false },
    /* 禁用（库自带降透明度样式） */
    disabled: { type: Boolean, default: false }
  },
  emits: ['change'],
  computed: {
    /* 打开态背景 = 当前主题主色（库 props 只接受静态色值，经 palette 随换肤更新） */
    activeColor() {
      return palette(this.__theme)['primary']
    }
  },
  methods: {
    /* u-switch 的 change 载荷即切换后的新布尔值，直接透传 */
    onChange(val) {
      this.$emit('change', val)
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：不破坏页面 flex 布局，类名可被页面样式覆盖 */
.sj-sw {
  display: inline-flex;
  align-items: center;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-sw 命名空间覆盖 u-switch 内部节点 ============
 * 库内联样式（宽高/transform）不带 !important，均可被此处压过；色值走语义令牌。 */
.sj-sw {
  /* 轨道：v2 .pg-sw 46×26px → 92×52rpx 全圆胶囊（库宽公式凑不出 92，强制覆盖）；
   * 去库 1px 透明边框，使圆点 inset 精确按 6rpx 起算；底色过渡 .25s（对齐 v2） */
  .u-switch {
    width: 92rpx !important;
    border-width: 0 !important;
    transition: background-color 0.25s !important;
  }
  /* 圆点：对齐 v2 ::after —— 40rpx 白点、top/left 6rpx、绘本暖棕阴影；
   * 库默认 flex 右对齐 + 内联 translateX，改绝对定位后位移语义与设计稿一致 */
  .u-switch__node {
    position: absolute !important;
    top: 6rpx;
    left: 6rpx;
    width: 40rpx !important;
    height: 40rpx !important;
    transform: translateX(0) !important;
    box-shadow: 0 4rpx 12rpx rgba(120, 70, 30, 0.25) !important;
    transition-property: transform !important;
    transition-duration: 0.25s !important;
    transition-timing-function: cubic-bezier(.34,1.56,.64,1) !important;
  }
  /* 开态：圆点右移 40rpx（v2 .pg-sw.on::after translateX(20px)） */
  .u-switch__node--on {
    transform: translateX(40rpx) !important;
  }
}
</style>
