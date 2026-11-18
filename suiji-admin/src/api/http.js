/**
 * 岁记管理后台 · HTTP 层（fetch 版，接线逻辑对齐 suiji-uniapp/src/api/http.js）
 *
 * 职责：信封加密（算法在 ./crypto.js，与服务端 payload_crypto.py 严格对应）、
 * JWT 注入、401 单飞刷新重试一次、409 密钥轮换重取公钥重试、服务端时间校正、错误映射。
 *
 * 加密清单必须与服务端 app/core/payload_crypto.py 对齐：
 *   /auth/login|register|refresh|logout|password|deactivate 精确路径；
 *   /admin/* 前缀强制加密，但 /content 结尾的媒体字节通道豁免
 *   （<img>/<video> 无法带信封头，媒体靠受限 media 令牌鉴权）。
 * 管理端「始终发加密请求」：拿不到公钥直接报错，绝不静默降级成明文发口令。
 */
import { clearPublicKey, hasPublicKey, sealRequest, setPublicKey, supported } from './crypto'

const BASE = '/api/v1'
const ACCESS_KEY = 'sj_admin_access'
const REFRESH_KEY = 'sj_admin_refresh'
const MEDIA_KEY = 'sj_admin_media'
const RSA_KEY = 'sj_admin_rsa'

/* ---------- 令牌存取（localStorage） ---------- */
const TOKEN_SEG_RE = /^[A-Za-z0-9_-]+$/
function isValidToken(t) {
  if (typeof t !== 'string' || !t) return false
  const parts = t.split('.')
  return parts.length === 3 && parts.every(p => p.length > 0 && TOKEN_SEG_RE.test(p))
}
function readToken(key) {
  const t = localStorage.getItem(key)
  return isValidToken(t) ? t : ''
}
export function getAccessToken() { return readToken(ACCESS_KEY) }
export function getRefreshToken() { return readToken(REFRESH_KEY) }
export function getMediaToken() { return readToken(MEDIA_KEY) }
export function setTokens(access, refresh, media) {
  if (access) localStorage.setItem(ACCESS_KEY, access)
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  if (media) localStorage.setItem(MEDIA_KEY, media)
}
export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem(MEDIA_KEY)
}

/* ---------- 加密路径判定（与服务端口径一致） ---------- */
const ENC_EXACT_RE = /^\/auth\/(register|login|password|deactivate|refresh|logout)$/
function isEncPath(path) {
  if (ENC_EXACT_RE.test(path)) return true
  return path.startsWith('/admin/') && !path.endsWith('/content')
}

/* ---------- 公钥：内存 → sessionStorage → 网络 ---------- */
let keyFetching = null

function loadKeyCache() {
  try {
    const raw = sessionStorage.getItem(RSA_KEY)
    if (!raw) return
    const info = JSON.parse(raw)
    if (info && info.n && info.e) setPublicKey(info)
  } catch (e) { /* 坏缓存按「没有公钥」处理 */ }
}

function ensurePublicKey() {
  if (hasPublicKey()) return Promise.resolve(true)
  loadKeyCache()
  if (hasPublicKey()) return Promise.resolve(true)
  if (keyFetching) return keyFetching
  keyFetching = fetch(BASE + '/crypto/public-key')
    .then(res => (res.ok ? res.json() : Promise.reject(new Error('key http ' + res.status))))
    .then(d => {
      const ok = !!(d && d.n && d.e)
      if (ok) {
        setPublicKey(d)
        try { sessionStorage.setItem(RSA_KEY, JSON.stringify({ kid: d.kid, n: d.n, e: d.e })) } catch (e) { /* 存不下每次重取 */ }
      }
      return ok
    })
    .catch(() => false)
    .then(ok => { keyFetching = null; return ok })
  return keyFetching
}

export function refreshPublicKey() {
  clearPublicKey()
  try { sessionStorage.removeItem(RSA_KEY) } catch (e) { /* ignore */ }
  return ensurePublicKey()
}

/* ---------- 服务端时间校正：时间戳参与 HMAC，本机漂移太大会被判重放 ---------- */
let timeOffset = 0
function syncServerTime(res) {
  const d = res.headers.get('date')
  if (!d) return
  const t = Date.parse(d)
  if (!isNaN(t)) timeOffset = t - Date.now()
}
function nowMs() { return Date.now() + timeOffset }

async function sealFor(method, path, data) {
  if (!isEncPath(path)) return null
  if (!supported()) throw makeError('当前浏览器不支持加密传输，请使用现代浏览器', 'no bigint')
  const ok = await ensurePublicKey()
  if (!ok) throw makeError('无法获取服务端加密公钥，请检查网络', 'no public key')
  // AAD 里的 path 必须与服务端 scope["path"] 逐字一致：含 /api/v1 前缀、不含 ?query
  // （服务端信封中间件取的是不含查询串的路径，带 query 会解密失败）
  return sealRequest(BASE + path.split('?')[0], data === undefined ? undefined : data, nowMs())
}

/* ---------- 底层请求 ---------- */
const NO_AUTH_RE = /^\/auth\/(login|register|refresh)$/

async function rawRequest(method, path, data) {
  const sealed = await sealFor(method, path, data)
  const headers = {}
  if (sealed) Object.assign(headers, sealed.header)
  const token = NO_AUTH_RE.test(path) ? '' : getAccessToken()
  if (token) headers.Authorization = 'Bearer ' + token
  let body
  if (data !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(sealed ? sealed.data : data)
  }
  let res
  try {
    res = await fetch(BASE + path, { method, headers, body })
  } catch (e) {
    throw makeError('网络连接失败，请检查后端服务是否启动', String(e))
  }
  syncServerTime(res)
  const ct = res.headers.get('content-type') || ''
  let out
  if (ct.indexOf('application/json') >= 0) out = await res.json().catch(() => ({}))
  else out = await res.text()
  if (sealed && typeof out === 'object' && out !== null) {
    const opened = sealed.open(out)
    if (opened === null && out.enc !== undefined) {
      throw makeError('数据校验失败，请重试', 'decrypt failed', res.status)
    }
    if (opened !== null) out = opened
  }
  return { status: res.status, data: out }
}

/* ---------- 401 单飞刷新 ---------- */
let refreshing = null
function tryRefresh() {
  if (refreshing) return refreshing
  const refresh = getRefreshToken()
  if (!refresh) return Promise.resolve(false)
  refreshing = rawRequest('POST', '/auth/refresh', { refresh })
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

/* ---------- 会话过期回调（main.js 注入 router 跳转，避免模块循环） ---------- */
let expireHandler = null
export function setExpireHandler(fn) { expireHandler = typeof fn === 'function' ? fn : null }
let expiring = false
function expireSession() {
  if (expiring) return
  expiring = true
  clearTokens()
  if (expireHandler) { try { expireHandler() } catch (e) { /* ignore */ } }
  setTimeout(() => { expiring = false }, 1000)
}

/* ---------- 错误对象 ---------- */
function makeError(friendly, raw, status) {
  const e = new Error(friendly || '操作失败，请稍后再试')
  e.friendly = friendly || '操作失败，请稍后再试'
  e.raw = raw || ''
  e.status = status || 0
  return e
}

const INTERNAL_DETAIL = /(Traceback|Exception|Error:|sqlalchemy|psycopg|pydantic|SELECT |INSERT |UPDATE |DELETE |\.(py|js|ts):|\/[a-z]+\/api\/)/i

function mapError(res) {
  const detail = res.data && res.data.detail
  const raw = Array.isArray(detail)
    ? detail.map(d => (d && d.msg) || String(d)).join('；')
    : (detail ? String(detail) : '')
  const shown = raw && INTERNAL_DETAIL.test(raw) ? '' : raw
  const s = res.status || 0
  if (s === 400) return makeError(shown || '请求有误，请检查后重试', raw, s)
  if (s === 401) return makeError(shown || '登录已过期，请重新登录', raw, s)
  if (s === 403) return makeError(shown || '没有权限执行该操作', raw, s)
  if (s === 404) return makeError(shown || '内容不存在或已被删除', raw, s)
  if (s === 409) return makeError(shown || '数据有冲突，请刷新后重试', raw, s)
  if (s === 422) return makeError(shown || '提交的内容有误，请检查后重试', raw, s)
  if (s === 429) return makeError('操作太频繁了，休息一下再试试', raw, s)
  if (s >= 500) return makeError('服务器开小差了，请稍后再试', raw, s)
  return makeError(shown || ('请求失败（' + s + '）'), raw, s)
}

/* ---------- 统一请求入口 ---------- */
const AUTH_NO_RETRY_RE = /^\/auth\/(login|refresh)$/

/**
 * @param {object} [opts] { silent }：silent=true 时失败不弹全局提示（由调用方自行处理）
 */
export function request(method, path, data, opts) {
  const o = opts || {}
  return rawRequest(method, path, data)
    .then(res => {
      if (res.status === 409 && res.data && res.data.detail === '密钥已更新，请重试' && !o._keyRetried) {
        return refreshPublicKey()
          .then(() => request(method, path, data, Object.assign({}, o, { _keyRetried: true })))
      }
      if (res.status === 401 && !o._retried && !AUTH_NO_RETRY_RE.test(path)) {
        return tryRefresh().then(ok => {
          if (!ok) {
            expireSession()
            throw makeError('登录已过期，请重新登录', '', 401)
          }
          return request(method, path, data, Object.assign({}, o, { _retried: true }))
        })
      }
      if (res.status >= 200 && res.status < 300) return res.data
      throw mapError(res)
    })
}

export function get(path, opts) { return request('GET', path, undefined, opts) }
export function post(path, data, opts) { return request('POST', path, data, opts) }

/* ---------- 媒体地址：content 通道基础路径 + 受限 media 令牌 ---------- */
/**
 * 把后端返回的 thumb_url/content_url（/api/v1/admin/media/{id}/content?...）拼上 media 令牌。
 * 令牌进 query 会落进 access_log/浏览器历史，所以只放「只能下载、不能调业务接口」的受限令牌。
 */
export function mediaUrl(u) {
  if (!u) return ''
  const t = getMediaToken()
  if (!t) return u
  return u + (u.indexOf('?') >= 0 ? '&' : '?') + 'token=' + encodeURIComponent(t)
}
