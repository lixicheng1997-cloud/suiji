/**
 * tabSwipe · 底部页签左右滑动切换 + 切页过渡动画 + 下拉刷新（四个 tab 页共用）
 *
 * 用法：页面根节点绑定 @touchstart="onTabTouchStart" @touchend="onTabTouchEnd"
 * 与 :class="swipeClass"（切页动画类，关键帧定义见 App.vue 全局样式）。
 * 页面自身可覆盖 tabSwipeAllowed() 在弹层/面板展开时临时禁用滑动；
 * 页面需顶层声明 onPullDownRefresh() { pullRefresh(this) }（Vue3 生命周期不放 methods），
 * 覆盖 tabAfterPull() 在下拉刷新重拉服务端快照（bootstrap）后做本页面重渲染。
 */

import * as ui from '@/utils/ui.js'
import * as api from '@/utils/api.js'

/* 与 pages.json tabBar 顺序一致 */
const TAB_URLS = ['/pages/index/index', '/pages/grow/grow', '/pages/family/family', '/pages/me/me']

const MIN_DX = 60      // 横向最小位移（px）
const MIN_RATIO = 1.8  // |dx| 需大于 |dy| 的该倍数，避免与纵向滚动误判
const OUT_MS = 180     // 当前页滑出时长（与 App.vue ts-out-slide-* 动画时长一致）

/**
 * 下拉刷新执行体：重拉服务端快照（bootstrap，force 强制新请求）成功后提示「已刷新」
 * 并调页面 tabAfterPull 重渲染；失败静默（bootstrap 已 silent，保留当前数据）。
 * 注意：uni-app Vue3 页面生命周期必须是组件顶层选项（混入 methods 里的 onPullDownRefresh 不会触发），
 * 故由各 tab 页顶层声明 onPullDownRefresh() { pullRefresh(this) } 转调此处。
 * @param {object} vm tab 页组件实例
 */
export function pullRefresh(vm) {
  api.bootstrap({ silent: true, force: true })
    .then(() => { ui.toast('已刷新'); return vm.tabAfterPull() })
    .catch(() => { /* 失败保留当前数据，静默收起 */ })
    .then(() => { uni.stopPullDownRefresh() })
}

/* touch 事件取末位触点（touchend 时 touches 已空，只能用 changedTouches） */
function pointOf(e) {
  const t = (e && e.changedTouches && e.changedTouches[0]) || (e && e.touches && e.touches[0])
  if (!t) return null
  return { x: t.clientX !== undefined ? t.clientX : t.pageX, y: t.clientY !== undefined ? t.clientY : t.pageY }
}

/* 当前页面在 TAB_URLS 中的下标；非 tab 页返回 -1 */
function currentIndex() {
  const pages = getCurrentPages()
  if (!pages.length) return -1
  const route = pages[pages.length - 1].route || ''
  return TAB_URLS.indexOf('/' + route)
}

export default {
  data() {
    return { tabTouchStart: null, swipeClass: '' }
  },

  /* 退场动画保持终态（both）直到换页完成，回到本页时清掉 */
  onHide() {
    this.swipeClass = ''
  },

  methods: {
    /* 默认允许滑动；页面覆盖即可临时关闭 */
    tabSwipeAllowed() {
      return true
    },
    /* 下拉刷新钩子：页面顶层 onPullDownRefresh 转调 pullRefresh() 重拉 bootstrap 后，
     * 由本方法做本地重渲染（页面覆盖） */
    tabAfterPull() {},

    onTabTouchStart(e) {
      const p = pointOf(e)
      this.tabTouchStart = p ? { x: p.x, y: p.y } : null
    },
    onTabTouchEnd(e) {
      const start = this.tabTouchStart
      this.tabTouchStart = null
      if (!start || this._tabSwitching || !this.tabSwipeAllowed()) return
      /* 弹窗 / 动作面板待应答时不切页（遮罩在页面之上，触摸仍会冒泡到根节点） */
      if (ui.isBusy()) return
      const p = pointOf(e)
      if (!p) return
      const dx = p.x - start.x
      const dy = p.y - start.y
      if (Math.abs(dx) < MIN_DX || Math.abs(dx) < Math.abs(dy) * MIN_RATIO) return
      const cur = currentIndex()
      if (cur < 0) return
      const next = dx < 0 ? cur + 1 : cur - 1
      if (next < 0 || next >= TAB_URLS.length) return
      /* 过渡只做退场：当前页朝滑动方向滑出淡出后换页，目标页直接呈现。
       * app 端目标页 webview 早已渲染，再补进场动画会先露静态帧再跳变，
       * 观感像"加载了两次"；退场类不清除，保持终态到 onHide 再清，
       * 避免换页瞬间透明度回弹闪一下 */
      const side = dx < 0 ? 'left' : 'right'
      this._tabSwitching = true
      this.swipeClass = 'ts-out-slide-' + side
      setTimeout(() => {
        uni.switchTab({
          url: TAB_URLS[next],
          fail: () => { this.swipeClass = '' },
          complete: () => { this._tabSwitching = false }
        })
      }, OUT_MS)
    }
  }
}
