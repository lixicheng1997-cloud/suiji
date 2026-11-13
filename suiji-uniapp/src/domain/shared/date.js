/**
 * 岁记 · 日期与月龄口径（领域层纯函数，可单测）
 * 统一约定：occurred_at / created_at 存储格式为 'YYYY-MM-DD HH:mm'。
 * 所有统计查询只允许读 occurred_at（TDD §6.1 强化口径）。
 */

const pad = n => (n < 10 ? '0' + n : '' + n)

/** Date → 'YYYY-MM-DD HH:mm' */
export function fmt(d) {
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
    ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes())
}

/** 'YYYY-MM-DD HH:mm' → Date（按本地时区解析） */
export function parse(s) {
  if (!s) return null
  const [d, t] = String(s).split(' ')
  const [y, m, day] = d.split('-').map(Number)
  const [hh = 0, mm = 0] = (t || '').split(':').map(Number)
  return new Date(y, m - 1, day, hh, mm)
}

/** 当前时间字符串 */
export function now() {
  return fmt(new Date())
}

/** 'YYYY-MM-DD HH:mm' → 'YYYY-MM-DD' */
export function dayKey(s) {
  return String(s).slice(0, 10)
}

/** 'YYYY-MM-DD HH:mm' → 'HH:mm' */
export function timeOf(s) {
  return String(s).slice(11, 16)
}

/** 'YYYY-MM-DD' → 'M 月 D 日' */
export function monthDay(dk) {
  /* 未排期的剂次传进来就是空串：NaN 月 NaN 日会直接印在疫苗列表上 */
  const parts = String(dk || '').split('-')
  if (parts.length < 3 || isNaN(Number(parts[1])) || isNaN(Number(parts[2]))) return ''
  const [, m, d] = parts
  return Number(m) + ' 月 ' + Number(d) + ' 日'
}

/** 日分组标签：今天 / 昨天 / M 月 D 日 */
export function dayLabel(dk, today = dayKey(now())) {
  if (dk === today) return '今天 · ' + monthDay(dk)
  const t = parse(today + ' 00:00')
  const y = new Date(t.getFullYear(), t.getMonth(), t.getDate() - 1)
  if (dk === fmt(y).slice(0, 10)) return '昨天 · ' + monthDay(dk)
  return monthDay(dk)
}

/** 两个 'YYYY-MM-DD' 之间的天数（b - a） */
export function daysBetween(a, b) {
  const da = parse(a + ' 00:00')
  const db = parse(b + ' 00:00')
  return Math.round((db - da) / 86400000)
}

/** 实际月龄（未做早产矫正） */
function actualMonths(b, t) {
  let months = (t.getFullYear() - b.getFullYear()) * 12 + (t.getMonth() - b.getMonth())
  months += (t.getDate() - b.getDate()) / 30.4375
  return months
}

/** 早产矫正基准周数（足月儿 40 周）；仅在实际年龄未满预产期前回拨 */
const TERM_WEEKS = 40

/**
 * 月龄文字「X 个月 Y 天」：按实际日历年龄计算，不做早产矫正回拨。
 * @param {string} birthDate 'YYYY-MM-DD'
 * @param {string} at 'YYYY-MM-DD HH:mm' 或 'YYYY-MM-DD'
 * @param {number} [gestWeeks] 出生胎龄（周），仅用于保持签名一致，文字月龄不矫正
 */
export function ageText(birthDate, at, gestWeeks) {
  const b = parse(birthDate + ' 00:00')
  const target = parse(at.length > 10 ? at.slice(0, 10) + ' 00:00' : at + ' 00:00')
  const months = actualMonths(b, target)
  if (months < 0) return '未出生'
  const m = Math.floor(months)
  const base = addMonths(b, m)
  const days = Math.max(0, Math.round((target - base) / 86400000))
  if (m === 0) return days + ' 天'
  return m + ' 个月' + (days > 0 ? ' ' + days + ' 天' : '')
}

/** 月龄（小数，用于曲线横轴；含早产矫正，满预产期后停止回拨） */
export function ageMonths(birthDate, at, gestWeeks) {
  const b = parse(birthDate + ' 00:00')
  const t = parse(at.length > 10 ? at : at + ' 00:00')
  let months = actualMonths(b, t)
  const gw = Number(gestWeeks || 0)
  if (gw && gw < 37) {
    const due = new Date(b.getTime() + (TERM_WEEKS - gw) * 7 * 86400000)
    if (t < due) months -= (TERM_WEEKS - gw) / 4.345
  }
  return months
}

/** Date + n 个月 */
export function addMonths(d, n) {
  const x = new Date(d.getFullYear(), d.getMonth() + n, d.getDate())
  return x
}
