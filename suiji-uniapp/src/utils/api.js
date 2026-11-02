/**
 * 岁记 · 数据门面（状态层出口）
 * 页面只调本文件，不直接触碰仓储（TDD §4.2 分层硬约束）。
 * 出入参形状与原型 utils/mock.js 渲染结构保持一致，页面模板零改动。
 * 云端版（TDD v3.0 §0 缓存镜像模式）：数据不落本地——
 *   启动 bootstrap 拉全量灌入内存缓存，同步 getter 只读缓存（签名与旧本地版一致）；
 *   写操作先乐观更新缓存再调 REST，失败 reject（页面已有错误提示）；
 *   派生逻辑（时光轴分组 / summary / 生长曲线 / 疫苗状态 / 今日统计 / 家庭动态）
 *   继续用 domain/ 纯函数在客户端计算，数据源为云端缓存（本机不再落业务库）。
 */
import * as http from '@/api/http.js'
import * as notify from '@/infra/notify.js'
import { saveTextFile, pickTextFile, notifySupported, areNotificationsEnabled, openNotificationSettings } from '@/infra/platform.js'
import { parsePack } from '@/infra/backup.js'
import { genId } from '@/domain/shared/id.js'
import { now, dayKey, timeOf, dayLabel, ageText, ageMonths, monthDay, daysBetween } from '@/domain/shared/date.js'
import { summarize } from '@/domain/summary.js'
import { todayStats as calcTodayStats } from '@/domain/stats.js'
import { chartData, chartDataDays, percentileOf, percentileBadge } from '@/domain/growth.js'
import { vaccineStatus, vaccineTip, daysToPlan, planDateFor, VACCINE_STATUS_TEXT } from '@/domain/vaccine.js'
import { PARENT_INFO, REMIND_DEFAULT, VACCINE_PROGRAM } from '@/utils/mock.js'
import { error as uiError, toast as uiToast } from '@/utils/ui.js'
import { SERVERS, MESSAGE_POLL_INTERVAL } from '@/config/app.js'

/* ---------- 内存缓存（= GET /bootstrap 响应镜像，契约 §3） ---------- */
const cache = {
  user: null,
  family: null,            // {id,name,readonly,role,members:[...]}
  active_baby_id: '',
  babies: [],
  entries: [],             // 未软删
  measurements: [],
  media: [],               // entry_media 行
  milestone_records: [],
  vaccines: [],
  journals: [],            // ai_journal 行
  settings: {},            // account/parent/switches/consent/remind/backupFlags/family/ai/trash...
  trash: []                // 已软删 entry 行（含 deleted_at/deleted_by）
}

function resetCache() {
  cache.user = null
  cache.family = null
  cache.active_baby_id = ''
  cache.babies = []
  cache.entries = []
  cache.measurements = []
  cache.media = []
  cache.milestone_records = []
  cache.vaccines = []
  cache.journals = []
  cache.settings = {}
  cache.trash = []
}

function fillCache(s) {
  cache.user = s.user || null
  cache.family = s.family || null
  cache.active_baby_id = s.active_baby_id || ''
  cache.babies = Array.isArray(s.babies) ? s.babies : []
  cache.entries = Array.isArray(s.entries) ? s.entries : []
  cache.measurements = Array.isArray(s.measurements) ? s.measurements : []
  cache.media = Array.isArray(s.media) ? s.media : []
  cache.milestone_records = Array.isArray(s.milestone_records) ? s.milestone_records : []
  cache.vaccines = Array.isArray(s.vaccines) ? s.vaccines : []
  cache.journals = Array.isArray(s.journals) ? s.journals : []
  cache.settings = s.settings && typeof s.settings === 'object' ? s.settings : {}
  cache.trash = Array.isArray(s.trash) ? s.trash : []
}

/**
 * 服务端返回 409 need_family（家庭归属被创建者移除 / 尚未关联）时清掉家庭维度缓存，
 * 使 hasFamily() 判定为 false，路由守卫据此把用户强制留在引导页。
 */
export function resetFamilyCache() {
  cache.family = null
  cache.active_baby_id = ''
  cache.babies = []
  cache.entries = []
  cache.measurements = []
  cache.media = []
  cache.milestone_records = []
  cache.vaccines = []
  cache.journals = []
  cache.trash = []
}

/* 服务端列表端点兼容裸数组、{rows:[...]}、{items:[...]} 三种包装 */
function rowsOf(r) { return Array.isArray(r) ? r : (r && Array.isArray(r.rows) ? r.rows : (r && Array.isArray(r.items) ? r.items : [])) }

/* ---------- 认证与会话 ---------- */
export function isLoggedIn() { return !!http.getAccessToken() }
/** 系统管理员：服务端 user.is_admin=1（启动自动播种的内置账号），据此放开「我的」页专属入口 */
export function isAdmin() {
  const u = cache.user || {}
  return u.is_admin === 1 || u.is_admin === true
}
/** 登录账号（当前用户 username，家长信息页只读展示用） */
export function getUsername() { return (cache.user || {}).username || '' }
/** 注册昵称（家长信息未填昵称时的展示兜底；与登录账号同名视为未设置） */
export function getNickname() {
  const u = cache.user || {}
  return u.name && u.name !== u.username ? u.name : ''
}
export function serverUrl() { return http.baseUrl() }
export function setServerUrl(url) { http.setBaseUrl(url) }

/* ---------- 服务器地址（写死在前端公共配置 config/app.js，页面只读 + 选择） ----------
 * 不再从服务端 /servers（server_endpoint 表）拉取；换环境/加地址只改配置文件。
 * 存储键与 http.js 共用（http.js 负责旧端口 8000 → 30080 的一次性迁移）。 */
const SERVER_KEY = http.SERVER_KEY

/** 当前选中的服务器行；未选择过（首次启动）时只有 url（id/name 为空） */
export function currentServer() {
  const url = http.baseUrl()
  try {
    const s = JSON.parse(uni.getStorageSync(SERVER_KEY) || '')
    if (s && s.url === url) return s
  } catch (e) { /* 缓存损坏按未选择处理 */ }
  return { id: '', name: '', url }
}
/** 展示文案：有名字显示名字，否则退化为去掉协议头的地址 */
export function serverLabel() {
  const s = currentServer()
  return s.name || String(s.url || '').replace(/^https?:\/\//, '')
}
/** 可选服务器列表：直接读前端公共配置（config/app.js），不再请求服务端 /servers */
export function fetchServers() {
  return Promise.resolve(SERVERS.filter(s => s && s.url))
}
/** 选中某条：改 base url 并记下展示信息（登录页/「我的」页共用） */
export function setServer(row) {
  const s = row || {}
  http.setBaseUrl(s.url)
  /* 取最终地址（http.setBaseUrl 已做旧端口升级），保证记录与实际请求地址一致 */
  const url = http.baseUrl()
  try {
    uni.setStorageSync(SERVER_KEY, JSON.stringify({ id: s.id || '', name: s.name || '', url }))
  } catch (e) { /* 存储失败不影响本次请求地址 */ }
}
/** 连通性探测：GET /crypto/public-key 为公开端点（不依赖数据库），未登录也能用来判断地址可达 */
export function pingServer() {
  return http.get('/crypto/public-key', { silent: true }).then(() => true).catch(() => false)
}
/** 首次启动（本机没选过）时按配置里的 is_default 落一个默认地址 */
export function pickDefaultServer() {
  const cur = currentServer()
  if (cur.id) return Promise.resolve(cur)
  /* 本机已有保存的地址（老版本遗留、端口已迁移到 30080）：沿用它，
   * 不再被服务端默认项覆盖（否则本地调试地址会被云端地址顶掉） */
  if (http.hasSavedBase()) return Promise.resolve(cur)
  return fetchServers().then(list => {
    const d = list.find(s => s.is_default) || list[0]
    if (d) setServer(d)
    return currentServer()
  })
}

/* ---------- 账号维度本机数据（同设备多账号防串号） ----------
 * 业务数据全在服务端（缓存镜像，不落本机），本机只有 3 个按账号归属的 key：
 * sj_notices（通知账本）/ sj_msg_read（消息中心已读态）/ sj_events_cursor + sj_events_ver（动态双水位）。
 * 这里记录当前账号标记（sj_account），登录时比对——换了账号就清掉上一账号的本机残留，
 * 避免新账号看到旧账号的通知/角标/已读态。 */
const ACCOUNT_KEY = 'sj_account'

function accountMarker() {
  try { return uni.getStorageSync(ACCOUNT_KEY) || '' } catch (e) { return '' }
}
function setAccountMarker(m) {
  try { m ? uni.setStorageSync(ACCOUNT_KEY, m) : uni.removeStorageSync(ACCOUNT_KEY) } catch (e) { /* ignore */ }
}

/** 清空所有按账号归属的本机数据（通知账本连带撤销未送达的系统通知并清角标） */
function purgeAccountData() {
  try { uni.removeStorageSync(EVENTS_CURSOR_KEY) } catch (e) { /* ignore */ }
  try { uni.removeStorageSync(MSG_READ_KEY) } catch (e) { /* ignore */ }
  notify.clearLedger()
}

/**
 * 登录/注册成功后记账当前账号；与上次标记不同（含升级后首次登录）则清掉残留。
 * 标记优先用服务端 user.id，退化为 username。
 */
function applyAccount(r) {
  const u = (r && r.user) || {}
  const marker = u.id ? 'u:' + u.id : (u.username || '')
  if (accountMarker() !== marker) purgeAccountData()
  setAccountMarker(marker)
}

export function login(username, password) {
  return http.post('/auth/login', { username, password }).then(r => {
    applyAccount(r)
    http.setTokens(r.access, r.refresh, r.media)
    cache.user = r.user || null
    cache.family = r.family || null
    clearEventsCursor()   // 换账号/换家庭：旧水位作废，首次探测重新初始化
    return r
  })
}

export function register(username, password, name) {
  const body = { username, password }
  if (name) body.name = name
  return http.post('/auth/register', body).then(r => {
    applyAccount(r)
    http.setTokens(r.access, r.refresh, r.media)
    cache.user = r.user || null
    cache.family = r.family || null
    clearEventsCursor()
    return r
  })
}

/**
 * 修改密码：服务端校验旧密码后写入新哈希，并抬高令牌水位线（其他设备全部下线），
 * 同时重签本机三件套令牌——必须用返回值覆盖本地令牌，否则旧令牌已失效会被踢出。
 */
export function changePassword(oldPassword, newPassword) {
  return http.post('/auth/password', { old_password: oldPassword, new_password: newPassword }).then(r => {
    http.setTokens(r.access, r.refresh, r.media)
    cache.user = r.user || cache.user
    return r
  })
}

/**
 * 退出登录：先让服务端撤销令牌（access 立即作废、refresh 一并废掉），再清本机会话。
 * 无网/服务端不可达时 logoutRemote 返回 false，本地照样退出并回登录页。
 */
export function logout() {
  return http.logoutRemote().then(() => {
    http.clearTokens()
    resetCache()
    stopEventsPolling()
    clearEventsCursor()
    purgeAccountData()   // 通知账本/已读态不跨账号残留
    setAccountMarker('')
    uni.reLaunch({ url: '/pages/login/login' })
  })
}

/**
 * 会话被服务端判过期（401 刷新失败，http 层经 setExpireHandler 转交——
 * http 层不反向依赖状态层以避免模块循环，与家庭门控 handler 同款做法）。
 * 只清内存缓存与轮询，不清按账号本机数据：同一账号重新登录后已读态/水位仍有意义；
 * 换账号的清理由 login() 的账号标记比对兜底。
 */
export function resetAccountSession() {
  resetCache()
  stopEventsPolling()
  clearEventsCursor()
}

/* ---------- 引导加载 ---------- */
let bootPromise = null
/**
 * 拉全量快照灌入缓存；并发调用共享同一请求（App 启动 + splash 门控只发一次）。
 * @param {{silent?: boolean, force?: boolean}} [opts] silent=true 时失败不弹提示（调用方自行提示）；
 *   force=true 时跳过在途请求复用、强制新发（下拉刷新场景，保证每次都真实重拉）
 */
export function bootstrap(opts) {
  const o = opts || {}
  const run = () => http.get('/bootstrap', o).then(s => {
    fillCache(s); syncEventsWatermark(s); syncNotify(); pullServerNotices(); return s
  })
  if (o.force) return run()
  if (bootPromise) return bootPromise
  bootPromise = run().finally(() => { bootPromise = null })
  return bootPromise
}

/**
 * 初始化：已登录则拉全量填充缓存。
 * @param {{silent?: boolean}} [opts] silent=true 时失败不弹提示（调用方自行提示）
 * @returns {Promise<boolean>} true=缓存就绪；false=未登录或网络失败（调用方决定去登录页）
 */
export function init(opts) {
  if (!isLoggedIn()) return Promise.resolve(false)
  return bootstrap(opts).then(() => true).catch(() => false)
}

/* ---------- 缓存读取小工具 ---------- */
function settingOf(key, dflt) {
  const v = cache.settings[key]
  return v === undefined ? dflt : v
}
function accountName() {
  /* 本机展示兜底名：家长昵称 → 注册昵称 → 账号名。
     落库的记录人/删除人名字由服务端按令牌解析（creator=display_name），不采信这里的值 */
  const u = cache.user || {}
  return (cache.settings.parent || {}).name || u.name || u.username || '妈妈'
}
/** 当前账号 ID：服务端 creator_id 的唯一来源（客户端提交的 ID 服务端不采信） */
function myUserId() {
  return (cache.user || {}).id || ''
}
/** 只读判定：创建者恒可写；非创建者看 family.readonly（服务端 403 兜底） */
function readOnly() {
  const fam = cache.family || {}
  if (fam.role === 'creator') return false
  if (fam.readonly) return true
  return (cache.settings.family || {}).readOnly === true
}

/**
 * 详情/编辑要展示的照片：优先 entry_media 台账行，台账没跟上（编辑换过图、
 * 或本轮乐观更新还没被 bootstrap 覆盖）就直接按 payload.photos 现造一份。
 * 造出来的行只在本次读取里存在，不进缓存——避免同一条记录留下新旧两套 media 行。
 */
function deriveMediaRows(entry) {
  const urls = Array.isArray(entry && entry.payload && entry.payload.photos) ? entry.payload.photos : []
  if (!urls.length) return []
  return urls.map(u => ({
    id: genId('md'), entry_id: entry.id, baby_id: entry.baby_id || '',
    url: u, local_path: u, sha256: '', size: 0, width: 0, height: 0
  }))
}

/* 同步写设置：立即改缓存 + 后台 PUT /settings，失败 toast 并重新 bootstrap 对齐 */
function writeSetting(key, val) {
  cache.settings[key] = val
  http.put('/settings', { key, value: val }).catch(e => {
    uiError(e, '设置同步失败')
    bootstrap().catch(() => { /* 无网时保留本地乐观值 */ })
  })
}

/* 提醒设置/疫苗排期变化后，把开启的提醒重排为系统通知并刷新图标角标（失败不阻断业务）。
 * 家人动态不再本地合成（旧版靠 creator 名字猜「是否本人」会误弹、老记录反复冒通知），
 * 改为服务端落库 → pullServerNotices 拉取合并，此处只负责提醒类通知。 */
function syncNotify() {
  try { notify.sync({ remind: getRemind(), vaccines: cache.vaccines, baby: getBaby() }) }
  catch (e) { /* ignore */ }
}

/* ---------- 家人动态增量探测（方案 A：纯前台轮询） ----------
 * App 在前台时按公共配置 MESSAGE_POLL_INTERVAL（config/app.js）问一次
 * GET /events/count，一个请求同时拿到三样东西：水位比对结果、本人未读通知、
 * 是否真有新增记录。弱网下串行两个请求就是肉眼可见的卡顿，所以通知随探测一起下发
 * （服务端 GET /notifications 仍保留，供消息中心手动刷新用）。
 * 水位两个维度：
 *   - since：已见过的最大 entry.id（两端同算法的 base36 毫秒时间戳 id，字典序即时间序）；
 *   - ver：family.events_version（任何写操作都 bump）。
 * 重拉 bootstrap 只在 new_entries=true 时发生：打卡/勾选/删除/改记录都只 bump 版本
 * 而不新增 id，为它们重下全家快照是上一次改造引入的卡顿主因；这类变更的数据对齐
 * 交给冷启动 bootstrap 与下拉刷新（本机自己操作时缓存已乐观更新，不受影响）。
 * 弹窗去重走本地账本（sj_notices），所以探测不区分是谁操作的。
 * 被杀场景不轮询，靠下次启动 bootstrap 的既有"补弹"机制兜底。 */
const EVENTS_CURSOR_KEY = 'sj_events_cursor'
const EVENTS_VER_KEY = 'sj_events_ver'
let eventsTimer = null
/* 一轮探测在途标记：慢网下 setInterval 的下一拍不该叠出第二份全家快照请求 */
let eventsChecking = false

function clearEventsCursor() {
  try { uni.removeStorageSync(EVENTS_CURSOR_KEY) } catch (e) { /* ignore */ }
  try { uni.removeStorageSync(EVENTS_VER_KEY) } catch (e) { /* ignore */ }
}

/**
 * 把水位对齐到服务端快照：entries 已在缓存里，通知也已由 bootstrap 链拉过，
 * 因此 since/ver 可直接推进到快照值（重登 / 冷启动后不再把存量当成新动态）。
 * @param {{entries?: Array, family?: object}} [snapshot] GET /bootstrap 响应
 */
function syncEventsWatermark(snapshot) {
  const s = snapshot || {}
  try {
    const ids = (Array.isArray(s.entries) ? s.entries : []).map(e => e && e.id).filter(Boolean)
    const max = ids.length ? ids.reduce((a, b) => (String(a) >= String(b) ? a : b)) : ''
    uni.setStorageSync(EVENTS_CURSOR_KEY, max || '0')
    const ver = Number((s.family || {}).events_version || 0)
    uni.setStorageSync(EVENTS_VER_KEY, String(ver))
  } catch (e) { /* ignore */ }
}

/**
 * 单次探测：返回是否发现家庭变更（网络失败静默，下个周期重试）。
 * 一个请求拿齐「水位比对 + 未读通知」：通知直接吃响应里的 notices，不再单独发
 * GET /notifications；只有真新增了记录才重拉全家快照。
 */
export function checkEvents() {
  if (!isLoggedIn()) return Promise.resolve(false)
  /* storage 读写在小程序配额异常/隐私模式下会同步抛错：这里在 setInterval 回调与
     onShow 同步路径上，抛出等于每 tick 一次未捕获错误，且会阻断轮询启动 */
  let since = ''
  let ver = ''
  try {
    since = uni.getStorageSync(EVENTS_CURSOR_KEY) || ''
    ver = uni.getStorageSync(EVENTS_VER_KEY) || ''
  } catch (e) { /* 读不到就按「首次」处理 */ }
  /* 一轮还没跑完（慢网 + 大快照）就不再发第二轮，否则 30s 周期能叠出并发全家快照 */
  if (eventsChecking) return Promise.resolve(false)
  eventsChecking = true
  const url = '/events/count?since=' + encodeURIComponent(since) + '&ver=' + encodeURIComponent(ver)
  const firstSeen = !since && !ver
  return http.get(url, { silent: true })
    .then(r => {
      const notices = (r && r.notices) || []
      /* 水位为空（会话重置/旧版本升级）：先 bootstrap 把水位建起来，存量记录不算"新动态" */
      if (firstSeen) return bootstrap({ force: true, silent: true }).then(() => false).catch(() => false)
      ingestNotices(notices)
      const advanced = !!r && (r.new_entries === true || (r.count || 0) > 0)
      if (advanced) {
        return bootstrap({ force: true, silent: true }).then(() => true).catch(() => false)
      }
      /* 只有版本前进（打卡/勾选/删除/改记录）：就地推进水位，
         下一次探测才会带上新 ver，否则每次轮询都会重复判定 changed 白跑一趟 */
      try {
        if (r && r.cursor) uni.setStorageSync(EVENTS_CURSOR_KEY, r.cursor)
        /* 老服务端不回 version 就保持本地水位，别误写 0 让每轮都判成 changed */
        if (r && r.version != null && r.version !== '') uni.setStorageSync(EVENTS_VER_KEY, String(r.version))
      } catch (e) { /* 水位写不进去最多是下次多拉一次，不该让整轮探测失败 */ }
      return !!(r && r.changed)
    })
    .catch(() => false)
    .then(ok => { eventsChecking = false; return ok })
}

/** 启动前台轮询（App.vue onShow 调）：立即探测一次，之后按 MESSAGE_POLL_INTERVAL 周期探测 */
export function startEventsPolling() {
  stopEventsPolling()
  if (!isLoggedIn()) return
  eventsTimer = setInterval(() => { checkEvents() }, MESSAGE_POLL_INTERVAL)
  checkEvents()
}

/** 停止轮询（App.vue onHide 调）：退到后台不耗电不耗流量 */
export function stopEventsPolling() {
  if (eventsTimer) { clearInterval(eventsTimer); eventsTimer = null }
}

/* ---------- 宝宝档案（同步读缓存；写走 REST） ---------- */
export function getBaby() {
  const b = cache.babies.find(x => x.is_active)
    || cache.babies.find(x => x.id === cache.active_baby_id)
    || cache.babies[0] || null
  if (!b) return null
  return Object.assign({}, b, { age: ageText(b.birth_date, now(), b.gestational_weeks) })
}
export function getBabies() {
  return cache.babies.map(b => Object.assign({}, b, { age: ageText(b.birth_date, now(), b.gestational_weeks) }))
}
export function getBabyById(id) {
  const b = cache.babies.find(x => x.id === id)
  if (!b) return null
  return Object.assign({}, b, { age: ageText(b.birth_date, now(), b.gestational_weeks) })
}
/**
 * 头像/文件展示源：/api/ 相对路径（文件行 url）→ 带 token 的绝对 URL；
 * 本地临时路径（blob:/wxfile:/_doc: 等）与 dataURL 原样透传，供选图后即时预览。
 */
export function fileSrc(u) {
  if (!u) return ''
  return /^\/api\//.test(String(u)) ? http.resolveUrl(u) : u
}
/** 建档：服务端同时初始化里程碑与疫苗排期（契约 §5），返回 Promise<row> */
export function createBaby(data) {
  const row = Object.assign({
    id: genId('baby'), name: '宝宝', birth_date: now().slice(0, 10), gestational_weeks: 40,
    gender: 'boy', birth_length: 0, birth_weight: 0,
    /* 自定义头像（/files 文件 URL）；空表示未设置，页面回退占位图 */
    avatar: '',
    created_at: now(), updated_at: now()
  }, data, { is_active: cache.babies.length ? 0 : 1 })
  cache.babies.push(row)
  return http.post('/babies', row).then(r => {
    const merged = Object.assign({}, row, r || {})
    const i = cache.babies.findIndex(b => b.id === merged.id)
    if (i > -1) cache.babies[i] = merged
    else cache.babies.push(merged)
    /* 服务端建档时已排好疫苗/里程碑，拉回缓存（失败静默，下次 bootstrap 对齐） */
    return ensureVaccineSchedule().then(() => { syncNotify(); return merged })
  }).catch(e => {
    const i = cache.babies.findIndex(b => b.id === row.id)
    if (i > -1) cache.babies.splice(i, 1)
    throw e
  })
}
/** 切换当前档案：同步返回，后台提交；失败 toast + 重新 bootstrap 对齐 */
export function setActiveBaby(id) {
  cache.babies.forEach(b => { b.is_active = b.id === id ? 1 : 0 })
  cache.active_baby_id = id
  http.post('/babies/' + id + '/activate').catch(e => {
    uiError(e, '切换同步失败')
    bootstrap().catch(() => {})
  })
}
export function updateBaby(id, patch) {
  const i = cache.babies.findIndex(b => b.id === id)
  if (i < 0) return Promise.reject(new Error('宝宝档案不存在'))
  const old = cache.babies[i]
  const merged = Object.assign({}, old, patch, { updated_at: now() })
  cache.babies[i] = merged
  return http.put('/babies/' + id, merged).then(r => {
    cache.babies[i] = Object.assign({}, merged, r || {})
    syncNotify()  /* 出生日期变化影响纪念日/疫苗排期 */
    return cache.babies[i]
  }).catch(e => {
    cache.babies[i] = old
    throw e
  })
}

/* ---------- 时光轴（分组派生逻辑与旧版一致，数据源=缓存） ---------- */
const toViewItem = e => ({
  id: e.id, time: timeOf(e.occurred_at), day: dayLabel(dayKey(e.occurred_at)),
  /* 原始日期键（YYYY-MM-DD）：日期行全天条数按它从服务端 day_totals 取值 */
  dk: dayKey(e.occurred_at),
  type: e.type, title: e.title, meta: e.meta || '', creator: e.creator || '',
  /* 记录人账号 ID：展示口径的可靠依据（creator 只是历史名字串） */
  creator_id: e.creator_id || '',
  badge: e.badge || (e.is_backfilled ? 'backfill' : ''), note: e.note || '',
  /* 列表用缩略图（400px 宽 JPEG，~100KB）；点进详情后再用原图 */
  photo: http.resolveThumb(e.photo || ''),
  /* 原始 photo URL 保留，详情页/大图预览用原图 */
  photo_full: http.resolveUrl(e.photo || ''),
  /* 时光轴紧凑播放条只读这几个字段，不整包透出 payload（段地址保持原样，由播放端补 token） */
  voice: e.type === 'voice' ? voiceView(e.payload) : null,
  /* 原始发生时间：首页「进行中」睡眠计时等实时派生用 */
  occurred_at: e.occurred_at
})

/** 语音 payload → 播放所需形状（兼容平铺与 payload.voice 嵌套两种写法） */
function voiceView(p) {
  const v = (p && p.voice) || p || {}
  return {
    segments: Array.isArray(v.segments) ? v.segments : [],
    url: v.url || '',
    duration: Number(v.duration) || 0,
    wave: Array.isArray(v.wave) ? v.wave : []
  }
}

/**
 * 拉取时光轴记录（按日分组，日内按时间升序，与原型 DB.entries 同形状）
 * @param {{ type?: string, limit?: number }} params
 */
export function fetchEntries(params = {}) {
  /* 多宝宝隔离：只展示当前宝宝的记录（无 baby_id 的历史记录视为当前宝宝） */
  const baby = getBaby()
  const babyId = baby ? baby.id : ''
  const rows = cache.entries
    .filter(e => !params.type || params.type === 'all' || e.type === params.type)
    .filter(e => !e.baby_id || e.baby_id === babyId)
    .sort((a, b) => (a.occurred_at < b.occurred_at ? 1 : -1))
  const groups = []
  const map = {}
  rows.forEach(e => {
    const dk = dayKey(e.occurred_at)
    if (!map[dk]) { map[dk] = { day: dayLabel(dk), items: [] }; groups.push(map[dk]) }
    map[dk].items.push(toViewItem(e))
  })
  groups.forEach(g => g.items.reverse())
  return Promise.resolve(params.limit ? groups.slice(0, params.limit) : groups)
}

/**
 * 主页时光轴专用接口：服务端游标分页（后期数据量大，主页不再读 bootstrap 全量缓存）。
 * GET /entries/timeline?limit=10[&cursor=xxx] → {items:[entry_row], next_cursor, has_more}
 * items 已按 occurred_at 倒序（最新在前），映射为渲染用 view item（同 toViewItem 形状）。
 */
export function fetchTimeline({ cursor = '', limit = 10 } = {}) {
  const q = '/entries/timeline?limit=' + limit + (cursor ? '&cursor=' + encodeURIComponent(cursor) : '')
  return http.get(q).then(r => ({
    items: rowsOf(r).map(toViewItem),
    next_cursor: (r && r.next_cursor) || '',
    has_more: !!(r && r.has_more),
    /* 本页涉及日期的全天真实条数（{ 'YYYY-MM-DD': n }），日期行按它显示，跨页不再只算已加载部分 */
    day_totals: (r && r.day_totals) || {}
  }))
}

/**
 * 搜索专用接口：服务端关键词匹配 + 游标分页（后期数据量大，搜索页不再读 bootstrap 全量缓存）。
 * GET /entries/search?q=xxx&type=all[&baby=xxx]&limit=10[&cursor=xxx] → {items, next_cursor, has_more}
 * q 为空时退化为最近记录分页；关键词对 title/note/meta/creator/occurred_at 子串匹配，
 * 日期搜索由调用方把「10月19」归一化为「10-19」（ISO occurred_at 子串）。
 */
export function fetchSearch({ q = '', type = 'all', cursor = '', limit = 10 } = {}) {
  const baby = getBaby()
  const parts = [
    '/entries/search?limit=' + limit,
    'q=' + encodeURIComponent(q),
    'type=' + encodeURIComponent(type || 'all'),
    'baby=' + encodeURIComponent((baby && baby.id) || '')
  ]
  if (cursor) parts.push('cursor=' + encodeURIComponent(cursor))
  return http.get(parts.join('&')).then(r => ({
    items: rowsOf(r).map(toViewItem),
    next_cursor: (r && r.next_cursor) || '',
    has_more: !!(r && r.has_more)
  }))
}

/** 今日记录条数（当前宝宝口径，与 fetchEntries 过滤一致；数据源=bootstrap 缓存） */
export function getTodayCount() {
  const baby = getBaby()
  const babyId = baby ? baby.id : ''
  const dk = dayKey(now())
  return cache.entries.filter(e => dayKey(e.occurred_at) === dk && (!e.baby_id || e.baby_id === babyId)).length
}

/** 进行中睡眠记录（原始缓存行，含 occurred_at 供首页实时计时）；无则 null */
export function getOngoingSleep() {
  const baby = getBaby()
  const babyId = baby ? baby.id : ''
  return cache.entries.find(e =>
    e.badge === 'ongoing' && e.type === 'sleep' && e.occurred_at &&
    (!e.baby_id || e.baby_id === babyId)
  ) || null
}

/* ---------- 记录保存（乐观更新缓存 → REST；含照片先传 /media） ---------- */
/** 测量 → 百分位徽标（取身高或体重的最新百分位） */
function measureBadge(baby, payload) {
  if (!baby) return ''
  const ageM = ageMonths(baby.birth_date, now(), baby.gestational_weeks)
  const metric = payload.height ? 'height' : payload.weight ? 'weight' : 'head'
  const v = payload[metric]
  if (!v) return ''
  return percentileBadge(percentileOf(metric, baby.gender, ageM, Number(v)))
}

/**
 * 逐张上传照片（契约 §7.5：先 POST /files 拿 url 回填，再 POST /entries；
 * 新建记录时 entry 尚未落库，先不挂 business_id，保存成功后再 PATCH 补挂）
 * @returns {Promise<{urls: string[], files: string[]}>} urls=展示用相对路径；files=本次新上传的文件 id
 */
function uploadPhotos(paths, babyId) {
  if (!paths || !paths.length) return Promise.resolve({ urls: [], files: [] })
  return paths.reduce(
    (p, path) => p.then(acc => {
      /* 已是云端 URL（编辑回填等场景）直接保留，不重复上传 */
      if (/^(https?:|\/api\/|data:)/i.test(path)) { acc.urls.push(path); return acc }
      return http.uploadFile(path, { businessType: 'entry', babyId: babyId || '' })
        .then(f => { acc.urls.push(f.url || ''); if (f.id) acc.files.push(f.id); return acc })
    }),
    Promise.resolve({ urls: [], files: [] })
  )
}

/**
 * 逐段上传语音（同样走 POST /files）。
 * 现在的录音是一段一条；历史的多段数据同样不落服务端合并——suiji-server 没有 ffmpeg 也没有转码队列，
 * 所以 N 段就是 N 个文件，播放端按顺序衔接（见 utils/voicePlayback.js）。
 * 上传后只留云端 url，本地 blob/临时路径不再写进 payload（回填时它是失效引用）。
 * @returns {Promise<{payload: {segments, url, path}, files: string[]}>}
 */
function uploadVoice(payload, babyId) {
  const src = (Array.isArray(payload.segments) && payload.segments.length)
    ? payload.segments
    : (payload.url || payload.path ? [{ start: 0, dur: payload.duration || 0, url: payload.url, path: payload.path }] : [])
  if (!src.length) return Promise.resolve({ payload: { segments: [], url: '', path: '' }, files: [] })
  const out = []
  const files = []
  return src.reduce(
    (p, s) => p.then(() => {
      const local = String((s && (s.url || s.path)) || '')
      if (!local) return undefined
      if (/^(https?:|\/api\/)/i.test(local)) { out.push(Object.assign({}, s, { url: local, path: '' })); return undefined }
      return http.uploadFile(local, { businessType: 'entry', babyId: babyId || '' })
        .then(f => { out.push(Object.assign({}, s, { url: f.url || '', path: '' })); if (f.id) files.push(f.id) })
    }),
    Promise.resolve()
  ).then(() => ({
    payload: {
      segments: out,
      /* 只有一段时给顶层直达字段，与历史数据、展示端读法保持一致 */
      url: out.length === 1 ? out[0].url : '',
      path: ''
    },
    files
  }))
}

/**
 * 保存一条记录（新建 POST /entries 带 Idempotency-Key=客户端 entry UUID；编辑 PUT）
 * @param {{ type, id?, occurred_at?, payload?, note?, photos?, backfill? }} entry
 */export function saveEntry(entry) {
  if (readOnly()) return Promise.reject(new Error('当前是只读模式，暂时不能修改'))
  const baby = getBaby()
  const old = entry.id ? cache.entries.find(e => e.id === entry.id) : null
  const occurred = entry.occurred_at || (old ? old.occurred_at : now())
  const payload = Object.assign({}, entry.payload || {})
  const extra = {
    ongoing: !!payload.ongoing,
    percentileBadge: entry.type === 'measure' ? measureBadge(baby, payload) : ''
  }
  const s = summarize(entry.type, payload, occurred, extra)
  const row = {
    id: entry.id || genId('e'),
    baby_id: baby ? baby.id : '',
    type: entry.type,
    occurred_at: occurred,
    created_at: old ? old.created_at : now(),
    updated_at: now(),
    is_backfilled: !!entry.backfill,
    note: entry.note || '',
    /* 记录人昵称由服务端按令牌解析（家长昵称优先），客户端不猜；ID 供乐观行即时展示 */
    creator_id: myUserId(),
    title: s.title, meta: s.meta || '', badge: s.badge || '',
    photo: payload.photo || '',
    payload
  }
  if (!row.created_at) row.created_at = now()

  /* 本条记录新上传的文件 id（照片 + 语音段），落库后统一 PATCH 补挂 */
  let urls = []
  let newFiles = []
  return uploadPhotos(entry.photos || [], row.baby_id).then(res => {
    urls = res.urls
    newFiles = res.files
    if (urls.length) {
      row.photo = urls[0]
      row.payload = Object.assign({}, payload, { photos: urls })
    }
    /* 语音：逐段传 /files 换云端地址（服务端不做合并，段与段各自成文件） */
    if (row.type !== 'voice') return null
    return uploadVoice(row.payload, row.baby_id).then(v => {
      row.payload = Object.assign({}, row.payload, v.payload)
      newFiles = newFiles.concat(v.files)
    })
  }).then(() => {
    /* 乐观更新缓存：entry + 派生 measurement / entry_media / milestone_record */
    const mRows = []
    if (row.type === 'measure') {
      ;['height', 'weight', 'head'].forEach(metric => {
        const v = Number(row.payload[metric])
        if (v > 0) mRows.push({
          id: genId('m'), entry_id: row.id, baby_id: row.baby_id, metric, value: v,
          occurred_at: occurred, corrected_age_flag: baby && baby.gestational_weeks < 37 ? 1 : 0
        })
      })
    }
    const mediaRows = row.type === 'photo' && urls.length
      ? urls.map(u => ({ id: genId('md'), entry_id: row.id, baby_id: row.baby_id, url: u, local_path: u, sha256: '', size: 0, width: 0, height: 0 }))
      : []
    let msOld = null
    let msNew = null
    if (row.type === 'milestone' && row.payload.name) {
      let ms = cache.milestone_records.find(m => m.name === row.payload.name)
      if (!ms) {
        /* 自定义里程碑：不在预置清单，新建记录（domain=自定义，sort=999 排最后，与服务端一致） */
        ms = {
          id: genId('msr'), baby_id: row.baby_id, name: row.payload.name, domain: '自定义',
          month: '', ref: '', done: false, achieved_at: '', source_entry_id: '', creator: '', sort: 999
        }
        cache.milestone_records.push(ms)
        msNew = ms
      }
      msOld = Object.assign({}, ms)
      Object.assign(ms, {
        done: true, achieved_at: occurred, source_entry_id: row.id,
        month: baby ? ageText(baby.birth_date, occurred, baby.gestational_weeks) + '达成' : '已达成'
      })
    }
    const idx = cache.entries.findIndex(e => e.id === row.id)
    if (idx > -1) cache.entries[idx] = row
    else cache.entries.unshift(row)
    /* 编辑同一条记录：先摘掉旧的派生行，否则改一次测量/换一次照片就多一套重复数据 */
    const oldM = cache.measurements.filter(m => m.entry_id === row.id)
    const oldMedia = cache.media.filter(m => m.entry_id === row.id)
    oldM.forEach(m => { const j = cache.measurements.indexOf(m); if (j > -1) cache.measurements.splice(j, 1) })
    oldMedia.forEach(m => { const j = cache.media.indexOf(m); if (j > -1) cache.media.splice(j, 1) })
    mRows.forEach(m => cache.measurements.push(m))
    mediaRows.forEach(m => cache.media.push(m))

    const req = old
      ? http.put('/entries/' + row.id, row)
      : http.post('/entries', row, { 'Idempotency-Key': row.id })
    return req.then(r => {
      /* 新上传的文件补挂到本条记录（尽力而为，失败不阻断：文件仍可按 url 访问） */
      newFiles.forEach(fid => {
        http.patch('/files/' + fid, { business_type: 'entry', business_id: row.id }).catch(() => {})
      })
      if (r && typeof r === 'object') {
        const i = cache.entries.findIndex(e => e.id === row.id)
        if (i > -1) cache.entries[i] = Object.assign({}, row, r)
      }
      return { id: row.id }
    }).catch(e => {
      /* REST 失败：回滚乐观缓存，页面提示后表单数据不丢 */
      const i = cache.entries.findIndex(x => x.id === row.id)
      if (i > -1) {
        if (old) cache.entries[i] = old
        else cache.entries.splice(i, 1)
      }
      mRows.forEach(m => { const j = cache.measurements.findIndex(x => x.id === m.id); if (j > -1) cache.measurements.splice(j, 1) })
      mediaRows.forEach(m => { const j = cache.media.findIndex(x => x.id === m.id); if (j > -1) cache.media.splice(j, 1) })
      /* 被摘掉的旧派生行放回去，曲线/照片回到编辑前的样子 */
      oldM.forEach(m => { if (!cache.measurements.includes(m)) cache.measurements.push(m) })
      oldMedia.forEach(m => { if (!cache.media.includes(m)) cache.media.push(m) })
      if (msNew) { const j = cache.milestone_records.findIndex(m => m.id === msNew.id); if (j > -1) cache.milestone_records.splice(j, 1) }
      else if (msOld) { const ms = cache.milestone_records.find(m => m.id === msOld.id); if (ms) Object.assign(ms, msOld) }
      throw e
    })
  })
}

export function fetchEntry(id) {
  const e = cache.entries.find(x => x.id === id) || cache.trash.find(x => x.id === id)
  if (!e) return Promise.resolve(null)
  const v = toViewItem(e)
  /* 附带原始字段，供编辑页回填（detail 只消费展示字段，不受影响） */
  v.payload = e.payload || {}
  v.occurred_at = e.occurred_at
  /* 照片优先读 entry_media 台账；台账没跟上（编辑换过图、或 /files 上传不落台账）
   * 时按 payload.photos 现造一份只读行，避免详情/编辑回填丢图 */
  const rows = cache.media.filter(m => m.entry_id === id)
  const mediaUrls = (rows.length ? rows : deriveMediaRows(e))
    .map(m => http.resolveUrl(m.url || m.local_path))
  v.photos = mediaUrls
  return Promise.resolve(v)
}

export function updateEntry(id, patch) {
  const i = cache.entries.findIndex(e => e.id === id)
  if (i < 0) return Promise.reject(new Error('记录不存在'))
  if (readOnly()) return Promise.reject(new Error('当前是只读模式，暂时不能修改'))
  const old = cache.entries[i]
  const merged = Object.assign({}, old, patch, { updated_at: now() })
  if (patch.payload) {
    const baby = getBaby()
    const s = summarize(merged.type, merged.payload, merged.occurred_at, {
      ongoing: !!merged.payload.ongoing,
      percentileBadge: merged.type === 'measure' ? measureBadge(baby, merged.payload) : ''
    })
    merged.title = s.title
    merged.meta = s.meta || ''
    merged.badge = s.badge || ''
  }
  cache.entries[i] = merged
  return http.put('/entries/' + id, merged).then(r => {
    cache.entries[i] = Object.assign({}, merged, r || {})
    return { id }
  }).catch(e => {
    cache.entries[i] = old
    throw e
  })
}

/** 删除记录：服务端软删进回收站（deleted_at/deleted_by 由服务端落，契约 §6） */
export function deleteEntry(id) {
  if (readOnly()) return Promise.reject(new Error('当前是只读模式，暂时不能修改'))
  const i = cache.entries.findIndex(e => e.id === id)
  if (i < 0) return Promise.reject(new Error('记录不存在'))
  const e = cache.entries[i]
  const row = Object.assign({}, e, { deleted_at: now(), deleted_by: accountName(), deleted_by_id: myUserId() })
  cache.entries.splice(i, 1)
  cache.trash.unshift(row)
  return http.del('/entries/' + id).then(() => ({ id })).catch(err => {
    /* 失败回滚：记录回到时光轴原位 */
    const j = cache.trash.findIndex(t => t.id === id)
    if (j > -1) cache.trash.splice(j, 1)
    cache.entries.splice(Math.min(i, cache.entries.length), 0, e)
    throw err
  })
}

/* ---------- 回收站（30 天保留 · 服务端定时物理删除） ---------- */
const TRASH_KEEP_DAYS = 30

function trashDaysLeft(deletedAt) {
  const passed = daysBetween(dayKey(deletedAt), dayKey(now()))
  return Math.max(0, TRASH_KEEP_DAYS - passed)
}

/** 回收站列表（展示形状与原型 TRASH 常量一致），过期项仅隐藏（物理清理由服务端负责） */
export function listTrash() {
  return cache.trash
    .filter(t => trashDaysLeft(t.deleted_at) > 0)
    .map(t => ({
      id: t.id,
      day: monthDay(dayKey(t.deleted_at)),
      type: t.type,
      title: t.title,
      by: creatorLabel({ deleted_by: t.deleted_by, deleted_by_id: t.deleted_by_id }) || '家人',
      by_id: t.deleted_by_id || '',
      daysLeft: trashDaysLeft(t.deleted_at)
    }))
}

/** 恢复：POST /entries/{id}/restore，成功后移回时光轴缓存 */
export function restoreEntry(id) {
  const i = cache.trash.findIndex(t => t.id === id)
  if (i < 0) return Promise.reject(new Error('回收站中没有该记录'))
  const t = cache.trash[i]
  cache.trash.splice(i, 1)
  cache.entries.unshift(Object.assign({}, t, { deleted_at: null }))
  return http.post('/entries/' + id + '/restore').catch(err => {
    cache.trash.splice(Math.min(i, cache.trash.length), 0, t)
    const j = cache.entries.findIndex(e => e.id === id)
    if (j > -1) cache.entries.splice(j, 1)
    throw err
  }).then(() => ({ id }))
}

/** 彻底删除（不可恢复）：DELETE /entries/trash/{id} */
export function purgeEntry(id) {
  const i = cache.trash.findIndex(t => t.id === id)
  const t = i > -1 ? cache.trash[i] : null
  if (t) cache.trash.splice(i, 1)
  return http.del('/entries/trash/' + id).catch(err => {
    if (t) cache.trash.splice(Math.min(i, cache.trash.length), 0, t)
    throw err
  }).then(() => ({ id }))
}

/** 清空回收站：DELETE /entries/trash */
export function clearTrash() {
  const backup = cache.trash.slice()
  cache.trash = []
  return http.del('/entries/trash').catch(err => {
    cache.trash = backup
    throw err
  })
}

/** 最近一次有奶量的喂养记录（编辑器「按上次智能带入」数据源）：{ amount, occurred_at }，无记录返回 null */
export function getLastFeeding() {
  const baby = getBaby()
  const babyId = baby ? baby.id : ''
  const rows = cache.entries
    .filter(e => e.type === 'feeding' && (!e.baby_id || e.baby_id === babyId))
    .sort((a, b) => (a.occurred_at < b.occurred_at ? 1 : -1))
  const e = rows.find(r => r.payload && Number(r.payload.amount) > 0)
  return e ? { amount: Number(e.payload.amount), occurred_at: e.occurred_at } : null
}

/* ---------- 今日概览 ---------- */
export function getTodayStats() {
  const baby = getBaby()
  const babyId = baby ? baby.id : ''
  return calcTodayStats(cache.entries.filter(e => !e.baby_id || e.baby_id === babyId))
}

/* ---------- 生长（曲线/百分位仍由 domain/growth.js 客户端计算，数据源=缓存） ---------- */
/**
 * 只取「记录还在时光轴上」的测量行。
 * Measurement 行不随软删消失（服务端要保留到物理删除，恢复时数据点才回得来），
 * 所以曲线/测量列表必须按 entry_id 过滤，否则删掉一条测量记录后点还留在图上。
 */
function liveMeasurements() {
  const live = {}
  cache.entries.forEach(e => { live[e.id] = true })
  return cache.measurements.filter(m => !m.entry_id || live[m.entry_id])
}

function measurePoints(metric) {
  const baby = getBaby()
  if (!baby) return []
  return liveMeasurements()
    /* 多宝宝隔离：无 baby_id 的历史测量视为当前宝宝 */
    .filter(m => m.metric === metric && (!m.baby_id || m.baby_id === baby.id))
    .map(m => ({ ageM: ageMonths(baby.birth_date, m.occurred_at, baby.gestational_weeks), value: m.value }))
    .filter(p => p.ageM >= 0)
    .sort((a, b) => a.ageM - b.ageM)
}

/** 近 N 天窗口的 X 轴刻度文案：'M.D'（今天 → N 天前，左旧右新） */
function weekLabels(days = 7) {
  const out = []
  const base = new Date()
  for (let i = days; i >= 0; i--) {
    const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() - i)
    out.push((d.getMonth() + 1) + '.' + d.getDate())
  }
  return out
}

/** 近 N 月窗口的 X 轴刻度文案：'M月'（N 个月前 → 本月，左旧右新），共 N+1 个真实月份 */
function monthLabels(months = 6) {
  const out = []
  const base = new Date()
  for (let i = months; i >= 0; i--) {
    const d = new Date(base.getFullYear(), base.getMonth() - i, 1)
    out.push((d.getMonth() + 1) + '月')
  }
  return out
}

/** 三指标曲线数据（rangeMonths: 0=全部，否则近 n 月；week: true 时按「近 7 天」天粒度窗口出图） */
export function getGrowth(rangeMonths = 0, week = false) {
  const baby = getBaby()
  const gender = baby ? baby.gender : 'boy'
  const curAge = baby ? ageMonths(baby.birth_date, now()) : 0
  const fromAge = curAge - rangeMonths
  const out = {}
  ;['weight', 'height', 'head'].forEach(metric => {
    let pts = measurePoints(metric)
    if (rangeMonths && baby) pts = pts.filter(p => p.ageM >= fromAge)
    /* 近 7 天：窗口按天分 8 刻度（起点早于出生时贴齐 0 月龄），labels 为日期文案 */
    /* 近 N 月：窗口按月分 N+1 刻度，labels 为真实日历月份（左旧右新），吸附容差半月 */
    out[metric] = week && baby
      ? chartDataDays(metric, gender, pts, Math.max(0, fromAge), curAge, 7, weekLabels(7))
      : rangeMonths && baby
        ? chartDataDays(metric, gender, pts, Math.max(0, fromAge), curAge, rangeMonths, monthLabels(rangeMonths), 0.5)
        : chartData(metric, gender, pts)
  })
  return out
}

/** 当前值三卡：各指标最新值 + 百分位 */
export function getLatest() {
  const baby = getBaby()
  const out = {}
  ;['weight', 'height', 'head'].forEach(metric => {
    const pts = measurePoints(metric)
    const last = pts[pts.length - 1]
    out[metric] = last
      ? { value: last.value, p: percentileBadge(percentileOf(metric, baby ? baby.gender : 'boy', last.ageM, last.value)) }
      : { value: '—', p: '' }
  })
  return out
}

/** 测量记录列表（按日期分组） */
export function getMeasures() {
  const baby = getBaby()
  const byDate = {}
  /* 多宝宝隔离：无 baby_id 的历史测量视为当前宝宝 */
  liveMeasurements()
    .filter(m => !m.baby_id || !baby || m.baby_id === baby.id)
    .forEach(m => {
      const dk = dayKey(m.occurred_at)
      byDate[dk] = byDate[dk] || { date: dk, h: '', w: '', c: '', by: '家庭自测', entry_id: m.entry_id }
      if (m.metric === 'height') byDate[dk].h = String(m.value)
      if (m.metric === 'weight') byDate[dk].w = String(m.value)
      if (m.metric === 'head') byDate[dk].c = String(m.value)
    })
  return Object.values(byDate)
    .sort((a, b) => (a.date < b.date ? 1 : -1))
    .map(r => {
      const e = r.entry_id ? cache.entries.find(x => x.id === r.entry_id) : null
      return {
        date: monthDay(r.date),
        age: baby ? ageText(baby.birth_date, r.date, baby.gestational_weeks) : '',
        h: r.h, w: r.w, c: r.c,
        by: (e && e.payload && (e.payload.source || e.payload.org)) || r.by
      }
    })
}

/* ---------- 里程碑（建档时服务端按清单初始化，客户端只读缓存 + 记录达成） ---------- */
export function getMilestones() {
  const baby = getBaby()
  const babyId = baby ? baby.id : ''
  return cache.milestone_records
    .filter(m => !m.baby_id || m.baby_id === babyId)
    .map(m => ({
      id: m.id, name: m.name, month: m.month, done: !!m.done, domain: m.domain,
      /* 达成日期与来源记录：里程碑纪念卡取日期、可按来源记录带出照片 */
      achieved_at: m.achieved_at || '', source_entry_id: m.source_entry_id || ''
    }))
}

/* ---------- 疫苗（排期由服务端建档完成；状态派生仍用 domain/vaccine.js） ---------- */
/**
 * 刷新当前宝宝的疫苗/里程碑缓存（GET /vaccines + GET /milestones）。
 * 建档/切宝宝/改出生日期后调用；失败静默（下次 bootstrap 对齐）。
 */
export function ensureVaccineSchedule() {
  const baby = getBaby()
  if (!baby) return Promise.resolve()
  const q = '?baby_id=' + encodeURIComponent(baby.id)
  return Promise.all([http.get('/vaccines' + q), http.get('/milestones' + q)])
    .then(([vs, ms]) => {
      cache.vaccines = cache.vaccines.filter(v => v.baby_id !== baby.id).concat(rowsOf(vs))
      cache.milestone_records = cache.milestone_records
        .filter(m => m.baby_id !== baby.id)
        .concat(rowsOf(ms).map(m => Object.assign({ baby_id: baby.id }, m)))
    })
    .catch(() => { /* 无网时保留缓存旧值 */ })
}

export function getVaccines() {
  const baby = getBaby()
  const babyId = baby ? baby.id : ''
  const today = dayKey(now())
  return cache.vaccines
    .filter(r => (r.baby_id || '') === babyId)
    .sort((a, b) => (a.sort || 0) - (b.sort || 0) || (a.months || 0) - (b.months || 0))
    .map(v => {
      const status = vaccineStatus(v, today)
      /* 按出生日期排期的默认日期：与它不一致即为用户自定义的预期接种时间 */
      const planDefault = planDateFor(baby ? baby.birth_date : '', v.months)
      return Object.assign({}, v, {
        status,
        status_text: VACCINE_STATUS_TEXT[status],
        plan_default: planDefault,
        plan_custom: !!(v.plan_date && planDefault && v.plan_date !== planDefault),
        plan_text: monthDay(v.plan_date),
        days_left: daysToPlan(v.plan_date, today),
        tip: vaccineTip(v, today),
        remind_text: v.done ? '' : (v.remind ? '提醒已开启' : '提醒未开启')
      })
    })
}

/** 局部更新一剂疫苗：乐观改缓存 + PUT /vaccines/{id} */
function patchVaccine(id, patch) {
  const row = cache.vaccines.find(v => v.id === id)
  if (!row) return Promise.reject(new Error('剂次不存在'))
  const old = Object.assign({}, row)
  Object.assign(row, patch, { updated_at: now() })
  return http.put('/vaccines/' + id, patch).catch(err => {
    Object.assign(row, old)
    throw err
  }).then(() => { syncNotify(); return { id } })
}

/**
 * 一键标记完成 / 取消完成（取消时清空接种信息，恢复为待接种）
 * @param {string} id
 * @param {boolean} done
 * @param {string} [doneDate] 完成接种日期（YYYY-MM-DD），缺省取当前日期
 */
export function setVaccineDone(id, done, doneDate) {
  const row = cache.vaccines.find(v => v.id === id)
  if (!row) return Promise.reject(new Error('剂次不存在'))
  const patch = done
    ? { done: true, done_date: doneDate || row.done_date || dayKey(now()), remind: false }
    : { done: false, done_date: '', org: '', lot: '' }
  return patchVaccine(id, patch)
}

/**
 * 自定义某一剂次的预期接种时间（plan_date）
 * @param {string} id
 * @param {string} date YYYY-MM-DD；留空则恢复按出生日期的排期默认值
 */
export function setVaccinePlanDate(id, date) {
  const row = cache.vaccines.find(v => v.id === id)
  if (!row) return Promise.reject(new Error('剂次不存在'))
  const baby = getBaby()
  const val = date || planDateFor(baby ? baby.birth_date : '', row.months)
  return patchVaccine(id, { plan_date: val })
}

/** 一键开启 / 关闭某一剂次提醒 */
export function setVaccineRemind(id, on) {
  return patchVaccine(id, { remind: !!on })
}

/** 批量更新剂次（POST /vaccines/sync，契约 §8）：rows 为 {code, baby_id, ...patch} */
function syncVaccines(rows) {
  if (!rows.length) return Promise.resolve({ count: 0 })
  return http.post('/vaccines/sync', { rows })
}

/** 当前宝宝全部未接种剂次一键开启 / 关闭提醒 */
export function setAllVaccineRemind(on) {
  const baby = getBaby()
  const babyId = baby ? baby.id : ''
  const targets = cache.vaccines.filter(r => (r.baby_id || '') === babyId && !r.done)
  const snapshot = targets.map(r => ({ id: r.id, remind: r.remind }))
  targets.forEach(r => { r.remind = !!on; r.updated_at = now() })
  return syncVaccines(targets.map(r => ({ code: r.code, baby_id: r.baby_id, remind: !!on })))
    .then(() => { syncNotify(); return { count: targets.length } })
    .catch(err => {
      snapshot.forEach(s => { const r = cache.vaccines.find(v => v.id === s.id); if (r) r.remind = s.remind })
      throw err
    })
}

/** 编辑接种信息（日期 / 机构 / 批号），传 done_date 时视为已接种 */
export function markVaccine(id, info) {
  const patch = Object.assign(
    { done: true, done_date: dayKey(now()), remind: false },
    info
  )
  return patchVaccine(id, patch)
}

/** 仅清空接种状态：服务端排期保留，各剂次回到初始状态 */
export function resetVaccineStatus() {
  const snapshot = cache.vaccines.map(v => ({ id: v.id, done: v.done, done_date: v.done_date, org: v.org, lot: v.lot, remind: v.remind }))
  cache.vaccines.forEach(v => {
    Object.assign(v, { done: false, done_date: '', org: '', lot: '', remind: true, updated_at: now() })
  })
  return syncVaccines(cache.vaccines.map(v => ({ code: v.code, baby_id: v.baby_id, done: false, done_date: '', org: '', lot: '', remind: true })))
    .then(() => { syncNotify() })
    .catch(err => {
      snapshot.forEach(s => { const v = cache.vaccines.find(x => x.id === s.id); if (v) Object.assign(v, s, { updated_at: v.updated_at }) })
      throw err
    })
}

/* ---------- 家庭（成员来自 bootstrap 的 family.members + 由真实记录派生动态） ---------- */
const FEED_TEXT = {
  milestone: e => '记录了里程碑「' + e.title + '」',
  sleep: () => '记录了一次睡眠',
  photo: e => '上传了 ' + (((e.payload || {}).photos || []).length || 1) + ' 张照片',
  feeding: () => '记录了一次喂养',
  measure: () => '记录了一次测量',
  poop: () => '记录了一次照护情况',
  temp: () => '记录了一次照护情况',
  med: () => '记录了一次照护情况'
}
export function getFamily() {
  const members = (cache.family && Array.isArray(cache.family.members)) ? cache.family.members : []
  const entries = cache.entries.slice().sort((a, b) => (a.occurred_at < b.occurred_at ? 1 : -1))
  const album = entries.filter(e => e.photo).slice(0, 4).map(e => http.resolveUrl(e.photo))
  /* 成员配色按 ID 命中，ID 缺失（老数据）再按名字串匹配 */
  const colorOf = e => (members.find(m => (e.creator_id && m.id === e.creator_id) || m.name === e.creator) || {}).color || '#FF6B8B'
  const feeds = entries.slice(0, 3).map(e => ({
    eid: e.id,
    c: colorOf(e),
    who: creatorLabel(e) || '家人',
    /* raw 保留原始 creator（账号名）：仅用于"过滤自己的操作"，不参与展示 */
    raw: e.creator || '',
    what: (FEED_TEXT[e.type] || (() => '记录了一条动态'))(e),
    time: dayKey(e.occurred_at) === dayKey(now()) ? timeOf(e.occurred_at) : '昨天'
  }))
  return { members, sharedCount: entries.length, album, feeds }
}

/**
 * 记录人展示口径：【与宝宝关系 + 昵称】（如「妈妈 · 小熊妈妈」），不展示登录账号。
 * creator 只是历史名字串（服务端按令牌解析：关系 → 昵称，见 rows.actor_label），
 * creator_id 才是可靠依据：先按 ID 查 family.members（member_row.id 即 user_id），
 * 查不到再退回名字串匹配。
 * @param {string|{creator?:string, creator_id?:string, deleted_by?:string, deleted_by_id?:string}} src
 */
export function creatorLabel(src) {
  const row = typeof src === 'object' && src ? src : { creator: src }
  const name = String(row.creator || row.deleted_by || '').trim()
  const cid = String(row.creator_id || row.deleted_by_id || '').trim()
  if (!name && !cid) return ''

  const trim = v => String(v || '').trim()
  const members = (cache.family && Array.isArray(cache.family.members)) ? cache.family.members : []
  const byId = cid ? members.find(x => x && x.id === cid) : null
  const byName = byId ? null : members.find(x => x && (x.name === name || x.relation === name))
  const m = byId || byName
  const u = cache.user || {}
  /* 本人判定：ID 命中，或（老数据无 ID 时）creator 就是自己的展示名/账号名/昵称 */
  const isMe = (cid && cid === u.id) || !!(name && (name === accountName() || name === trim(u.username) || name === trim(u.name)))
  const parent = cache.settings.parent || {}

  let rel = trim(m && m.relation)
  let nm = trim(m && m.name)
  /* 成员行没填家长信息时（关系/昵称皆空），本人视角还能读自己的 settings.parent */
  if (isMe && !rel && !nm) {
    rel = trim(parent.relation)
    /* 家长昵称未填时，退回注册昵称（与服务端 display_name 同口径，等于账号名视为未设置） */
    nm = trim(parent.name) || (u.name && u.name !== u.username ? trim(u.name) : '')
  }
  /* 防账号名透出：昵称与登录账号同名时丢弃（老数据/旧服务端可能存了账号名） */
  if (nm && nm === trim(u.username)) nm = ''

  /* 关系在前、昵称在后；两者其一为空则只展示另一个，都解析不到才落「家人」 */
  if (rel && nm && nm !== rel) return rel + ' · ' + nm
  return rel || nm || '家人'
}

/* ---------- 服务端家人动态通知（落库 + 读后即删） ----------
 * 服务端在记录创建时按收件人 user_id 逐人落库（排除操作者本人），
 * bootstrap 后拉取合并进本地通知账本（弹窗/角标/消息中心复用既有链路）；
 * 消息中心读掉后调 POST /notifications/read 删除服务端行。
 * 旧版「客户端从最新 3 条 feeds 合成通知」已废弃：靠 creator 名字字符串
 * 判断是否本人会误弹（昵称不同步/重名），且老记录在本地账本 30 天过期后
 * 会作为「新通知」反复弹出——没人操作却多出通知的主要来源。 */

/* ---------- 未读角标变化订阅（首页铃铛等常驻 UI） ----------
 * 轮询拉到新服务端通知 / 消息中心已读变化时广播最新未读总数；
 * 页面 onShow 各自刷新兜底，这里覆盖「停留页面期间角标要跟着动」的场景。 */
let unreadListeners = []
/** 订阅未读总数变化，返回退订函数；注册即回调一次当前值 */
export function onUnreadChange(cb) {
  if (typeof cb !== 'function') return () => {}
  unreadListeners.push(cb)
  try { cb(getUnreadTotal()) } catch (e) { /* ignore */ }
  return () => { unreadListeners = unreadListeners.filter(f => f !== cb) }
}
function emitUnreadChange() {
  const n = getUnreadTotal()
  unreadListeners.forEach(f => { try { f(n) } catch (e) { /* ignore */ } })
}

/** 把一批服务端通知合并进本地账本（/events/count 与 GET /notifications 共用）。
 *  remind.msg 关闭时只进消息中心不弹系统通知；H5/小程序端 notifySupported=false
 *  不弹系统通知，这里在 fresh>0 且用户未关「家人动态」开关时补一条顶部 toast 兜底。 */
function ingestNotices(items) {
  const list = Array.isArray(items) ? items : []
  if (!list.length) return 0
  const jobs = list.map(n => ({
    id: 'f:' + n.id,
    type: n.type || 'feed',
    eid: n.entry_id || '',
    title: n.title || '家人动态',
    content: n.content || '',
    when: new Date(n.created_at || '').getTime() || Date.now()
  }))
  const msgOn = !!(getRemind() || {}).msg
  const fresh = notify.mergeFeed(jobs, { silent: !msgOn })
  if (fresh > 0) {
    emitUnreadChange()
    if (msgOn) {
      const latest = list[0]
      uiToast(fresh > 1 ? `家人有 ${fresh} 条新动态` : (latest && latest.content || '家人有新动态'), 2600, 'ok')
    }
  }
  return list.length
}

/** 拉取本人通知并合并进账本（消息中心手动刷新 / 冷启动补弹用；
 *  前台轮询走 /events/count 顺带下发的 notices，不再单独发这个请求） */
export function pullServerNotices() {
  return http.get('/notifications', { silent: true }).then(r => ingestNotices((r && r.items) || []))
    .catch(() => 0)
}

/** 已读即删：删除消息中心读掉的服务端通知行（失败静默，「全部已读」会再兜底） */
function readServerNotices(ids) {
  if (!ids.length) return
  http.post('/notifications/read', { ids }, { silent: true }).catch(() => {})
}

/** 消息中心通知 id（'n:f:<nid>'）→ 服务端通知 id；非家人动态返回空串 */
function serverNoticeIdOf(msgId) {
  const s = String(msgId)
  return s.indexOf('n:f:') === 0 ? s.slice(4) : ''
}

/* ---------- AI 成长日记（生成管线移到服务端，契约 §11；Key 绝不下发客户端） ---------- */
/** 段落形状归一化：diary 页消费 {text, src:[展示串], entryIds:[记录id]}；旧行只有 cites 时以其为 entryIds */
function normParas(paras) {
  return (Array.isArray(paras) ? paras : []).map(p => ({
    text: p.text || '',
    src: Array.isArray(p.src) ? p.src : [],
    entryIds: Array.isArray(p.entryIds) ? p.entryIds : (Array.isArray(p.cites) ? p.cites : [])
  }))
}
/** 全部日记（草稿+归档），按创建时间倒序；diary 页「日记档案」列表用 */
export function listDiaries() {
  const js = cache.journals.slice().sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
  return Promise.resolve(js.map(d => ({
    id: d.id, range: d.range, paras: normParas(d.paras), status: d.status, created_at: d.created_at,
    range_start: d.range_start || '', range_end: d.range_end || ''
  })))
}

/** 生成周记草稿：POST /journals/generate（缺省近 7 天），响应 journal 行入缓存 */
export function generateDiary() {
  const baby = getBaby()
  const body = {}
  if (baby) body.baby_id = baby.id
  return http.post('/journals/generate', body).then(row => {
    if (row && row.id) {
      const i = cache.journals.findIndex(j => j.id === row.id)
      if (i > -1) cache.journals[i] = row
      else cache.journals.unshift(row)
    }
    return { id: row.id, range: row.range, paras: normParas(row.paras), status: row.status || 'draft' }
  })
}

/** 更新日记：PUT /journals/{id}；patch = { paras?, status? }（暂存只传 paras，归档另传 status:'archived'） */
export function updateDiary(id, patch) {
  const row = cache.journals.find(j => j.id === id)
  const old = row ? Object.assign({}, row) : null
  if (row) Object.assign(row, patch, { updated_at: now() })
  return http.put('/journals/' + id, patch).catch(err => {
    if (row && old) Object.assign(row, old)
    throw err
  }).then(r => {
    if (row && r) Object.assign(row, r)
    return { id }
  })
}

/* ---------- 设置 / 同意 / AI 开关（同步读缓存；写=乐观改缓存+后台 PUT /settings） ---------- */
export function getSwitches() { return settingOf('switches', { checkup: true, anniversary: true, notify: true }) }
export function setSwitch(key, val) {
  const s = Object.assign({}, getSwitches())
  s[key] = val
  writeSetting('switches', s)
}
export function getConsent() { return settingOf('consent', null) }
export function saveConsent(flags) {
  writeSetting('consent', Object.assign({ agreed_at: now(), policy_version: 'v1.0' }, flags))
}
/** AI 配置：仅保留 enabled 开关门控；baseUrl/model/key 已废弃（Key 走服务端环境变量） */
export function getAiConfig() {
  const a = settingOf('ai', {})
  return { enabled: !!a.enabled, baseUrl: '', model: '', hasKey: false }
}
export function setAiConfig(cfg) {
  const a = Object.assign({}, settingOf('ai', {}))
  a.enabled = !!(cfg && cfg.enabled)
  writeSetting('ai', a)
  return getAiConfig()
}
/* 家长信息：setting 'parent'，未保存时回退 PARENT_INFO 默认值 */
export function getParentInfo() {
  return Object.assign({}, PARENT_INFO, settingOf('parent', {}))
}
export function saveParentInfo(info) {
  writeSetting('parent', info)
}
/* 健康日志可见性：0 家人可见 / 1 仅自己可见 / 2 隐藏（存服务端 settings） */
export function getHealthVisibility() { return settingOf('health_visibility', 0) }
export function setHealthVisibility(i) { writeSetting('health_visibility', i) }
export function getFamilyFlags() { return settingOf('family', { mode: 'solo', readOnly: false, lock: false }) }
export function setFamilyFlag(key, val) {
  const f = Object.assign({}, getFamilyFlags())
  f[key] = val
  writeSetting('family', f)
}

/* ---------- 家庭契约（API-CONTRACT §4）：创建 / 邀请码 / 凭码加入 / 家庭只读开关 ---------- */
/** 是否已关联家庭：bootstrap 后 family.id 为空视为无家庭（登录门控用） */
export function hasFamily() { return !!(cache.family && cache.family.id) }
/** 当前家庭契约状态 {id,name,readonly,role}（无家庭时 null） */
export function getFamilyInfo() { return cache.family || null }
export function getFamilyRole() { return (cache.family || {}).role || 'member' }
export function isFamilyReadonly() { return !!(cache.family && cache.family.readonly) }
/** 创建新家庭：POST /family { name }，成功后重新 bootstrap 拉取家庭数据 */
export function createFamily(name) {
  return http.post('/family', { name: (name || '').trim() }).then(() => bootstrap())
}
/** 生成邀请码：POST /family/invite → { code, expires_at } */
export function inviteFamily() {
  return http.post('/family/invite')
}
/**
 * 凭邀请码加入：POST /family/join { code }。
 * 一个用户仅允许关联一个家庭：服务端在加入时与当前家庭解绑，响应带回 left_family
 * （被解绑的家庭 {id,name} 或 null）。客户端先清掉旧家庭的缓存镜像，再 bootstrap 灌新家庭。
 * @returns {Promise<{family: object, members: Array, left_family: object|null}>}
 */
export function joinFamily(code) {
  return http.post('/family/join', { code: (code || '').trim() }).then(r => {
    resetFamilyCache()
    return bootstrap().then(() => r)
  })
}
/** 家庭只读开关（仅创建者）：PATCH /family/readonly，乐观更新缓存，失败回滚并重新对齐 */
export function setFamilyReadonly(val) {
  const fam = cache.family || {}
  const old = fam.readonly
  fam.readonly = !!val
  cache.family = fam
  return http.patch('/family/readonly', { readonly: !!val }).catch(err => {
    fam.readonly = old
    uiError(err, '只读开关设置失败')
    return bootstrap().catch(() => { /* 无网时保留回滚值 */ })
  })
}

/** 本机导出服务端不可观测，成功后上报一次留痕（FR-22）；失败不影响导出结果 */
function reportExport() {
  http.post('/family/audit/export', {}, { silent: true }).catch(() => { /* 留痕失败不阻断导出 */ })
}

/* ---------- 操作留痕（P20 · FR-22：服务端 audit_log，保留 180 天，成员不可删除） ---------- */
const AUDIT_TAGS = {
  create: '创建', invite: '邀请', join: '加入', leave: '退出', role: '角色变更',
  readonly: '只读开关', delete: '删除', purge: '彻底删除', export: '导出', wipe: '数据清除'
}
const AUDIT_COLORS = {
  create: '#FF6B8B', invite: '#5FB87A', join: '#5FB87A', leave: '#E85D5D', role: '#FF9E58',
  readonly: '#FF9E58', delete: '#E85D5D', purge: '#E85D5D', export: '#8FA8D8', wipe: '#E85D5D'
}
/**
 * 家庭操作留痕列表：GET /family/audit（真实数据，非原型常量）
 * 上滑分页：offset 从 0 起按页递增，返回不足 limit 条即已到末页。
 * who 展示口径：与宝宝关系在前、昵称在后（服务端已保证 actor_name 不含登录账号）。
 * @returns {Promise<Array<{id,act,tag,color,who,text,time}>>}
 */
export function getAudit(offset = 0, limit = 10) {
  return http.get('/family/audit?limit=' + limit + '&offset=' + offset).then(r => rowsOf(r).map(a => {
    const act = a.action || ''
    const at = a.created_at || ''
    const rel = a.actor_relation || ''
    const nm = a.actor_name || ''
    return {
      id: a.id,
      act,
      tag: AUDIT_TAGS[act] || '操作',
      color: AUDIT_COLORS[act] || '#9A8580',
      who: rel && nm && nm !== rel ? rel + ' · ' + nm : (rel || nm || '家人'),
      text: a.text || '',
      time: at ? (dayKey(at).slice(5).replace('-', '/') + ' ' + timeOf(at)) : ''
    }
  }))
}

/* ---------- 备份（导出=缓存快照 JSON 落盘；导入=解析后 POST /import 合并） ---------- */
function buildSnapshot() {
  return {
    format: 'suiji-backup',
    version: 2,
    cloud: true,
    manifest: {
      exported_at: now(),
      counts: {
        entry: cache.entries.length,
        baby: cache.babies.length,
        measurement: cache.measurements.length,
        milestone: cache.milestone_records.length,
        journal: cache.journals.length
      }
    },
    _exported_at: now(),
    baby: cache.babies,
    entry: cache.entries,
    entry_media: cache.media,
    measurement: cache.measurements,
    milestone_record: cache.milestone_records,
    vaccine: cache.vaccines,
    member: (cache.family && cache.family.members) || [],
    ai_journal: cache.journals,
    app_setting: cache.settings
  }
}

/**
 * 导出全量数据副本：云端版直接以缓存快照生成明文 JSON 落盘
 * （数据主权在服务端，加密通道 + JWT 已保障传输安全；password 参数保留兼容旧调用，
 *   旧版加密包导入仍走 backup.js parsePack 解密）。
 */
export function exportBackup(password) {
  const pack = JSON.stringify(buildSnapshot())
  const fname = 'suiji-backup_' + now().replace(/[-: ]/g, '').slice(0, 14) + '.json'
  /* saveTextFile 的失败（App 写盘 onerror / H5 Blob 异常）必须原样抛出：
     之前 .catch(() => '') 把它吞成「路径为空」，页面照样报「已生成」，用户以为有备份 */
  return saveTextFile(fname, pack).then(w => {
    const b = Object.assign({}, settingOf('backup', {}))
    b.lastExportAt = now()
    writeSetting('backup', b)
    reportExport()
    return { filename: fname, path: w || '', size: pack.length }
  })
}
/** 解析备份文本：兼容旧版加密包（parsePack）与云端版明文 JSON */
function parseBackupText(text, password) {
  let obj = null
  try { obj = JSON.parse(text) } catch (e) { /* 走加密包分支或报错 */ }
  if (!obj || obj.format !== 'suiji-backup') throw new Error('不是岁记备份包')
  if (obj.cipher) return parsePack(text, password)          /* 旧版加密包 */
  return { data: obj, manifest: obj.manifest || {} }         /* 云端版明文包 */
}

function doImport(text, password) {
  const { data, manifest } = parseBackupText(text, password)
  /* 按 id upsert 合并交由服务端执行（契约 §12：同 id 取 updated_at 新者） */
  return http.post('/import', { snapshot: data }).then(() => bootstrap()).then(() => manifest)
}
export function importBackupFromFile(password, merge) {
  return pickTextFile().then(text => doImport(text, password))
}
export function getBackupInfo() {
  const b = settingOf('backup', {})
  return {
    lastExportAt: b.lastExportAt || '',
    lastAutoAt: b.lastAutoAt || '',
    autoCount: 0 /* 云端版不再保留本机自动备份滚动列表 */
  }
}

/* ---------- 成长档案导出（HTML 本机生成逻辑保持不变，数据源=缓存） ---------- */
export function exportArchive() {
  const baby = getBaby()
  const latest = getLatest()
  const measures = getMeasures()
  const vaccines = getVaccines()
  const milestones = getMilestones().filter(m => m.done)
  const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const tr = arr => '<tr>' + arr.map(c => '<td>' + esc(c) + '</td>').join('') + '</tr>'
  const table = (heads, rows) =>
    '<table><thead><tr>' + heads.map(h => '<th>' + esc(h) + '</th>').join('') + '</tr></thead><tbody>' +
    (rows.length ? rows.map(r => tr(r)).join('') : '<tr><td colspan="' + heads.length + '">暂无记录</td></tr>') +
    '</tbody></table>'
  const html = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">' +
    '<title>岁记成长档案' + (baby ? ' · ' + esc(baby.name) : '') + '</title>' +
    '<style>body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;color:#4A3B38;max-width:720px;margin:0 auto;padding:24px;background:#FFF6F0}' +
    'h1{font-size:22px;color:#E86FA0}h2{font-size:16px;margin-top:28px;border-left:4px solid #FF6B8B;padding-left:8px}' +
    'p{font-size:14px;line-height:1.7}table{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}' +
    'th,td{border:1px solid #F0DCCF;padding:6px 10px;text-align:left;background:#fff}th{background:#FFE9EF}' +
    '.meta{color:#9A8580;font-size:12px}</style></head><body>' +
    '<h1>岁记 · 成长档案</h1>' +
    (baby
      ? '<p>' + esc(baby.name) + '（' + (baby.gender === 'girl' ? '女' : '男') + '）· ' + esc(baby.age) +
        '<br><span class="meta">出生日期 ' + esc(baby.birth_date) + (Number(baby.gestational_weeks) < 37 ? ' · 早产（胎龄 ' + esc(baby.gestational_weeks) + ' 周，曲线按矫正月龄）' : '') + '</span></p>'
      : '<p>尚未创建宝宝档案</p>') +
    '<h2>当前指标（WHO 参考百分位）</h2>' +
    table(['指标', '最新值', '百分位'], [
      ['体重', latest.weight.value + ' kg', latest.weight.p],
      ['身高', latest.height.value + ' cm', latest.height.p],
      ['头围', latest.head.value + ' cm', latest.head.p]
    ]) +
    '<h2>测量记录</h2>' +
    table(['日期', '月龄', '身高 cm', '体重 kg', '头围 cm', '来源'],
      measures.map(m => [m.date, m.age, m.h || '—', m.w || '—', m.c || '—', m.by])) +
    '<h2>已达成里程碑</h2>' +
    table(['里程碑', '达成月龄', '领域'], milestones.map(m => [m.name, m.month, m.domain])) +
    '<h2>疫苗接种时间表</h2>' +
    table(['疫苗', '剂次', '月龄', '计划日期', '状态', '接种日期'],
      vaccines.map(v => [v.n, v.dose, v.age, v.plan_text, v.status_text, v.done_date || '—'])) +
    '<p class="meta">由岁记 App 生成 · ' + esc(now()) + ' · 本档案为记录数据汇编，不含医学解读</p>' +
    '</body></html>'
  const fname = 'suiji-archive_' + now().replace(/[-: ]/g, '').slice(0, 14) + '.html'
  /* 落盘失败必须原样抛出：吞掉后页面照样显示「已生成 · 已保存」，用户以为有档案 */
  return saveTextFile(fname, html).then(w => {
    reportExport()
    return { filename: fname, path: w || '', size: html.length }
  })
}

/* ---------- 首次引导（建档变异步：服务端排期里程碑/疫苗） ---------- */
export function onboardBaby(data) {
  if (cache.babies.length) return Promise.resolve(getBaby())
  return createBaby(Object.assign({ birth_date: dayKey(now()) }, data))
}

/* ---------- 提醒设置（P23 · FR-23/24/25，持久化 setting 'remind'） ---------- */
export function getRemind() {
  return Object.assign({}, REMIND_DEFAULT, settingOf('remind', {}))
}
export function setRemind(patch) {
  const r = Object.assign(getRemind(), patch)
  writeSetting('remind', r)
  syncNotify()
  return r
}

/* ---------- 系统通知权限状态（提醒设置页提示条用） ---------- */
/** supported=当前平台能否排期系统通知；enabled=系统通知权限是否开启（非 App 端恒 true） */
export function notifyAuthStatus() { return { supported: notifySupported(), enabled: areNotificationsEnabled() } }
/** 跳转系统通知设置页（仅 App 端有效） */
export function openNotifySettings() { openNotificationSettings() }

/* ---------- 系统通知未读（图标角标由 infra/notify.js 维护） ---------- */
/** 未读系统通知数 */
export function getUnreadNoticeCount() { return notify.unreadCount() }
/** 标记全部已送达通知为已读并清角标（消息中心「全部已读」时调用） */
export function markNoticesRead() { notify.markDeliveredRead() }

/* ---------- 消息中心：通知 / 待办（首页铃铛入口） ---------- */
/* 通知 = 已送达的系统提醒（已读态由 infra/notify 账本维护）+ 家人动态（已读态存本机）
   待办 = 疫苗逾期 / 近期剂次 / 未归档日记草稿 / 回收站待清理
   待办是实时派生的事项，没有「已读」这一说：看过还在，只有处理完（接种打卡、
   日记归档、回收站清空）才消失，所以它不参与铃铛角标，只在消息中心里列着。 */
const MSG_READ_KEY = 'sj_msg_read'

function msgReadMap() {
  try { return JSON.parse(uni.getStorageSync(MSG_READ_KEY) || '{}') || {} }
  catch (e) { return {} }
}
function writeMsgReadMap(m) {
  try { uni.setStorageSync(MSG_READ_KEY, JSON.stringify(m)) } catch (e) { /* ignore */ }
}

/** epoch 毫秒 → 'M月D日 HH:mm'（今天/昨天简化为 HH:mm / 昨天 HH:mm） */
function timeText(ts) {
  const d = new Date(ts)
  const pad = n => (n < 10 ? '0' + n : '' + n)
  const today = new Date()
  const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  const hm = pad(d.getHours()) + ':' + pad(d.getMinutes())
  const y = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1)
  if (sameDay(d, today)) return hm
  if (sameDay(d, y)) return '昨天 ' + hm
  return (d.getMonth() + 1) + '月' + d.getDate() + '日 ' + hm
}

/** 通知列表：已送达系统提醒（倒序在前）+ 家人动态 · 图标与跳转按来源派生 */
export function getNotices() {
  const read = msgReadMap()
  const me = accountName()
  /* 历史账本里自己记录的家人动态不再进通知流：服务端按 user_id 精确投递（永不含本人），
     这条过滤只为兼容旧版本地合成的 'f:<entryId>' 条目（新条目 eid 为空，天然放行） */
  const delivered = notify.delivered().filter(j => {
    if (j.id.indexOf('f:') !== 0 || !j.eid) return true
    const e = cache.entries.find(x => x.id === j.eid)
    if (!e) return true
    if (e.creator_id) return e.creator_id !== myUserId()
    return (e.creator || '') !== me
  })
  const out = delivered.map(j => {
    const feed = j.id.indexOf('f:') === 0
    const vaccine = j.id.indexOf('v:') === 0
    const ann = j.id.indexOf('ann:') === 0
    const ck = j.id.indexOf('ck:') === 0
    const daily = j.id === 'daily'
    const id = 'n:' + j.id
    /* 服务端家人动态通知：按 type 出图标，记录仍在则直达详情页（删除类跳时光轴） */
    const ftype = feed ? (j.type || 'feed') : ''
    const eid = ftype === 'feed' || ftype === 'milestone'
      ? (cache.entries.find(e => e.id === j.eid) ? j.eid : '') : ''
    const icon = feed
      ? (['delete', 'restore'].indexOf(ftype) >= 0 ? 'alert' : ftype === 'vaccine' ? 'gift' : ftype === 'journal' ? 'pencil' : 'users')
      : vaccine ? 'gift' : daily ? 'sparkles' : 'heart'
    const go = feed
      ? (eid ? '/pages/detail/detail?id=' + eid
        : ftype === 'vaccine' ? '/pages/vaccine/vaccine'
        : ftype === 'journal' ? '/pages/diary/diary'
        : '/pages/index/index')
      : vaccine ? '/pages/vaccine/vaccine' : ann ? '/pages/diary/diary' : ck ? '/pages/grow/grow' : '/pages/remind/remind'
    return {
      id,
      title: j.title,
      desc: j.content,
      time: timeText(j.when),
      read: !!j.read || !!read[id],
      icon,
      tint: vaccine ? '#FFF6DC' : (daily ? '#FFE9EF' : '#FFF0E2'),
      go
    }
  })
  /* 家人动态改由服务端落库通知（账本 id 'f:<nid>'），已随 delivered 一起输出，
     不再从 bootstrap feeds 本地合成；历史账本里旧 'f:<eid>' 条目保留只读展示直至滚出 */
  return out
}
/** 标记单条通知已读（系统提醒同步清账本与角标；家人动态读后即删服务端行） */
export function markNoticeRead(id) {
  const m = msgReadMap()
  m[id] = 1
  writeMsgReadMap(m)
  if (String(id).indexOf('n:') === 0) notify.markOneRead(String(id).slice(2))
  const nid = serverNoticeIdOf(id)
  if (nid) readServerNotices([nid])
  emitUnreadChange()
}
/** 全部已读（通知 tab）：账本内已送达通知直接删除（列表清空），未到点排期保留；
 *  服务端本人通知行全删（含账本尚未合并到的行），不会再现 */
export function markAllNoticesRead() {
  notify.removeDelivered()
  http.post('/notifications/read', {}, { silent: true }).catch(() => {})
  emitUnreadChange()
}
/** 删除单条通知（消息中心详情关闭后调用）：清账本条目与已读残留；家人动态读后即删服务端行 */
export function removeNotice(id) {
  const s = String(id)
  if (s.indexOf('n:') === 0) notify.removeOne(s.slice(2))
  const m = msgReadMap()
  if (m[s]) { delete m[s]; writeMsgReadMap(m) }
  const nid = serverNoticeIdOf(s)
  if (nid) readServerNotices([nid])
  emitUnreadChange()
}

/**
 * 待办列表：逾期疫苗 → 7 天内剂次 → 未归档日记草稿 → 回收站待清理
 * 每项形状与通知一致（id/title/desc/time/icon/tint/go/btn）；无已读态，处理完自然不再出现
 */
export function getTodos() {
  const vs = getVaccines()
  /* 全局「疫苗接种提醒」开关：关闭后不产生任何疫苗待办（逾期/近期剂次都不进列表与角标） */
  const vaccineRemindOn = !!(getRemind() || {}).vaccine
  const out = []
  /* 逾期未接种 */
  vs.filter(v => !v.done && v.status === 'overdue' && vaccineRemindOn && v.remind).forEach(v => {
    out.push({
      id: 'todo:v:' + v.id,
      title: v.n + ' ' + v.dose + ' 已逾期',
      desc: '计划 ' + v.plan_text + ' 接种 · ' + v.status_text + '，请尽快补种',
      time: '逾期',
      icon: 'alert', tint: '#FFE9E5',
      go: '/pages/vaccine/vaccine', btn: '去处理'
    })
  })
  /* 7 天内待接种（含今天） */
  vs.filter(v => !v.done && v.status !== 'overdue' && vaccineRemindOn && v.remind && v.days_left <= 7).forEach(v => {
    const when = v.days_left <= 0 ? '就在今天' : v.days_left + ' 天后'
    out.push({
      id: 'todo:v:' + v.id,
      title: v.n + ' ' + v.dose + ' 待接种',
      desc: when + ' · 计划 ' + v.plan_text + ' 接种',
      time: when,
      icon: 'gift', tint: '#FFF6DC',
      go: '/pages/vaccine/vaccine', btn: '去接种'
    })
  })
  /* AI 成长日记草稿未归档 */
  const js = cache.journals.slice().sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
  const draft = js[0]
  if (draft && draft.status !== 'archived') {
    out.push({
      id: 'todo:j:' + draft.id,
      title: 'AI 成长日记草稿待核对',
      desc: (draft.range || '本周周记') + ' · 核对后可归档到成长档案',
      time: '待核对',
      icon: 'pencil', tint: '#F3EAE2',
      go: '/pages/diary/diary', btn: '去核对'
    })
  }
  /* 回收站待清理（30 天到期自动清除） */
  const trashCount = listTrash().length
  if (trashCount) {
    out.push({
      id: 'todo:trash',
      title: '回收站 ' + trashCount + ' 条待处理',
      desc: '保留 30 天 · 可恢复或彻底删除',
      time: '待清理',
      icon: 'trash', tint: '#F3EAE2',
      go: '/pages/trash/trash', btn: '去清理'
    })
  }
  return out
}
/** 消息中心未读总数 = 未读通知数（首页铃铛角标）；待办不计入，见上方口径说明 */
export function getUnreadTotal() {
  return getNotices().filter(n => !n.read).length
}

/* ---------- 备份开关（P25 · FR-33/36，持久化 setting 'backupFlags'） ---------- */
export function getBackupFlags() {
  return settingOf('backupFlags', { cloud: true, orig: false })
}
export function setBackupFlag(key, val) {
  const f = Object.assign({}, getBackupFlags())
  f[key] = !!val
  writeSetting('backupFlags', f)
  return f
}

/* ---------- 新建时间表（P22 · FR-23） ---------- */
/**
 * 按所选国家免疫规划疫苗生成提醒排期：
 * 内置时间表已由服务端建档时全量排好，此处语义为——选中规划内的未接种剂次开启提醒，未选中的关闭。
 * 名称按去掉「疫苗」后的核心词匹配（如 乙脑 ↔ 乙脑减毒活疫苗、流脑 ↔ A 群流脑疫苗）。
 * @param {number[]} selectedIdx VACCINE_PROGRAM 下标数组
 */
export function generateVaccineSchedule(selectedIdx) {
  const baby = getBaby()
  const babyId = baby ? baby.id : ''
  const cores = (selectedIdx || [])
    .map(i => (VACCINE_PROGRAM[i] || {}).n)
    .filter(Boolean)
    .map(n => n.replace('疫苗', ''))
  let count = 0
  const targets = cache.vaccines.filter(r => (r.baby_id || '') === babyId && !r.done)
  const snapshot = targets.map(r => ({ id: r.id, remind: r.remind }))
  const rows = targets.map(r => {
    const on = cores.some(c => (r.n || '').indexOf(c) >= 0)
    if (!!r.remind !== on) count++
    r.remind = on
    r.updated_at = now()
    return { code: r.code, baby_id: r.baby_id, remind: on }
  })
  return syncVaccines(rows)
    .then(() => { syncNotify(); return { count } })
    .catch(err => {
      snapshot.forEach(s => { const r = cache.vaccines.find(v => v.id === s.id); if (r) r.remind = s.remind })
      throw err
    })
}
