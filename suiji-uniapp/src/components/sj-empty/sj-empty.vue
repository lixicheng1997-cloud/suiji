<template>
  <view class="sj-ep">
    <!-- 图标圆底（v2 .ee-ava：primary-soft 圆 + peek 摇摆；image 用 aspectFit 防拉伸） -->
    <view class="ee-ava">
      <image class="ee-img" :src="iconSrc" mode="aspectFit" />
    </view>
    <text class="ee-title">{{ text }}</text>
    <text v-if="sub" class="ee-sub">{{ sub }}</text>
  </view>
</template>

<script>
/**
 * 岁记 · 空态（自组 v2 .pg-empty 结构，easycom 自动注册）
 * 外观 1:1 对齐 v2 .pg-empty（styles.css L644-648 + peek L167，px×2→rpx）：
 * 图标圆底 92px→184rpx --sj-primary-soft + peek 摇摆动画（3s ease-in-out infinite，
 * 50% 处 translateY(-6px→-12rpx) + rotate(4deg)）；图标 64px→128rpx aspectFit；
 * 主文案 18px→36rpx ink 特粗（display 字体族）、上间距 14px→28rpx；
 * 副文案 12.5px→25rpx --sj-sub、上间距 6px→12rpx、下间距 18px→36rpx。
 * 选型说明：此前用 u-empty 图片分支，库 image 固定 mode="widthFix" 且圆底只能经
 * padding 加在 image 自身，H5 端内部 img 铺满 padding 盒导致图标拉伸；
 * 改为自组结构（同 sj-circle-progress 先例：库结构无法承载设计稿形态时自绘），
 * 纯展示组件无交互内核损失。
 * 图标路径按当前主题解析：icon 传 v2 png 名时取 /static/icons/{theme}/{icon}.png；
 * 不传 icon 时默认用 ctl-v2 空态概念图去底切图（69-ctl-empty，掀空奶纸箱张望，
 * scripts/cut-ctl-icons.py 生成到 /static/icons/ctl/{theme}/128/）。
 * 用法：<sj-empty text="这里空空如也" />（默认空态图）
 *       <sj-empty icon="24-fn-search" text="没有找到相关记录" sub="换个关键词试试" />
 */
export default {
  name: 'SjEmpty',
  props: {
    /* v2 png 图标名（不含路径与扩展名） */
    icon: { type: String, default: '' },
    /* 主文案 */
    text: { type: String, default: '' },
    /* 副文案（可空） */
    sub: { type: String, default: '' }
  },
  computed: {
    /* 自定义图标取主题目录 v2 png；缺省回落 ctl-v2 空态切图（128rpx 规格） */
    iconSrc() {
      if (this.icon) return `/static/icons/${this.__theme}/${this.icon}.png`
      return `/static/icons/ctl/${this.__theme}/128/69-ctl-empty.png`
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：纵向居中 */
.sj-ep {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40rpx 0;
}
/* 图标圆底（v2 .ee-ava 92px→184rpx，primary-soft 浅底 + peek 摇摆） */
.ee-ava {
  width: 184rpx;
  height: 184rpx;
  border-radius: 50%;
  background: var(--sj-primary-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: sjPeek 3s ease-in-out infinite;
}
/* 图标（v2 .ee-ava img 64px→128rpx，aspectFit 保比例不拉伸） */
.ee-img {
  width: 128rpx;
  height: 128rpx;
}
/* 主文案（v2 h4：display 字体 18px→36rpx ink 特粗，上间距 28rpx） */
.ee-title {
  font-family: var(--sj-font-display);
  font-size: 36rpx;
  font-weight: 800;
  color: var(--sj-ink);
  margin-top: 28rpx;
}
/* 副文案（v2 p：12.5px→25rpx sub，上间距 12rpx、下间距 36rpx） */
.ee-sub {
  font-size: 25rpx;
  font-weight: 600;
  color: var(--sj-sub);
  margin-top: 12rpx;
  margin-bottom: 36rpx;
}
</style>

<style lang="scss">
/* v2 @keyframes peek（styles.css L167，sj 前缀防全局泄漏） */
@keyframes sjPeek {
  0%,
  100% {
    transform: translateY(0) rotate(0deg);
  }
  50% {
    transform: translateY(-12rpx) rotate(4deg);
  }
}
</style>
