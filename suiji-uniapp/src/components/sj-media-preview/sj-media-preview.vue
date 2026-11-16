<template>
  <view
    v-if="show"
    class="smp-mask"
    @click="close"
    @touchstart="onTouchStart"
    @touchend="onTouchEnd"
  >
    <view class="smp-stage" @click.stop>
      <!-- 图片 -->
      <swiper v-if="currentItem.type === 'image'" class="smp-swiper" :current="idx" @change="onSwiperChange" :indicator-dots="false">
        <swiper-item v-for="(it, i) in items" :key="'img' + i">
          <view class="smp-img-wrap">
            <image class="smp-img" :src="it.url" mode="aspectFit" @click="close" />
          </view>
        </swiper-item>
      </swiper>
      <!-- 视频：不swiper，单段全屏播放（多段在下方切换） -->
      <view v-else class="smp-video-wrap">
        <video
          class="smp-video"
          :src="currentItem.url"
          :poster="currentItem.thumb || ''"
          :controls="true"
          :autoplay="true"
          :show-center-play-btn="true"
          :show-fullscreen-btn="true"
          :enable-progress-gesture="true"
          :object-fit="'contain'"
        />
      </view>
    </view>

    <!-- 顶部栏：关闭 + 计数（cover-view 才能盖在 App 端原生 video 之上） -->
    <cover-view class="smp-top" :style="{ paddingTop: (statusBarHeight + 12) + 'px' }" @click.stop>
      <cover-view class="smp-count">{{ idx + 1 }} / {{ items.length }}</cover-view>
      <cover-view class="smp-close" @click="close">×</cover-view>
    </cover-view>

    <!-- 多段视频：底部切换条（cover-view） -->
    <cover-view v-if="items.length > 1 && currentItem.type === 'video'" class="smp-bar" :style="{ bottom: (safeBottom + 16) + 'px' }" @click.stop>
      <cover-view class="smp-bar-btn" :class="{ off: idx === 0 }" @click="prev">
        <cover-view>‹ 上一段</cover-view>
      </cover-view>
      <cover-view class="smp-bar-btn" :class="{ off: idx === items.length - 1 }" @click="next">
        <cover-view>下一段 ›</cover-view>
      </cover-view>
    </cover-view>
  </view>
</template>

<script>
/**
 * 岁记 · 全屏媒体预览（easycom 自动注册）
 * 用法：<sj-media-preview v-model:show="show" :items="[{type:'image',url:''},{type:'video',url:'',thumb:''}]" :current="0" />
 *
 * - 图片：swiper 左右滑动切换，点击关闭
 * - 视频：单段全屏播放，多段时底部出"上一段/下一段"按钮
 * - 所有 URL 调用方负责 resolveUrl 拼好 host+token
 */
export default {
  name: 'SjMediaPreview',
  props: {
    show: { type: Boolean, default: false },
    items: { type: Array, default: () => [] },
    current: { type: Number, default: 0 }
  },
  data() {
    return {
      idx: this.current,
      statusBarHeight: 20,
      safeBottom: 0,
      touchStartX: 0,
      touchStartY: 0,
      edgeGesture: false
    }
  },
  computed: {
    currentItem() {
      if (!this.items.length) return { type: 'image', url: '' }
      const i = Math.max(0, Math.min(this.idx, this.items.length - 1))
      return this.items[i]
    }
  },
  watch: {
    show(v) { if (v) this.idx = this.current },
    current(v) { this.idx = v }
  },
  mounted() {
    try {
      const info = uni.getSystemInfoSync()
      this.statusBarHeight = info.statusBarHeight || 20
      this.safeBottom = (info.safeAreaInsets && info.safeAreaInsets.bottom) || 0
    } catch (e) { /* 保持默认 */ }
  },
  methods: {
    onSwiperChange(e) { this.idx = e.detail.current },
    prev() { if (this.idx > 0) this.idx-- },
    next() { if (this.idx < this.items.length - 1) this.idx++ },
    close() { this.$emit('update:show', false) },

    /* 边缘滑动返回：仅视频场景，左边缘 24px 内起步、右滑超过 60px、纵向偏移小于 40px 视为返回手势（坐标为 px） */
    onTouchStart(e) {
      const t = e.touches && e.touches[0]
      if (!t) return
      this.touchStartX = t.clientX
      this.touchStartY = t.clientY
      this.edgeGesture = this.currentItem.type === 'video' && t.clientX <= 24
    },
    onTouchEnd(e) {
      if (!this.edgeGesture) return
      const t = e.changedTouches && e.changedTouches[0]
      if (!t) return
      const dx = t.clientX - this.touchStartX
      const dy = t.clientY - this.touchStartY
      if (dx > 60 && Math.abs(dy) < 40) this.close()
      this.edgeGesture = false
    }
  }
}
</script>

<style lang="scss" scoped>
.smp-mask {
  position: fixed;
  left: 0; right: 0; top: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.95);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}
.smp-stage {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.smp-swiper { width: 100%; height: 100%; }
.smp-img-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.smp-img { width: 100%; height: 80vh; }
.smp-video-wrap { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
.smp-video { width: 100%; height: 100%; }

.smp-top {
  position: absolute;
  top: 0; left: 0; right: 0;
  padding: 0 32rpx 20rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  z-index: 2;
}
.smp-count {
  color: #fff;
  font-size: 26rpx;
  font-weight: 700;
  padding: 4rpx 20rpx;
  border-radius: 20rpx;
  background: rgba(255, 255, 255, 0.15);
}
.smp-close {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  font-size: 44rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.smp-bar {
  position: absolute;
  left: 0; right: 0;
  display: flex;
  justify-content: space-between;
  padding: 0 32rpx;
  gap: 20rpx;
}
.smp-bar-btn {
  flex: 1;
  height: 80rpx;
  border-radius: 40rpx;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  font-size: 28rpx;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.smp-bar-btn.off { opacity: 0.4; }
</style>
