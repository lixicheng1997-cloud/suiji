<template>
  <!-- v2 .cu-avgrp：flex 行，子头像带 overlap 左叠 -24rpx；more 在末尾追加「+N」计数位 -->
  <view class="sj-avgrp">
    <slot />
    <view v-if="moreNum > 0" class="sj-av-more is-overlap" :style="boxStyle">
      <text>+{{ more }}</text>
    </view>
  </view>
</template>

<script>
/**
 * 岁记 · 头像重叠组（easycom 自动注册 <sj-avatar-group>，对齐 v2 .cu-avgrp）
 * 家庭空间成员展示：默认插槽放若干 <sj-avatar overlap>，相邻重叠 -24rpx
 * （重叠由 sj-avatar 的 overlap prop 自管——MP 端 scoped 样式选不到子组件根，勿在此处隔层控制）；
 * more 传数字在末尾追加「+N」灰底计数位（自带重叠）。
 * 用法：<sj-avatar-group :more="2">
 *         <sj-avatar icon="29-fn-babies" themed overlap />
 *         <sj-avatar icon="13-tab-me" themed ring="g2" overlap />
 *         <sj-avatar icon="28-fn-invite" themed ring="g3" overlap />
 *       </sj-avatar-group>
 */
export default {
  name: 'SjAvatarGroup',
  props: {
    /* 末尾「+N」计数，0/空则不显示 */
    more: { type: [Number, String], default: 0 },
    /* 与子头像同尺寸（rpx），保证计数位对齐 */
    size: { type: [Number, String], default: 88 }
  },
  computed: {
    moreNum() {
      return Number(this.more) || 0
    },
    boxStyle() {
      const s = (typeof this.size === 'number' ? this.size : Number(this.size) || 88) + 'rpx'
      return { width: s, height: s }
    }
  }
}
</script>

<style lang="scss" scoped>
.sj-avgrp {
  display: flex;
  align-items: center;
}
/* 「+N」计数位：v2 组内末位用 line 底 + sub 字；.is-overlap 与 sj-avatar 同名规则重叠 -24rpx */
.sj-av-more {
  flex: none;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--sj-r-pill);
  background: var(--sj-line);
  border: 4rpx solid var(--sj-white);
  z-index: 1;
}
.sj-av-more.is-overlap {
  margin-left: -24rpx;
}
.sj-av-more text {
  font-size: 24rpx;
  font-weight: 900;
  color: var(--sj-sub);
  line-height: 1;
}
</style>
