/**
 * 岁记 · 统计口径（领域层纯函数）
 * 硬约束（TDD §6.1）：统计只读 occurred_at，禁止 created_at。
 */
import { dayKey, now } from './shared/date.js'
import { sleepMinutes } from './summary.js'

/**
 * 今日概览三卡（与原型 DB.todayStats 同形状）
 * @param {Array} entries entry 行（含 type/occurred_at/payload）
 * @param {string} atNow 'YYYY-MM-DD HH:mm'
 */
export function todayStats(entries, atNow = now()) {
  const today = dayKey(atNow)
  const feedings = entries.filter(e => e.type === 'feeding' && dayKey(e.occurred_at) === today)
  const todays = entries.filter(e => dayKey(e.occurred_at) === today)

  /* 近 24h 睡眠：occurred_at 在 [now-24h, now] 的睡眠记录时长求和 */
  const from = new Date(String(atNow).replace(' ', 'T')).getTime() - 24 * 3600 * 1000
  let sleepMin = 0
  entries.filter(e => e.type === 'sleep').forEach(e => {
    const t = new Date(String(e.occurred_at).replace(' ', 'T')).getTime()
    if (t >= from && t <= new Date(String(atNow).replace(' ', 'T')).getTime()) {
      sleepMin += e.payload && e.payload.end ? sleepMinutes(e.payload) : (e.payload && e.payload.duration) || 0
    }
  })

  return [
    { icon: 'bottle', num: feedings.length + ' 次', label: '今日喂养', type: 'feeding' },
    { icon: 'moon', num: (sleepMin ? (sleepMin / 60).toFixed(1) : '0') + ' h', label: '近 24h 睡眠', type: 'sleep' },
    { icon: 'sparkles', num: todays.length + ' 条', label: '今日记录', type: 'milestone' }
  ]
}

/** 近 n 天各类型计数（日记事实 / 家庭动态用） */
export function countByType(entries, days = 7) {
  const from = new Date()
  from.setDate(from.getDate() - days)
  const out = {}
  entries.forEach(e => {
    const t = new Date(String(e.occurred_at).replace(' ', 'T'))
    if (t >= from) out[e.type] = (out[e.type] || 0) + 1
  })
  return out
}

/** 喂养量趋势（近 7 日瓶喂均值，日记事实用，只输出聚合值） */
export function feedingAgg(entries, days = 7) {
  const from = new Date()
  from.setDate(from.getDate() - days)
  let total = 0
  let n = 0
  entries.forEach(e => {
    if (e.type !== 'feeding') return
    const t = new Date(String(e.occurred_at).replace(' ', 'T'))
    if (t < from) return
    const ml = e.payload && e.payload.amount
    if (ml) { total += Number(ml); n++ }
  })
  return { count: n, avg: n ? Math.round(total / n) : 0 }
}
