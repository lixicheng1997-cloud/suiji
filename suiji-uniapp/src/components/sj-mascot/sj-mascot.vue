<template>
  <image class="sj-mascot" :src="src" :style="boxStyle" mode="aspectFit" />
</template>

<script>
/**
 * 岁记 · IP 吉祥物（easycom 自动注册 <sj-mascot>）
 * 按主题渲染小熊/小鸭，含呼吸浮动 + 眨眼动画。
 * 说明：App 端（安卓）不支持内联 <svg> 标签，统一改用 <image> 引用
 *       static/anim/{bear|duck}-face.svg（动画内置于 SVG 文件 <style>，
 *       webview 的 img 渲染可正常播放）。
 */
export default {
  name: 'SjMascot',
  props: {
    size: { type: [Number, String], default: 240 },
    theme: { type: String, default: '' }
  },
  computed: {
    resolvedTheme() {
      return this.theme || this.__theme || 'bear'
    },
    src() {
      const t = this.resolvedTheme === 'duck' ? 'duck' : 'bear'
      return `/static/anim/${t}-face.svg`
    },
    boxStyle() {
      const s = typeof this.size === 'number' ? this.size + 'rpx' : this.size
      return { width: s, height: s }
    }
  }
}
</script>

<style lang="scss" scoped>
.sj-mascot { display: inline-block; flex: none; }
</style>
