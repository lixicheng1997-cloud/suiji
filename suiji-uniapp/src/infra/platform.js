/**
 * 岁记 · 平台差异收口（TDD §4.3：唯一允许接触 plus.* 的文件）
 * App 端（HTML5+）优先用 plus.sqlite / plus.io / plus.runtime；
 * H5 与小程序端回退到 uni storage（同步、本地、零网络）。
 * 迁库（如换框架）时只需重写本文件，领域层与仓储 API 不变。
 */

import { PHONE_AUTH_PLUGIN, PHONE_AUTH_SDK_INFO, PHONE_AUTH_H5_SDK, PHONE_AUTH_H5_GLOBAL } from '@/config/app.js'

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
 * 令牌必须持久化（否则每次冷启动都要重新登录）。
 *
 * 历史教训（2026-11-16 排查报告）：早期这里用「设备标识 + 应用内盐」做 XOR
 * 混淆落盘，但混淆密钥掺了 uni.getSystemInfoSync().deviceId——该标识由框架本地
 * 随机生成、清 Storage 即变，存/读两次密钥不一致时令牌会被还原成含控制字符的
 * 坏串，拼进 Authorization 头被 webview 拒绝（setRequestHeader 抛错、请求中断）。
 * 故方案 A 直接明文落盘，不再做这层可逆混淆：它本就防不住拿到完整设备权限的
 * 攻击者（那需要系统级 Keystore/Keychain，uni-app 无统一接口），安全收益有限，
 * 却引入了往返损坏风险。令牌合法性/字符集校验在 api/http.js 出口统一兜底。
 */
/* 旧版本混淆存储使用的前缀键，仅在清理时一并删除遗留数据，新代码不再读取 */
const SECRET_PREFIX = 'sj_sec_'

export function kvSetSecret(key, val) {
  const s = String(val == null ? '' : val)
  if (!s) { kvRemove(key); kvRemove(SECRET_PREFIX + key); return }
  try { kvSet(key, s) } catch (e) { /* 存储失败按未保存处理 */ }
}
export function kvGetSecret(key) {
  try { return kvGet(key) || '' } catch (e) { return '' }
}
export function kvRemoveSecret(key) {
  kvRemove(key)
  kvRemove(SECRET_PREFIX + key)   // 清掉旧版本遗留的混淆键
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

/* ---------- App 端原生覆盖控件（plus.nativeObj.View） ----------
 * 背景：App-vue 页面里 video 是原生控件，层级高于 webview 内普通 DOM / cover-view，
 * 普通按钮既盖不上去也点不到。这里用 plus.nativeObj.View 在原生层绘制可点按钮。
 * 仅 APP-PLUS 可用；H5 / 小程序一律返回 null，上层回退普通 view / cover-view 模板。
 * 架构约束：plus.* 只允许出现在本文件（TDD §4.3）。
 */

/** 当前环境是否支持原生覆盖控件 */
export function nativeOverlaySupported() {
  // #ifdef APP-PLUS
  try { return typeof plus !== 'undefined' && !!(plus.nativeObj && plus.nativeObj.View) } catch (e) { return false }
  // #endif
  return false
}

/**
 * 创建一个原生覆盖按钮（独立 View、独立点击回调，不做坐标热区命中）
 * @param {Object} o
 * @param {string} o.id 唯一标识
 * @param {{top:string,left:string,width:string,height:string}} o.rect 相对屏幕区域，单位 px 字符串
 * @param {string} [o.bg] 背景色 rgba() / #RRGGBB；空串表示透明
 * @param {string} [o.text] 文案
 * @param {string} [o.color] 文字颜色，默认 #FFFFFF
 * @param {number} [o.fontSize] 字号 px
 * @param {boolean} [o.bold] 是否加粗，默认 true
 * @param {number|string} [o.radius] 背景圆角半径 px（数字）或带单位字符串；不传为直角
 * @param {Function} [o.onClick] 点击回调；不传则为纯展示控件
 * @returns {null|{setText(t:string):void, setOpacity(n:number):void, destroy():void}}
 */
export function createNativeButton(o) {
  // #ifdef APP-PLUS
  try {
    if (!nativeOverlaySupported()) return null
    const view = new plus.nativeObj.View(o.id, {
      top: o.rect.top,
      left: o.rect.left,
      width: o.rect.width,
      height: o.rect.height,
      backgroundColor: 'rgba(0,0,0,0)'
    })
    const bg = o.bg || ''
    if (bg) {
      /* radius 传入时按 RectStyles 对象绘制圆角矩形；否则保持原字符串颜色直角矩形 */
      const styles = o.radius
        ? { color: bg, radius: typeof o.radius === 'number' ? o.radius + 'px' : o.radius }
        : bg
      view.drawRect(styles, { top: '0px', left: '0px', width: '100%', height: '100%' }, o.id + '-bg')
    }
    const drawTx = (txt) => {
      view.drawText(txt, { top: '0px', left: '0px', width: '100%', height: '100%' }, {
        size: (o.fontSize || 14) + 'px',
        color: o.color || '#FFFFFF',
        align: 'center',
        verticalAlign: 'middle',
        weight: o.bold === false ? 'normal' : 'bold'
      }, o.id + '-tx')
    }
    drawTx(o.text || '')
    if (typeof o.onClick === 'function') {
      view.addEventListener('click', () => { try { o.onClick() } catch (e) { /* 回调异常不影响原生控件 */ } }, false)
    }
    view.show()
    return {
      setText(t) { drawTx(t) },
      setOpacity(n) { try { view.setStyle({ opacity: n }) } catch (e) { /* 低版本不支持则忽略 */ } },
      destroy() { try { view.close() } catch (e) { /* ignore */ } }
    }
  } catch (e) { return null }
  // #endif
  return null
}

/* ---------- 小程序 SVG 兜底切换（第 9 项一期） ----------
 * 微信小程序 <image> 不支持 SVG（Android 真机尤为明显），H5/App 正常。
 * 本函数把 /static/anim|loading/*.svg 路径切换为同名 3× .png（由
 * scripts/gen-mp-png.mjs 离线生成），其他端原样返回。
 * 一期取静态基础帧，动效降级为静图；二期可补 sprite 帧动画。 */
export function mpSrc(path) {
  // #ifdef MP-WEIXIN
  return path.replace(/\.svg$/, '.png')
  // #endif
  // #ifndef MP-WEIXIN
  return path
  // #endif
}

/* ---------- 阿里云号码认证（一键登录 / 本机号码校验） ----------
 * 平台差异继续收口在本文件：App 端走 uni.requireNativePlugin（原生插件），
 * H5 端动态注入网页版 SDK；小程序端不支持（恒返回 null）。
 * 任何失败——插件缺失 / 标准基座 / 未插 SIM / 运营商不支持 / SDK 加载失败——
 * 一律 resolve(null)，由上层静默回退账号密码登录，UI 不阻塞不报错。
 * 令牌均为一次性：服务端 GetMobile / VerifyPhone 用掉即废，无重放风险。
 *
 * 插件市场地址：https://ext.dcloud.net.cn/plugin?id=4297
 * 插件名：AliCloud-NirvanaPns
 * 官方文档：https://help.aliyun.com/zh/pnvs/developer-reference/uni-app-access
 * 实际 API 契约（App 端）：
 *   setAuthSDKInfo(info)                          — 必调，设置控制台密钥
 *   checkEnvAvailable(authType, cb)               — 1=本机校验, 2=一键登录
 *   accelerateLoginPage(timeout, cb)              — 一键登录前预取（建议提前 2~3 秒）
 *   getLoginToken(timeout, config, tokenCb, uiCb, customCb) — 唤起授权页
 *   quitLoginPage()                               — 关闭授权页
 *   accelerateVerify(timeout, cb)                 — 本机校验前预取
 *   getVerifyToken(timeout, cb)                   — 获取校验令牌（不需要 phone 参数）
 *   回调 resultCode === "600000" 表示成功 */

/* App 端插件懒加载 + 密钥初始化（只初始化一次） */
let _appPluginInited = false
function getAppPlugin() {
  // #ifdef APP-PLUS
  try {
    const plugin = uni.requireNativePlugin(PHONE_AUTH_PLUGIN)
    if (!plugin) return null
    if (!_appPluginInited) {
      _appPluginInited = true
      if (PHONE_AUTH_SDK_INFO) {
        plugin.setAuthSDKInfo(PHONE_AUTH_SDK_INFO)
      }
    }
    return plugin
  } catch (e) { return null }
  // #endif
  // eslint-disable-next-line no-unreachable
  return null
}

/* H5 网页版 SDK 懒加载（只注一次；超时/失败均按不支持处理） */
let _h5SdkLoading = null
function loadH5Sdk() {
  // #ifdef H5
  if (typeof window !== 'undefined' && window.PHONE_AUTH_SDK_READY) {
    return Promise.resolve(window[PHONE_AUTH_H5_GLOBAL])
  }
  if (_h5SdkLoading) return _h5SdkLoading
  _h5SdkLoading = new Promise(resolve => {
    const s = document.createElement('script')
    let done = false
    const finish = ok => {
      if (done) return
      done = true
      window.PHONE_AUTH_SDK_READY = !!ok
      _h5SdkLoading = null
      resolve(ok ? window[PHONE_AUTH_H5_GLOBAL] : null)
    }
    s.src = PHONE_AUTH_H5_SDK
    s.async = true
    s.onload = () => finish(!!window[PHONE_AUTH_H5_GLOBAL])
    s.onerror = () => finish(false)
    document.head.appendChild(s)
    setTimeout(() => finish(false), 8000)
  })
  return _h5SdkLoading
  // #endif
  // eslint-disable-next-line no-unreachable
  return Promise.resolve(null)
}

/** 当前平台是否具备号码认证能力（按钮显隐用；能力探测失败按钮自动隐藏） */
export async function phoneAuthSupported() {
  // #ifdef APP-PLUS
  const plugin = getAppPlugin()
  if (!plugin) return false
  return new Promise(resolve => {
    try {
      plugin.checkEnvAvailable(2, res => {
        resolve(!!res && res.resultCode === '600000')
      })
    } catch (e) { resolve(false) }
  })
  // #endif
  // #ifdef H5
  const sdk = await loadH5Sdk()
  return !!sdk
  // #endif
  // eslint-disable-next-line no-unreachable
  return false
}

/** 一键登录预取号（accelerateLoginPage）：提前 2~3 秒调用可让授权页秒开并即时展示本机号码；
 *  官方文档要求仅在未登录场景调用、勿频繁调用，故只在登录页 onLoad 触发一次。
 *  App 端走插件预取；H5 网页 SDK 内部自行预取，此处 no-op。 */
export function prefetchOneClickLogin() {
  // #ifdef APP-PLUS
  const plugin = getAppPlugin()
  if (!plugin || typeof plugin.accelerateLoginPage !== 'function') return
  try { plugin.accelerateLoginPage(5000, () => {}) } catch (e) { /* 预取失败不阻断：getLoginToken 会自行取号 */ }
  // #endif
}

/** 一键登录取号：弹出运营商授权页，用户确认后 resolve(令牌)；失败/取消 resolve(null) */
export function getOneClickToken() {
  // #ifdef APP-PLUS
  return new Promise(resolve => {
    const plugin = getAppPlugin()
    if (!plugin || typeof plugin.getLoginToken !== 'function') return resolve(null)
    try {
      plugin.getLoginToken(
        5000,
        {},
        res => {
          const r = res || {}
          if (r.resultCode === '600000' && r.token) {
            resolve(r.token)
          } else {
            resolve(null)
          }
        },
        /* uiCallback：授权页生命周期事件（打开/关闭/点击等），按需埋点，此处不处理 */
        () => {},
        /* customUiCallback：自定义授权页 UI 配置，留空使用默认样式 */
        () => {}
      )
    } catch (e) { resolve(null) }
  })
  // #endif
  // #ifdef H5
  return loadH5Sdk().then(sdk => new Promise(resolve => {
    if (!sdk || typeof sdk.getLoginToken !== 'function') return resolve(null)
    try {
      sdk.getLoginToken(res => {
        const r = res || {}
        resolve((r.resultCode === '600000' || r.code === 0 || r.success) && r.token ? r.token : null)
      })
    } catch (e) { resolve(null) }
  }))
  // #endif
  // eslint-disable-next-line no-unreachable
  return Promise.resolve(null)
}

/** 关闭一键登录授权页（用户取消或超时后调用） */
export function quitLoginPage() {
  // #ifdef APP-PLUS
  const plugin = getAppPlugin()
  if (plugin && typeof plugin.quitLoginPage === 'function') {
    try { plugin.quitLoginPage() } catch (e) { /* ignore */ }
  }
  // #endif
}

/** 本机号码校验取号：resolve(令牌)；失败/不匹配 resolve(null)
 * 注意：getVerifyToken 不需要传 phone 参数，token 本身即代表本机号码，
 * 服务端用 VerifyPhone(PhoneNumber=用户输入号, AccessToken=token) 做比对校验。 */
export function getVerifyToken() {
  // #ifdef APP-PLUS
  return new Promise(resolve => {
    const plugin = getAppPlugin()
    if (!plugin || typeof plugin.getVerifyToken !== 'function') return resolve(null)
    try {
      plugin.getVerifyToken(5000, res => {
        const r = res || {}
        resolve(r.resultCode === '600000' && r.token ? r.token : null)
      })
    } catch (e) { resolve(null) }
  })
  // #endif
  // #ifdef H5
  return loadH5Sdk().then(sdk => new Promise(resolve => {
    if (!sdk || typeof sdk.getVerifyToken !== 'function') return resolve(null)
    try {
      sdk.getVerifyToken(res => {
        const r = res || {}
        resolve((r.resultCode === '600000' || r.code === 0 || r.success) && r.token ? r.token : null)
      })
    } catch (e) { resolve(null) }
  }))
  // #endif
  // eslint-disable-next-line no-unreachable
  return Promise.resolve(null)
}


