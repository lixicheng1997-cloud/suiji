<template>
  <image v-if="src" class="sj-weather" :src="src" :style="sizeStyle" mode="aspectFit" />
</template>

<script>
/**
 * 岁记 · 天气卡通动效（easycom 自动注册 <sj-weather>）
 * 按服务端返回的中文天气描述，渲染对应内置 CSS 动画的 SVG（/static/anim/weather-*.svg）。
 * App 端不支持内联 <svg>，统一用 <image> 引用 SVG 文件，动画内置于文件 <style>。
 * text 为空时不渲染（父级可用 v-if 控制整段天气位显隐）。
 */
export default {
  name: 'SjWeather',
  props: {
    /* 服务端中文天气描述，如「晴」「小雨」「雷阵雨」「小雪」「雨夹雪」 */
    text: { type: String, default: '' },
    size: { type: [Number, String], default: 88 }
  },
  computed: {
    /* 中文描述 → 天气类型；判定顺序需先于宽泛词（雷阵雨→雷、雨夹雪→雪/雨） */
    type() {
      const t = String(this.text || '')
      if (!t) return ''
      if (t.includes('雷')) return 'thunder'
      if (t.includes('雨夹雪')) return 'sleet'
      if (t.includes('雪') || t.includes('冰粒')) return 'snow'
      if (t.includes('沙尘') || t.includes('尘')) return 'dust'
      if (t.includes('雾') || t.includes('霾')) return 'fog'
      if (t.includes('雨')) return 'rain'
      if (t.includes('多云')) return 'partly'
      if (t.includes('阴')) return 'cloudy'
      if (t.includes('晴')) return 'sun'
      return 'partly'
    },
    src() {
      return this.type ? `/static/anim/weather-${this.type}.svg` : ''
    },
    sizeStyle() {
      const s = typeof this.size === 'number' ? this.size + 'rpx' : this.size
      return { width: s, height: s }
    }
  }
}
</script>

<style lang="scss" scoped>
.sj-weather { display: inline-block; flex: none; }
</style>
