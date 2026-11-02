/**
 * 岁记 · 疫苗时间表（领域层纯函数，可单测）
 * 时间表按接种时间顺序内置，不随清空数据丢失；持久化的只有各剂次的接种状态与提醒开关。
 */
import { parse, fmt, dayKey, daysBetween, monthDay, now } from './shared/date.js'

/**
 * 内置时间表：国家免疫规划（一类免费），按接种月龄升序排列
 * code 为剂次唯一标识（用于状态持久化对齐），months 为出生后月龄。
 */
export const VACCINE_SCHEDULE = [
  { code: 'bcg', n: '卡介苗', dose: '第 1 剂', age: '出生时', months: 0, cls: '一类' },
  { code: 'hbv1', n: '乙肝疫苗', dose: '第 1 剂', age: '出生 24 小时内', months: 0, cls: '一类' },
  { code: 'hbv2', n: '乙肝疫苗', dose: '第 2 剂', age: '1 月龄', months: 1, cls: '一类' },
  { code: 'ipv1', n: '脊髓灰质炎疫苗', dose: '第 1 剂', age: '2 月龄', months: 2, cls: '一类' },
  { code: 'dtap1', n: '百白破疫苗', dose: '第 1 剂', age: '3 月龄', months: 3, cls: '一类' },
  { code: 'ipv2', n: '脊髓灰质炎疫苗', dose: '第 2 剂', age: '3 月龄', months: 3, cls: '一类' },
  { code: 'ipv3', n: '脊髓灰质炎疫苗', dose: '第 3 剂', age: '4 月龄', months: 4, cls: '一类' },
  { code: 'dtap2', n: '百白破疫苗', dose: '第 2 剂', age: '4 月龄', months: 4, cls: '一类' },
  { code: 'dtap3', n: '百白破疫苗', dose: '第 3 剂', age: '5 月龄', months: 5, cls: '一类' },
  { code: 'hbv3', n: '乙肝疫苗', dose: '第 3 剂', age: '6 月龄', months: 6, cls: '一类' },
  { code: 'mpsva1', n: 'A 群流脑疫苗', dose: '第 1 剂', age: '6 月龄', months: 6, cls: '一类' },
  { code: 'mr1', n: '麻腮风疫苗', dose: '第 1 剂', age: '8 月龄', months: 8, cls: '一类' },
  { code: 'je1', n: '乙脑减毒活疫苗', dose: '第 1 剂', age: '8 月龄', months: 8, cls: '一类' },
  { code: 'mpsva2', n: 'A 群流脑疫苗', dose: '第 2 剂', age: '9 月龄', months: 9, cls: '一类' },
  { code: 'dtap4', n: '百白破疫苗', dose: '第 4 剂', age: '18 月龄', months: 18, cls: '一类' },
  { code: 'mr2', n: '麻腮风疫苗', dose: '第 2 剂', age: '18 月龄', months: 18, cls: '一类' },
  { code: 'hepa1', n: '甲肝减毒活疫苗', dose: '第 1 剂', age: '18 月龄', months: 18, cls: '一类' },
  { code: 'je2', n: '乙脑减毒活疫苗', dose: '第 2 剂', age: '2 周岁', months: 24, cls: '一类' },
  { code: 'mpsvac1', n: 'AC 群流脑疫苗', dose: '第 1 剂', age: '3 周岁', months: 36, cls: '一类' },
  { code: 'ipv4', n: '脊髓灰质炎疫苗', dose: '第 4 剂', age: '4 周岁', months: 48, cls: '一类' },
  { code: 'dt', n: '白破疫苗', dose: '第 1 剂', age: '6 周岁', months: 72, cls: '一类' },
  { code: 'mpsvac2', n: 'AC 群流脑疫苗', dose: '第 2 剂', age: '6 周岁', months: 72, cls: '一类' }
]

/**
 * 计划接种日期：出生日期 + 月龄（月末夹紧，与服务端 add_months_str 一致：
 * 如 1-31 +1 → 2-28/29，而非 3-03）。
 */
export function planDateFor(birthDate, months) {
  const b = parse((birthDate || dayKey(now())) + ' 00:00')
  const y = b.getFullYear()
  const m = b.getMonth() + Number(months || 0)
  const ty = y + Math.floor(m / 12)
  const tm = ((m % 12) + 12) % 12
  const lastDay = new Date(ty, tm + 1, 0).getDate()
  return fmt(new Date(ty, tm, Math.min(b.getDate(), lastDay))).slice(0, 10)
}

/** 距计划接种日的天数：>0 未到 / =0 当天 / <0 已逾期 */
export function daysToPlan(planDate, today = dayKey(now())) {
  return daysBetween(today, planDate)
}

/** 剂次状态：done 已接种 / overdue 逾期未接种 / pending 待接种 */
export function vaccineStatus(row, today = dayKey(now())) {
  if (row.done) return 'done'
  return daysToPlan(row.plan_date, today) < 0 ? 'overdue' : 'pending'
}

export const VACCINE_STATUS_TEXT = { done: '已接种', overdue: '逾期未接种', pending: '待接种' }

/** 状态补充说明：还剩几天 / 已逾期几天 / 接种日期 */
export function vaccineTip(row, today = dayKey(now())) {
  if (row.done) return row.done_date ? '接种于 ' + monthDay(row.done_date) : '已接种'
  const d = daysToPlan(row.plan_date, today)
  if (d === 0) return '就在今天'
  if (d > 0) return '还有 ' + d + ' 天'
  return '已逾期 ' + Math.abs(d) + ' 天'
}
