<template>
  <view class="sj-in" :class="variant === 'box' ? 'sj-in--box' : ''">
    <!-- 输入行为交给 uview-plus u-input（border=none 透明无边框，嵌在页面自绘容器内） -->
    <u-input
      :modelValue="modelValue"
      :placeholder="placeholder"
      :type="type"
      :maxlength="maxlength"
      :disabled="disabled"
      :focus="focus"
      border="none"
      color="#5B4636"
      fontSize="27rpx"
      placeholderStyle="color: #C7B6A8; font-weight: 600;"
      @update:modelValue="onInput"
      @confirm="$emit('confirm')"
    >
      <!-- 清除钮：ctl-v2 48-ctl-clear 去底切图（48rpx），clearable 且有内容时出现 -->
      <template v-if="clearable && modelValue && !disabled" #suffix>
        <image class="in-clear" :src="clearSrc" mode="aspectFit" @click.stop="onClear" />
      </template>
    </u-input>
  </view>
</template>

<script>
/**
 * 岁记 · 行内输入框（uview-plus u-input 封装，easycom 自动注册）
 * 定位为「无边框透明输入」：容器边框/底色由页面自绘，本组件只负责输入与字色观感。
 * variant="box" 时自带 v2 表单域外观（毛玻璃底 --sj-glass + 半透高光描边 + 28rpx 圆角 + 88rpx 高），
 * 页面无需再自绘容器，用于独立成行的输入（家庭名称、邀请码等）。
 * 字号统一到 v2 .pg-field 13.5px→27rpx（L569）：值 ink(#5B4636) 字重 800（经 .sj-in 命名空间
 * 全局覆盖补字重）、占位 faint(#C7B6A8) 字重 600（.pg-field .ph，L573）；ink/faint 双主题相同直接写死。
 * 宽度 100%，透传 update:modelValue 支持 v-model。
 * clearable：有内容时输入区右缘显示 ctl-v2 清除切图（48-ctl-clear，48rpx，
 * scripts/cut-ctl-icons.py 生成到 /static/icons/ctl/{theme}/48/），点击清空并 emit clear。
 * 用法：<sj-input v-model="name" placeholder="宝宝小名" :maxlength="12" />
 *       <sj-input v-model="code" variant="box" clearable :maxlength="8" />
 */
export default {
  name: 'SjInput',
  props: {
    /* 当前文本（v-model） */
    modelValue: { type: String, default: '' },
    /* 占位文案 */
    placeholder: { type: String, default: '' },
    /* 输入类型：text/number/idcard/digit 等（透传给库） */
    type: { type: String, default: 'text' },
    /* 最大长度，-1 不限制 */
    maxlength: { type: Number, default: -1 },
    /* 禁用 */
    disabled: { type: Boolean, default: false },
    /* 自动聚焦（弹窗内输入用；H5/小程序由库决定键盘是否真的弹起） */
    focus: { type: Boolean, default: false },
    /* 外观：plain 透明无边框（嵌页面容器）/ box 自带 v2 表单域描边 */
    variant: { type: String, default: 'plain' },
    /* 显示清除钮（有内容且未禁用时） */
    clearable: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'confirm', 'clear'],
  computed: {
    /* 当前主题下的清除钮切图（彩色绘本图，不走 color 重染） */
    clearSrc() {
      return `/static/icons/ctl/${this.__theme}/48/48-ctl-clear.png`
    }
  },
  methods: {
    /* u-input 的 update:modelValue 载荷即字符串值，直接透传 */
    onInput(val) {
      this.$emit('update:modelValue', val)
    },
    /* 点击清除：回写空串并通知页面 */
    onClear() {
      this.$emit('update:modelValue', '')
      this.$emit('clear')
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：占满父容器宽度，继承行内布局 */
.sj-in {
  width: 100%;
}
/* 清除钮切图（48rpx，切图自带约 11% 留白） */
.in-clear {
  width: 48rpx;
  height: 48rpx;
  margin-left: 12rpx;
  flex: none;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-in 命名空间覆盖 u-input 内部节点 ============ */
.sj-in {
  /* 输入文字：特粗 + ink（颜色库已内联传入，此处兜底并补字重） */
  .u-input__content__field-wrapper__field {
    font-weight: 800;
    color: var(--sj-ink) !important;
  }
  /* 占位符：faint（小程序端 placeholder-class 通路兜底，H5 走 ::placeholder） */
  .input-placeholder {
    color: var(--sj-faint);
  }
  .u-input__content__field-wrapper__field::placeholder {
    color: var(--sj-faint);
  }
  /* box 形态：v2 表单域外观（88rpx 高 / 28rpx 圆角），底色换成毛玻璃面（半透 + 模糊 + 内高光） */
  &--box .u-input.u-input {
    height: 88rpx !important;
    background: var(--sj-glass) !important;
    border: 2rpx solid var(--sj-glass-line) !important;
    border-radius: 28rpx !important;
    box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
    padding: 0 28rpx !important;
    box-sizing: border-box !important;
  }
}
</style>
