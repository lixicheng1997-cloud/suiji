/**
 * 岁记 · 本机分层日志（所有环境采集，数据只存终端本地，可在页面清空）
 *
 * 用途：把业务链路 / 接口 / 上传等信息按级别与模块标签落到本机，
 * 在「我的 → 调试日志」页面分层查看，便于真机 / 小程序排障与问题反馈。
 *
 * 分层：
 *   debug  开发细节（请求出入参摘要、状态流转、进度等，量大，可随时忽略）
 *   info   关键业务节点（启动、bootstrap 成功、登录、切换服务器、上传完成）
 *   warn   可恢复的异常 / 降级 / 重试（409、密钥轮换、上传重试、缓存回退）
 *   error  失败链路（网络失败、接口报错、上传最终失败、未捕获异常）
 *
 * 约束（安全 + 性能）：
 *   - 日志只存本机，不上报服务端；序列化前按键名剔除口令 / 令牌等敏感字段。
 *   - 内存环形缓冲 + 本机 Storage 持久化，条数有上限，不会无限膨胀。
 *   - 控制台（console）同步仅开发环境打开，正式包不向控制台吐日志。
 *
 * 存储：内存环形缓冲（MAX_MEMORY）+ 本机 Storage（MAX_STORE），冷启动后
 * 日志页仍能看到上一轮会话的记录；页面「清空」同时清两处。
 */
import { APP_ENV } from '@/config/app.js'

const IS_DEV = APP_ENV === 'dev'

/* 级别权重：越大越严重 */
export const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 }
export const LEVEL_LABEL = { debug: 'DEBUG', info: 'INFO', warn: 'WARN', error: 'ERROR' }
/* 页面筛选顺序 */
export const LEVEL_ORDER = ['debug', 'info', 'warn', 'error']

const STORE_KEY = 'sj_logs'
const MAX_MEMORY = 500
const MAX_STORE = 1000
/* 持久化节流窗口：高频 debug 不逐条同步写 Storage，合并落盘避免卡主线程 */
const SAVE_DEBOUNCE = 500

/* 运行端类型（条件编译在打包期确定，三端各自命中对应分支） */
let PLATFORM = 'unknown'
// #ifdef H5
PLATFORM = 'H5'
// #endif
// #ifdef MP-WEIXIN
PLATFORM = '微信小程序'
// #endif
// #ifdef APP-PLUS
PLATFORM = 'App'
// #endif

/* 敏感键名：命中即从结构化 data 里剔除，避免口令 / 令牌落进本机日志 */
const SENSITIVE_KEY_RE = /(password|passwd|pwd|token|secret|refresh|access|media_key|authorization|credential|private)/i

let memory = []
let seq = 0

/* ---------- 启动回填：上一轮会话的日志从 Storage 读回内存 ---------- */
function loadPersisted() {
  try {
    const raw = uni.getStorageSync(STORE_KEY)
    const arr = Array.isArray(raw) ? raw : (raw ? JSON.parse(raw) : [])
    if (Array.isArray(arr) && arr.length) {
      memory = arr.filter(isValidEntry).slice(-MAX_MEMORY)
      seq = memory.reduce((m, x) => Math.max(m, Number(x.id) || 0), 0)
    }
  } catch (e) { /* 损坏的日志缓存直接丢弃，不阻断启动 */ memory = [] }
}

let saveTimer = null
function flushPersist() {
  saveTimer = null
  try {
    const slice = memory.slice(-MAX_STORE)
    uni.setStorageSync(STORE_KEY, JSON.stringify(slice))
  } catch (e) { /* Storage 配额不足 / 隐私模式：保留内存态即可 */ }
}
function persist() {
  if (saveTimer) return
  saveTimer = setTimeout(flushPersist, SAVE_DEBOUNCE)
}

/* ---------- 序列化 ---------- */
function sanitize(value, depth) {
  if (depth > 4) return '[depth-limit]'
  if (value instanceof Error) return { message: value.message, stack: String(value.stack || '').split('\n').slice(0, 3).join(' ↩ ') }
  if (Array.isArray(value)) return value.map(v => sanitize(v, depth + 1))
  if (value && typeof value === 'object') {
    const out = {}
    Object.keys(value).forEach(k => {
      if (SENSITIVE_KEY_RE.test(k)) { out[k] = '[hidden]'; return }
      out[k] = sanitize(value[k], depth + 1)
    })
    return out
  }
  return value
}

function serialize(data) {
  if (data === undefined || data === null) return ''
  const clean = sanitize(data, 0)
  try { return JSON.stringify(clean) } catch (e) { return String(clean) }
}

/* 列表过滤：级别 / 模块标签 / 关键词，getLogs 与 counts 共用同一口径 */
function applyFilter(list, f) {
  let l = list
  if (f.level && LEVELS[f.level] != null) l = l.filter(x => x.level === f.level)
  if (f.tag) l = l.filter(x => x.tag === f.tag)
  if (f.q) {
    const q = String(f.q).toLowerCase()
    l = l.filter(x => x.msg.toLowerCase().includes(q) || x.tag.toLowerCase().includes(q))
  }
  return l
}

/* 估算字符串 UTF-8 字节数（三端无 TextEncoder 时的手写兜底） */
function utf8Bytes(str) {
  let n = 0
  for (let i = 0; i < str.length; i++) {
    const c = str.charCodeAt(i)
    if (c < 0x80) n += 1
    else if (c < 0x800) n += 2
    else n += 3
  }
  return n
}

function pad(n, w) { return String(n).padStart(w, '0') }
function fmtTime(ts) {
  const d = new Date(ts)
  return pad(d.getHours(), 2) + ':' + pad(d.getMinutes(), 2) + ':' + pad(d.getSeconds(), 2) + '.' + pad(d.getMilliseconds(), 3)
}
function fmtDate(ts) {
  const d = new Date(ts)
  return d.getFullYear() + '-' + pad(d.getMonth() + 1, 2) + '-' + pad(d.getDate(), 2)
}

/* 条目形状校验：回填坏缓存时过滤掉缺字段 / 级别非法的记录 */
function isValidEntry(x) {
  return x && typeof x === 'object' && LEVELS[x.level] != null && typeof x.msg === 'string'
}

/* 同步到控制台：各端 console 方法不齐，逐级回退到 log */
function toConsole(level, tag, msg, data) {
  const line = '[' + tag + '] ' + msg
  const fn = (console && (console[level] || console.log)) || console.log
  if (typeof fn !== 'function') return
  try {
    if (data !== undefined && data !== null) fn.call(console, line, data)
    else fn.call(console, line)
  } catch (e) { /* 控制台写入失败不影响业务 */ }
}

/* ---------- 写入 ---------- */
function push(level, tag, msg, data) {
  const ts = Date.now()
  const entry = {
    id: ++seq,
    ts,
    date: fmtDate(ts),
    time: fmtTime(ts),
    platform: PLATFORM,
    level,
    tag: String(tag || 'app'),
    msg: String(msg == null ? '' : msg),
    data: serialize(data)
  }
  memory.push(entry)
  if (memory.length > MAX_MEMORY) memory.splice(0, memory.length - MAX_MEMORY)
  persist()
  /* 控制台同步仅开发环境打开：正式包不向 webview / 调试器吐日志 */
  if (IS_DEV) toConsole(level, entry.tag, entry.msg, data)
}

export const logger = {
  /** 当前编译环境：'dev' | 'prod'（页面展示用，不做访问门控） */
  appEnv: APP_ENV,
  /** 当前运行端类型：H5 / 微信小程序 / App */
  platform: PLATFORM,
  isDev: IS_DEV,
  debug: (tag, msg, data) => push('debug', tag, msg, data),
  info: (tag, msg, data) => push('info', tag, msg, data),
  warn: (tag, msg, data) => push('warn', tag, msg, data),
  error: (tag, msg, data) => push('error', tag, msg, data),

  /**
   * 读取日志（默认时间正序：旧 → 新）。
   * @param {{level?: string, tag?: string, q?: string}} [filter] level 取某一级；
   *   tag 精确匹配模块；q 模糊匹配消息 / 标签。
   */
  getLogs(filter) {
    return applyFilter(memory, filter || {}).slice()
  },

  /**
   * 各级别条数（页面筛选 tab 角标用）；可传入与列表一致的筛选口径，
   * 使模块 / 关键词过滤下的级别计数与当前列表对齐。
   */
  counts(filter) {
    const c = { debug: 0, info: 0, warn: 0, error: 0 }
    applyFilter(memory, filter || {}).forEach(x => { if (c[x.level] != null) c[x.level]++ })
    return c
  },

  /** 本机日志占用字节数：优先取已持久化内容，节流未落盘时回退内存序列化估算 */
  sizeBytes() {
    let raw = null
    try { raw = uni.getStorageSync(STORE_KEY) } catch (e) { /* 回退内存估算 */ }
    if (raw == null) return utf8Bytes(JSON.stringify(memory))
    const s = typeof raw === 'string' ? raw : JSON.stringify(raw)
    return utf8Bytes(s)
  },

  /** 结构化 data 美化：可解析的 JSON 缩进输出，否则原样返回 */
  formatData(str) {
    if (!str) return ''
    try { return JSON.stringify(JSON.parse(str), null, 2) } catch (e) { return str }
  },

  /** 出现过的模块标签（去重，按首次出现顺序） */
  tags() {
    const seen = []
    memory.forEach(x => { if (!seen.includes(x.tag)) seen.push(x.tag) })
    return seen
  },

  /** 清空内存与本机持久化日志 */
  clear() {
    memory = []
    seq = 0
    if (saveTimer) { clearTimeout(saveTimer); saveTimer = null }
    try { uni.removeStorageSync(STORE_KEY) } catch (e) { /* ignore */ }
  },

  /**
   * 导出为纯文本（复制 / 落盘用）。
   * @param {Array} [entries] 指定条目；缺省导出全部内存日志
   */
  exportLogs(entries) {
    const list = entries || memory
    return list.map(x => {
      const head = '[' + (x.date || '') + ' ' + x.time + '] ' + LEVEL_LABEL[x.level] + ' ' + x.tag + ' · ' + x.msg
      return x.data ? head + '\n    ' + x.data : head
    }).join('\n')
  }
}

loadPersisted()

export default logger
