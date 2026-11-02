<template>
  <view
    class="sj-cell"
    :class="{ 'is-danger': danger, 'is-disabled': disabled }"
    :hover-class="hoverable ? 'hover-press' : ''"
    :hover-stay-time="80"
    @click="onTap"
  >
    <!-- 图标位：sj-icon 主题 PNG（34px→68rpx、r10→20rpx、cream 底 + 3px→6rpx 内衬，v2 .cu-cell img） -->
    <view v-if="icon" class="sj-cell-ic">
      <sj-icon :name="icon" :size="56" />
      <sj-badge v-if="badge || badgeDot" :value="badge" :dot="badgeDot" />
    </view>
    <slot name="icon" />

    <view class="sj-cell-tt">
      <slot>
        <text class="sj-cell-tx" :class="{ 'tx-danger': danger }">{{ title }}</text>
      </slot>
      <text v-if="desc" class="sj-cell-desc">{{ desc }}</text>
    </view>

    <!-- 右值：sub 12px→24rpx/600（v2 .cu-cell .v）；danger 值走 bad 色 -->
    <view v-if="value || $slots.value" class="sj-cell-v" :class="{ 'v-danger': dangerValue }">
      <slot name="value">
        <text>{{ value }}</text>
      </slot>
    </view>

    <slot name="right" />
    <sj-tag v-if="tag" :text="tag" :variant="tagVariant" class="sj-cell-tag" />
    <sj-switch v-if="showSwitch" :checked="checked" :disabled="disabled" @change="v => $emit('update:checked', v)" />

    <image v-if="arrow" class="sj-cell-chev" src="/static/icons/chevron-right.svg" />
  </view>
</template>

<script>
/**
 * 岁记 · 单元格（easycom 自动注册 <sj-cell>，对齐 v2「单元格列表」卡 .cu-cell，设置流主力控件）
 * 结构：图标块 + 标题/副标 + 右值 / sj-tag / 开关 / 徽标 / 箭头；danger 项标题红字。
 * 点击：hover 按压缩放 + emit click；url 传入时自动 uni.navigateTo（isTab 走 switchTab）。
 * 色值全部 var(--sj-*)，随 bear/duck 换肤。
 * 用法：<sj-cell icon="29-fn-babies" title="宝宝档案" value="安安 · 8月12天" url="/pages/baby/baby" />
 *       <sj-cell icon="30-fn-elder" title="长辈模式" showSwitch v-model:checked="elderOn" />
 *       <sj-cell icon="27-fn-trash" title="删除全部本地数据" value="演示二次确认" danger arrow />
 */
export default {
  name: 'SjCell',
  props: {
    /* 主题图标名（static/icons/{theme}/{icon}.png，如 '29-fn-babies'）；也可用 #icon 插槽 */
    icon: { type: String, default: '' },
    title: { type: String, default: '' },
    /* 标题下副标（可选） */
    desc: { type: String, default: '' },
    /* 右侧值文案；也可用 #value 插槽放任意节点 */
    value: { type: String, default: '' },
    /* 右值是否红色（如「3 条待清理」） */
    dangerValue: { type: Boolean, default: false },
    /* 危险项：标题 bad 色 */
    danger: { type: Boolean, default: false },
    /* 右侧 sj-tag（如云端备份「正常」）与其变体 */
    tag: { type: String, default: '' },
    tagVariant: { type: String, default: 'ok' },
    /* 右侧开关（v-model:checked） */
    showSwitch: { type: Boolean, default: false },
    checked: { type: Boolean, default: false },
    /* 图标右上角徽标 */
    badge: { type: [Number, String], default: 0 },
    badgeDot: { type: Boolean, default: false },
    arrow: { type: Boolean, default: true },
    disabled: { type: Boolean, default: false },
    /* 点击后跳转地址（tabBar 页配 isTab） */
    url: { type: String, default: '' },
    isTab: { type: Boolean, default: false }
  },
  emits: ['click', 'update:checked'],
  computed: {
    hoverable() {
      return !this.disabled
    }
  },
  methods: {
    onTap() {
      if (this.disabled) return
      this.$emit('click')
      if (!this.url) return
      if (this.isTab) uni.switchTab({ url: this.url })
      else uni.navigateTo({ url: this.url })
    }
  }
}
</script>

<style lang="scss" scoped>
/* v2 .cu-cell：#fff 底、1px line 描边、r16→32rpx、padding 12/14px→24/28rpx、13.5px→27rpx/700 */
.sj-cell {
  display: flex;
  align-items: center;
  gap: 24rpx;
  width: 100%;
  box-sizing: border-box;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: 32rpx;
  padding: 24rpx 28rpx;
}
.sj-cell-ic {
  position: relative;
  flex: none;
  width: 68rpx;
  height: 68rpx;
  border-radius: 20rpx;
  background: var(--sj-cream);
  padding: 6rpx;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* 图标图片圆角与外圈曲线平行（同心）：外半径 20 - 内边距 6 = 14rpx */
.sj-cell-ic .sj-icon { border-radius: 14rpx; }
.sj-cell-tt {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}
.sj-cell-tx {
  font-size: 27rpx;
  font-weight: 700;
  color: var(--sj-ink);
}
.tx-danger {
  color: var(--sj-bad);
  font-weight: 900;
}
.sj-cell-desc {
  margin-top: 4rpx;
  font-size: 22rpx;
  color: var(--sj-faint);
  font-weight: 600;
}
/* 右值：v2 .cu-cell .v sub 12px→24rpx/600（右对齐由标题容器 flex:1 保证） */
.sj-cell-v {
  display: flex;
  align-items: center;
}
.sj-cell-v text {
  font-size: 24rpx;
  font-weight: 600;
  color: var(--sj-sub);
}
.v-danger text {
  color: var(--sj-bad);
}
.sj-cell-chev {
  width: 32rpx;
  height: 32rpx;
  flex: none;
}
.sj-cell.is-disabled {
  opacity: 0.5;
}
</style>
