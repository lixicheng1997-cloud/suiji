/**
 * 岁记 · HTTP 客户端层（TDD v3.0 §4.2：统一 base URL，禁止页面散落 uni.request）
 * 职责：请求封装 / JWT 注入 / 401 刷新重试一次 / 错误码映射（TDD §12）/ 媒体上传。
 * 本机 kv 只保留两类键：token（sj_token_*）与服务器地址（sj_api_base），业务数据一律不落本地。
 */
import { kvGet, kvSet, kvRemove, kvGetSecret, kvSetSecret, kvRemoveSecret } from '@/infra/platform.js'
import { DEFAULT_BASE, LEGACY_PORT, CURRENT_PORT } from '@/config/app.js'
import { toast as uiToast } from '@/utils/ui.js'
import { clearPublicKey, hasPublicKey, sealRequest, setPublicKey, supported } from '@/infra/crypto.js'

const BASE_KEY = 'sj_api_base'
/* 「已选服务器」记录键：api.js 复用同一份，避免两处各写一个字符串 */
export const SERVER_KEY = 'sj_server'
const ACCESS_KEY = 'sj_token_access'
const REFRESH_KEY = 'sj_token_refresh'
/* 媒体令牌：只能用于 /files|/media 下载，不能调业务接口。
 * 图片/视频直连（<img src>）无法带 Authorization 头，只能把凭证放进 query；
 * 用专用受限令牌而非 access，即便 URL 泄露也读不到任何结构化数据。 */
const MEDIA_KEY = 'sj_token_media'
/* 兜底地址与端口常量统一来自公共配置 @/config/app.js：
 * 服务器列表已写死在前端配置文件，不再由服务端 /servers（数据库表）下发 */

/* ---------- 服务器地址 ---------- */
/**
 * 把地址里的历史端口换成现役端口（主机与路径保持不变）：
 *   http://localhost:8000/api/v1 → http://localhost:30080/api/v1
 *   http://49.233.77.155:8000/api/v1 → http://49.233.77.155:30080/api/v1
 */
export function upgradePort(url) {
  const s = String(url || '').trim()
  if (!s) return s
  return s.replace(
    new RegExp('^([a-z][a-z0-9+.-]*://[^/:]+):' + LEGACY_PORT + '(?=$|[/?#])', 'i'),
    '$1:' + CURRENT_PORT
  )
}

/**
 * 一次性迁移本机已保存的服务器地址（读取地址时触发，幂等）。
 * 旧版本把地址写进了本机 Storage（sj_api_base / sj_server），
 * 只改代码里的默认值并不会覆盖它——客户端会一直请求历史端口 8000。
 * 这里在读地址时把旧端口就地升级为 30080，并同步修正「已选服务器」记录，
 * 保证用户此前选定的主机（本地/云端）不变，只换端口。
 */
let portUpgraded = false
function ensurePortUpgraded() {
  if (portUpgraded) return
  portUpgraded = true
  const raw = kvGet(BASE_KEY)
  if (raw) {
    const fixed = upgradePort(raw)
    if (fixed !== raw) kvSet(BASE_KEY, fixed)
  }
  try {
    const s = JSON.parse(uni.getStorageSync(SERVER_KEY) || '')
    if (s && s.url) {
      const fixed = upgradePort(s.url)
      if (fixed !== s.url) {
        uni.setStorageSync(SERVER_KEY, JSON.stringify(Object.assign({}, s, { url: fixed })))
      }
    }
  } catch (e) { /* 记录损坏按未选择处理 */ }
}

/**
 * 服务器地址合法性校验。
 *
 * 这个地址决定「账号密码和 JWT 发给谁」——客户端会在登录页把口令 POST 过去。
 * 列表写死在前端公共配置文件，但仍可能被本机篡改（Storage 里的历史值 / 手工改包），
 * 不加校验就等于把全部凭证主动交给攻击者。所以这里强制三件事：
 *   1. 必须是 http/https（挡掉 file:、javascript:、data: 之类的伪协议）
 *   2. 必须带 host（挡掉相对路径 / 空值）
 *   3. 路径必须以 /api/v1 结尾（契约固定的基址形状，顺带挡掉任意站点）
 * 不通过一律返回空串，调用方按「未设置」处理并回落到 DEFAULT_BASE。
 */
export function sanitizeBase(url) {
  const s = String(url || '').trim().replace(/\/+$/, '')
  if (!s) return ''
  if (!/^https?:\/\/[^\s/?#]+/i.test(s)) return ''      // 协议 + host
  if (!/\/api\/v1$/i.test(s)) return ''                  // 契约固定的基址后缀
  return s
}

export function baseUrl() {
  ensurePortUpgraded()
  const saved = kvGet(BASE_KEY)
  return sanitizeBase(saved) || DEFAULT_BASE
}
export function setBaseUrl(url) {
  // 端口升级后再校验：顺序反了会把带旧端口的合法地址直接判掉
  const v = sanitizeBase(upgradePort(String(url || '').trim()))
  if (v) kvSet(BASE_KEY, v)
  else kvRemove(BASE_KEY)
}
/** 本机是否已保存过服务器地址（用于区分「首次启动」与「沿用已有地址」） */
export function hasSavedBase() {
  ensurePortUpgraded()
  return !!kvGet(BASE_KEY)
}

/* ---------- Token 存取 ----------
 * access 2 小时 / refresh 30 天（服务端一次性轮换）/ media 7 天（仅下载）。
 * 三件套必须一起换：refresh 是轮换式的，老 refresh 用过即废，
 * 只更新 access 会导致下次刷新被判定重放并强制下线。
 * 落盘走 kv*Secret：不明文写 Storage（见 infra/platform.js 的说明）。 */
export function getAccessToken() { return kvGetSecret(ACCESS_KEY) || '' }
export function getRefreshToken() { return kvGetSecret(REFRESH_KEY) || '' }
export function getMediaToken() { return kvGetSecret(MEDIA_KEY) || '' }
export function setTokens(access, refresh, media) {
  if (access) kvSetSecret(ACCESS_KEY, access)
  if (refresh) kvSetSecret(REFRESH_KEY, refresh)
  if (media) kvSetSecret(MEDIA_KEY, media)
}
export function clearTokens() {
  kvRemoveSecret(ACCESS_KEY)
  kvRemoveSecret(REFRESH_KEY)
  kvRemoveSecret(MEDIA_KEY)
}

/* ---------- 媒体地址解析：服务端返回 /api/v1/... 相对路径 → 绝对 URL ----------
 * /files/{id}/download 追加 ?token=（契约 §7.5：img/video 标签无法携带 Authorization 头）；
 * 本地临时路径（blob:/wxfile:/_doc/ 等）原样透传，供选图后即时预览。 */
export function resolveUrl(u) {
  if (!u) return ''
  const s = String(u)
  const base = baseUrl()
  const origin = (base.match(/^(https?:\/\/[^/]+)/i) || ['', ''])[1]
  if (/^(https?:)/i.test(s)) {
    /* 绝对地址只认当前服务器同域：服务端返回的图片地址被污染成外链时，
     * 直接加载既会泄漏 Referer（带 token 的 URL），也可能把用户引到钓鱼页。 */
    return s.indexOf(origin + '/') === 0 ? s : ''
  }
  if (/^(data:|blob:|file:|wxfile:)/i.test(s)) return s   // 本地临时路径：选图后即时预览
  if (s.charAt(0) !== '/') return s
  let url = origin + s
  if (/^\/api\/v1\/(files|media)\//.test(s) && s.indexOf('token=') < 0) {
    /* 只放受限的 media 令牌：服务端已拒绝把 access 放进 query，
     * 这里若回落到 access，图片会直接 403；拿不到 media 就不带 token，
     * 由调用方决定是否走带 Header 的下载，绝不拿 access 去换可用性。 */
    const t = getMediaToken()
    if (t) url += (url.indexOf('?') < 0 ? '?' : '&') + 'token=' + encodeURIComponent(t)
  }
  return url
}

/**
 * 列表缩略图地址：在 resolveUrl 基础上追加 &variant=thumb。
 * 服务端对图片返回 400px 宽的预生成 JPEG（通常 50-150KB），
 * 而不是 3-10MB 的原图；变体不存在时服务端自动回退原图，不会 404。
 * 详情页/点开放大仍用 resolveUrl 拿原图。
 */
export function resolveThumb(u) {
  const url = resolveUrl(u)
  if (!url) return ''
  // 只对 /files/{id}/download 和 /media/{id} 加 variant；其他地址（静态图标、本地临时路径）不动
  if (!/^\/api\/v1\/(files|media)\//.test(String(u).split('?')[0])) return url
  if (url.indexOf('variant=') >= 0) return url
  return url + (url.indexOf('?') < 0 ? '?' : '&') + 'variant=thumb'
}

/* ---------- 传输加密：敏感接口端到端加密（详见 infra/crypto.js 头注释） ----------
 * 客户端与服务端之间是明文 HTTP：口令、令牌三件套、邀请码、导出数据在链路上裸奔，
 * 这一层让「链路被看穿」也不等于「明文被拿走」：
 *   RSA-OAEP-256 用服务端公钥封装一次性会话密钥 → AES-256-CBC + HMAC-SHA256 加密报文。
 * 服务端私钥从不下发，所以只有真正的服务端能解开会话密钥。
 *
 * 清单必须与服务端 app/core/payload_crypto.py 的 ENCRYPTED_PATHS 逐条对齐，
 * 否则一边加密一边不解密，接口会直接 400。
 * 照片/视频等大文件刻意不在清单内：几百 MB 在 JS 里做对称加密会卡死主线程。 */
export const ENC_PATH_RE = /^\/(auth\/(register|login|password|refresh|logout)|family\/(join|invite)|export\/data)$/

const RSA_KEY = 'sj_rsa_key'    // 公钥缓存（换服务器 / 服务端轮换密钥时按 kid 失效重取）
let keyFetching = null

function loadKeyCache() {
  try {
    const raw = kvGet(RSA_KEY)
    if (!raw) return
    const info = JSON.parse(raw)
    if (info && info.n && info.e) setPublicKey(info)
  } catch (e) { /* 坏缓存按「没有公钥」处理，会走一次网络重取 */ }
}

/**
 * 取服务端 RSA 公钥：内存 → 本机缓存 → 网络。
 *
 * 公钥本身不是秘密（真正的秘密是服务端私钥），所以这个接口无需鉴权；
 * 拿不到时返回 false，调用方退回明文——服务端 CRYPTO_MODE=required 时明文会被拒绝，
 * 宁可报「网络不可用」也不要静默把口令明文发出去。
 */
function ensurePublicKey() {
  if (hasPublicKey()) return Promise.resolve(true)
  loadKeyCache()
  if (hasPublicKey()) return Promise.resolve(true)
  if (keyFetching) return keyFetching
  keyFetching = new Promise(resolve => {
    uni.request({
      url: baseUrl() + '/crypto/public-key',
      method: 'GET',
      timeout: 15000,
      success: res => {
        const d = res && res.data
        if (res && res.statusCode === 200 && d && d.n && d.e) {
          setPublicKey(d)
          try { kvSet(RSA_KEY, JSON.stringify({ kid: d.kid, n: d.n, e: d.e })) } catch (e) { /* 存不下就每次重取 */ }
          resolve(true)
        } else {
          resolve(false)
        }
      },
      fail: () => resolve(false)
    })
  }).then(ok => { keyFetching = null; return ok })
  return keyFetching
}

/** 服务端轮换密钥后（接口返回「密钥已更新」）清缓存重取一次 */
export function refreshPublicKey() {
  clearPublicKey()
  try { kvRemove(RSA_KEY) } catch (e) { /* ignore */ }
  return ensurePublicKey()
}

/* 服务端时间校正：时间戳参与 HMAC 且服务端有 ±5 分钟窗口，
 * 本机时钟漂太多会被直接判成重放。用响应头 Date 持续校正，不额外发请求。 */
let timeOffset = 0
function syncServerTime(res) {
  const h = res && res.header
  const d = h && (h.Date || h.date)
  if (!d) return
  const t = Date.parse(d)
  if (!isNaN(t)) timeOffset = t - Date.now()
}
function nowMs() { return Date.now() + timeOffset }

/**
 * 请求前加密：命中清单且拿到公钥时返回密文包 {header, data, open}，否则返回 null（明文）。
 * @returns {Promise<object|null>}
 */
async function sealFor(method, path, data) {
  if (!ENC_PATH_RE.test(path)) return null
  if (!supported()) return null          // 无 BigInt 的老引擎：只能明文
  const ok = await ensurePublicKey()
  if (!ok) return null
  // AAD 里的 path 必须与服务端 scope["path"] 完全一致——服务端用的是含
  // /api/v1 前缀的完整 URL 路径（见 payload_crypto.py 的 ENCRYPTED_PATHS），
  // 这里传的是 baseUrl() 之后的相对路径，必须补回前缀，否则 HMAC 校验失败、
  // 敏感接口一律 400「加密载荷无效」。baseUrl 由 sanitizeBase 强制以 /api/v1 结尾。
  return sealRequest('/api/v1' + path, data === undefined ? undefined : data, nowMs())
}

/* ---------- 底层请求 ---------- */
async function rawRequest(method, path, data, header) {
  const sealed = await sealFor(method, path, data).catch(() => null)
  const token = getAccessToken()
  const res = await new Promise((resolve, reject) => {
    uni.request({
      url: baseUrl() + path,
      method,
      // 加密时 body 换成密文信封（无 body 的请求 data 保持 undefined）
      data: sealed ? sealed.data : (data === undefined ? undefined : JSON.parse(JSON.stringify(data))),
      timeout: 30000,
      header: Object.assign(
        { 'Content-Type': 'application/json' },
        token ? { Authorization: 'Bearer ' + token } : {},
        header || {},
        sealed ? sealed.header : {}
      ),
      // uni.request 响应字段为 statusCode，统一补 status 供上层判断
      success: res => resolve(Object.assign({}, res, { status: res.statusCode })),
      fail: err => reject(Object.assign(new Error('NET_FAIL'), { netFail: true, raw: err }))
    })
  })
  syncServerTime(res)
  if (!sealed) return res
  const opened = sealed.open(res.data)
  if (opened === null) {
    // 2xx 却解不开 = 响应被篡改或密钥错乱：绝不能把密文当业务数据往下传
    const e = makeError('数据校验失败，请重试', 'decrypt failed', res.status || 0, 2)
    throw e
  }
  return Object.assign({}, res, { data: opened })
}

/* 401 → 用 refresh 换三件套的单飞表（并发请求共享一次刷新）。
 * 服务端 refresh 是一次性的：每次刷新都会下发新的 refresh，必须整组落盘；
 * 若服务端未返回某一项（旧版本兼容），沿用本机旧值。 */
let refreshing = null
function tryRefresh() {
  if (refreshing) return refreshing
  const refresh = getRefreshToken()
  if (!refresh) return Promise.resolve(false)
  refreshing = rawRequest('POST', '/auth/refresh', { refresh }, { Authorization: '' })
    .then(res => {
      if (res.status >= 200 && res.status < 300 && res.data && res.data.access) {
        const d = res.data
        setTokens(d.access, d.refresh || '', d.media || '')
        return true
      }
      return false
    })
    .catch(() => false)
    .then(ok => { refreshing = null; return ok })
  return refreshing
}

/**
 * 服务端登出：撤销当前 access 并作废 refresh。
 * 只清本地令牌是不够的——服务端无状态，不清账本的话旧令牌在寿命内（access 2 小时）仍可用。
 * 失败不阻断：网络不通时也必须能退出本地会话。
 * @returns {Promise<boolean>} 服务端是否确认撤销
 */
export function logoutRemote() {
  const refresh = getRefreshToken()
  const access = getAccessToken()
  if (!access) return Promise.resolve(false)
  return rawRequest('POST', '/auth/logout', { refresh })
    .then(res => res.status >= 200 && res.status < 300)
    .catch(() => false)
}

function expireSession() {
  /* 并发在途请求会各自撞到 401 → 各自调用这里：不去重的话就是 N 条提示 + N 次 reLaunch，
     登录页被反复重启，用户看到的是「闪屏 + 一直退回」 */
  if (expiring) return
  expiring = true
  clearTokens()
  if (expireHandler) { try { expireHandler() } catch (e) { /* 清理失败不影响下线流程 */ } }
  uiToast('登录已过期，请重新登录', 2200, 'warn')
  setTimeout(() => {
    uni.reLaunch({ url: '/pages/login/login', complete: () => { expiring = false } })
  }, 300)
}

/* ---------- 家庭门控：409 need_family ----------
 * 账号尚未关联家庭时服务端拒绝一切业务接口；这里统一强制回退到引导页
 * （创建家庭 / 邀请码加入二选一）。清缓存的动作由 utils/first-run.js 注册的 handler 完成，
 * 本层不反向依赖状态层以避免模块循环。 */
const FAMILY_SETUP = '/pages/family-setup/family-setup'
let needFamilyHandler = null
export function setNeedFamilyHandler(fn) {
  needFamilyHandler = typeof fn === 'function' ? fn : null
}
/** 会话过期（401 刷新失败）回调注册：由 first-run.js 注入状态层清理（清内存缓存/停轮询），同样避免模块循环 */
let expireHandler = null
/* expireSession 去重门：一次过期只提示一次、只跳一次登录页 */
let expiring = false
export function setExpireHandler(fn) {
  expireHandler = typeof fn === 'function' ? fn : null
}
function isNeedFamily(res) {
  const d = res && res.data && res.data.detail
  return d === 'need_family'
}
/** 服务端换了 RSA 密钥：本机缓存的 kid 已失效，重取公钥后自动重试一次 */
function isKeyRotated(res) {
  const d = res && res.data && res.data.detail
  return d === '密钥已更新，请重试'
}
function needFamilyError() {
  return makeError('请先创建家庭，或用邀请码加入家庭', 'need_family', 409, 8)
}

/* ---------- 错误对象：message 就是给用户看的友好文案 ---------- */
const GENERIC_FAIL = '操作失败，请稍后再试'

/**
 * 构造带友好文案的错误：
 *   e.friendly / e.message → 弹给用户的文案；e.raw → 服务端原文（排查用）；
 *   e.weight → 同批多条错误时的展示优先级（越大越优先）。
 */
function makeError(friendly, raw, status, weight) {
  const e = new Error(friendly || GENERIC_FAIL)
  e.friendly = friendly || GENERIC_FAIL
  e.raw = raw || ''
  e.status = status || 0
  e.weight = weight || 0
  return e
}
/** 会话过期已由 expireSession 提示过，标记为已提示避免二次弹窗 */
function mutedError(friendly) {
  const e = makeError(friendly, '', 401, 9)
  e.__notified = true
  return e
}

/** 网络层失败：区分超时与断网（uni.request 的 fail.errMsg 形如 request:fail timeout） */
function netError(err) {
  const msg = (err && err.raw && err.raw.errMsg) || ''
  const friendly = /timeout/i.test(msg) ? '请求超时，请检查网络后重试' : '网络连接失败，请检查网络后重试'
  return makeError(friendly, msg, 0, 3)
}

/* 服务端 detail 里偶然会带上堆栈、SQL、文件路径——这些不能弹给用户，
 * 弹出去等于把后端实现细节送出去。业务文案（如「邀请码无效」）要保留，
 * 所以只过滤掉明显属于内部错误的特征串。 */
const INTERNAL_DETAIL = /(Traceback|Exception|Error:|sqlalchemy|psycopg|pydantic|SELECT |INSERT |UPDATE |DELETE |\.(py|js|ts):|\/[a-z]+\/api\/)/i

/** FastAPI 错误体 {detail} → 用户可读文案（TDD §12 / 契约 §15） */
function mapError(res) {
  const detail = res.data && res.data.detail
  /* 422 的 detail 是 pydantic 英文校验信息，只留作 raw，不直接给用户看 */
  const raw = Array.isArray(detail)
    ? detail.map(d => (d && d.msg) || String(d)).join('；')
    : (detail ? String(detail) : '')
  /* 内部错误特征串一律不回显，只留 raw 供排查 */
  const shown = raw && INTERNAL_DETAIL.test(raw) ? '' : raw
  const s = res.status || 0
  if (s === 400) return makeError(shown || '请求有误，请检查后重试', raw, s, 1)
  if (s === 403) return makeError(shown || '当前是只读模式，暂时不能修改', raw, s, 1)
  if (s === 404) return makeError(shown || '内容不存在或已被删除', raw, s, 1)
  if (s === 409) return makeError(shown || '数据有冲突，请刷新后重试', raw, s, 1)
  if (s === 422) return makeError('提交的内容有误，请检查后重试', raw, s, 1)
  if (s === 429) return makeError('操作太频繁了，休息一下再试试', raw, s, 2)
  if (s >= 500) return makeError('服务器开小差了，请稍后再试', raw, s, 2)
  return makeError(shown || ('请求失败（' + s + '）'), raw, s, 1)
}

/* ---------- 统一错误提示：接口报错一律友好提示给用户 ---------- */
let presenter = null        // 自定义展示器 (msg, err) => void，默认走 ui.toast
let lastMsg = ''
let lastAt = 0
let queue = []
let flushing = false

/**
 * 自定义错误展示方式（例如改用弹窗）：
 *   http.setErrorPresenter(msg => ui.alert({ title: '出错了', content: msg }))
 * @param {Function|null} fn 传 null 恢复默认轻提示
 */
export function setErrorPresenter(fn) {
  presenter = typeof fn === 'function' ? fn : null
}

/**
 * 排队提示：Promise 的 catch 属微任务，一定早于本函数的 setTimeout，
 * 因此页面若在 catch 里自行提示（ui.error / 赋值 __notified），兜底提示会自动取消。
 */
function notify(err, opts) {
  if (!err || err.__notified) return
  if (opts && opts.silent) { err.__notified = true; return }
  /* 非对象（字符串 reject 等）无法打标记，直接提示，避免严格模式下赋值报错 */
  if (typeof err !== 'object') { uiToast(String(err), 2600, 'err'); return }
  if (!err.friendly) err.friendly = err.message || GENERIC_FAIL
  err.__pending = true
  queue.push(err)
  if (!flushing) { flushing = true; setTimeout(flushNotify, 0) }
}

function flushNotify() {
  flushing = false
  const list = queue
  queue = []
  const now = Date.now()
  /* 同一批（多为并发 bootstrap）只提示最重要的一条，避免连续弹窗刷屏 */
  list.sort((a, b) => (b.weight || 0) - (a.weight || 0))
  for (let i = 0; i < list.length; i++) {
    const err = list[i]
    err.__pending = false
    if (err.__notified) continue        // 页面已自行提示
    err.__notified = true
    if (i > 0) continue                 // 同批只展示权重最高的一条
    if (err.friendly === lastMsg && now - lastAt < 2000) continue   // 同文案 2s 内不重复
    if (now - lastAt < 1200) continue   // 短时间内已有提示，静默后续
    lastMsg = err.friendly
    lastAt = now
    if (presenter) presenter(err.friendly, err)
    else uiToast(err.friendly, 2600, 'err')
  }
}

/**
 * 统一请求入口：自动带 Token；401 刷新后重试一次；错误映射为 Error(message)。
 * 例外：/auth/login、/auth/refresh 自身的 401 不参与自动刷新——这两个接口失败
 * 必须把服务端的具体原因（用户名不存在 / 密码错误等）原样回给页面，
 * 否则会被「登录已过期」吞掉并踢回登录页，用户永远看不到真正的失败原因。
 * @param {string} method GET/POST/PUT/PATCH/DELETE
 * @param {string} path 以 / 开头的 API 路径（相对 baseUrl）
 * @param {object} [data] JSON 请求体
 * @param {{header?: object, silent?: boolean}} [opts] silent=true 表示失败不弹提示（轮询/预拉取）
 */
const AUTH_NO_RETRY_RE = /^\/auth\/(login|refresh)$/

export function request(method, path, data, opts) {
  const o = opts || {}
  return rawRequest(method, path, data, o.header)
    .then(res => {
      if (res.status === 409 && isKeyRotated(res) && !o._keyRetried) {
        return refreshPublicKey()
          .then(() => request(method, path, data, Object.assign({}, o, { _keyRetried: true })))
      }
      if (res.status === 401 && !o._retried && !AUTH_NO_RETRY_RE.test(path)) {
        return tryRefresh().then(ok => {
          if (!ok) { expireSession(); throw mutedError('登录已过期，请重新登录') }
          return request(method, path, data, Object.assign({}, o, { _retried: true }))
        })
      }
      if (res.status === 409 && isNeedFamily(res)) {
        const e = needFamilyError()
        notify(e, o)
        if (needFamilyHandler) needFamilyHandler()
        else uni.reLaunch({ url: FAMILY_SETUP })
        throw e
      }
      if (res.status >= 200 && res.status < 300) return res.data
      throw mapError(res)
    })
    .catch(err => {
      const e = (err && err.netFail) ? netError(err) : err
      notify(e, o)
      throw e
    })
}

/* 便捷方法：第三个参数可直接传 header 对象（如 { 'Idempotency-Key': x }），
 * 也可传 { header, silent }；silent=true 时接口失败不弹提示。 */
export function get(path, opts) { return request('GET', path, undefined, opts) }
export function post(path, data, opts) { return request('POST', path, data, normOpts(opts)) }
export function put(path, data, opts) { return request('PUT', path, data, normOpts(opts)) }
export function patch(path, data, opts) { return request('PATCH', path, data, normOpts(opts)) }
export function del(path, data, opts) { return request('DELETE', path, data, normOpts(opts)) }

/** 兼容两种写法：opts 既可当 header 用，也可写 { header, silent } */
function normOpts(opts) {
  if (opts && (opts.header !== undefined || opts.silent !== undefined)) return opts
  return { header: opts }
}

/* 允许上传的扩展名（与服务端 app/media/safety.py 的白名单保持一致）。
 * 前端先挡一次，避免用户选了不支持的文件白等一轮上传才被 422 拒绝。
 * 刻意排除 html/htm/svg/xml/js：这些被下载端点内联渲染就是存储型 XSS。 */
export const ALLOWED_UPLOAD_EXT = /\.(jpe?g|png|gif|webp|bmp|heic|heif|avif|tiff|mp4|mov|m4v|webm|3gp|mp3|m4a|aac|wav|ogg|flac|pdf|txt|csv|json|zip)$/i

/**
 * 非结构化文件上传：multipart POST /files（契约 §7.5），uni.uploadFile 走同一套鉴权与错误映射。
 * 字节统一入对象存储，业务行只保存返回的文件 URL；挂载点可上传后再经 PATCH /files/{id} 补挂。
 * @param {string} filePath 本地临时文件路径
 * @param {{businessType?: string, businessId?: string, babyId?: string}} [opts] 业务挂载参数
 * @returns {Promise<{id, url, ...}>} 文件行（url 为 /api/v1/files/{id}/download 相对路径）
 */
export function uploadFile(filePath, opts) {
  const o = opts || {}
  /* 只在「文件名带扩展名且不在白名单」时本地拒绝：
   * H5/App 选图返回的多是无扩展名临时路径（blob:/content:/_doc: 末段为 UUID 或数字 id），
   * 扩展名对这类路径不是可靠信号，放行后由服务端 magic bytes 嗅探兜底判定。 */
  const base = String(filePath || '').split('?')[0].split('/').pop()
  const dot = base.lastIndexOf('.')
  const hasExt = dot > 0 && dot < base.length - 1
  if (hasExt && !ALLOWED_UPLOAD_EXT.test(base)) {
    const e = makeError('不支持的文件类型', 'extension not allowed', 422, 2)
    notify(e, o)
    return Promise.reject(e)
  }
  return new Promise((resolve, reject) => {
    const token = getAccessToken()
    uni.uploadFile({
      url: baseUrl() + '/files',
      filePath,
      name: 'file',
      formData: {
        business_type: o.businessType || '',
        business_id: o.businessId || '',
        baby_id: o.babyId || ''
      },
      timeout: 120000,
      header: token ? { Authorization: 'Bearer ' + token } : {},
      success: res => {
        let body = {}
        try { body = JSON.parse(res.data) } catch (e) { /* 非 JSON 走状态码判断 */ }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          /* 批量上传可能 200 带 errors（部分失败），同样要让用户知道 */
          if (Array.isArray(body.errors) && body.errors.length) {
            const n = body.errors.length
            const e = makeError(n + ' 个文件上传失败，请重试', body.errors.map(x => x && (x.detail || x.filename)).join('；'), res.statusCode, 2)
            notify(e, o); reject(e); return
          }
          resolve(body); return
        }
        if (res.statusCode === 401) { expireSession(); reject(mutedError('登录已过期，请重新登录')); return }
        if (res.statusCode === 409 && body && body.detail === 'need_family') {
          const e = needFamilyError()
          notify(e, o)
          if (needFamilyHandler) needFamilyHandler()
          else uni.reLaunch({ url: FAMILY_SETUP })
          reject(e); return
        }
        const e = mapError({ status: res.statusCode, data: body })
        notify(e, o)
        reject(e)
      },
      fail: err => {
        const e = netError(Object.assign(new Error('NET_FAIL'), { netFail: true, raw: err }))
        e.friendly = '文件上传失败，请检查网络后重试'
        notify(e, o)
        reject(e)
      }
    })
  })
}
