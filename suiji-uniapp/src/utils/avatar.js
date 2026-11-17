/**
 * 头像选择工具（跨端）
 * 相册 / 拍照选一张图 → 压缩 → 返回本地临时路径。
 * 字节由调用方经 http.uploadFile 上传到 POST /files（契约 §7.5），
 * 档案行只保存返回的文件 URL，不再内联 base64 dataURL。
 */

/* 压缩目标：长边 ≤ 400px（页面最大展示 112rpx 圆形头像，足够清晰） */
const MAX_EDGE = 400
const JPEG_QUALITY = 80

/* App 端运行时权限：相机 / 相册分别申请；未声明或被拒也放行，交由系统或宿主提示 */
function grant(sourceType) {
  // #ifdef APP-PLUS
  const perms = sourceType === 'camera'
    ? ['android.permission.CAMERA', 'android.permission.RECORD_AUDIO']
    : ['android.permission.READ_MEDIA_IMAGES', 'android.permission.READ_EXTERNAL_STORAGE']
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
}

/**
 * 调起相册 / 相机选一张图并返回可上传的本地临时路径
 * @param {'album'|'camera'} [sourceType] 来源；缺省由系统弹默认来源选择
 * @returns {Promise<string>} 临时文件路径；用户取消时 reject
 */
export function pickAvatar(sourceType) {
  const source = sourceType ? [sourceType] : ['album', 'camera']
  return grant(sourceType).then(() => new Promise((resolve, reject) => {
    uni.chooseImage({
      count: 1,
      sourceType: source,
      sizeType: ['compressed'],
      success: res => {
        const path = (res.tempFilePaths || [])[0]
        if (!path) { reject(new Error('no tempFilePath')); return }
        // #ifdef H5
        /* H5 的 blob 路径可直接交给 uni.uploadFile */
        resolve(path)
        // #endif
        // #ifndef H5
        /* 小程序 / App：先系统压缩到目标尺寸再上传 */
        uni.compressImage({
          src: path,
          quality: JPEG_QUALITY,
          width: MAX_EDGE + 'px',
          success: r => resolve(r && r.tempFilePath ? r.tempFilePath : path),
          fail: () => resolve(path)
        })
        // #endif
      },
      fail: reject
    })
  }))
}
