<template>
  <view class="sj-bt" :class="['sj-bt--' + variant, size === 'lg' ? 'sj-bt--lg' : '', block ? 'sj-bt--block' : '']" @touchstart="onRipple" @click="onRipple">
    <!-- 交互内核交给 uview-plus u-button（点击节流/loading/disabled 拦截由库保证） -->
    <u-button
      :text="text"
      shape="circle"
      :size="size === 'mini' ? 'mini' : 'normal'"
      :loading="loading"
      :disabled="disabled"
      :hairline="false"
      type="info"
      :color="solidColor"
      :customStyle="btnCustomStyle"
      @click="onClick"
    >
      <!-- 文字恒由本组件渲染（loading 时让库的 spinner + 文案分支独占）：
           小程序端插槽名是编译期静态声明的，库的 $slots.default 恒为真、
           会丢掉自带 <text> 兜底，故不能只在带 icon 时才提供插槽内容 -->
      <template v-if="!loading" #default>
        <view class="bt-ico">
          <image v-if="ctlSrc" class="bt-img" :src="ctlSrc" mode="aspectFit" />
          <text class="u-button__text" :style="txtStyle">{{ text }}</text>
        </view>
      </template>
    </u-button>
    <!-- 按压波纹层：盖在按钮上方的纯装饰层，pointer-events:none 不吃事件 -->
    <view class="sj-rip-layer">
      <view
        v-for="r in ripples"
        :key="r.id"
        class="sj-rip"
        :style="{ left: r.x + 'px', top: r.y + 'px', width: r.d + 'px', height: r.d + 'px', background: rippleColor }"
      />
    </view>
  </view>
</template>

<script>
/**
 * 岁记 · 按钮（uview-plus u-button 封装，easycom 自动注册）
 * 外观严格对齐 v2 .cu-btn（components.html L118-140「按钮」六变体；styles.css L683-697，px×2→rpx）：
 * 胶囊圆角（shape=circle）、字重 800、normal 13.5px→27rpx / mini 11.5px→23rpx、
 * primary = 145deg 主色渐变（palette primary→primary-deep，随主题换肤）+ 暖橙投影、
 * danger = 珊瑚红渐变 #EF7A7A→#D95A5A；plain 白底主色描边深字 / light 主色浅底 /
 * ghost 白底线描边 sub 字 / text 无底 primary-deep 字；按压弹性 scale(.94) 走 --sj-spring。
 * 库 color prop 仅接受完整 linear-gradient(...) 字符串（源码以 indexOf('gradient') 识别并写 backgroundImage），
 * 故主色渐变经 palette 两色拼成渐变串传入；plain/light/ghost/text 走 type=info + 命名空间 CSS 覆盖。
 * icon：传 ctl-v2 切图名（如 '40-ctl-btn-confirm' / '41-ctl-btn-add'）时文字前置 48rpx 角色切图，
 * scripts/cut-ctl-icons.py 生成到 /static/icons/ctl/{theme}/48/，随主题换肤。
 * 用法：<sj-button text="保存" @click="save" />
 *       <sj-button text="确认" icon="40-ctl-btn-confirm" @click="save" />
 *       <sj-button variant="danger" size="mini" :loading="busy" text="删除" @click="del" />
 *       <sj-button block variant="plain" text="描边通栏" @click="x" />
 */
import { palette } from '@/theme/theme.js'

/* 波纹圆点自增 id（模块级，避免同一毫秒连点撞 key） */
let rippleSeq = 0

export default {
  name: 'SjButton',
  props: {
    /* 按钮文字 */
    text: { type: String, default: '' },
    /* 变体：primary 主色渐变 / plain 描边 / light 浅底 / ghost 中性 / text 文字 / danger 珊瑚红 */
    variant: { type: String, default: 'primary' },
    /* 尺寸：lg 通栏主 CTA（29rpx/900、内距 26rpx）/ normal / mini */
    size: { type: String, default: 'normal' },
    /* 加载中（库自动置灰并显示 spinner） */
    loading: { type: Boolean, default: false },
    /* 禁用 */
    disabled: { type: Boolean, default: false },
    /* 通栏（宽 100%） */
    block: { type: Boolean, default: false },
    /* 前置 ctl-v2 切图名（'' = 无图标） */
    icon: { type: String, default: '' }
  },
  emits: ['click'],
  data() {
    return {
      /* 按压波纹圆点队列（一次点击一枚，动画结束即移除） */
      ripples: []
    }
  },
  computed: {
    /* 实心渐变底用白波纹，浅底/描边底用墨色淡波纹 */
    rippleColor() {
      return this.solidVariant ? 'rgba(255,255,255,.45)' : 'rgba(74,50,38,.14)'
    },
    /* 当前主题下的前置切图路径（彩色绘本图，不走 color 重染） */
    ctlSrc() {
      if (!this.icon) return ''
      return `/static/icons/ctl/${this.__theme}/48/${this.icon}.png`
    },
    /* primary/danger 用库 color 内联渐变，其余变体交给 CSS 覆盖 */
    solidVariant() {
      return this.variant === 'primary' || this.variant === 'danger'
    },
    /* 库只认完整渐变串：primary = 主题两色拼 145deg 渐变；danger = 设计稿固定珊瑚红渐变 */
    solidColor() {
      if (!this.solidVariant) return ''
      if (this.variant === 'danger') return 'linear-gradient(145deg, #EF7A7A, #D95A5A)'
      const p = palette(this.__theme)
      return `linear-gradient(145deg, ${p['primary']}, ${p['primary-deep']})`
    },
    /* 通栏/自适应宽度（customStyle 内联优先于库类样式，行为确定） */
    btnCustomStyle() {
      return { width: this.block ? '100%' : 'auto' }
    },
    /* 自绘文字的颜色/字号：小程序端父组件样式跨不进库组件的插槽作用域，
     * 下方非scoped 的 .sj-bt--x .u-button__text 只在 H5 生效，故内联兜底（色值与 CSS 侧一致）。 */
    txtStyle() {
      const p = palette(this.__theme)
      let color = p['primary-deep']
      if (this.disabled) color = p['faint']
      else if (this.solidVariant) color = p['white']
      else if (this.variant === 'ghost') color = p['sub']
      return {
        color,
        fontSize: (this.size === 'mini' ? '23rpx' : this.size === 'lg' ? '29rpx' : '27rpx')
      }
    }
  },
  methods: {
    /* 库仅在非 disabled/loading 时发 click，直接透传 */
    onClick(e) {
      this.$emit('click', e)
    },
    /* 按压波纹：touchstart 取命中点，生成一枚扩散圆，520ms 动画后自清；
     * 纯 transform/opacity 合成层动画，单点单元素，性能开销可忽略 */
    onRipple(e) {
      if (this.disabled || this.loading) return
      /* 触屏 touchstart 先响：600ms 内忽略其合成 click，避免一次点击双波纹 */
      if (e.type === 'click' && Date.now() - (this._lastTouchAt || 0) < 600) return
      if (e.type === 'touchstart') this._lastTouchAt = Date.now()
      const t = (e.touches && e.touches[0]) || e
      if (!t || t.clientX === undefined) return
      uni.createSelectorQuery().in(this).select('.sj-bt').boundingClientRect(rect => {
        if (!rect) return
        const d = Math.max(rect.width, rect.height) * 1.6
        const id = ++rippleSeq
        this.ripples.push({ id, x: t.clientX - rect.left - d / 2, y: t.clientY - rect.top - d / 2, d })
        setTimeout(() => {
          const i = this.ripples.findIndex(r => r.id === id)
          if (i >= 0) this.ripples.splice(i, 1)
        }, 520)
      }).exec()
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：inline-flex 不破坏页面排布，类名可被页面样式覆盖 */
.sj-bt {
  display: inline-flex;
  align-items: center;
  position: relative;
}
/* 波纹层：胶囊裁剪、盖在按钮上方但不吃事件 */
.sj-rip-layer {
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  border-radius: 999rpx;
  overflow: hidden;
  pointer-events: none;
  z-index: 2;
}
.sj-rip {
  position: absolute;
  border-radius: 50%;
  opacity: 0.7;
  transform: scale(0);
  animation: sj-rip 0.5s ease-out forwards;
}
@keyframes sj-rip {
  to { transform: scale(1); opacity: 0; }
}
.sj-bt--block {
  display: flex;
  width: 100%;
}
/* 带 icon 的自定义插槽内容：切图 + 文字横排居中 */
.bt-ico {
  display: flex;
  align-items: center;
  justify-content: center;
}
.bt-img {
  width: 48rpx;
  height: 48rpx;
  margin-right: 10rpx;
  flex: none;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-bt 命名空间覆盖 u-button 内部节点 ============
 * 对齐 v2 .cu-btn（styles.css L683-697）；色值走 var(--sj-*) 令牌随页面根节点换肤。 */
.sj-bt {
  /* 基础形态：字号/字重/内距（v2 padding 10px 22px → 20rpx 44rpx，font 13.5px → 27rpx） */
  .u-button {
    transition: transform 0.2s var(--sj-spring), box-shadow 0.2s;
  }
  /* 库默认 info 灰描边（#dadbde）在奶油底色上发暗、像一圈黑边：
   * 统一收口为柔和的主题分隔线色；plain/ghost/text/light 等变体规则在后、各自覆盖 */
  .u-button {
    border-color: var(--sj-line) !important;
  }
  .u-button__text,
  .u-button__loading-text {
    font-size: 27rpx !important;
    font-weight: 800;
    line-height: 1.4;
  }
  .u-button {
    padding: 20rpx 44rpx !important;
    height: auto !important;
    min-width: 0 !important;
  }
  /* 按压弹性（v2 .cu-btn:active scale(.94)；库 hover-class 命中 u-button--active） */
  .u-button--active {
    transform: scale(0.94);
    opacity: 1;
  }
  /* mini（v2 padding 6px 14px → 12rpx 28rpx，font 11.5px → 23rpx） */
  .u-button--size-mini {
    padding: 12rpx 28rpx !important;
  }
  .u-button--size-mini .u-button__text,
  .u-button--size-mini .u-button__loading-text {
    font-size: 23rpx !important;
  }
  /* lg（页面原 .pg-btn 主 CTA 规格：内距 26rpx 0、字号 29rpx/900、通栏） */
  &--lg .u-button {
    padding: 26rpx 0 !important;
  }
  &--lg .u-button__text,
  &--lg .u-button__loading-text {
    font-size: 29rpx !important;
    font-weight: 900;
  }
  /* 禁用（v2 .cu-btn.dis：--sj-line 底 + --sj-faint 字，去投影） */
  .u-button--disabled {
    background: var(--sj-line) !important;
    background-image: none !important;
    border-color: var(--sj-line) !important;
    box-shadow: none !important;
    opacity: 1 !important;
  }
  .u-button--disabled .u-button__text {
    color: var(--sj-faint) !important;
  }
  /* primary：暖橙投影（v2 0 6px 14px rgba(224,126,51,.3) → rpx） */
  &--primary .u-button {
    box-shadow: 0 12rpx 28rpx rgba(224, 126, 51, 0.3);
  }
  /* primary/danger 带 icon 插槽：库的白字内联样式只作用于自身文字节点，自定义文字补白字 */
  &--primary .u-button__text,
  &--danger .u-button__text {
    color: #fff !important;
  }
  /* danger：珊瑚红投影（v2 .cu-btn.err） */
  &--danger .u-button {
    box-shadow: 0 12rpx 28rpx rgba(217, 90, 90, 0.3);
  }
  /* plain（v2 .cu-btn.plain：白底 primary-deep 字 + 1.5px→3rpx primary 描边，无投影） */
  &--plain .u-button {
    background: var(--sj-surface) !important;
    border: 3rpx solid var(--sj-primary) !important;
  }
  &--plain .u-button__text,
  &--plain .u-button__loading-text {
    color: var(--sj-primary-deep) !important;
  }
  /* light（v2 .cu-btn.light：primary-soft 浅底 + primary-deep 字，无描边） */
  &--light .u-button {
    background: var(--sj-primary-soft) !important;
    border-color: transparent !important;
  }
  &--light .u-button__text,
  &--light .u-button__loading-text {
    color: var(--sj-primary-deep) !important;
  }
  /* ghost（v2 .cu-btn.ghost：白底 + line 描边 + sub 字） */
  &--ghost .u-button {
    background: var(--sj-surface) !important;
    border: 3rpx solid var(--sj-line) !important;
  }
  &--ghost .u-button__text,
  &--ghost .u-button__loading-text {
    color: var(--sj-sub) !important;
  }
  /* text（v2 .cu-btn.txt：无底无投影，primary-deep 字，左右收窄 8px→16rpx） */
  &--text .u-button {
    background: transparent !important;
    border-color: transparent !important;
    box-shadow: none !important;
    padding: 20rpx 16rpx !important;
  }
  &--text .u-button__text,
  &--text .u-button__loading-text {
    color: var(--sj-primary-deep) !important;
  }
}
</style>
