/**
 * 岁记 · ID 生成（领域层，零平台依赖）
 * 客户端生成 id 作为记录主键，需保证跨设备唯一。
 * 采用「时间戳 base36 + 随机段」组合，碰撞概率对自用场景足够。
 */
export function genId(prefix = '') {
  const t = Date.now().toString(36)
  const r = Math.random().toString(36).slice(2, 8)
  return (prefix ? prefix + '_' : '') + t + r
}
