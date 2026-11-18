/** 展示格式小工具：后端时间统一是 ISO 字符串（混存口径），展示时尽量本地化。 */

export function fmtTime(s) {
  if (!s) return '-'
  const t = Date.parse(s)
  if (isNaN(t)) return String(s)
  const d = new Date(t)
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

export function fmtDate(s) {
  if (!s) return '-'
  const t = Date.parse(s)
  if (isNaN(t)) return String(s).slice(0, 10)
  const d = new Date(t)
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export function fmtBytes(b) {
  b = Number(b || 0)
  if (b < 1024) return b + ' B'
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB'
  if (b < 1073741824) return (b / 1048576).toFixed(1) + ' MB'
  return (b / 1073741824).toFixed(2) + ' GB'
}
