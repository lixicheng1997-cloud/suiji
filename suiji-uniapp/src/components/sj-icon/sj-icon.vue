<template>
  <image
    class="sj-icon"
    :src="src"
    :style="sizeStyle"
    mode="aspectFit"
  />
</template>

<script>
/**
 * 岁记 · 主题图标（easycom 自动注册 <sj-icon>）
 * 按当前主题解析 v2 图标库：/static/icons/{bear|duck}/{name}.png
 * name 取 mock.js TYPES[].png（如 '01-feeding'）或 fn/tab 图标名（如 '20-fn-diary'）。
 * theme 可显式覆盖，默认跟随全局主题混入的 __theme。
 * 注意：PNG 为彩色绘本图标，不可用 color 重染；描边类单色图标仍走旧 SVG。
 */
export default {
  name: 'SjIcon',
  props: {
    name: { type: String, required: true },
    size: { type: [Number, String], default: 48 },
    theme: { type: String, default: '' }
  },
  computed: {
    resolvedTheme() {
      return this.theme || this.__theme || 'bear'
    },
    src() {
      return `/static/icons/${this.resolvedTheme}/${this.name}.png`
    },
    sizeStyle() {
      const s = typeof this.size === 'number' ? this.size + 'rpx' : this.size
      return { width: s, height: s }
    }
  }
}
</script>

<style lang="scss" scoped>
.sj-icon {
  display: block;
  flex: none;
}
</style>
