<template>
  <view class="sj-rd" :class="{ 'sj-rd--bare': !label }">
    <!-- u-radio 强制要求 u-radio-group 父级提供受控值（库源码 mounted 校验），
         故内部包一个单选项 group：group 的 modelValue 即外部传入的「当前选中值」，
         name === modelValue 时本项选中，实现脱离页面级 group 的 usedAlone 用法 -->
    <u-radio-group
      :modelValue="modelValue"
      :customStyle="{ flex: 'none' }"
      @change="onChange"
    >
      <u-radio
        :name="name"
        :label="label"
        :disabled="disabled"
        shape="circle"
        :size="20"
        :labelSize="13"
        :activeColor="activeColor"
        inactiveColor="#C7B6A8"
        labelColor="#5B4636"
      />
    </u-radio-group>
  </view>
</template>

<script>
/**
 * 岁记 · 单选框（uview-plus u-radio 封装，easycom 自动注册）
 * 对齐 v2 设计稿 components.html L248-262（开关/复选/单选区）+ styles.css L746-750
 * （.cu-radio，px×2→rpx）：圆环 40rpx（size=20px）、边框 4rpx --sj-faint(#C7B6A8)、
 * 选中 = 描边切主色 + 内点 20rpx 弹性放大（spring），label 26rpx(13px) 特粗 ink(#5B4636)、图文间距 14rpx。
 * 库选中态默认「填充底 + 白色勾」与设计稿不符，经 .sj-rd 命名空间 !important 覆盖为
 * 透明底 + primary 描边 + ::after 内点（勾图标隐藏），内点色走 var(--sj-primary) 随页面换肤。
 * activeColor 仅影响库内联描边/底色基线，真正描边色由 CSS 令牌覆盖；
 * faint/ink 双主题相同直接写死，primary 需静态传库故取 palette。
 * 受控用法：父级把同一 modelValue 分发给整组 sj-radio，点击仅 emit，由父级更新。
 * 用法：<sj-radio v-model="feed" name="母乳" label="母乳" />
 */
import { palette } from '@/theme/theme.js'

export default {
  name: 'SjRadio',
  props: {
    /* 当前选中值（受控，v3 v-model；与 name 相同时本项选中） */
    modelValue: { type: [String, Number], default: '' },
    /* 本选项的值 */
    name: { type: [String, Number], default: '' },
    /* 文案，可空（空时页面自行排文字） */
    label: { type: String, default: '' },
    /* 禁用（库拦截点击并弱化样式） */
    disabled: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    /* 选中描边基线色取当前主题 primary（库 props 只接受静态色值，随换肤更新） */
    activeColor() {
      return palette(this.__theme)['primary']
    }
  },
  methods: {
    /* 内部 group 的 change 载荷即被选中项的 name，透传两个事件 */
    onChange(name) {
      this.$emit('update:modelValue', name)
      this.$emit('change', name)
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：不破坏页面 flex 布局 */
.sj-rd {
  display: inline-flex;
  align-items: center;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-rd 命名空间覆盖 u-radio 内部类 ============ */
.sj-rd {
  /* 去库默认上下外边距 */
  .u-radio {
    margin: 0 !important;
  }
  /* 圆环：v2 边框 2px→4rpx（库默认 1px）；底色透明露出页面背景（库内联涂白/主色） */
  .u-radio__icon-wrap {
    border-width: 4rpx !important;
    background-color: transparent !important;
    margin-right: 14rpx !important;
  }
  /* 选中：描边切主色（覆盖库内联 activeColor 基线） */
  .u-radio__icon-wrap--checked {
    border-color: var(--sj-primary) !important;
  }
  /* 隐藏库默认白色勾图标，改用 ::after 内点呈现 v2 观感 */
  .u-radio__icon-wrap__icon {
    display: none !important;
  }
  /* 内点：v2 .cu-radio i::after —— 20rpx 主色圆点，scale 0→1 弹性放大（spring） */
  .u-radio__icon-wrap::after {
    content: "";
    width: 20rpx;
    height: 20rpx;
    border-radius: 50%;
    background: var(--sj-primary);
    transform: scale(0);
    transition: transform 0.25s cubic-bezier(.34,1.56,.64,1);
  }
  .u-radio__icon-wrap--checked::after {
    transform: scale(1);
  }
  /* label：ink 特粗（颜色/字号已由 props 传入，字重库未提供 prop） */
  .u-radio__text {
    font-weight: 800 !important;
  }
  /* 无 label 时去掉圆环右间距，避免空文本节点撑出缝隙 */
  &--bare .u-radio__icon-wrap {
    margin-right: 0 !important;
  }
}
</style>
