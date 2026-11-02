/**
 * 岁记 · 系统通知与应用图标角标
 * 用户在 App 内开启的提醒（疫苗剂次 / 体检节点 / 每日汇总 / 纪念日 / 家人动态）同步为手机系统通知：
 *   App 端通过 plus.push 本地通知按 when 排期，到点由系统送达（退后台/被杀仍生效）；
 *   H5 / 小程序端无本地排期能力，静默降级为仅维护未读账本。
 * 未读口径：本地账本 sj_notices 记录每条通知，触发时刻已过且未读即计入图标角标
 *   （plus.runtime.setBadgeNumber）；点击通知或进入「提醒设置」页标记已读并刷新角标。
 * 每日汇总仅排下一次触发，随每次启动/设置变更滚动重排。
 * plus.* 调用全部收口在 infra/platform.js（TDD §4.3）。
 */
import {
  kvGet, kvSet, kvRemove, notifySupported, requestNotifyPermission, scheduleLocalNotice,
  clearLocalNotices, setBadgeNumber, onNoticeClick
} from '@/infra/platform.js'
import { parse, monthDay } from '@/domain/shared/date.js'

const STORE_KEY = 'sj_notices'
const HISTORY_KEEP_MS = 30 * 86400000  // 已送达通知账本保留窗口
const MAX_SCHEDULED = 30               // 排期上限（iOS 系统限 64 条，留余量）

/* 儿保体检节点（中性时间提示，不含评估结论）：42 天 + 关键月龄点 */
const CHECKUP_NODES = [
  { d: 42, label: '42 天' },
  { m: 3, label: '3 月龄' },
  { m: 6, label: '6 月龄' },
  { m: 8, label: '8 月龄' },
  { m: 12, label: '1 周岁' },
  { m: 18, label: '18 月龄' },
  { m: 24, label: '2 周岁' },
  { m: 30, label: '30 月龄' },
  { m: 36, label: '3 周岁' }
]

/* ---------- 本地账本 { jobs:[{id,title,content,when,read}], sig } ---------- */
/* when 落盘为 ISO 串：读入时统一还原为 epoch 毫秒，避免与 Date.now() 比较失真 */
function loadState() {
  try {
    const j = JSON.parse(kvGet(STORE_KEY) || '{}')
    const jobs = (Array.isArray(j.jobs) ? j.jobs : []).map(x =>
      Object.assign({}, x, { when: new Date(x.when).getTime() || 0 }))
    return { jobs, sig: j.sig || '', scheduled: Array.isArray(j.scheduled) ? j.scheduled : null }
  } catch (e) { return { jobs: [], sig: '', scheduled: null } }
}
function saveState(st) {
  try { kvSet(STORE_KEY, JSON.stringify(st)) } catch (e) { /* ignore */ }
}

/**
 * 清空通知账本（换账号防串号时调用）：账本删除、撤销本机尚未送达的系统通知、清角标。
 * 同设备切换账号后，旧账号排期的疫苗/体检/家人动态通知不应再送达或计入新账号角标。
 */
export function clearLedger() {
  try { kvRemove(STORE_KEY) } catch (e) { /* ignore */ }
  if (notifySupported()) clearLocalNotices()
  setBadgeNumber(0)
}

/* ---------- 触发时刻计算 ---------- */
/** 指定日期按提醒时刻取触发时间；免打扰开启且落在 22:00–07:00 时顺延到当日 07:00 */
function atDay(day, remind) {
  const p = String(remind.time || '09:00').split(':').map(Number)
  let h = isNaN(p[0]) ? 9 : p[0]
  let m = isNaN(p[1]) ? 0 : p[1]
  if (remind.quiet && (h >= 22 || h < 7)) { h = 7; m = 0 }
  return new Date(day.getFullYear(), day.getMonth(), day.getDate(), h, m, 0, 0)
}
/** 不早于 after 的下一次触发时刻（今天或明天） */
function nextOccurrence(remind, after) {
  const t = atDay(after, remind)
  if (t > after) return t
  return atDay(new Date(after.getFullYear(), after.getMonth(), after.getDate() + 1), remind)
}

/* ---------- 提醒任务生成 ---------- */
/**
 * 按当前提醒设置生成全部通知任务（id 稳定，设置变更后重排幂等）
 * @param {{ remind: object, vaccines: Array, baby: object|null, feeds: Array }} ctx
 */
function buildJobs(ctx) {
  const { remind, vaccines, baby, feeds } = ctx
  const t0 = new Date()
  const babyId = baby ? baby.id : ''
  const mine = vaccines.filter(v => !v.baby_id || !babyId || v.baby_id === babyId)
  const jobs = []

  /* 疫苗剂次：未接种且剂次提醒开启，计划日当天提醒时刻逐剂送达；
     已逾期（含今日已过提醒时刻）合并为一条「N 剂已逾期」每天提醒一次，避免逐剂刷屏 */
  if (remind.vaccine) {
    const overdue = []
    mine.filter(v => !v.done && v.remind && v.plan_date).forEach(v => {
      const plan = parse(v.plan_date + ' 00:00')
      const du = daysUntil(plan, t0)
      const when = atDay(plan, remind)
      if (du > 0 || (du === 0 && when > t0)) {
        jobs.push({
          id: 'v:' + v.id,
          title: '疫苗接种提醒',
          content: '宝宝「' + v.n + ' ' + v.dose + '」计划 ' + monthDay(v.plan_date) + ' 接种，记得提前准备',
          when
        })
      } else {
        overdue.push(v)
      }
    })
    if (overdue.length) {
      jobs.push({
        id: 'v:overdue',
        title: '疫苗接种提醒',
        content: overdue.length + ' 剂疫苗已过计划日期，请按当地门诊安排补种',
        when: nextOccurrence(remind, t0)
      })
    }
  }

  /* 体检与月龄发育提示：儿保节点 14 天窗口内按提醒时刻排期（中性提示，不含评估结论） */
  if (remind.checkup && baby && baby.birth_date) {
    const b = parse(baby.birth_date + ' 00:00')
    CHECKUP_NODES.forEach(nd => {
      const day = nd.d
        ? new Date(b.getFullYear(), b.getMonth(), b.getDate() + nd.d)
        : new Date(b.getFullYear(), b.getMonth() + nd.m, b.getDate())
      const du = daysUntil(day, t0)
      if (du >= 0 && du <= 14) {
        const when = atDay(day, remind)
        if (when > t0) {
          jobs.push({
            id: 'ck:' + nd.label,
            title: '体检与发育提示',
            content: '宝宝即将满' + nd.label + '，可按当地门诊安排进行儿童保健检查',
            when
          })
        }
      }
    })
  }

  /* 每日汇总：任一提醒开关开启即按提醒时刻每天提示一次（疫苗待接种数仅在疫苗提醒开启时播报） */
  if (remind.vaccine || remind.checkup || remind.anniversary || remind.msg) {
    const pending = remind.vaccine ? mine.filter(v => !v.done).length : 0
    jobs.push({
      id: 'daily',
      title: '岁记 · 每日提醒',
      content: pending ? '今日成长记录待查看 · ' + pending + ' 剂疫苗待接种' : '今日成长记录待查看',
      when: nextOccurrence(remind, t0)
    })
  }

  /* 纪念日：百日 / 生日，提前 3 天与当天各提醒一次（14 天窗口内才排期） */
  if (remind.anniversary && baby && baby.birth_date) {
    const b = parse(baby.birth_date + ' 00:00')
    const targets = []
    const hundred = new Date(b.getFullYear(), b.getMonth(), b.getDate() + 100)
    if (daysUntil(hundred, t0) >= 0 && daysUntil(hundred, t0) <= 14) targets.push({ name: '百日纪念', day: hundred })
    let bday = new Date(t0.getFullYear(), b.getMonth(), b.getDate())
    if (bday < t0) bday = new Date(t0.getFullYear() + 1, b.getMonth(), b.getDate())
    if (daysUntil(bday, t0) <= 14) targets.push({ name: '生日纪念', day: bday })
    targets.forEach(tg => {
      [-3, 0].forEach(off => {
        const day = new Date(tg.day.getFullYear(), tg.day.getMonth(), tg.day.getDate() + off)
        const when = atDay(day, remind)
        if (when > t0) {
          jobs.push({
            id: 'ann:' + tg.name + ':' + off,
            title: '纪念日提醒',
            content: off === -3
              ? '宝宝' + tg.name + '还有 3 天，可提前准备成长日记'
              : '今天是宝宝' + tg.name + '！',
            when
          })
        }
      })
    })
  }
  /* 家人动态：新动态即时送达（按记录 id 去重，同一动态只提醒一次） */
  if (remind.msg && Array.isArray(feeds)) {
    feeds.forEach(f => {
      if (!f || !f.eid) return
      jobs.push({
        id: 'f:' + f.eid,
        title: '家人动态',
        content: (f.who || '家人') + ' · ' + (f.what || '记录了一条动态'),
        when: t0
      })
    })
  }
  return jobs
}

/* 按类型配额截断：疫苗剂次再多也不应把体检/纪念日通知挤出排期（总额仍守 MAX_SCHEDULED） */
function capByType(list) {
  const pick = prefix => list.filter(j => j.id.indexOf(prefix) === 0).sort((a, b) => a.when - b.when)
  const rest = list.filter(j => j.id.indexOf('v:') !== 0 && j.id.indexOf('ck:') !== 0 && j.id.indexOf('ann:') !== 0)
  return pick('v:').slice(0, 20)
    .concat(pick('ck:').slice(0, 6), pick('ann:').slice(0, 4), rest)
    .sort((a, b) => a.when - b.when)
    .slice(0, MAX_SCHEDULED)
}

function daysUntil(d, from) {
  return Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(from.getFullYear(), from.getMonth(), from.getDate())) / 86400000)
}

/* ---------- 对外接口 ---------- */
/**
 * 同步提醒设置 → 系统通知排期 + 未读账本（bootstrap / 提醒或疫苗设置变更后调用）
 * 排期签名未变化时不重排，避免每次启动清空通知中心。
 */
export function sync(ctx) {
  const t0 = Date.now()
  const saved = loadState()
  const history = saved.jobs.filter(j => j.when <= t0 && t0 - j.when < HISTORY_KEEP_MS)
  const known = new Set(saved.jobs.map(j => j.id))
  const all = buildJobs(ctx)
  /* 即时通知（家人动态等）：触发时刻已过且账本未记录才入账，不参与排期签名 */
  const immediate = all.filter(j => j.when <= t0 && !known.has(j.id))
  const future = capByType(all.filter(j => j.when > t0))
  const keyOf = j => j.id + '@' + (+j.when)
  const sig = future.map(keyOf).join('|')
  if (!notifySupported()) {
    saveState({ jobs: history.concat(immediate, future), sig, scheduled: [] })
    refreshBadge()
    return
  }
  /* 增量重排：仅当「尚未到点的旧排期」失效（需取消）才全量 clearLocalNotices；
     纯新增或已送达项滚动不触发清空，保留通知中心里已送达的历史通知 */
  const scheduled = saved.scheduled
  const newKeys = new Set(future.map(keyOf))
  let stalePending = []
  if (scheduled) {
    stalePending = scheduled.filter(s => s.when > t0 && !newKeys.has(s.id + '@' + s.when))
  } else if (saved.sig) {
    stalePending = [{ id: 'legacy', when: t0 }] /* 旧版本无排期快照：升级后保守全量清排一次 */
  }
  if (sig !== saved.sig) {
    if (stalePending.length) {
      clearLocalNotices()
      future.forEach(scheduleLocalNotice)
    } else {
      const oldKeys = new Set((scheduled || []).map(s => s.id + '@' + s.when))
      future.filter(j => !oldKeys.has(keyOf(j))).forEach(scheduleLocalNotice)
    }
  }
  /* 即时通知延后数秒送达：排在 clearLocalNotices 之后，不被重排清掉 */
  immediate.forEach(j => scheduleLocalNotice(Object.assign({}, j, { when: t0 + 3000 })))
  saveState({ jobs: history.concat(immediate, future), sig, scheduled: future.map(j => ({ id: j.id, when: +j.when })) })
  refreshBadge()
}

/**
 * 合并服务端下发的家人动态通知进本地账本（只增，不重排既有排期）：
 * - 账本里没有的 id 才入账（幂等，重复拉取不会重复弹）；
 * - 入账即视为已送达（when=服务端创建时刻，通常已过），计入未读角标；
 * - silent=false 时对未知条目排一条即时系统通知（延迟数秒，避开重排清空）；
 *   silent=true 只进账本/消息中心，不弹系统通知（用户关了「家人动态」提醒时）。
 * 服务端为「读后即删」：读过（消息中心点击/全部已读）后由 api 层通知服务端删行，
 * 本地账本里保留只读展示，30 天后随 HISTORY_KEEP_MS 滚出。
 * @param {Array<{id:string,type?:string,eid?:string,title:string,content:string,when:number}>} jobs
 * @param {{silent?: boolean}} [opts]
 */
export function mergeFeed(jobs, opts) {
  const list = (Array.isArray(jobs) ? jobs : []).filter(j => j && j.id)
  if (!list.length) return 0
  const t0 = Date.now()
  const saved = loadState()
  const known = new Set(saved.jobs.map(j => j.id))
  const fresh = list.filter(j => !known.has(j.id))
  if (!fresh.length) return 0
  const history = saved.jobs.filter(j => j.when <= t0 && t0 - j.when < HISTORY_KEEP_MS)
  const future = saved.jobs.filter(j => j.when > t0)
  const jobsIn = fresh.map(j => ({
    id: j.id, type: j.type || '', eid: j.eid || '',
    title: j.title || '家人动态', content: j.content || '', when: j.when || t0, read: false
  }))
  saveState({ jobs: history.concat(jobsIn, future), sig: saved.sig, scheduled: saved.scheduled })
  if (!opts || !opts.silent) {
    if (notifySupported()) jobsIn.forEach(j => scheduleLocalNotice(Object.assign({}, j, { when: t0 + 3000 })))
  }
  refreshBadge()
  return fresh.length
}

/** 未读通知数 = 触发时刻已过且未读的任务数 */
export function unreadCount() {
  const t0 = Date.now()
  return loadState().jobs.filter(j => j.when <= t0 && !j.read).length
}

/** 按账本刷新应用图标角标（App onShow 时调用） */
export function refreshBadge() {
  setBadgeNumber(unreadCount())
}

/** 标记全部已送达通知为已读并清角标 */
export function markDeliveredRead() {
  const t0 = Date.now()
  const st = loadState()
  let changed = false
  st.jobs.forEach(j => { if (j.when <= t0 && !j.read) { j.read = true; changed = true } })
  if (changed) saveState(st)
  setBadgeNumber(0)
}

/** 删除全部已送达通知并清角标（消息中心「全部已读」时调用）：账本里已送达条目直接移除，列表清空；
 *  尚未到点的排期保留，到点后仍正常送达 */
export function removeDelivered() {
  const t0 = Date.now()
  const st = loadState()
  const kept = st.jobs.filter(j => j.when > t0)
  if (kept.length !== st.jobs.length) { st.jobs = kept; saveState(st) }
  setBadgeNumber(0)
}

/** 已送达通知清单（触发时刻已过，按时间倒序）· 供「消息中心 · 通知」展示 */
export function delivered() {
  const t0 = Date.now()
  return loadState().jobs
    .filter(j => j.when <= t0)
    .sort((a, b) => b.when - a.when)
    .map(j => ({ id: j.id, type: j.type || '', eid: j.eid || '', title: j.title || '岁记提醒', content: j.content || '', when: j.when, read: !!j.read }))
}

/** 标记单条通知已读并刷新角标 */
export function markOneRead(id) {
  const st = loadState()
  const j = st.jobs.find(x => x.id === id)
  if (j && !j.read) { j.read = true; saveState(st) }
  refreshBadge()
}

/** 删除单条账本条目并刷新角标（消息中心通知详情关闭后删除消息时调用） */
export function removeOne(id) {
  const st = loadState()
  const kept = st.jobs.filter(x => x.id !== id)
  if (kept.length !== st.jobs.length) { st.jobs = kept; saveState(st) }
  refreshBadge()
}

/* ---------- 通知点击直达：按任务 id 前缀解析目标页（tab 页须 switchTab） ---------- */
const TAB_PAGES = ['/pages/index/index', '/pages/grow/grow', '/pages/family/family', '/pages/me/me']
function noticeTargetUrl(id) {
  if (id && id.indexOf('v:') === 0) return '/pages/vaccine/vaccine'
  if (id && id.indexOf('ann:') === 0) return '/pages/diary/diary'
  if (id && id.indexOf('ck:') === 0) return '/pages/grow/grow'
  if (id && id.indexOf('f:') === 0) return '/pages/family/family'
  return '/pages/notify/notify'
}
function openNoticeTarget(id) {
  const url = noticeTargetUrl(id)
  const open = TAB_PAGES.indexOf(url) >= 0 ? uni.switchTab : uni.navigateTo
  open({ url, fail: () => uni.reLaunch({ url }) })
}

/** App 启动初始化：拉起通知权限、注册点击监听、按账本恢复角标 */
export function init() {
  if (!notifySupported()) return
  requestNotifyPermission()
  onNoticeClick(payload => {
    const id = payload && payload.id
    if (id) {
      const st = loadState()
      const j = st.jobs.find(x => x.id === id)
      if (j && !j.read) { j.read = true; saveState(st) }
    }
    setBadgeNumber(unreadCount())
    /* 尽力直达对应功能页（冷启动由通知拉起时等页面栈就绪再跳） */
    setTimeout(() => openNoticeTarget(id), 1200)
  })
  setBadgeNumber(unreadCount())
}
