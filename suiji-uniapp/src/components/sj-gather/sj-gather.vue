<!--
  sj-gather · 正在为你采集成长好物的 IP 吉祥物（easycom 自动注册 <sj-gather>）
  用途：全屏加载/获取动画（splash 等）。星星、爱心、闪光依次飘落接取，竹篮随接收弹动，
  围巾飘动 + 眨眼 + 闪光点缀；2.4s 无缝循环。
  配色与 v2 图标库一致：奶白小熊 + 薄荷绿围巾 / 雪白小鸭 + 天蓝围巾，深棕统一细描边。
  安卓适配：App 端不支持内联 <svg>，图形走 <image> + 静态 SVG 文件（动画内置于文件）。
-->
<template>
  <view class="sj-gather" :style="boxStyle">
    <image class="gt-img" :src="src" mode="aspectFit" />
  </view>
</template>

<script>
/* 与 splash 的 faceSrc 相同的主题解析方式：props.theme 优先，否则跟随全局 __theme */
export default {
  name: 'SjGather',
  props: {
    size: { type: [Number, String], default: 240 },
    theme: { type: String, default: '' }
  },
  computed: {
    src() {
      const t = (this.theme || this.__theme || 'bear') === 'duck' ? 'duck' : 'bear'
      return `/static/anim/${t}-gather.svg`
    },
    boxStyle() {
      const s = typeof this.size === 'number' ? this.size + 'rpx' : this.size
      return { width: s, height: s }
    }
  }
}
</script>

<style scoped>
.sj-gather { display: inline-block; }
.gt-img { width: 100%; height: 100%; }
</style>
