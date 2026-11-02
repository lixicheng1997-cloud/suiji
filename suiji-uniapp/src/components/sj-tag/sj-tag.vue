<template>
  <view
    class="sj-tg"
    :class="['sj-tg--' + variant, size === 'mini' ? 'sj-tg--mini' : '']"
    :hover-class="pressable ? 'hover-press' : ''"
    :hover-stay-time="80"
    @click="$emit('click')"
  >
    <!-- 配色全部经 u-tag 的 bgColor/color/borderColor 内联下发（可精确命中设计稿），
         形状/尺寸基线由库提供，字号字重圆角内衬经 .sj-tg 命名空间覆盖对齐 v2 -->
    <!-- u-tag 根节点自带 @tap.stop（阻止冒泡），外层 wrapper 收不到点击；
         必须监听 u-tag 自身 $emit('click') 再转发，chip 选中态才能响应 -->
    <u-tag
      :text="text"
      type="primary"
      :size="size === 'mini' ? 'mini' : 'medium'"
      :shape="variant === 'pill' || variant === 'chip' ? 'circle' : 'square'"
      :plain="variant === 'plain'"
      :bgColor="colors.bg"
      :color="colors.fg"
      :borderColor="colors.border"
      @click="$emit('click')"
    >
      <!-- 前置图标：ctl-v2 去底切图（36rpx，经 u-tag #icon 插槽） -->
      <template v-if="ctlSrc" #icon>
        <image class="tg-ic" :src="ctlSrc" mode="aspectFit" />
      </template>
    </u-tag>
  </view>
</template>

<script>
/**
 * 岁记 · 标签（uview-plus u-tag 封装，easycom 自动注册，纯展示无事件）
 * 对齐 v2 设计稿 components.html L142-161（标签区）+ styles.css L701-707（.cu-tag，px×2→rpx）：
 * 字号 23rpx(11.5px) 特粗、圆角 16rpx(8px)、内衬 8rpx 24rpx(4px 12px)；
 * 变体：default=primary 底白字 / soft=primary-soft 底 primary-deep 字 / plain=白底 primary 描边
 * + primary-deep 字 / ok(#E2F5EA+#2E7D4F) / warn(#FFF3C4+#B47714) / err(#FDF0F0+#B04A4A)
 * / pill=胶囊圆角（类别色浅底+深字，经 bg/color 传入；缺省 primary 底白字，对齐设计稿首列「喂奶」）
 * / chip=可选中胶囊（对齐页面原 .pg-chip：白底 line 描边 sub 字，active 时 primary-soft 底
 * + primary 描边 + primary-deep 字；配合 pressable 出按压弹性与 @click）。
 * primary 族色随主题换肤，取 palette 静态传入（u-tag 内联 style 优先级高于其 scoped 类，无需覆盖色值）；
 * 语义三色双主题相同写死。库对非 plain 形态也画 1px 同色边框，统一覆盖为 2rpx 且描边色=底色，视觉无感。
 * 用法：<sj-tag text="正常" variant="ok" /> <sj-tag text="睡眠" variant="pill" bg="#E9EEFB" color="#4A5E96" />
 *       <sj-tag variant="chip" pressable :active="sex === 'M'" text="男" @click="sex = 'M'" />
 *       <sj-tag text="筛选" variant="soft" icon="43-ctl-tag-filter" />
 * icon：传 ctl-v2 切图名（如 42-ctl-tag / 43-ctl-tag-filter）时文字前置 36rpx 角色切图，
 * scripts/cut-ctl-icons.py 生成到 /static/icons/ctl/{theme}/36/，随主题换肤。
 */
import { palette } from '@/theme/theme.js'

export default {
  name: 'SjTag',
  props: {
    /* 标签文字 */
    text: { type: String, default: '' },
    /* 变体：default|soft|plain|ok|warn|err|pill */
    variant: { type: String, default: 'default' },
    /* pill 自定义底色（类别浅底） */
    bg: { type: String, default: '' },
    /* pill 自定义字色（类别深字） */
    color: { type: String, default: '' },
    /* 尺寸：mini|normal */
    size: { type: String, default: 'normal' },
    /* chip 选中态（仅 variant=chip 有色差，其它变体忽略） */
    active: { type: Boolean, default: false },
    /* 可点击（开启按压弹性；点击一律 $emit('click')） */
    pressable: { type: Boolean, default: false },
    /* 前置 ctl-v2 切图名（'' = 无图标） */
    icon: { type: String, default: '' }
  },
  emits: ['click'],
  computed: {
    /* 当前主题下的前置切图（彩色绘本图，不走 color 重染） */
    ctlSrc() {
      if (!this.icon) return ''
      return `/static/icons/ctl/${this.__theme}/36/${this.icon}.png`
    },
    /* 变体 → 底色/字色/描边映射；primary 族取当前主题 palette */
    colors() {
      const p = palette(this.__theme)
      const map = {
        default: { bg: p['primary'], fg: '#FFFFFF', border: p['primary'] },
        soft: { bg: p['primary-soft'], fg: p['primary-deep'], border: p['primary-soft'] },
        plain: { bg: '#FFFFFF', fg: p['primary-deep'], border: p['primary'] },
        ok: { bg: '#E2F5EA', fg: '#2E7D4F', border: '#E2F5EA' },
        warn: { bg: '#FFF3C4', fg: '#B47714', border: '#FFF3C4' },
        err: { bg: '#FDF0F0', fg: '#B04A4A', border: '#FDF0F0' },
        chip: this.active
          ? { bg: p['primary-soft'], fg: p['primary-deep'], border: p['primary'] }
          : { bg: p['surface'], fg: p['sub'], border: p['line'] },
        pill: {
          bg: this.bg || p['primary'],
          fg: this.color || '#FFFFFF',
          border: this.bg || p['primary']
        }
      }
      return map[this.variant] || map.default
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：不破坏页面 flex/行内排版 */
.sj-tg {
  display: inline-flex;
  align-items: center;
}
/* 前置切图（36rpx，切图自带约 11% 留白） */
.tg-ic {
  width: 36rpx;
  height: 36rpx;
  margin-right: 6rpx;
  flex: none;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-tg 命名空间覆盖 u-tag 内部类 ============
 * 库 scoped 选择器带 [data-v]，与双类选择器同权重，关键覆盖以重复类名提权 + !important。 */
.sj-tg {
  /* 主体：v2 .cu-tag 内衬 8rpx 24rpx、描边 2rpx（非 plain 时描边色=底色，视觉无感）；
   * 高度改为内容自适应（库 mini/medium 固定高与设计稿不符） */
  .u-tag.u-tag {
    height: auto !important;
    line-height: 1 !important;
    padding: 8rpx 24rpx !important;
    border-width: 2rpx !important;
  }
  /* 圆角：普通 16rpx（v2 8px→16rpx，库 square 默认 3px）；pill 走全胶囊令牌 */
  .u-tag.u-tag--square {
    border-radius: 16rpx !important;
  }
  .u-tag.u-tag--circle {
    border-radius: var(--sj-r-pill) !important;
  }
  /* 文字：23rpx 特粗（v2 11.5px→23rpx，字重库无 prop） */
  .u-tag__text.u-tag__text {
    font-size: 23rpx !important;
    line-height: 1.2 !important;
    font-weight: 800 !important;
  }
  /* chip（页面原 .pg-chip 规格：内衬 12rpx 28rpx、字号 25rpx/800、全胶囊） */
  &--chip .u-tag.u-tag {
    padding: 12rpx 28rpx !important;
  }
  &--chip .u-tag__text.u-tag__text {
    font-size: 25rpx !important;
  }
  /* mini 档：整体缩一号（内衬 4rpx 16rpx、字号 20rpx；置于 chip 之后以便 chip+mini 取小尺寸） */
  &--mini .u-tag.u-tag {
    padding: 4rpx 16rpx !important;
  }
  &--mini .u-tag__text.u-tag__text {
    font-size: 20rpx !important;
  }
}
</style>
