/**
 * 岁记 · 主题状态存储
 * 轻量全局单例：内存 current + uni storage 持久化 + uni.$emit 广播。
 * 页面通过 theme/useTheme.js 混入订阅 'sj:theme' 实现实时换肤。
 */
import { DEFAULT_THEME } from './theme.js'

const KEY = 'sj_theme'

let current = DEFAULT_THEME
try {
  const saved = uni.getStorageSync(KEY)
  if (saved === 'bear' || saved === 'duck') current = saved
} catch (e) { /* ignore */ }

export function getTheme() {
  return current
}

export function setTheme(name) {
  if (name !== 'bear' && name !== 'duck') return
  if (name === current) return
  current = name
  try { uni.setStorageSync(KEY, name) } catch (e) { /* ignore */ }
  uni.$emit('sj:theme', name)
}

export function toggleTheme() {
  setTheme(current === 'duck' ? 'bear' : 'duck')
}
