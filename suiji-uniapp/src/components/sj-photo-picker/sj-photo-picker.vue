<template>
  <view class="sj-pp">
    <!-- 已选照片：缩略图 + 右上角删除；点击整体预览大图 -->
    <view v-for="(p, i) in list" :key="i" class="ph-item" hover-class="hover-press" @click="onPreview(i)">
      <image class="ph-img" :src="srcOf(p)" mode="aspectFill" />
      <view class="ph-del" @click.stop="onRemove(i)"><text class="ph-x">×</text></view>
    </view>

    <!-- 添加位：达上限后隐藏；图标为 ctl-v2 上传概念图去底切图（96rpx，随主题切换） -->
    <view v-if="list.length < max" class="ph-add" hover-class="hover-press" @click="onAdd">
      <image class="ph-ic" :src="uploadSrc" mode="aspectFit" />
    </view>

    <!-- 来源选择对话框（sj-modal）：点选项行调起对应来源，「取消」关闭 -->
    <sj-modal v-model:show="srcShow" title="添加照片" confirmText="取消">
      <view class="src-row" hover-class="hover-press" @click="chooseSource('camera')">
        <sj-icon class="src-ic" name="04-photo" :size="72" />
        <view class="src-txt">
          <text class="src-label">拍照</text>
          <text class="src-sub">调起系统相机</text>
        </view>
      </view>
      <view class="src-row" hover-class="hover-press" @click="chooseSource('album')">
        <sj-icon class="src-ic" name="31-fn-compare" :size="72" />
        <view class="src-txt">
          <text class="src-label">从相册选择</text>
          <text class="src-sub">已有照片</text>
        </view>
      </view>
    </sj-modal>

    <sj-notify ref="ntf" />
  </view>
</template>

<script>
/**
 * 岁记 · 照片选择器（easycom 自动注册，components/sj-photo-picker/）
 * 用法：<sj-photo-picker v-model="photos" :max="9" />
 * 职责：
 * 1. 缩略图回显——本地临时路径（blob:/file:/_doc/…）与云端 /api/v1/… 相对路径统一可渲染；
 * 2. 选图入口——先弹「拍照 / 从相册选择」对话框（sj-modal），再按 sourceType 精确调起相机或相册；
 *    （此前无 sourceType 的 uni.chooseImage 在 App 端不会拉起相机，是本组件修复的核心问题）；
 * 3. 权限——App 端（Android 6+）调起前显式申请相机/相册运行时权限；
 * 4. 预览 / 删除。
 * 上传仍由调用方保存时统一走 http.uploadFile（POST /files），本组件只产出本地路径。
 */
import { resolveUrl } from '@/api/http.js'
import { play } from '@/utils/sound.js'

export default {
  name: 'SjPhotoPicker',
  props: {
    /* 已选路径数组：本地临时路径或云端 URL */
    modelValue: { type: Array, default: () => [] },
    /* 上限 */
    max: { type: Number, default: 9 }
  },
  data() {
    return {
      /* 来源选择对话框显隐 */
      srcShow: false
    }
  },
  computed: {
    list() {
      return Array.isArray(this.modelValue) ? this.modelValue : []
    },
    /* 添加位切图路径（scripts/cut-ctl-icons.py 生成到 /static/icons/ctl/{theme}/96/） */
    uploadSrc() {
      return `/static/icons/ctl/${this.__theme}/96/58-ctl-upload.png`
    }
  },
  methods: {
    /* 云端 /api/ 相对路径 → 带 token 的绝对地址；本地路径原样透传 */
    srcOf(p) {
      return resolveUrl(p)
    },
    /* 添加：先弹出来源对话框（sj-modal），再按所选来源调起相机/相册 */
    onAdd() {
      if (this.list.length >= this.max) {
        this.$refs.ntf.show({ type: 'warn', message: '最多添加 ' + this.max + ' 张' })
        return
      }
      this.srcShow = true
    },
    /* 选择来源：收起对话框后申请权限并调起选图 */
    chooseSource(sourceType) {
      this.srcShow = false
      this.grant(sourceType)
        .then(() => this.pick(sourceType))
        .then(paths => {
          if (paths && paths.length) {
            /* 仅「拍照」来源完成、照片进入预览时播快门音；从相册选择不播 */
            if (sourceType === 'camera') play('S06')
            this.append(paths)
          }
        })
        .catch(e => this.onFail(e))
    },
    /**
     * 调起选图（sourceType 必须显式指定，否则 App 端不会拉起相机）
     * @param {'camera'|'album'} sourceType
     * @returns {Promise<string[]>} 本地临时路径数组
     */
    pick(sourceType) {
      const left = this.max - this.list.length
      return new Promise((resolve, reject) => {
        const opts = {
          count: left > 0 ? left : 1,
          sourceType: [sourceType],
          sizeType: ['compressed'],
          success: res => {
            const paths = (res.tempFilePaths && res.tempFilePaths.length)
              ? res.tempFilePaths
              : (res.tempFiles || []).map(f => f.path).filter(Boolean)
            resolve(paths)
          },
          fail: reject
        }
        /* chooseImage 覆盖 H5/小程序/App 全端；缺失时回退 chooseMedia（含 camera 参数） */
        if (typeof uni.chooseImage === 'function') {
          uni.chooseImage(opts)
        } else if (typeof uni.chooseMedia === 'function') {
          uni.chooseMedia(Object.assign({ mediaType: ['image'], camera: 'back' }, opts))
        } else {
          reject({ errMsg: '当前平台不支持选择图片' })
        }
      })
    },
    /* App 端运行时权限：只申请本次来源所需权限；未声明/被拒也放行，交由系统或宿主提示，避免静默失败 */
    grant(sourceType) {
      // #ifdef APP-PLUS
      const perms = sourceType === 'camera'
        ? ['android.permission.CAMERA']
        : ['android.permission.READ_MEDIA_IMAGES', 'android.permission.READ_EXTERNAL_STORAGE']
      return new Promise(resolve => {
        try {
          if (typeof plus === 'undefined' || !plus.android || !plus.android.requestPermissions) { resolve(true); return }
          plus.android.requestPermissions(
            perms,
            () => resolve(true),
            () => resolve(true)
          )
        } catch (e) { resolve(true) }
      })
      // #endif
      // #ifndef APP-PLUS
      return Promise.resolve(true)
      // #endif
    },
    /* 追加并去重，超出上限截断 */
    append(paths) {
      const merged = this.list.slice()
      paths.forEach(p => { if (p && merged.indexOf(p) < 0) merged.push(p) })
      const next = merged.slice(0, this.max)
      if (next.length < merged.length) this.$refs.ntf.show({ type: 'warn', message: '最多 ' + this.max + ' 张，已保留前 ' + this.max + ' 张' })
      this.emit(next)
    },
    onRemove(i) {
      const next = this.list.slice()
      next.splice(i, 1)
      this.emit(next)
    },
    onPreview(i) {
      const urls = this.list.map(p => this.srcOf(p))
      uni.previewImage({ current: i, urls })
    },
    emit(next) {
      this.$emit('update:modelValue', next)
      this.$emit('change', next)
    },
    /* 用户取消静默；其余（权限未开/无相机/被系统拦截）给出可读提示 */
    onFail(e) {
      const msg = (e && (e.errMsg || e.message)) || ''
      if (!msg || /cancel/i.test(msg)) return
      if (/permission|denied|权限|授权/i.test(msg)) {
        this.$refs.ntf.show({ type: 'err', message: '未获得相机/相册权限，请在系统设置中开启' })
        return
      }
      this.$refs.ntf.show({ type: 'err', message: '选图失败：' + msg })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 照片栅格：与编辑页 .photo-add 同尺寸（144rpx 方砖），一行三张后自动换行 */
.sj-pp {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}
.ph-item {
  position: relative;
  width: 144rpx;
  height: 144rpx;
  border-radius: $sj-r-sm;
  overflow: visible;
}
.ph-img {
  width: 144rpx;
  height: 144rpx;
  border-radius: $sj-r-sm;
}
.ph-del {
  position: absolute;
  top: -10rpx;
  right: -10rpx;
  width: 40rpx;
  height: 40rpx;
  border-radius: 50%;
  background: rgba(74, 58, 62, 0.78);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ph-x {
  color: #fff;
  font-size: 26rpx;
  line-height: 1;
}
.ph-add {
  width: 144rpx;
  height: 144rpx;
  border: 3rpx dashed $sj-border;
  border-radius: $sj-r-sm;
  background: #FFF9F5;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
}
.ph-ic { width: 96rpx; height: 96rpx; }

/* 来源对话框选项行（sj-modal 默认 slot，对齐 .bs-row 卡片栅格风格：左图标 + 右标题/副标题） */
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
