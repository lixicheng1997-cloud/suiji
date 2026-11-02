<template>
  <view
    class="sj-nb"
    :class="{ 'is-at-min': modelValue <= min, 'is-at-max': modelValue >= max }"
  >
    <!-- 加减号语义图标：uview 内置 minus/plus 矢量字形（15px bold），色随主题 primary-deep，
         到达 min/max 时库自动加 --disabled 类（本组件压回主题底色 + 整钮弱化） -->
    <u-number-box
      :modelValue="modelValue"
      :min="min"
      :max="max"
      :step="step"
      :disabledInput="disabledInput"
      :buttonSize="34"
      :buttonWidth="36"
      :inputWidth="44"
      buttonRadius="0"
      :bgColor="btnBg"
      :color="btnFg"
      inputBgColor="#FFFFFF"
      disabledBgColor="#FFF8F0"
      @change="onChange"
    />
  </view>
</template>

<script>
/**
 * 岁记 · 步进器（uview-plus u-number-box 封装，easycom 自动注册）
 * 外观 1:1 对齐 v2 .cu-nb（components.html L286-291；styles.css L735-739，px×2→rpx）：
 * 胶囊容器（圆角 --sj-r-pill + 3rpx(1.5px) line 描边 + overflow hidden 裁内角），
 * 加减按钮 36×34px→buttonWidth/buttonSize 直传，primary-soft 浅底 + primary-deep 号（±），
 * 数值区 min-width 44px→inputWidth、28rpx(14px)/900 ink（库 color 同控号与数值，
 * 数值色经 .sj-nb 覆盖为 ink；库无容器边框 prop，胶囊描边/裁角/输入区 margin 归零均走命名空间覆盖）。
 * primary-soft/primary-deep 随主题变化，经 palette(this.__theme) 传库内联基线；
 * surface/line/ink/cream(#FFF8F0) 双主题相同，写死。
 * 加减号用库内置 minus/plus 语义矢量字形（15px bold，缩放不糊、双主题同构），
 * 到达 min/max 时库自动挂 --disabled 类，本组件覆盖为整钮弱化（is-at-min/is-at-max 由库判定，
 * 包装类仅用于语义标记，弱化样式统一走库 --disabled 类）。
 * u-number-box 的 change 载荷为 { value, name, type }，本组件归一为 Number 后
 * 同时 emit update:modelValue（支持 v-model）与 change。
 * 用法：<sj-number-box v-model="milk" :min="0" :max="200" :step="10" />
 */
import { palette } from '@/theme/theme.js'

export default {
  name: 'SjNumberBox',
  props: {
    /* 当前数值（v-model） */
    modelValue: { type: Number, default: 0 },
    /* 最小值 */
    min: { type: Number, default: 0 },
    /* 最大值 */
    max: { type: Number, default: 999 },
    /* 步长 */
    step: { type: Number, default: 1 },
    /* 禁用中间输入框直接编辑（默认允许输入，失焦时由库按 min/max/step 钳制回写） */
    disabledInput: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    /* 按钮浅底：库内联基线取当前主题 primary-soft */
    btnBg() {
      return palette(this.__theme)['primary-soft']
    },
    /* 按钮 ± 号色：库 color 同控号与数值，数值色另经 .sj-nb 覆盖为 ink */
    btnFg() {
      return palette(this.__theme)['primary-deep']
    }
  },
  methods: {
    /* 库 change 载荷 { value } 可能是字符串（toFixed 场景），统一转 Number */
    onChange(e) {
      const val = Number(e.value)
      this.$emit('update:modelValue', val)
      this.$emit('change', val)
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：不破坏页面 flex 布局 */
.sj-nb {
  display: inline-flex;
  align-items: center;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-nb 命名空间覆盖 u-number-box 内部类 ============
 * 库按钮内联只含背景/尺寸/字色/圆角（buttonRadius 已传 0），
 * 胶囊容器描边与裁角、数值字号字重由此处覆盖；色值走 var(--sj-*) 令牌。 */
.sj-nb {
  /* 容器：v2 .cu-nb —— 白底 + 3rpx(1.5px) line 描边 + 胶囊圆角，overflow hidden 裁掉方角按钮 */
  .u-number-box {
    border: 3rpx solid var(--sj-line);
    border-radius: var(--sj-r-pill);
    overflow: hidden;
    background-color: var(--sj-surface);
  }
  /* 按压反馈：v2 hover 为浅底提暗（brightness .95），压掉库灰底 hover
   *（三类叠加抬权重，稳过库 scoped 单类+属性选择器的 !important） */
  .u-number-box .u-number-box__minus--hover,
  .u-number-box .u-number-box__plus--hover {
    background-color: var(--sj-primary-soft) !important;
    filter: brightness(0.95);
  }
  /* 中间数值：v2 .cu-nb span —— 28rpx(14px)/900 ink（库 color 同控数值色，压回 ink）；
   * 库 margin 0 2px 会露缝，归零；两侧 hairline 与加减钮做视觉分隔 */
  .u-number-box__input {
    margin: 0 !important;
    font-weight: 900;
    font-size: 28rpx !important;
    color: var(--sj-ink) !important;
    border-left: 3rpx solid var(--sj-line);
    border-right: 3rpx solid var(--sj-line);
    text-align: center;
  }
  /* 输入框显式禁用（传 disabledInput）时数值仍保持 ink 观感，白底与容器无缝 */
  .u-number-box__input--disabled {
    color: var(--sj-ink) !important;
    background-color: var(--sj-surface) !important;
  }
  /* 边界禁用态（库在 min/max 时自动挂 --disabled 类，加/减钮共用此类名）：
   * 底色压回主题浅底（覆盖库内联 cream），整钮含 ± 号弱化并拦截点击，避免无效按压反馈 */
  .u-number-box .u-number-box__minus--disabled {
    background-color: var(--sj-primary-soft) !important;
    opacity: 0.45;
    pointer-events: none;
  }
}
</style>
