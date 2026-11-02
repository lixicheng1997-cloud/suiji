<template>
  <view class="sj-sl">
    <!-- 交互行为交给 uview-plus u-slider（v3 API：:modelValue + @change/@update:modelValue，
         点击轨道取值/拖动/禁用拦截均由库保证） -->
    <u-slider
      :modelValue="modelValue"
      :min="min"
      :max="max"
      :step="step"
      :disabled="disabled"
      height="16rpx"
      :blockSize="22"
      blockColor="#FFFFFF"
      :activeColor="activeColor"
      inactiveColor="#F3E4D3"
      :innerStyle="{ padding: '10px 12px' }"
      @change="onChange"
      @update:modelValue="onInput"
    />
    <!-- 右侧当前值：数值 + 单位，保留 decimals 位小数 -->
    <text class="sj-sl__val">{{ displayText }}</text>
  </view>
</template>

<script>
/**
 * 岁记 · 滑块（uview-plus u-slider 封装，easycom 自动注册）
 * 对齐 v2 设计稿 components.html L266-292（滑块/步进器区）+ styles.css L730-734
 * （.cu-sld，px×2→rpx）：轨道高 16rpx 圆角 8rpx 底色 --sj-line(#F3E4D3)；
 * 填充 primary→primary-deep 90° 渐变（库只接受单色 activeColor，渐变经命名空间覆盖实现）；
 * 圆钮 44rpx（blockSize=22px）白底 + 6rpx primary-deep 描边 + 暖阴影 --sj-sh-sm；
 * 非拖动期库自带 width .2s 过渡，观感对齐 .cu-sld .kn left .2s spring。
 * 右侧值文本对齐 v2 .cu-sld .vl：12px→24rpx / 900 / --sj-primary-deep，
 * 格式 = 数值(保留 decimals 位) + unit。
 * line/白 双主题相同写死；primary/primary-deep 走 var(--sj-*) 令牌覆盖，
 * activeColor 仅传 palette primary 作库内联基线。
 * 用法：<sj-slider v-model="temp" :min="35" :max="40" :step="0.1" :decimals="1" unit=" ℃" />
 */
import { palette } from '@/theme/theme.js'

export default {
  name: 'SjSlider',
  props: {
    /* 当前取值（受控，v3 v-model） */
    modelValue: { type: Number, default: 0 },
    /* 最小值 */
    min: { type: Number, default: 0 },
    /* 最大值 */
    max: { type: Number, default: 100 },
    /* 步长（支持小数，如 0.1） */
    step: { type: Number, default: 1 },
    /* 值文本后缀单位（如 ' ℃'、'%'、'ml'） */
    unit: { type: String, default: '' },
    /* 值文本保留小数位数 */
    decimals: { type: Number, default: 0 },
    /* 禁用（库置灰并拦截交互） */
    disabled: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    /* 库内联填充色基线取当前主题 primary（真正渐变效果由 .sj-sl 覆盖命中） */
    activeColor() {
      return palette(this.__theme)['primary']
    },
    /* 展示文本：数值按 decimals 格式化 + unit */
    displayText() {
      const num = Number(this.modelValue)
      return (Number.isFinite(num) ? num : 0).toFixed(this.decimals) + this.unit
    }
  },
  methods: {
    /* u-slider 的 change 载荷即格式化后的新数值（拖动结束/点击轨道），透传 */
    onChange(val) {
      this.$emit('change', val)
    },
    /* 双向绑定值透传给父级（库在拖动过程中也会持续发出） */
    onInput(val) {
      this.$emit('update:modelValue', val)
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：轨道占满剩余宽度，右侧值文本固定排尾 */
.sj-sl {
  display: flex;
  align-items: center;
  width: 100%;
}
/* 值文本：v2 .cu-sld .vl —— 24rpx(12px) / 900 / primary-deep，右对齐贴近轨道 */
.sj-sl__val {
  margin-left: 14rpx;
  font-size: 24rpx;
  font-weight: 900;
  color: var(--sj-primary-deep);
  white-space: nowrap;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-sl 命名空间覆盖 u-slider 内部类 ============ */
.sj-sl {
  /* 轨道主体占满弹性宽度 */
  .u-slider {
    flex: 1;
    min-width: 0;
  }
  /* 底部轨道：圆角 8rpx（v2 .tr 4px→8rpx），底色由 inactiveColor 传入 */
  .u-slider__base {
    border-radius: 8rpx !important;
  }
  /* 填充条：库内联单色 activeColor，!important 覆盖为 v2 主色 90° 渐变 + 圆角 */
  .u-slider__gap {
    background: linear-gradient(90deg, var(--sj-primary), var(--sj-primary-deep)) !important;
    border-radius: 8rpx !important;
  }
  /* 圆钮：v2 .kn —— 白底(库保证) + 6rpx primary-deep 描边 + 暖阴影；去库 scale(.9) 与黑阴影 */
  .u-slider__button {
    border: 6rpx solid var(--sj-primary-deep) !important;
    box-shadow: var(--sj-sh-sm) !important;
    transform: none !important;
  }
}
</style>
