<template>
  <!-- v2 components.html「步骤条」卡 .cu-steps：等分节点 + 连线；
       MP 端伪元素拿不到动态色，连线走真实 <view>（同 onboard .pg-step 惯例） -->
  <view class="sj-steps">
    <view v-for="(item, i) in items" :key="i" class="sj-sp-node" hover-class="hover-press" :hover-stay-time="80" @click="$emit('click', i)">
      <view class="sj-sp-wire" :class="{ 'is-first': i === 0, 'wire-done': i <= current }" />
      <view class="sj-sp-st" :class="{ done: i < current, now: i === current }">
        <text>{{ i < current ? '✓' : i + 1 }}</text>
      </view>
      <text class="sj-sp-lb" :class="{ 'lb-now': i === current }">{{ labelOf(item) }}</text>
    </view>
  </view>
</template>

<script>
/**
 * 岁记 · 步骤条（easycom 自动注册 <sj-steps>，对齐 v2「步骤条」卡 .cu-steps 与引导流 P06）
 * current 为 0 基当前步索引：之前 = done（绿圆白✓、连线绿）、当前 = now（主色 + 呼吸光晕）、
 * 之后 = 未到（白底 line 描边、faint 数字）。items 支持字符串数组或 { title } 对象数组。
 * 色值全部 var(--sj-*)，随 bear/duck 换肤。
 * 用法：<sj-steps :current="step" :items="['创建家庭', '监护人同意', '宝宝信息', '开始记录']" />
 */
export default {
  name: 'SjSteps',
  props: {
    /* 步骤文案数组（String 或 { title }） */
    items: { type: Array, default: () => [] },
    /* 0 基当前步索引 */
    current: { type: Number, default: 0 }
  },
  methods: {
    labelOf(item) {
      return item && typeof item === 'object' ? String(item.title ?? '') : String(item ?? '')
    }
  }
}
</script>

<style lang="scss" scoped>
.sj-steps {
  display: flex;
  align-items: flex-start;
}
.sj-sp-node {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}
/* 连线：v2 .sp-node::before top 13px、2px→4rpx；覆盖前一节点到当前节点段 */
.sj-sp-wire {
  position: absolute;
  top: 26rpx;
  left: -50%;
  width: 100%;
  height: 4rpx;
  border-radius: 4rpx;
  background: var(--sj-line);
}
.sj-sp-wire.is-first {
  display: none;
}
.sj-sp-wire.wire-done {
  background: var(--sj-ok);
}
/* 节点圆：v2 .sp-node i 26px→52rpx、12px→24rpx/900 */
.sj-sp-st {
  position: relative;
  z-index: 2;
  width: 52rpx;
  height: 52rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--sj-surface);
  border: 4rpx solid var(--sj-line);
  box-sizing: border-box;
  transition: all 0.25s var(--sj-smooth);
}
.sj-sp-st text {
  font-size: 24rpx;
  font-weight: 900;
  color: var(--sj-faint);
  line-height: 1;
}
.sj-sp-st.done {
  background: var(--sj-ok);
  border-color: var(--sj-ok);
}
.sj-sp-st.done text {
  color: #fff;
}
.sj-sp-st.now {
  background: var(--sj-primary);
  border-color: var(--sj-primary);
  animation: sj-sp-glow 2s infinite;
}
.sj-sp-st.now text {
  color: #fff;
}
/* 标签：v2 .sp-node em 10.5px→21rpx/800 sub；当前步 ink 强调 */
.sj-sp-lb {
  margin-top: 10rpx;
  font-size: 21rpx;
  font-weight: 800;
  color: var(--sj-sub);
  text-align: center;
}
.sj-sp-lb.lb-now {
  color: var(--sj-ink);
}
/* 当前步呼吸光晕（v2 glow：主色扩散环） */
@keyframes sj-sp-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(247, 161, 92, 0.4); }
  50% { box-shadow: 0 0 0 12rpx rgba(247, 161, 92, 0); }
}
</style>

