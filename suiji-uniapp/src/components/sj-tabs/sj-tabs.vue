<template>
  <view class="sj-tb">
    <!-- 交互内核交给 uview-plus u-tabs（滑块测位/滚动居中/点击切换由库保证） -->
    <u-tabs
      :list="tabList"
      :current="modelValue"
      :scrollable="scrollable"
      :lineColor="lineColor"
      :lineWidth="lineWidth"
      :lineHeight="lineHeight"
      :activeStyle="activeStyle"
      :inactiveStyle="inactiveStyle"
      :itemStyle="itemStyle"
      :duration="300"
      @change="onChange"
    />
  </view>
</template>

<script>
/**
 * 岁记 · 选项卡（uview-plus u-tabs 封装，easycom 自动注册）
 * 外观严格对齐 v2 .cu-tabs（components.html L409-420「选项卡：下划线弹性入场」；
 * styles.css L756-759，px×2→rpx）：字号 13.5px→27rpx 全项字重 800；
 * 未选中 --sj-sub(#9C8878)、选中 --sj-primary-deep（设计稿 .on 即主色深字，随主题换肤）；
 * 下划线 --sj-primary、高 3.5px→7rpx、圆角 4rpx，位移缓动改走 --sj-spring 弹性曲线
 * （库 line 内联仅控制 duration，timing-function 经命名空间 CSS 覆盖）。
 * items 传字符串数组，内部映射为库 list（keyName=name）；受控用法：父更新 modelValue 即移动滑块。
 * 用法：<sj-tabs :items="['体重','身高','头围']" v-model="tabIdx" @change="i => ..." />
 */
import { palette } from '@/theme/theme.js'

export default {
  name: 'SjTabs',
  props: {
    /* 标签文案数组（字符串数组） */
    items: { type: Array, default: () => [] },
    /* 当前下标（受控，v-model） */
    modelValue: { type: Number, default: 0 },
    /* 是否可横向滚动（默认等分不滚动） */
    scrollable: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    /* 库 list 约定对象数组，keyName 默认 name */
    tabList() {
      return (this.items || []).map(name => ({ name }))
    },
    /* 下划线主色随主题换肤（库 props 只接受静态色值） */
    lineColor() {
      return palette(this.__theme)['primary']
    },
    /* 选中字色 = 设计稿 .on 的 primary-deep */
    activeStyle() {
      return { color: palette(this.__theme)['primary-deep'] }
    },
    /* 未选中字色 = --sj-sub（双主题相同） */
    inactiveStyle() {
      return { color: '#9C8878' }
    },
    /* 下划线宽：库为全局定值（v2 为条目宽 70%，无法逐条命中，取折中定值 40rpx） */
    lineWidth() {
      return '40rpx'
    },
    /* 下划线高：v2 3.5px → 7rpx */
    lineHeight() {
      return '7rpx'
    },
    /* 条目内距：v2 padding 8px 2px + gap 18px 合并为左右 18rpx 内距
     * （用 padding 而非 margin，保证库按 rect 宽测位的下划线不错位） */
    itemStyle() {
      return { height: 'auto', padding: '16rpx 18rpx' }
    }
  },
  methods: {
    /* 库 change 载荷 ({...item, index}, index)，对外只抛下标 */
    onChange(item, index) {
      this.$emit('update:modelValue', index)
      this.$emit('change', index)
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：不破坏页面 flex 布局 */
.sj-tb {
  display: block;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-tb 命名空间覆盖 u-tabs 内部节点 ============
 * 对齐 v2 .cu-tabs（styles.css L756-759）；色值走 var(--sj-*) 令牌随换肤。 */
.sj-tb {
  /* 底部 1.5px→3rpx 分隔线（v2 border-bottom: 1.5px solid var(--line)） */
  .u-tabs {
    border-bottom: 3rpx solid var(--sj-line);
  }
  /* 左对齐排列：非滚动下库内联 flex:1 等分，改 flex:none 贴左（v2 为 gap 左排布） */
  .u-tabs__wrapper__nav {
    display: flex;
    justify-content: flex-start;
  }
  .u-tabs__wrapper__nav__item {
    flex: none !important;
  }
  /* 文案：v2 全项 13.5px/800 */
  .u-tabs__wrapper__nav__item__text {
    font-size: 27rpx;
    font-weight: 800;
  }
  /* 下划线：圆角 2px→4rpx；位移缓动对齐 v2 弹性曲线（scrIn/smooth 族） */
  .u-tabs__wrapper__nav__line {
    border-radius: 4rpx;
    transition-timing-function: var(--sj-spring) !important;
  }
}
</style>
