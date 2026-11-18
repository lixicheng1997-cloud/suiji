/**
 * 岁记 · 浮层布局共享计算
 *
 * sj-notify（顶部通知横幅）与 sj-net-banner（全局离线横幅）都是 fixed 贴顶浮层，
 * 共用同一套「状态栏 / 原生导航栏避让」计算，避免两处逻辑漂移。
 */

/* 使用默认原生导航栏的页面（pages.json 未设 navigationStyle:custom）：
 * fixed 坐标已从导航栏下缘起算，再叠加 statusBarHeight 会导致浮层整体偏下 */
const NATIVE_NAV_ROUTES = ['pages/grow/grow', 'pages/family/family', 'pages/me/me']

/* 离线横幅固定高度（rpx，与 sj-net-banner 样式一致），供 sj-notify 避让下移 */
export const NET_BANNER_H = 64

/**
 * 计算顶部 fixed 浮层的定位样式。
 * App/小程序端 CSS 变量 --status-bar-height 为固定 25px 不可靠，改用 JS 实际像素值；
 * 取不到系统信息时返回 CSS 变量兜底 calc（uni 三端均定义 --window-top/--status-bar-height）。
 * @param {number} [gapUpx=24] 浮层上缘呼吸间距（rpx）
 * @param {number} [extraUpx=0] 额外下移量（rpx，如离线横幅占位高度）
 * @returns {{ top: string } | null} 内联 style（null = 交回样式表 CSS 变量兜底）
 */
export function notifyTop(gapUpx = 24, extraUpx = 0) {
  const extra = extraUpx > 0 ? uni.upx2px(extraUpx) : 0
  let sb = 0
  let route = ''
  try {
    const info = (uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()) || {}
    sb = info.statusBarHeight || 0
    const pages = getCurrentPages()
    const cur = pages[pages.length - 1]
    route = (cur && cur.route) || ''
  } catch (e) { /* 取不到时走 CSS 变量兜底 */ }
  if (NATIVE_NAV_ROUTES.indexOf(route) !== -1) {
    // #ifndef H5
    return { top: (uni.upx2px(gapUpx) + extra) + 'px' }
    // #endif
    // #ifdef H5
    return { top: `calc(var(--window-top, 0px) + ${gapUpx}rpx${extra ? ' + ' + extra + 'px' : ''})` }
    // #endif
  }
  if (sb > 0) return { top: (sb + uni.upx2px(gapUpx) + extra) + 'px' }
  return { top: `calc(var(--window-top, 0px) + var(--status-bar-height, 0px) + ${gapUpx}rpx${extra ? ' + ' + extra + 'px' : ''})` }
}
