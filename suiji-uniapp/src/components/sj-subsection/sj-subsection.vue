<template>
  <view class="sj-ss">
    <!-- 交互行为交给 uview-plus u-subsection（v3 API：:current 下标受控 + @change(下标)，
         点击/滑块位移/禁用拦截由库保证） -->
    <u-subsection
      :list="options"
      :current="modelValue"
      mode="button"
      activeColor="#FFFFFF"
      inactiveColor="#9C8878"
      bgColor="#FFFFFF"
      :fontSize="13"
      :bold="false"
      :disabled="disabled"
      @change="onChange"
    />
  </view>
</template>

<script>
/**
 * 岁记 · 分段器（uview-plus u-subsection 封装，easycom 自动注册）
 * 对齐 v2 设计稿 components.html L315-325（分段器区）+ styles.css L563-565
 * （.pg-seg，px×2→rpx）：白底胶囊容器 + 2rpx --sj-line 描边 + 8rpx 内衬，
 * 项文字 26rpx(13px) 特粗 --sj-sub(#9C8878)，选中块主色底白字 + 暖橙投影 0 8rpx 24rpx。
 * 选型：用库 mode="button"（滑块式位移），activeColor 传 #FFF 即「选中文字白色」，
 * 滑块本体默认白色经 .sj-ss 命名空间 !important 覆盖为 var(--sj-primary) 主色底 + 胶囊圆角；
 * 注意：这些库内部节点覆盖必须写在 App.vue 的全局样式里——组件 SFC 的「非 scoped 块」在
 * H5 / App 端仍会被编译器追加 [data-v]，而 .u-subsection__bar 等只带库自身作用域，覆盖会全部失效；
 * 动画方案：保留库 translateX 位移，缓动函数覆盖为 cubic-bezier(.34,1.56,.64,1) 弹性收尾；
 * 设计稿 gap:4px（8rpx 项间距）还原：库按 index*item宽 位移、不能给 item 加 margin（累积错位），
 * 改为滑块左右 4rpx 透明边框 + background-clip:padding-box——可见胶囊缩为格宽-8rpx 且居中，
 * 相邻胶囊间隙恰为 8rpx，位移公式不受影响（边框盒仍与格对齐）；
 * 容器改 overflow:visible，使选中块暖橙投影可溢出容器边缘（v2 .pg-seg 无裁剪、投影外露）。
 * sub 色双主题相同写死；primary 走 var(--sj-primary) 令牌随页面换肤。
 * 用法：<sj-subsection v-model="tab" :options="['日','周','月','全部']" />
 */
export default {
  name: 'SjSubsection',
  props: {
    /* 当前选中下标（受控，v3 v-model） */
    modelValue: { type: Number, default: 0 },
    /* 选项文案数组（字符串数组；库亦支持对象数组但本封装按契约仅字符串） */
    options: { type: Array, default: () => [] },
    /* 禁用（库拦截点击并弱化文字色） */
    disabled: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change'],
  methods: {
    /* u-subsection 的 change 载荷即新选中下标，透传两个事件 */
    onChange(index) {
      this.$emit('update:modelValue', index)
      this.$emit('change', index)
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：库根节点自带 width:100%，此处仅做命名空间挂载 */
.sj-ss {
  display: block;
}
</style>

