<template>
  <view class="sj-ta">
    <!-- 输入行为交给 uview-plus u-textarea（count 默认关闭，页面已有文案时不显计数） -->
    <u-textarea
      :modelValue="modelValue"
      :placeholder="placeholder"
      :maxlength="maxlength"
      :height="height"
      :autoHeight="height === 'auto'"
      placeholderStyle="color: #C7B6A8; font-weight: 600;"
      @update:modelValue="onInput"
    />
    <!-- 清除钮：ctl-v2 48-ctl-clear 去底切图（48rpx），浮于右上角，clearable 且有内容时出现 -->
    <image
      v-if="clearable && modelValue"
      class="ta-clear"
      :src="clearSrc"
      mode="aspectFit"
      @click="onClear"
    />
  </view>
</template>

<script>
/**
 * 岁记 · 多行备注框（uview-plus u-textarea 封装，easycom 自动注册）
 * 外观严格对齐 v2 .pg-field 表单域 tokens（styles.css L569-573，px×2→rpx）：
 * 毛玻璃底 --sj-glass（半透 + 模糊 + 内高光）+ 半透高光描边 + 圆角 14px→28rpx + 内边距 10px/14px→20rpx 28rpx
 * + 字号 13.5px→27rpx 字色 ink（经 .sj-ta 命名空间全局覆盖库 scoped 默认值）、
 * 占位 faint 字重 600（placeholderStyle 内联传入）。
 * height 传 'auto' 时自动增高（库 autoHeight），也可传带单位字符串如 '200rpx'。
 * clearable：有内容时右上角浮出 ctl-v2 清除切图（48-ctl-clear，48rpx，
 * scripts/cut-ctl-icons.py 生成到 /static/icons/ctl/{theme}/48/），点击清空并 emit clear。
 * 用法：<sj-textarea v-model="note" placeholder="补充备注…" :maxlength="200" />
 *       <sj-textarea v-model="note" clearable />
 */
export default {
  name: 'SjTextarea',
  props: {
    /* 当前文本（v-model） */
    modelValue: { type: String, default: '' },
    /* 占位文案 */
    placeholder: { type: String, default: '' },
    /* 最大长度（500 与记录备注同口径：足够写满一屏，又挡住能把服务端字段撑爆的量） */
    maxlength: { type: Number, default: 500 },
    /* 高度：'auto' 自动增高，或带单位字符串（如 '200rpx'） */
    height: { type: String, default: 'auto' },
    /* 显示清除钮（有内容时） */
    clearable: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'clear'],
  computed: {
    /* 当前主题下的清除钮切图（彩色绘本图，不走 color 重染） */
    clearSrc() {
      return `/static/icons/ctl/${this.__theme}/48/48-ctl-clear.png`
    }
  },
  methods: {
    /* u-textarea 的 update:modelValue 载荷即字符串值，直接透传 */
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
/* 外层包裹：占满父宽度；为清除钮浮层提供定位参照 */
.sj-ta {
  position: relative;
  width: 100%;
}
/* 清除钮切图（48rpx，浮于表单域右上角，切图自带约 11% 留白） */
.ta-clear {
  position: absolute;
  top: 16rpx;
  right: 20rpx;
  width: 48rpx;
  height: 48rpx;
  z-index: 1;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-ta 命名空间覆盖 u-textarea 内部节点 ============
 * 库 scoped 默认：4px 圆角 / 9px 内边距 / --up-content-color 字色，均压成 v2 观感。 */
.sj-ta {
  /* 容器：v2 .pg-field 表单域 —— 毛玻璃底 + 半透高光描边 + 28rpx 圆角 + 20rpx/28rpx 内边距 */
  .u-textarea {
    background: var(--sj-glass) !important;
    border: 2rpx solid var(--sj-glass-line) !important;
    border-radius: 28rpx !important;
    box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
    padding: 20rpx 28rpx !important;
  }
  /* 输入文字：v2 表单域 27rpx ink（库默认 15px） */
  .u-textarea__field {
    color: var(--sj-ink) !important;
    font-size: 27rpx !important;
  }
}
</style>
