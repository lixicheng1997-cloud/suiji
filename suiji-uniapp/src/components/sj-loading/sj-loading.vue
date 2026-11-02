<template>
  <view class="sj-ld">
    <!-- 全屏遮罩交给 uview-plus u-overlay（fixed 铺满 + 淡入淡出）；内容自组居中 -->
    <u-overlay
      :show="show"
      :zIndex="12000"
      :customStyle="{ backgroundColor: 'rgba(74, 50, 38, .55)' }"
    >
      <view class="ld-center">
        <view class="ld-panel" :class="{ 'is-in': show }">
          <!-- IP 加载图标：动画内置于 SVG（1.6s 轨道环绕 + 呼吸 + 眨眼），外层不再叠浮动 -->
          <image class="ld-img" :src="resolvedImage" :style="imgStyle" mode="aspectFit" />
          <text class="ld-text">{{ text }}</text>
          <!-- 第二级：客观进度说明（有 sub 才出现，禁止假进度安抚） -->
          <text v-if="sub" class="ld-sub">{{ sub }}</text>
          <view v-if="hasPercent" class="ld-track">
            <view class="ld-fill" :style="{ width: percentClamped + '%' }" />
          </view>
        </view>
      </view>
    </u-overlay>
  </view>
</template>

<script>
/**
 * 岁记 · 全屏加载动画（uview-plus u-overlay 封装，easycom 自动注册 <sj-loading>）
 * 用途：长任务（同步 / 导出 / 生成纪念卡 / 上传）全屏阻断式等待。
 * 设计稿：suiji-loading-fullscreen/preview.html；图标来自 suiji-loading（落库 src/static/loading/）。
 * 观感：暖可可深遮罩 rgba(74,50,38,.55) + 白 94% 毛玻璃面板（--sj-r-lg / --sj-sh-lg）；
 * 遮罩 240ms 淡入，面板 320ms 弹性入场（退场不缩放，避免收尾抖动）；
 * 小熊 / 小鸭同 viewBox 同时长，主题切换零重排。
 * 降级：长辈模式或低端机可传 image="/static/loading/{theme}-loading-dots.svg"（连跳变体，重绘面积更小）。
 * 用法：<sj-loading :show="busy" text="正在同步云端…" />
 *       <sj-loading :show="up" text="正在上传照片…" :sub="pct + '% · 保持应用打开'" :percent="pct" />
 */
export default {
  name: 'SjLoading',
  props: {
    /* 显隐 */
    show: { type: Boolean, default: false },
    /* 主文案：≤12 字、现在进行时 */
    text: { type: String, default: '加载中，请稍候…' },
    /* 进度副文案（'' = 不显示第二级） */
    sub: { type: String, default: '' },
    /* 进度百分比（不传 = 不显示进度条） */
    percent: { type: [Number, String], default: null },
    /* 加载图路径（'' = 按当前主题取 IP 主图标） */
    image: { type: String, default: '' },
    /* 显式主题覆盖（'' = 跟随全局 __theme） */
    theme: { type: String, default: '' },
    /* 图标尺寸 rpx */
    size: { type: [Number, String], default: 200 }
  },
  computed: {
    themeKey() {
      return (this.theme || this.__theme || 'bear') === 'duck' ? 'duck' : 'bear'
    },
    resolvedImage() {
      return this.image || `/static/loading/${this.themeKey}-loading.svg`
    },
    imgStyle() {
      const s = typeof this.size === 'number' ? this.size + 'rpx' : this.size
      return { width: s, height: s }
    },
    hasPercent() {
      return this.percent !== null && this.percent !== '' && !isNaN(Number(this.percent))
    },
    percentClamped() {
      return Math.max(0, Math.min(100, Number(this.percent)))
    }
  }
}
</script>

<style lang="scss" scoped>
/* 组件包裹：u-overlay 自身 fixed，此层不占布局 */
.sj-ld {
  width: 0;
  height: 0;
}
/* 遮罩内全屏居中容器 */
.ld-center {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* 毛玻璃面板：默认停在入场起点，退场时 transition 归零不回落缩放 */
.ld-panel {
  max-width: 560rpx;
  background: rgba(255, 255, 255, 0.94);
  border: 2rpx solid rgba(255, 255, 255, 0.9);
  border-radius: var(--sj-r-lg);
  padding: 56rpx 72rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  box-shadow: var(--sj-sh-lg);
  transform: scale(0.92) translateY(16rpx);
  backdrop-filter: blur(10px);
}
.ld-panel.is-in {
  transform: scale(1) translateY(0);
  transition: transform 0.32s var(--sj-spring) 0.06s;
}
/* 主文案 */
.ld-text {
  font-family: var(--sj-font-display);
  font-size: 30rpx;
  font-weight: 800;
  color: var(--sj-ink);
  text-align: center;
  margin-top: 8rpx;
}
/* 进度副文案 */
.ld-sub {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--sj-sub);
  text-align: center;
  margin-top: 8rpx;
}
/* 进度条 */
.ld-track {
  width: 300rpx;
  height: 12rpx;
  border-radius: var(--sj-r-pill);
  background: var(--sj-primary-soft);
  overflow: hidden;
  margin-top: 20rpx;
}
.ld-fill {
  height: 100%;
  border-radius: var(--sj-r-pill);
  background: linear-gradient(90deg, var(--sj-primary), var(--sj-primary-deep));
  transition: width 0.5s var(--sj-smooth);
}
</style>
