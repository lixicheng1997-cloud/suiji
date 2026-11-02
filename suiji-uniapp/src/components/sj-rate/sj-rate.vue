<template>
  <view class="sj-rt" :class="{ 'sj-rt--pop': popping }">
    <!-- 交互行为交给 uview-plus u-rate（v3 API：:modelValue + @change/@update:modelValue） -->
    <u-rate
      :modelValue="modelValue"
      :count="count"
      :size="size"
      :disabled="disabled"
      :minCount="0"
      :gutter="5"
      activeIcon="heart-fill"
      inactiveIcon="heart"
      activeColor="#FF8FAB"
      inactiveColor="#F3E4D3"
      @change="onChange"
      @update:modelValue="onInput"
    />
  </view>
</template>

<script>
/**
 * 岁记 · 爱心评分（uview-plus u-rate 封装，easycom 自动注册）
 * 对齐 v2 设计稿 components.html L295-312（评分区）+ styles.css L740-743（.cu-rate，px×2→rpx）：
 * 心形图标 44rpx（size=22px）、间距 10rpx（gutter=5px）、
 * 选中 --sj-blush(#FF8FAB)、未选中 --sj-line(#F3E4D3)（双主题同色，直接写死经 props 传入）。
 * 心形选型：u-rate 的 activeIcon/inactiveIcon 支持 uview 内置图标，
 * 库内恰有 heart-fill / heart 心形（u-icon/icons.js），无需 CSS mask 退而求其次。
 * 点击弹性放大：值变化时给根节点挂 .sj-rt--pop，经命名空间命中 .uicon-heart-fill
 * 播放 sj-rt-pop（scale+微倾斜，对齐 .cu-rate hover scale(1.25) rotate(-8deg) 与 spring 缓动）。
 * minCount=0 放开库默认最少 1 星限制，允许 modelValue 默认 0（未评分）。
 * 用法：<sj-rate v-model="score" :count="5" @change="score = $event" />
 */
export default {
  name: 'SjRate',
  props: {
    /* 当前评分（受控，v3 v-model） */
    modelValue: { type: Number, default: 0 },
    /* 最多可选心形数量 */
    count: { type: Number, default: 5 },
    /* 图标大小，单位 px（对齐 v2 22px→44rpx） */
    size: { type: Number, default: 22 },
    /* 禁用（库拦截点击并弱化颜色） */
    disabled: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change'],
  data() {
    return {
      /* 弹性动画开关：值变化后短暂挂起，动画结束自动摘除以便下次重触发 */
      popping: false,
      popTimer: null
    }
  },
  beforeUnmount() {
    if (this.popTimer) clearTimeout(this.popTimer)
  },
  methods: {
    /* u-rate 内部已做归一化，change 载荷即新评分，透传并触发弹性动画 */
    onChange(val) {
      this.$emit('change', val)
      this.startPop()
    },
    /* 双向绑定值透传给父级 */
    onInput(val) {
      this.$emit('update:modelValue', val)
    },
    /* 重触发选中爱心的弹性放大动画 */
    startPop() {
      this.popping = false
      if (this.popTimer) clearTimeout(this.popTimer)
      // 先移除再加回，确保连续点击时动画可重复播放
      this.$nextTick(() => {
        this.popping = true
        this.popTimer = setTimeout(() => { this.popping = false }, 350)
      })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：不破坏页面 flex 布局 */
.sj-rt {
  display: inline-flex;
  align-items: center;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-rt 命名空间覆盖 u-rate 内部类 ============ */
.sj-rt {
  /* 去库默认外边距，交由页面布局控制 */
  .u-rate {
    margin: 0;
  }
  /* 颜色切换过渡 .2s（对齐 .cu-rate svg transition fill .2s） */
  .u-icon__icon {
    transition: color 0.2s;
  }
}
/* 点击弹性：仅已选中的实心爱心播放（scale+微倾斜，对齐 .cu-rate hover 观感） */
.sj-rt--pop .uicon-heart-fill {
  animation: sj-rt-pop 0.3s cubic-bezier(.34,1.56,.64,1);
}
@keyframes sj-rt-pop {
  0% { transform: scale(1) rotate(0deg); }
  40% { transform: scale(1.3) rotate(-8deg); }
  100% { transform: scale(1) rotate(0deg); }
}
</style>
