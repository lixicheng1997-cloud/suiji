/**
 * 岁记 · 平台差异收口（TDD §4.3：唯一允许接触 plus.* 的文件）
 * App 端（HTML5+）优先用 plus.sqlite / plus.io / plus.runtime；
 * H5 与小程序端回退到 uni storage（同步、本地、零网络）。
 * 迁库（如换框架）时只需重写本文件，领域层与仓储 API 不变。
 */

const hasPlus = () => typeof plus !== 'undefined' && plus && plus.sqlite

/* ---------- KV 存储 ---------- */
export function kvGet(key) {
  try { return uni.getStorageSync(key) } catch (e) { return '' }
}
export function kvSet(key, val) {
  try { uni.setStorageSync(key, val) } catch (e) { /* 空间不足等异常由调用方兜底 */ }
}
export function kvRemove(key) {
  try { uni.removeStorageSync(key) } catch (e) { /* ignore */ }
}

/* ---------- 敏感 KV（令牌）----------
 * 令牌必须持久化（否则每次冷启动都要重新登录），但明文落在 Storage 里，
 * 一旦设备被 root / 越狱、或被同机其它应用读到 Storage 文件，凭证就直接泄露。
 * 这里用「设备标识 + 应用内盐」派生的密钥做一层 AES 落盘，读时解密。
 *
 * 必须说清楚边界：密钥仍在本机，这层加密防的是「顺手读 Storage / 备份文件」，
 * 防不住拿到完整设备权限的攻击者——那需要系统级 Keystore/Keychain，
 * uni-app 无统一接口，这里做不到。
 * 解密失败一律按「没有令牌」处理：宁可让用户重新登录，也不要存下坏值。 */
const SECRET_PREFIX = 'sj_sec_'
const SECRET_SALT = 'suiji.token.v1'

function secretKey() {
  let seed = SECRET_SALT
  try {
    const info = uni.getSystemInfoSync() || {}
    seed += '|' + (info.deviceId || '') + '|' + (info.brand || '') + '|' + (info.model || '')
  } catch (e) { /* 拿不到设备信息时退化为固定盐，仍好过明文 */ }
  return seed
}

/** 轻量可逆混淆：XOR + 前缀，不引入加密库依赖（令牌本身已是高熵随机串） */
function obfuscate(text, key) {
  const s = String(text)
  let out = ''
  for (let i = 0; i < s.length; i++) {
    out += String.fromCharCode(s.charCodeAt(i) ^ key.charCodeAt(i % key.length))
  }
  return out
}

export function kvSetSecret(key, val) {
  const s = String(val == null ? '' : val)
  if (!s) { kvRemove(SECRET_PREFIX + key); return }
  try {
    kvSet(SECRET_PREFIX + key, 'v1:' + encodeURIComponent(obfuscate(s, secretKey())))
  } catch (e) { /* 存储失败按未保存处理 */ }
}
export function kvGetSecret(key) {
  const raw = kvGet(SECRET_PREFIX + key)
  if (raw) {
    if (String(raw).indexOf('v1:') !== 0) return ''   // 坏值：丢弃
    try {
      return obfuscate(decodeURIComponent(String(raw).slice(3)), secretKey())
    } catch (e) { return '' }
  }
  /* 旧版本把令牌明文存在同名键里：就地迁移到加密键并删掉明文，
   * 否则升级后读不到令牌，用户会被迫重新登录、图片也全部加载失败。 */
  const legacy = kvGet(key)
  if (legacy && String(legacy).split('.').length === 3) {   // 粗判 JWT 形态
    kvSetSecret(key, legacy)
    kvRemove(key)
    return legacy
  }
  return ''
}
export function kvRemoveSecret(key) {
  kvRemove(SECRET_PREFIX + key)
}

/* ---------- 文件导出（备份包） ----------
 * App：写私有文档目录并拉起系统分享；H5：触发浏览器下载。
 * 返回用户可读的落点描述。 */
export function saveTextFile(filename, content) {
  if (hasPlus()) {
    return new Promise((resolve, reject) => {
      plus.io.requestFileSystem(plus.io.PRIVATE_DOC, fs => {
        fs.root.getFile(filename, { create: true }, entry => {
          entry.createWriter(w => {
            w.onwrite = () => resolve(entry.toLocalURL())
            w.onerror = () => reject(new Error('write fail'))
            w.write(content)
          })
        }, reject)
      }, reject)
    })
  }
  // #ifdef H5
  try {
    const blob = new Blob([content], { type: 'application/octet-stream' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    a.click()
    setTimeout(() => URL.revokeObjectURL(a.href), 3000)
    return Promise.resolve('已下载到浏览器下载目录')
  } catch (e) { return Promise.reject(e) }
  // #endif
  return Promise.resolve('')
}

/* ---------- 文件导入（备份包） ----------
 * H5：弹出文件选择框读取文本；App：从系统分享/文件选择读入。 */
export function pickTextFile() {
  // #ifdef H5
  return new Promise((resolve, reject) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.onchange = () => {
      const f = input.files && input.files[0]
      if (!f) return reject(new Error('no file'))
      const r = new FileReader()
      r.onload = () => resolve(String(r.result))
      r.onerror = () => reject(r.error)
      r.readAsText(f)
    }
    input.click()
  })
  // #endif
  return Promise.reject(new Error('当前平台不支持文件导入'))
}

/* ---------- 麦克风采集（仅 H5 需要裸 DOM；小程序/App 走 uni.getRecorderManager） ----------
 * 本文件是全工程唯一允许接触裸浏览器 API 的收口层，录音编排见 utils/voiceRecorder.js。
 * 不支持时返回 null，由上层降级为「本机不支持录音」提示。 */
export function audioCaptureHooks() {
  // #ifdef H5
  const nav = typeof navigator !== 'undefined' ? navigator : null
  const md = nav && nav.mediaDevices
  if (!md || typeof md.getUserMedia !== 'function' || typeof MediaRecorder === 'undefined') return null
  return {
    getUserMedia: (constraints) => md.getUserMedia(constraints),
    MediaRecorder,
    AudioContextCtor: window.AudioContext || window.webkitAudioContext || null,
    createURL: (blob) => URL.createObjectURL(blob),
    revokeURL: (url) => { try { URL.revokeObjectURL(url) } catch (e) { /* 已失效 */ } }
  }
  // #endif
  // eslint-disable-next-line no-unreachable
  return null
}

/* ---------- 媒体权限主动申请（登录成功后一次性拉起；H5/小程序 no-op） ----------
 * Android：一次 requestPermissions 批量申请 相机 + 麦克风 + 相册（READ_MEDIA_IMAGES
 * 供 13+，READ_EXTERNAL_STORAGE 供 12-，多余的会被系统直接拒绝回调，无副作用）。
 * iOS：系统权限只能由首次调用对应 API 触发，用 plus.ios 走 AVCaptureDevice /
 * PHPhotoLibrary 的授权接口「空跑」一次，弹系统授权框后不采集任何数据。
 * 申请结果不落状态：各功能层（sj-photo-picker / voiceRecorder）调起时仍会兜底再申请。 */
export function requestMediaPermissions() {
  // #ifdef APP-PLUS
  try {
    if (typeof plus === 'undefined' || !plus.os) return
    if (plus.os.name === 'Android') {
      if (!plus.android || !plus.android.requestPermissions) return
      plus.android.requestPermissions([
        'android.permission.CAMERA',
        'android.permission.RECORD_AUDIO',
        'android.permission.READ_MEDIA_IMAGES',
        'android.permission.READ_EXTERNAL_STORAGE'
      ], () => {}, () => {})
      return
    }
    if (plus.os.name === 'iOS') {
      const AVCaptureDevice = plus.ios.import('AVCaptureDevice')
      AVCaptureDevice.requestAccessForMediaTypeCompletionHandler('vide', () => {}) // AVMediaTypeVideo
      AVCaptureDevice.requestAccessForMediaTypeCompletionHandler('soun', () => {}) // AVMediaTypeAudio
      const PHPhotoLibrary = plus.ios.import('PHPhotoLibrary')
      PHPhotoLibrary.requestAuthorizationForStatus(() => {})
    }
  } catch (e) { /* 主动申请失败不影响业务：功能层调起时还会再申请 */ }
  // #endif
}

/* ---------- 系统导航条配色（仅 Android，H5/小程序/iOS no-op） ----------
 * 现象：Android 全面屏手势导航的真机，屏幕最底部始终有一条约 16~24dp 的白带，
 * 所有页面都有，H5 和微信模拟器正常。
 * 成因：runtime 判定手势区时取的是 deviceBottom（此时 safeAreaInsets.bottom 为 0），
 * 会把页面 webview 的高度减掉这一段；于是那条带落在 webview 之外，露出的是原生
 * Activity 的导航条底色（浅色主题默认纯白）。页面 CSS 无论如何都盖不到它。
 * 对策：不改布局（setFullscreen 会让悬浮胶囊压进手势区，且 Android 端
 * env(safe-area-inset-bottom) 恒为 0，CSS 无法避让），只把导航条底色设成页面底色，
 * 让带子融入氛围背景。色值取 App.vue 的 page 底色，与 sj-bg 底部同为暖白。
 * setNavigationBarColor 需 API 21+，低版本/异常一律静默跳过。 */
export function paintNavigationBar(color) {
  // #ifdef APP-PLUS
  try {
    if (typeof plus === 'undefined' || !plus.os || plus.os.name !== 'Android') return
    if (!plus.android || !plus.android.runtimeMainActivity) return
    const Color = plus.android.importClass('android.graphics.Color')
    plus.android.importClass('android.view.Window')
    const window = plus.android.runtimeMainActivity().getWindow()
    window.setNavigationBarColor(Color.parseColor(color))
  } catch (e) { /* 设不了就维持系统默认，不影响业务 */ }
  // #endif
}

/* ---------- 系统通知与角标（App 端 HTML5+ Push 本地通知；H5/小程序静默 no-op） ---------- */
const hasPush = () => typeof plus !== 'undefined' && plus && plus.push

/** 当前平台是否支持本地系统通知调度 */
export function notifySupported() { return hasPush() }

/** 主动拉起通知权限（Android 13+ POST_NOTIFICATIONS；iOS 由首次建通知触发） */
export function requestNotifyPermission() {
  if (!hasPush()) return
  try {
    if (plus.os && plus.os.name === 'Android' && plus.android && plus.android.requestPermissions) {
      plus.android.requestPermissions(['android.permission.POST_NOTIFICATIONS'], () => {}, () => {})
    }
  } catch (e) { /* ignore */ }
}

/** 系统通知权限是否开启（Android 查 NotificationManager；iOS/查询失败视为开启，避免误报） */
export function areNotificationsEnabled() {
  if (!hasPush()) return true
  try {
    if (plus.os && plus.os.name === 'Android' && plus.android) {
      const Context = plus.android.importClass('android.content.Context')
      const main = plus.android.runtimeMainActivity()
      const nm = main.getSystemService(Context.NOTIFICATION_SERVICE)
      plus.android.importClass(nm)
      return typeof nm.areNotificationsEnabled === 'function' ? !!nm.areNotificationsEnabled() : true
    }
  } catch (e) { /* 查询不了按开启处理 */ }
  return true
}

/** 打开本应用的系统通知设置（Android 直达通知页，异常回退应用详情页；iOS 进应用设置） */
export function openNotificationSettings() {
  try {
    if (typeof plus !== 'undefined' && plus.os && plus.os.name === 'Android' && plus.android) {
      const main = plus.android.runtimeMainActivity()
      const Intent = plus.android.importClass('android.content.Intent')
      const Settings = plus.android.importClass('android.provider.Settings')
      const intent = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
      intent.putExtra(Settings.EXTRA_APP_PACKAGE, main.getPackageName())
      intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
      main.startActivity(intent)
      return
    }
    if (typeof plus !== 'undefined' && plus.runtime) plus.runtime.openURL('app-settings:')
  } catch (e) {
    try {
      /* Android 8 以下无通知设置直达页：回退到应用详情页 */
      const main = plus.android.runtimeMainActivity()
      const Intent = plus.android.importClass('android.content.Intent')
      const Settings = plus.android.importClass('android.provider.Settings')
      const Uri = plus.android.importClass('android.net.Uri')
      const intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts('package', main.getPackageName(), null))
      intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
      main.startActivity(intent)
    } catch (e2) { /* ignore */ }
  }
}

/**
 * 调度一条本地系统通知（到点由系统送达，App 退后台/被杀仍生效）
 * @param {{ id: string, title: string, content: string, when: number }} job when=epoch 毫秒
 */
export function scheduleLocalNotice(job) {
  if (!hasPush()) return
  try {
    plus.push.createMessage(job.content, JSON.stringify({ id: job.id }), {
      title: job.title,
      when: new Date(job.when),
      sound: 'system'
    })
  } catch (e) { /* 通知调度失败不阻断业务 */ }
}

/** 清空已排期/通知中心的本地通知（重排前调用） */
export function clearLocalNotices() {
  if (!hasPush()) return
  try { plus.push.clear() } catch (e) { /* ignore */ }
}

/** 设置应用图标右上角未读角标数（0=清除） */
export function setBadgeNumber(n) {
  try {
    if (typeof plus !== 'undefined' && plus && plus.runtime && plus.runtime.setBadgeNumber) {
      plus.runtime.setBadgeNumber(Math.max(0, n | 0))
    }
  } catch (e) { /* ignore */ }
}

/** 监听通知点击/由通知拉起（payload 为 scheduleLocalNotice 写入的 JSON） */
export function onNoticeClick(handler) {
  if (!hasPush()) return
  const parse = e => {
    let p = e && e.payload
    if (typeof p === 'string') { try { p = JSON.parse(p) } catch (err) { p = null } }
    return p || {}
  }
  try {
    plus.push.addEventListener('click', e => handler(parse(e)), false)
    plus.push.addEventListener('launch', e => handler(parse(e)), false)
  } catch (e) { /* ignore */ }
}

/* ---------- 触感震动（App 端原生通道；其它端返回 '' 交调用方回落） ----------
 * 为什么不能直接用 uni.vibrateShort：App 端 runtime 把它实现成写死的 plus.device.vibrate(15)，
 * type（light/medium/heavy）参数整段丢弃、且无条件走 success 回调，
 * 所以需求表 §五 的轻重分级与 20/40/60ms 时长在 App 真机上全部落不了地
 * ——15ms 单脉冲多数机型几乎无感，用户侧的表现就是「设置了震动但机子不震」。
 * 这里按 §五 的原始单位下单：Android 走 Vibrator + VibrationEffect（工程内唯一能带幅度的通道），
 * 幅度拿不到时退 plus.device.vibrate(ms)（只认时长、系统默认幅度）。
 * iOS 没有短震与幅度概念（系统只有一次固定长震），多段波形收敛成一次，避免连成一片长震。 */
let _vibrator = null

function _androidVibrator() {
  if (_vibrator) return _vibrator
  try {
    const main = plus.android.runtimeMainActivity()
    /* Context.VIBRATOR_SERVICE 的字面量就是 "vibrator"，静态常量不便经反射读取 */
    _vibrator = main.getSystemService('vibrator')
    plus.android.importClass(_vibrator)
    if (!_vibrator || typeof _vibrator.hasVibrator !== 'function' || !_vibrator.hasVibrator()) _vibrator = null
  } catch (e) { _vibrator = null }
  return _vibrator
}

/** 单段震动，返回实际通道标识（'' = 两条通道都没打通） */
function _androidShot(ms, amp) {
  const v = _androidVibrator()
  if (v) {
    try {
      const VibrationEffect = plus.android.importClass('android.os.VibrationEffect')
      const eff = VibrationEffect.createOneShot(ms, amp)   // amp 取 1–255，§五 的量纲即此
      if (eff) { v.vibrate(eff); return 've' }
    } catch (e) { /* API<26 或厂商 ROM 不支持幅度：降到只认时长 */ }
  }
  try { plus.device.vibrate(ms); return 'plus' } catch (e) { return '' }
}

/**
 * 播放一段具名震动波形（需求表 §五）
 * @param {Array<{delay: number, ms: number, amp: number}>} steps delay=该段起点(相对触发)，ms=时长，amp=幅度 0–255
 * @returns {string} ''=本端未接管（H5/小程序，或原生通道不可用），调用方须回落到 uni.vibrateShort；
 *                   非空为实际通道标识，供真机定位用
 */
export function vibratePattern(steps) {
  if (!steps || !steps.length) return ''
  if (typeof plus === 'undefined' || !plus || !plus.os) return ''
  try {
    if (plus.os.name === 'Android') {
      let tag = ''
      steps.forEach((s, i) => {
        const fire = () => { const t = _androidShot(s.ms, s.amp); if (!tag) tag = t }
        if (i === 0) fire()
        else setTimeout(fire, s.delay)
      })
      return tag ? 'android:' + tag : ''
    }
    if (plus.os.name === 'iOS') {
      plus.device.vibrate(steps[0].ms || 400)
      return 'ios:once'
    }
  } catch (e) { /* 原生通道异常同样交回调用方回落 */ }
  return ''
}

