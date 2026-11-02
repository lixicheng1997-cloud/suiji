/**
 * 岁记 · 记录摘要生成（领域层纯函数）
 * Schema 驱动口径（TDD §5.2）：表单 payload → 时光轴展示 title/meta/badge。
 * 合规：体温 ≥38°C 仅显示固定中性文案，不做医学解读（R-04）。
 */

/** '2026-10-21 13:05' → '13:05' */
const hhmm = s => String(s).slice(11, 16)

/** 分钟 → '2 小时 15 分' / '45 分' */
function durText(min) {
  if (!min || min <= 0) return ''
  const h = Math.floor(min / 60)
  const m = Math.round(min % 60)
  return (h ? h + ' 小时' : '') + (m ? (h ? ' ' : '') + m + ' 分' : '')
}

/** 秒 → '12 秒' / '2 分 05 秒' */
function secText(s) {
  const n = Math.round(Number(s) || 0)
  if (n <= 0) return ''
  const m = Math.floor(n / 60)
  const x = n % 60
  if (!m) return n + ' 秒'
  return x ? m + ' 分 ' + (x < 10 ? '0' + x : x) + ' 秒' : m + ' 分'
}

export function sleepMinutes(payload) {
  if (!payload.start || !payload.end) return 0
  const a = new Date(payload.start.replace(' ', 'T'))
  const b = new Date(payload.end.replace(' ', 'T'))
  return Math.max(0, Math.round((b - a) / 60000))
}

/**
 * @param {string} type 记录类型
 * @param {object} payload 表单结构化数据
 * @param {string} occurredAt 'YYYY-MM-DD HH:mm'
 * @param {object} [extra] { percentileBadge, ongoing, photoCount }
 */
export function summarize(type, payload = {}, occurredAt = '', extra = {}) {
  const p = payload
  switch (type) {
    case 'feeding': {
      const method = p.method || '瓶喂'
      if (method === '辅食') {
        const foods = (p.foods || []).filter(f => f && f.indexOf('+') < 0)
        return { title: '辅食' + (foods.length ? ' · ' + foods.join('、') : ''), meta: '' }
      }
      if (method === '母乳亲喂') {
        const min = p.duration || 18
        return { title: '母乳亲喂 ' + min + ' 分钟', meta: '' }
      }
      const ml = p.amount || 120
      return { title: '瓶喂 ' + ml + 'ml', meta: (p.temp ? p.temp + '°C · ' : '') + (p.duration ? p.duration + ' 分钟喝完' : '') }
    }
    case 'sleep': {
      if (extra.ongoing) return { title: '夜间入睡', meta: hhmm(occurredAt) + ' 开始 · 进行中', badge: 'ongoing' }
      const min = sleepMinutes(p)
      return { title: (p.period || '午睡') + ' ' + (durText(min) || '—'), meta: (p.start ? hhmm(p.start) : '') + (p.end ? ' – ' + hhmm(p.end) : '') }
    }
    case 'milestone':
      return { title: p.name || '里程碑', badge: 'milestone' }
    case 'photo': {
      const n = (p.photos || []).length
      return { title: p.caption || '照片', meta: (n ? n + ' 张照片' : '') + (p.video ? ' · 1 段视频' : '') }
    }
    case 'measure': {
      const parts = []
      if (p.height) parts.push('身高 ' + p.height + 'cm')
      if (p.weight) parts.push('体重 ' + p.weight + 'kg')
      if (p.head) parts.push('头围 ' + p.head + 'cm')
      return {
        title: parts.join(' · ') || '测量',
        meta: (p.source || '') + (p.org ? ' · ' + p.org : ''),
        badge: extra.percentileBadge || ''
      }
    }
    case 'poop': {
      const ab = (p.abnormal || []).filter(Boolean)
      return {
        title: '便便 · ' + (p.texture || '未填'),
        meta: ab.length ? '标记：' + ab.join('、') : '性状正常'
      }
    }
    case 'temp': {
      const t = parseFloat(p.value) || 36.8
      const warn = t >= 38
      return {
        title: '体温 ' + t.toFixed(1) + '°C',
        meta: (p.site || '腋下') + ' · ' + (warn ? '体温偏高，建议咨询医生' : '正常范围')
      }
    }
    case 'med':
      return {
        title: p.name || '用药',
        meta: (p.dose ? p.dose + ' · ' : '') + (p.basis || '') + (p.ongoing ? ' · 连续用药中' : '')
      }
    case 'voice': {
      const dur = secText(p.duration)
      const n = (p.segments || []).length
      return {
        title: '语音' + (dur ? ' · ' + dur : ''),
        meta: (n > 1 ? n + ' 段连播' : '一段录音')
      }
    }
    default:
      return { title: p.title || '记录', meta: '' }
  }
}
