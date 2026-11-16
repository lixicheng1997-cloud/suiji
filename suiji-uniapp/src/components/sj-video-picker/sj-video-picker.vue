<template>
  <view class="sj-vp">
    <!-- 已选视频卡片：封面图或占位兜底（不实例化播放器），点击弹全屏预览 -->
    <view v-for="(v, i) in list" :key="v.key || i" class="vp-item" hover-class="hover-press" @click="onPreview(i)">
      <sj-video-cover
        class="vp-video"
        :thumb="v.thumb ? (isCloud(v.thumb) ? resolve(v.thumb) : v.thumb) : ''"
      />
      <view class="vp-mask" />
      <!-- 压缩中：只显示占位遮罩与文案，不实例化播放按钮；后台压缩完成后回写封面与路径 -->
      <view v-if="isCompressing(v)" class="vp-compress">
        <view class="vp-spinner" />
        <text class="vp-compress-txt">压缩中…</text>
      </view>
      <template v-else>
        <view class="vp-play">
          <view class="vp-tri" />
        </view>
        <view class="vp-dur"><text>{{ formatDur(v.duration) }}</text></view>
      </template>
      <view class="vp-del" @click.stop="onRemove(i)"><text class="vp-x">×</text></view>
    </view>

    <!-- 添加位：达上限后隐藏 -->
    <view v-if="list.length < max" class="vp-add" hover-class="hover-press" @click="onAdd">
      <image class="vp-ic" :src="uploadSrc" mode="aspectFit" />
      <text class="vp-add-text">录制 / 选视频</text>
    </view>

    <!-- 来源选择对话框 -->
    <sj-modal v-model:show="srcShow" title="添加视频" confirmText="取消">
      <view class="src-row" hover-class="hover-press" @click="chooseSource('camera')">
        <sj-icon class="src-ic" name="33-fn-video" :size="72" />
        <view class="src-txt">
          <text class="src-label">拍摄视频</text>
          <text class="src-sub">最长 {{ maxSeconds }} 秒 · 高码率录制</text>
        </view>
      </view>
      <view class="src-row" hover-class="hover-press" @click="chooseSource('album')">
        <sj-icon class="src-ic" name="31-fn-compare" :size="72" />
        <view class="src-txt">
          <text class="src-label">从相册选择</text>
          <text class="src-sub">已有视频 · 超 {{ maxSeconds }} 秒将被拒绝</text>
        </view>
      </view>
    </sj-modal>

    <!-- 全屏预览层：点击封面后弹出，自动播放当前段 -->
    <view v-if="preview.show" class="vp-preview-mask" @click="closePreview">
      <video
        class="vp-preview-video"
        :src="preview.url"
        :poster="preview.poster"
        :controls="true"
        :autoplay="true"
        :show-center-play-btn="true"
        :show-fullscreen-btn="true"
        :enable-progress-gesture="true"
        :object-fit="'contain'"
      />
      <view class="vp-preview-close" @click.stop="closePreview"><text>×</text></view>
    </view>

    <sj-notify ref="ntf" />
  </view>
</template>

<script>
/**
 * 岁记 · 视频选择器（easycom 自动注册，components/sj-video-picker/）
 * 用法：<sj-video-picker v-model="videos" :max="9" :max-seconds="30" />
 *
 * v-model 数组每项形状：
 *   { key: '<本地唯一标识，压缩回写定位用>',
 *     path: '<本地临时路径或云端 /api/v1/files/{id}/download>',
 *     duration: 12.5,
 *     size: 1234567,
 *     thumb: '<封面图路径（本地临时或云端 /api/v1/files/{id}/download）>',
 *     status: 'compressing' | 'ready' }
 *
 * 设计：
 *  - 选片后先以原片立即上卡片（compressing 态），本地压缩放到后台 Promise 跑，
 *    完成再回写 path/thumb/size——避免压缩转码阻塞卡片出现（App 端大视频转码可达数十秒）
 *  - 卡片只显示封面图 + 播放按钮，不在 picker 内联播（避免占资源/串音）
 *  - 点击卡片弹出全屏播放层，autoplay
 *  - 上传由调用方在保存时统一走 http.uploadFile（带 duration + thumb）
 */
import { resolveUrl } from '@/api/http.js'

export default {
  name: 'SjVideoPicker',
  props: {
    modelValue: { type: Array, default: () => [] },
    max: { type: Number, default: 9 },
    maxSeconds: { type: Number, default: 30 },
    /* 超过该字节数视为大原片，选择后先在本地压缩（失败回退原片，不阻断） */
    maxBytes: { type: Number, default: 25 * 1024 * 1024 }
  },
  data() {
    return {
      srcShow: false,
      /* 是否有压缩任务在跑：仅用于节流连续添加，不再阻塞卡片先上屏 */
      compressing: false,
      /* 在途压缩任务 Promise（whenReady 汇总等待）；完成后保留在数组内（已 settle，无副作用） */
      compressJobs: [],
      /* 已删除项的 key：后台压缩结果回来时直接丢弃，不回写 */
      cancelled: {},
      preview: { show: false, url: '', poster: '' }
    }
  },
  computed: {
    list() { return Array.isArray(this.modelValue) ? this.modelValue : [] },
    uploadSrc() {
      return `/static/icons/ctl/${this.__theme}/96/58-ctl-upload.png`
    }
  },
  methods: {
    isCloud(p) { return /^\/api\//.test(String(p || '')) },
    resolve(p) { return resolveUrl(p) },
    formatDur(s) {
      s = Math.max(0, Math.round(Number(s) || 0))
      const m = Math.floor(s / 60)
      const r = s % 60
      return (m ? m + ':' : '') + (m ? (r < 10 ? '0' : '') + r : r + 's')
    },
    onAdd() {
      if (this.list.length >= this.max) {
        this.$refs.ntf.show({ type: 'warn', message: '最多添加 ' + this.max + ' 段视频' })
        return
      }
      this.srcShow = true
    },
    chooseSource(sourceType) {
      this.srcShow = false
      if (this.compressing) return
      this.grant(sourceType)
        .then(() => this.pick(sourceType))
        .then(item => {
          if (!item) return
          if (item.size && item.size > this.maxBytes) {
            this.$refs.ntf.show({ type: 'warn', message: '原片较大，正在本地压缩…' })
          }
          const key = this.genKey()
          /* 先以原片立即上屏（compressing 态）；压缩放到后台 Promise，完成再回写，
             避免 App 端转码数十秒期间卡片一直不出现 */
          this.append(Object.assign({ key, status: 'compressing' }, item))
          this.compressing = true
          const job = Promise.resolve()
            .then(() => this.compressIfNeeded(item))
            .then(compressed => this.applyResult(key, this.asReady(compressed)))
            .catch(() => this.applyResult(key, this.asReady(item)))
            .finally(() => { this.compressing = false })
          this.compressJobs.push(job)
        })
        .catch(e => this.onFail(e))
    },
    /* 本地唯一标识：压缩回写按 key 定位，不依赖可能重复/缺失的临时路径 */
    genKey() {
      return 'v' + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36)
    },
    asReady(item) {
      return Object.assign({}, item, { status: 'ready' })
    },
    isCompressing(v) {
      return !!v && v.status === 'compressing'
    },
    /* 后台压缩结果回写：项已被删除则丢弃；否则按 key 覆盖 path/thumb/size 并置 ready */
    applyResult(key, result) {
      if (!key || this.cancelled[key]) { if (key) delete this.cancelled[key]; return }
      const next = this.list.slice()
      const idx = next.findIndex(x => x && x.key === key)
      if (idx < 0) return
      next[idx] = Object.assign({}, next[idx], result)
      this.emit(next)
    },
    /* 保存前等待所有在途压缩完成：避免拿半压缩/原片状态上传。无在途任务时立即 resolve */
    whenReady() {
      if (!this.compressJobs.length) return Promise.resolve()
      return Promise.all(this.compressJobs.slice()).catch(() => {})
    },
    /* 选片后本地压缩：App 走 uni.compressVideo，微信小程序走 wx.compressVideo；
       其余平台（H5 等）无可靠本地转码能力，原样回退。压缩失败也回退原片，不阻断选择。 */
    compressIfNeeded(item) {
      // #ifdef APP-PLUS
      if (uni.compressVideo) return this._compressApp(item)
      // #endif
      // #ifdef MP-WEIXIN
      if (typeof wx !== 'undefined' && wx.compressVideo) return this._compressWx(item)
      // #endif
      return Promise.resolve(item)
    },
    _compressApp(item) {
      return new Promise(resolve => {
        uni.compressVideo({
          src: item.path,
          quality: 'medium',
          resolution: 0.75,
          fps: 24,
          bitrate: 1000,
          success: r => {
            const out = r && r.tempFilePath
            if (!out || out === item.path) return resolve(item)
            /* 压缩后旧首帧临时图可能已失效，清空封面；新大小按返回值(kB)回填，取不到留 0 由服务端补 */
            const kb = Number(r.size)
            resolve(Object.assign({}, item, {
              path: out,
              thumb: '',
              size: kb ? Math.round(kb * 1024) : 0
            }))
          },
          fail: () => resolve(item)
        })
      })
    },
    _compressWx(item) {
      return new Promise(resolve => {
        wx.compressVideo({
          src: item.path,
          quality: 'medium',
          success: r => {
            const out = r && r.tempFilePath
            if (!out || out === item.path) return resolve(item)
            resolve(Object.assign({}, item, { path: out, thumb: '', size: 0 }))
          },
          fail: () => resolve(item)
        })
      })
    },
    pick(sourceType) {
      return new Promise((resolve, reject) => {
        const done = (res) => {
          const f = (res.tempFiles && res.tempFiles[0])
            || (res.tempFilePath ? { path: res.tempFilePath, duration: res.duration, size: res.size } : null)
            || res
          if (!f) return resolve(null)
          /* chooseMedia 在 App/小程序返回 tempFilePath（H5 才是 path）；两者都要认，
             否则真机选完/拍完 path 为空，视频不进列表 */
          const path = f.path || f.tempFilePath || ''
          if (!path) return resolve(null)
          const dur = Number(f.duration || 0)
          if (dur > this.maxSeconds) {
            this.$refs.ntf.show({ type: 'warn', message: '视频 ' + Math.round(dur) + ' 秒，超过 ' + this.maxSeconds + ' 秒上限' })
            return resolve(null)
          }
          /* chooseMedia 返回 thumbTempFilePath（首帧缩略图）；chooseVideo 在部分平台返回 thumb 字段 */
          const thumb = f.thumbTempFilePath || f.thumbUrl || f.thumb || ''
          resolve({
            path,
            duration: dur,
            size: Number(f.size || 0),
            thumb: thumb
          })
        }
        if (typeof uni.chooseMedia === 'function') {
          uni.chooseMedia({
            count: 1,
            mediaType: ['video'],
            sourceType: [sourceType],
            maxDuration: this.maxSeconds,
            camera: 'back',
            compressed: true,
            success: done,
            fail: reject
          })
        } else if (typeof uni.chooseVideo === 'function') {
          uni.chooseVideo({
            sourceType: [sourceType],
            maxDuration: this.maxSeconds,
            camera: 'back',
            compressed: true,
            success: done,
            fail: reject
          })
        } else {
          reject({ errMsg: '当前平台不支持选择视频' })
        }
      })
    },
    grant(sourceType) {
      // #ifdef APP-PLUS
      const perms = sourceType === 'camera'
        ? ['android.permission.CAMERA', 'android.permission.RECORD_AUDIO']
        : ['android.permission.READ_MEDIA_VIDEO', 'android.permission.READ_EXTERNAL_STORAGE']
      return new Promise(resolve => {
        try {
          if (typeof plus === 'undefined' || !plus.android || !plus.android.requestPermissions) { resolve(true); return }
          plus.android.requestPermissions(perms, () => resolve(true), () => resolve(true))
        } catch (e) { resolve(true) }
      })
      // #endif
      // #ifndef APP-PLUS
      return Promise.resolve(true)
      // #endif
    },
    append(item) {
      if (!item || !item.path) return
      const next = this.list.slice()
      next.push(item)
      this.emit(next)
    },
    onRemove(i) {
      const v = this.list[i]
      /* 压缩中的项被删：登记取消，后台结果回来时不再回写 */
      if (v && v.key) this.cancelled[v.key] = true
      const next = this.list.slice()
      next.splice(i, 1)
      this.emit(next)
    },
    onPreview(i) {
      const v = this.list[i]
      if (!v) return
      /* 压缩未完成：原片路径可能即将被压缩产物替换，禁用预览，避免播到失效/旧临时文件 */
      if (this.isCompressing(v)) return
      /* 云端路径拼 host + token；本地临时路径原样给 video 组件 */
      const url = this.isCloud(v.path) ? this.resolve(v.path) : v.path
      const poster = v.thumb ? (this.isCloud(v.thumb) ? this.resolve(v.thumb) : v.thumb) : ''
      this.preview = { show: true, url, poster }
    },
    closePreview() {
      this.preview = { show: false, url: '', poster: '' }
    },
    emit(next) {
      this.$emit('update:modelValue', next)
      this.$emit('change', next)
    },
    onFail(e) {
      const msg = (e && (e.errMsg || e.message)) || ''
      if (!msg || /cancel/i.test(msg)) return
      if (/permission|denied|权限|授权/i.test(msg)) {
        this.$refs.ntf.show({ type: 'err', message: '未获得相机/相册权限，请在系统设置中开启' })
        return
      }
      this.$refs.ntf.show({ type: 'err', message: '选择视频失败：' + msg })
    }
  }
}
</script>

<style lang="scss" scoped>
.sj-vp {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}
.vp-item {
  position: relative;
  width: 216rpx;
  height: 162rpx;
  border-radius: $sj-r-sm;
  overflow: hidden;
  background: #000;
}
.vp-video {
  width: 216rpx;
  height: 162rpx;
}
.vp-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.25);
}
.vp-compress {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
}
.vp-spinner {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  border: 4rpx solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  animation: vp-spin 0.8s linear infinite;
}
.vp-compress-txt { color: #fff; font-size: 20rpx; font-weight: 600; }
@keyframes vp-spin { to { transform: rotate(360deg); } }
.vp-play {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 0;
  height: 0;
  transform: translate(-50%, -50%);
}
.vp-tri {
  width: 0;
  height: 0;
  border-left: 18rpx solid #fff;
  border-top: 12rpx solid transparent;
  border-bottom: 12rpx solid transparent;
  margin-left: 4rpx;
  filter: drop-shadow(0 2rpx 4rpx rgba(0, 0, 0, 0.4));
}
.vp-dur {
  position: absolute;
  left: 8rpx;
  bottom: 8rpx;
  padding: 2rpx 12rpx;
  border-radius: 20rpx;
  background: rgba(0, 0, 0, 0.65);
  color: #fff;
  font-size: 20rpx;
  font-weight: 700;
}
.vp-del {
  position: absolute;
  top: 6rpx;
  right: 6rpx;
  width: 40rpx;
  height: 40rpx;
  border-radius: 50%;
  background: rgba(74, 58, 62, 0.78);
  display: flex;
  align-items: center;
  justify-content: center;
}
.vp-x { color: #fff; font-size: 26rpx; line-height: 1; }
.vp-add {
  width: 216rpx;
  height: 162rpx;
  border: 3rpx dashed $sj-border;
  border-radius: $sj-r-sm;
  background: #FFF9F5;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  box-sizing: border-box;
}
.vp-ic { width: 72rpx; height: 72rpx; }
.vp-add-text { font-size: 22rpx; color: var(--sj-sub); font-weight: 600; }

/* 全屏预览层 */
.vp-preview-mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.92);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}
.vp-preview-video {
  width: 100%;
  height: 100%;
}
.vp-preview-close {
  position: absolute;
  right: 32rpx;
  top: 32rpx;
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  font-size: 44rpx;
  line-height: 64rpx;
  text-align: center;
}

.src-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 20rpx 24rpx;
  border-radius: 28rpx;
  border: 2rpx solid var(--sj-line);
  background: rgba(255, 253, 251, 0.9);
}
.src-ic { flex: none; border-radius: 20rpx; overflow: hidden; }
.src-txt { display: flex; flex-direction: column; gap: 4rpx; }
.src-label { font-size: 28rpx; font-weight: 800; color: var(--sj-ink); }
.src-sub { font-size: 22rpx; font-weight: 600; color: var(--sj-sub); }
</style>
