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
      <!-- 视频：单段全屏播放（多段在下方切换） -->
      <view v-else class="smp-video-wrap">
        <video
          class="smp-video"
          :src="currentItem.url"
          :poster="currentItem.thumb || ''"
          :controls="true"
          :autoplay="true"
          :show-center-play-btn="true"
          :show-fullscreen-btn="true"
          :enable-progress-gesture="false"
          :object-fit="'contain'"
        />
      </view>
    </view>

    <!-- #ifndef APP-PLUS -->
    <!-- 顶部栏：关闭 + 计数（H5 / 小程序；App 端按钮由 plus.nativeObj.View 原生绘制，见 mountNativeOverlay） -->
    <cover-view class="smp-top" :style="{ paddingTop: (statusBarHeight + 20) + 'px' }" @click.stop>
      <cover-view class="smp-count">
        <cover-view class="smp-count-tx">{{ idx + 1 }} / {{ items.length }}</cover-view>
      </cover-view>
      <cover-view class="smp-actions">
        <cover-view v-if="showDownload" class="smp-dl" @click="download">
          <cover-view class="smp-dl-tx">↓</cover-view>
        </cover-view>
        <cover-view class="smp-close" @click="close">
          <cover-view class="smp-close-tx">×</cover-view>
        </cover-view>
      </cover-view>
    </cover-view>

    <!-- 多段视频：底部切换条（cover-view）；上移避让原生 video 底部控制条（进度条/播放钮） -->
    <cover-view v-if="items.length > 1 && currentItem.type === 'video'" class="smp-bar" :style="{ bottom: (safeBottom + 80) + 'px' }" @click.stop>
      <cover-view class="smp-bar-btn" :class="{ off: idx === 0 }" @click="prev">
        <cover-view class="smp-bar-tx">‹ 上一段</cover-view>
      </cover-view>
      <cover-view class="smp-bar-btn" :class="{ off: idx === items.length - 1 }" @click="next">
        <cover-view class="smp-bar-tx">下一段 ›</cover-view>
      </cover-view>
    </cover-view>
    <!-- #endif -->
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
 *
 * 端差异：
 * - App（app-vue）：video 是原生控件，层级高于 webview 内普通 DOM / cover-view，
 *   按钮用 plus.nativeObj.View 在原生层绘制（封装在 infra/platform.js），可点可盖。
 * - H5 / 小程序：按钮走 cover-view 模板。
 */
import { nativeOverlaySupported, createNativeButton } from '@/infra/platform.js'
import { toast } from '@/utils/ui.js'

export default {
  name: 'SjMediaPreview',
  props: {
    show: { type: Boolean, default: false },
    items: { type: Array, default: () => [] },
    current: { type: Number, default: 0 },
    /* 是否在关闭按钮左侧显示下载按钮（照片/视频存到本地相册或浏览器下载） */
    showDownload: { type: Boolean, default: false }
  },
  data() {
    return {
      idx: this.current,
      statusBarHeight: 20,
      safeBottom: 0,
      winW: 375,
      winH: 667,
      touchStartX: 0,
      touchStartY: 0,
      edgeGesture: false,
      swipeGesture: false
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
    show(v) {
      if (v) {
        this.idx = this.current
        this.mountNativeOverlay()
      } else {
        this.destroyNativeOverlay()
      }
    },
    current(v) { this.idx = v },
    idx() { this.refreshNativeOverlay() }
  },
  created() {
    /* 原生按钮句柄集合，不纳入响应式：{ close, dl, count, prev, next } */
    this._native = null
    /* 下载在途标记，防重复点击（无需驱动视图，不进响应式） */
    this._dlBusy = false
  },
  mounted() {
    try {
      const info = uni.getSystemInfoSync()
      this.statusBarHeight = info.statusBarHeight || 20
      this.safeBottom = (info.safeAreaInsets && info.safeAreaInsets.bottom) || 0
      this.winW = info.windowWidth || 375
      this.winH = info.windowHeight || 667
    } catch (e) { /* 保持默认 */ }
    if (this.show) this.mountNativeOverlay()
  },
  beforeUnmount() {
    this.destroyNativeOverlay()
  },
  methods: {
    onSwiperChange(e) { this.idx = e.detail.current },
    prev() { if (this.idx > 0) this.idx-- },
    next() { if (this.idx < this.items.length - 1) this.idx++ },
    close() { this.$emit('update:show', false) },

    /* 下载当前媒体（照片/视频）：
     * - App / 小程序：uni.downloadFile 拉字节到临时文件 → save*ToPhotosAlbum 存相册；
     *   小程序相册写入需 scope.writePhotosAlbum，被拒后引导授权重试一次。
     * - H5：下载端点 307 跳对象存储直链（跨域），优先 fetch→blob→a[download] 落地；
     *   对象存储未放行 CORS 时回退新窗口打开，由浏览器接管保存。 */
    download() {
      const it = this.currentItem
      if (!it || !it.url) { toast('内容不存在或已被删除', 2200, 'err'); return }
      if (this._dlBusy) return
      this._dlBusy = true
      const isVideo = it.type === 'video'
      const dateStr = String(it.occurredAt || '').slice(0, 10).replace(/-/g, '')
      const filename = '岁记_' + (dateStr || '相册') + (isVideo ? '_视频.mp4' : '_照片.jpg')

      // #ifdef H5
      this._downloadH5(it.url, filename)
      return
      // #endif

      // #ifndef H5
      toast('正在下载…', 1600, 'ok')
      uni.downloadFile({
        url: it.url,
        success: (res) => {
          if (res.statusCode !== 200 || !res.tempFilePath) { this._dlDone(); toast('下载失败，请重试', 2200, 'err'); return }
          this._saveToAlbum(res.tempFilePath, isVideo, false)
        },
        fail: () => { this._dlDone(); toast('下载失败，请检查网络', 2200, 'err') }
      })
      // #endif
    },

    /* 临时文件写入系统相册；authErr 时（小程序）拉起授权后重试一次 */
    _saveToAlbum(filePath, isVideo, retried) {
      const apiName = isVideo ? 'saveVideoToPhotosAlbum' : 'saveImageToPhotosAlbum'
      uni[apiName]({
        filePath,
        success: () => { this._dlDone(); toast('已保存到相册', 2000, 'ok') },
        fail: (e) => {
          const msg = (e && (e.errMsg || e.message)) || ''
          const authErr = /auth|deny|scope|permission/i.test(msg)
          // #ifdef MP-WEIXIN
          if (authErr && !retried) {
            uni.authorize({
              scope: 'scope.writePhotosAlbum',
              success: () => this._saveToAlbum(filePath, isVideo, true),
              fail: () => { this._dlDone(); toast('需要相册权限，请在「设置」中开启', 2400, 'warn') }
            })
            return
          }
          // #endif
          this._dlDone()
          toast(authErr ? '没有相册权限，请在系统设置中开启' : '保存失败，请重试', 2400, authErr ? 'warn' : 'err')
        }
      })
    },

    /* H5 下载：fetch 取字节转 Blob 触发浏览器下载；跨域被 CORS 拦下则新窗口打开兜底 */
    _downloadH5(url, filename) {
      // #ifdef H5
      toast('正在下载…', 1600, 'ok')
      fetch(url)
        .then(r => { if (!r.ok) throw new Error('http ' + r.status); return r.blob() })
        .then(blob => {
          const objUrl = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = objUrl
          a.download = filename
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
          setTimeout(() => { try { URL.revokeObjectURL(objUrl) } catch (e) { /* 已失效 */ } }, 3000)
          this._dlDone()
          toast('已开始下载', 2000, 'ok')
        })
        .catch(() => {
          try { window.open(url, '_blank') } catch (e) { /* 弹窗被拦截 */ }
          this._dlDone()
          toast('已在新窗口打开，请长按/右键保存', 2600, 'warn')
        })
      // #endif
    },

    _dlDone() { this._dlBusy = false },

    countText() { return (this.idx + 1) + ' / ' + this.items.length },

    /* ---------- App 端原生覆盖按钮（plus.nativeObj.View，封装见 infra/platform.js） ---------- */
    mountNativeOverlay() {
      this.destroyNativeOverlay()
      if (!nativeOverlaySupported()) return
      const r = (v) => uni.upx2px(v)
      const sb = this.statusBarHeight
      const btns = {}

      // 关闭钮（右上）
      const closeSize = r(64)
      const closeTop = sb + 20
      const closeLeft = this.winW - r(32) - closeSize
      btns.close = createNativeButton({
        id: 'smp-close',
        rect: { top: closeTop + 'px', left: closeLeft + 'px', width: closeSize + 'px', height: closeSize + 'px' },
        bg: 'rgba(255,255,255,0.2)',
        radius: closeSize / 2,
        text: '×', color: '#FFFFFF', fontSize: r(44), bold: true,
        onClick: () => this.close()
      })

      // 下载钮（关闭钮左侧，仅 showDownload 时绘制）
      if (this.showDownload) {
        btns.dl = createNativeButton({
          id: 'smp-dl',
          rect: { top: closeTop + 'px', left: (closeLeft - r(28) - closeSize) + 'px', width: closeSize + 'px', height: closeSize + 'px' },
          bg: 'rgba(255,255,255,0.2)',
          radius: closeSize / 2,
          text: '↓', color: '#FFFFFF', fontSize: r(28), bold: true,
          onClick: () => this.download()
        })
      }

      // 计数（顶部居中，纯展示）
      const countW = r(160)
      const countH = r(40)
      btns.count = createNativeButton({
        id: 'smp-count',
        rect: { top: closeTop + 'px', left: (this.winW - countW) / 2 + 'px', width: countW + 'px', height: countH + 'px' },
        bg: 'rgba(255,255,255,0.15)',
        radius: countH / 2,
        text: this.countText(), color: '#FFFFFF', fontSize: r(26), bold: true
      })

      // 视频多段：上一段 / 下一段（底部左右）
      if (this.items.length > 1 && this.currentItem.type === 'video') {
        const btnH = r(80)
        const gap = r(20)
        const side = r(32)
        const btnW = (this.winW - side * 2 - gap) / 2
        const barTop = this.winH - this.safeBottom - r(80) - btnH
        btns.prev = createNativeButton({
          id: 'smp-prev',
          rect: { top: barTop + 'px', left: side + 'px', width: btnW + 'px', height: btnH + 'px' },
          bg: 'rgba(255,255,255,0.2)',
          radius: btnH / 2,
          text: '‹ 上一段', color: '#FFFFFF', fontSize: r(28), bold: true,
          onClick: () => this.prev()
        })
        btns.next = createNativeButton({
          id: 'smp-next',
          rect: { top: barTop + 'px', left: side + btnW + gap + 'px', width: btnW + 'px', height: btnH + 'px' },
          bg: 'rgba(255,255,255,0.2)',
          radius: btnH / 2,
          text: '下一段 ›', color: '#FFFFFF', fontSize: r(28), bold: true,
          onClick: () => this.next()
        })
      }

      this._native = btns
      this.refreshNativeOverlay()
    },

    refreshNativeOverlay() {
      const n = this._native
      if (!n) return
      if (n.count) n.count.setText(this.countText())
      if (n.prev) n.prev.setOpacity(this.idx === 0 ? 0.4 : 1)
      if (n.next) n.next.setOpacity(this.idx === this.items.length - 1 ? 0.4 : 1)
    },

    destroyNativeOverlay() {
      const n = this._native
      if (n) {
        Object.keys(n).forEach(k => {
          try { n[k] && n[k].destroy() } catch (e) { /* ignore */ }
        })
      }
      this._native = null
    },

    /* 视频场景手势（图片由 swiper 原生左右滑动切换）：
     * - 左边缘 24px 内起步右滑超过 60px：关闭预览；
     * - 其余区域左右滑动超过 60px（纵向偏移小于 40px）：切换上一张/下一张媒体；
     * - 视频自身已禁用进度手势（enable-progress-gesture=false），左右滑动不再快进/后退。
     * 注：App 端 video 为原生控件会吞掉其表面的触摸，此时用底部「上一段/下一段」按钮切换。 */
    onTouchStart(e) {
      const t = e.touches && e.touches[0]
      if (!t) return
      this.touchStartX = t.clientX
      this.touchStartY = t.clientY
      const isVideo = this.currentItem.type === 'video'
      this.edgeGesture = isVideo && t.clientX <= 24
      this.swipeGesture = isVideo && !this.edgeGesture
    },
    onTouchEnd(e) {
      if (!this.edgeGesture && !this.swipeGesture) return
      const t = e.changedTouches && e.changedTouches[0]
      if (!t) { this.edgeGesture = false; this.swipeGesture = false; return }
      const dx = t.clientX - this.touchStartX
      const dy = t.clientY - this.touchStartY
      if (Math.abs(dy) < 40) {
        if (this.edgeGesture) {
          if (dx > 60) this.close()
        } else if (dx < -60) this.next()
        else if (dx > 60) this.prev()
      }
      this.edgeGesture = false
      this.swipeGesture = false
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
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4rpx 20rpx;
  border-radius: 20rpx;
  background: rgba(255, 255, 255, 0.15);
}
.smp-count-tx {
  color: #fff;
  font-size: 26rpx;
  font-weight: 700;
  line-height: 1.2;
  text-align: center;
}
.smp-close {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}
.smp-close-tx {
  color: #fff;
  font-size: 44rpx;
  line-height: 1;
  text-align: center;
}
.smp-actions {
  display: flex;
  align-items: center;
  gap: 28rpx;
}
.smp-dl {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}
.smp-dl-tx {
  color: #fff;
  font-size: 26rpx;
  line-height: 1;
  text-align: center;
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
  display: flex;
  align-items: center;
  justify-content: center;
}
.smp-bar-tx {
  width: 100%;
  color: #fff;
  font-size: 28rpx;
  font-weight: 700;
  line-height: 80rpx;
  text-align: center;
}
.smp-bar-btn.off { opacity: 0.4; }
</style>
