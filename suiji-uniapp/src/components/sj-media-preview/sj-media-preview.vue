<template>
  <view v-if="show" class="smp-mask" @click="close">
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

    <!-- 顶部栏：关闭 + 计数 -->
    <view class="smp-top">
      <text class="smp-count">{{ idx + 1 }} / {{ items.length }}</text>
      <view class="smp-close" @click="close"><text>×</text></view>
    </view>

    <!-- 多段视频：底部切换条 -->
    <view v-if="items.length > 1 && currentItem.type === 'video'" class="smp-bar">
      <view class="smp-bar-btn" :class="{ off: idx === 0 }" @click="prev">
        <text>‹ 上一段</text>
      </view>
      <view class="smp-bar-btn" :class="{ off: idx === items.length - 1 }" @click="next">
        <text>下一段 ›</text>
      </view>
    </view>
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
    return { idx: this.current }
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
  methods: {
    onSwiperChange(e) { this.idx = e.detail.current },
    prev() { if (this.idx > 0) this.idx-- },
    next() { if (this.idx < this.items.length - 1) this.idx++ },
    close() { this.$emit('update:show', false) }
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
  padding: calc(env(safe-area-inset-top) + 20rpx) 32rpx 20rpx;
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
  line-height: 64rpx;
  text-align: center;
}

.smp-bar {
  position: absolute;
  left: 0; right: 0;
  bottom: calc(env(safe-area-inset-bottom) + 32rpx);
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
