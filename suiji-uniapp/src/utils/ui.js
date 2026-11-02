/**
 * 岁记 · UI 交互调用层（替代 uni.showModal / showToast / showActionSheet / showLoading）
 * Promise 化：本文件通过 uni.$emit 把请求广播给页面里的 sj-ui-host 组件渲染，
 * host 收到用户操作后经 'sj-ui-cb' 事件回传结果，本文件 resolve。
 * 多页栈安全：pending 一次性消费（get 后立即 delete），即使栈中多个 host
 * 同时响应，也只有第一个回传的 cbId 能命中，其余被忽略。
 */

/* cbId -> resolve 的等待表 */
const pending = new Map()
let cbSeq = 0

/* 模块顶层注册一次回调监听 */
uni.$on('sj-ui-cb', ({ cbId, result }) => {
  const settle = pending.get(cbId)
  if (!settle) return
  pending.delete(cbId)
  settle(result)
})

/* 浮层宿主存活探测：uni.$emit 是同步广播，emit 后计数未变说明当前页没有
 * 可用的 <sj-ui-host />（未挂载 / 不在栈顶），此时降级到 uni 原生 API，
 * 保证「接口报错一定让用户看见」，不会因漏挂宿主而静默失败。 */
let toastAck = 0
let dialogAck = 0
let loadingAck = 0
uni.$on('sj-ui-toast-ack', () => { toastAck++ })
uni.$on('sj-ui-dialog-ack', () => { dialogAck++ })
uni.$on('sj-ui-loading-ack', () => { loadingAck++ })

/* ---------- 全屏加载（sj-loading 的唯一调用入口） ----------
 * 页面不再各自铺 <sj-loading> 标签：本层维护一条栈，栈顶那项即当前展示项，
 * 由 <sj-ui-host> 里的 sj-loading 渲染。并发长任务（如上传 + 建档）各持句柄，
 * 后打开的覆盖先打开的文案，关闭后自动回落到下一条，互不打架。
 * 无宿主时降级 uni.showLoading(mask)，保证「等待一定看得见」，与 dialog/toast 同一策略。 */
const loadingStack = []
let loadingSeq = 0
let nativeLoading = false    // 当前是否处于原生降级展示
/* 看门狗：漏写 close（异常分支、Promise 永不 settle）会把全屏遮罩永久留在屏幕上，
 * 宁可到点自动收起，也不能让用户只能杀应用。超时长任务用 opts.timeout 放宽。 */
const LOADING_MAX_MS = 30000

function topLoading() {
  return loadingStack.length ? loadingStack[loadingStack.length - 1] : null
}

function renderLoading() {
  const item = topLoading()
  const before = loadingAck
  uni.$emit('sj-ui-loading', { item })
  if (loadingAck !== before || !item) {
    /* 宿主已接管：交给 sj-loading 渲染，原生不再插手 */
    if (nativeLoading) { uni.hideLoading(); nativeLoading = false }
    return
  }
  nativeLoading = true
  uni.showLoading({ title: item.text, mask: true })
}

/**
 * 打开全屏阻断式加载（异步取数 / 上传 / 导出 / 生成等长任务）。
 * **务必在 finally 里 h.close()**；即便漏写，看门狗也会在 timeout 后自动收起。
 * @param {string} text 主文案，≤12 字、现在进行时（如「正在上传照片…」）
 * @param {object} [opts] { sub='', percent=null, timeout=30000 }
 *                        percent 不传则不显示进度条；timeout 传 0 表示不自动收起
 * @returns {{ id:number, close:Function, update:Function }} 句柄
 */
export function loading(text, opts) {
  const o = opts || {}
  const item = {
    id: ++loadingSeq,
    text: String(text || '加载中，请稍候…'),
    sub: o.sub || '',
    percent: o.percent === undefined || o.percent === null ? null : Number(o.percent)
  }
  loadingStack.push(item)
  renderLoading()
  const close = () => {
    const i = loadingStack.indexOf(item)
    if (i < 0) return
    clearTimeout(item.timer)
    loadingStack.splice(i, 1)
    /* 原生降级与宿主可能同时在场（loading 在 onShow 打开、host 随后 created 同步展示）：
     * 收起原生后必须再 renderLoading() 广播一次，否则 host 的 sj-loading 收不到
     * item=null，遮罩会永久留在屏幕上。 */
    if (nativeLoading) {
      uni.hideLoading()
      nativeLoading = false
    }
    renderLoading()
  }
  const ms = o.timeout === undefined ? LOADING_MAX_MS : Number(o.timeout)
  if (ms > 0) item.timer = setTimeout(close, ms)
  const repaint = () => {
    /* 只有栈顶项的变化才需要重新渲染 */
    if (topLoading() === item) renderLoading()
  }
  return {
    id: item.id,
    close,
    /** 更新文案 / 进度（同一句柄原地刷新，不产生新的遮罩层级） */
    update(next) {
      const n = next || {}
      if (n.text !== undefined) item.text = String(n.text)
      if (n.sub !== undefined) item.sub = String(n.sub)
      if (n.percent !== undefined) {
        item.percent = n.percent === null || n.percent === '' ? null : Number(n.percent)
      }
      /* 文案一变说明任务仍在推进，看门狗重新计时 */
      if (item.timer) {
        clearTimeout(item.timer)
        if (ms > 0) item.timer = setTimeout(close, ms)
      }
      repaint()
    }
  }
}

/* 当前应展示的全屏加载项（栈顶）；无在途任务返回 null，供新挂载的 host 补同步 */
export function loadingState() {
  return topLoading()
}

/* 是否有等待用户应答的浮层（alert / confirm / sheet 都挂在 pending 上）。
 * tab 页左右滑动切换前用它避让，避免在弹窗下面误切页。 */
export function isBusy() {
  return pending.size > 0 || loadingStack.length > 0
}

/**
 * 轻提示（即发即忘，不返回 Promise）
 * 页面内提示已迁移为 <sj-notify ref="ntf" /> 直接调用；本函数仅保留给
 * 非组件场景（http.js 兜底、error() 统一入口）经 <sj-ui-host> 内嵌的
 * sj-notify 渲染顶部横幅。
 * @param {string} title 文案
 * @param {number} duration 停留毫秒，默认 2200
 * @param {string} type sj-notify 语义：'ok'|'warn'|'err'，默认 'ok'
 */
export function toast(title, duration = 2200, type = 'ok') {
  const text = String(title || '')
  const before = toastAck
  uni.$emit('sj-ui-toast', { payload: { title: text, duration, type } })
  if (toastAck === before) uni.showToast({ title: text, icon: 'none', duration })
}

/**
 * 错误提示（接口报错统一入口）：同一条错误只提示一次。
 * api/http.js 会在请求失败时排队兜底提示，页面 catch 内先调用本函数
 * 即可用自己的文案覆盖兜底文案（并取消排队的那一条）。
 * @param {Error|string} err 错误对象（取 err.friendly / err.message）
 * @param {string} [fallback] 错误对象无文案时的兜底
 */
export function error(err, fallback) {
  if (!err) {
    if (fallback) toast(fallback, 2200, 'err')
    return
  }
  if (typeof err !== 'object') { toast(String(err) || fallback || '操作失败，请稍后再试', 2200, 'err'); return }
  if (err.__notified) return   // 已提示过，不重复打扰
  err.__notified = true
  err.__pending = false        // 取消 http.js 的排队兜底提示
  toast(err.friendly || err.message || fallback || '操作失败，请稍后再试', 2200, 'err')
}

/**
 * 单按钮提示弹窗（需要用户明确知晓的场景，如接口报错）
 * @param {object|string} opts { title, content, confirmText='我知道了', danger, icon } 或直接传文案
 * @returns {Promise<{confirm: boolean, content: string}>}
 */
export function alert(opts) {
  const o = typeof opts === 'string' ? { content: opts } : (opts || {})
  return confirm({
    title: o.title || '提示',
    content: o.content || '',
    confirmText: o.confirmText || '我知道了',
    cancelText: '',
    showCancel: false,
    danger: !!o.danger,
    icon: o.icon || ''
  })
}

/**
 * 自定义确认弹窗（对齐 uni.showModal 语义）
 * @param {object} opts { title, content, confirmText='确定', cancelText='取消',
 *                        showCancel=true, danger=false, editable=false, placeholder='',
 *                        icon=''（sj-modal 图标：'danger'|'info'|'ok' 语义或 v2 png 图标名） }
 * @returns {Promise<{confirm: boolean, content: string}>}
 */
export function confirm(opts) {
  const payload = Object.assign({
    title: '', content: '', confirmText: '确定', cancelText: '取消',
    showCancel: true, danger: false, editable: false, placeholder: '', icon: ''
  }, opts || {})
  return new Promise(resolve => {
    const cbId = ++cbSeq
    pending.set(cbId, resolve)
    const before = dialogAck
    uni.$emit('sj-ui-dialog', { payload, cbId })
    /* 无宿主渲染时降级到 uni.showModal，避免弹窗「发了但没人接」导致流程卡死 */
    if (dialogAck === before) {
      pending.delete(cbId)
      uni.showModal({
        title: payload.title,
        content: payload.content,
        confirmText: payload.confirmText,
        cancelText: payload.cancelText,
        showCancel: payload.showCancel,
        editable: payload.editable,
        placeholderText: payload.placeholder,
        success: r => resolve({ confirm: !!r.confirm, content: r.content || '' }),
        fail: () => resolve({ confirm: false, content: '' })
      })
    }
  })
}

/**
 * 底部动作面板（对齐 uni.showActionSheet 语义）
 * @param {object} opts { itemList: [{ label, sub?, danger? }], alert? }
 * @returns {Promise<number>} 选中下标；取消为 -1
 */
export function sheet(opts) {
  const o = opts || {}
  const payload = { itemList: o.itemList || [], alert: o.alert || '' }
  return new Promise(resolve => {
    const cbId = ++cbSeq
    pending.set(cbId, resolve)
    uni.$emit('sj-ui-sheet', { payload, cbId })
  })
}

/**
 * 兼容旧模式：接受 uni.showModal 原始参数（含 success/fail/complete 回调），
 * 页面接线时可直接把 `uni.showModal(` 改成 `ui.showModal(`。
 * 支持 showCancel:false、editable:true、placeholderText、confirmText/cancelText。
 * @returns {Promise<{confirm: boolean, content: string}>}
 */
export function showModal(opts) {
  const o = opts || {}
  return confirm({
    title: o.title,
    content: o.content,
    confirmText: o.confirmText || '确定',
    cancelText: o.cancelText || '取消',
    showCancel: o.showCancel !== false,
    danger: !!o.danger,
    editable: !!o.editable,
    placeholder: o.placeholderText || '',
    icon: o.icon || ''
  }).then(res => {
    const r = { confirm: res.confirm, content: res.content || '' }
    if (typeof o.success === 'function') o.success(r)
    if (typeof o.complete === 'function') o.complete(r)
    return r
  })
}

/**
 * 兼容旧模式：接受 uni.showActionSheet 原始参数（itemList 为字符串数组），
 * 页面接线时可直接把 `uni.showActionSheet(` 改成 `ui.showActionSheet(`。
 * 取消按 uni 语义走 fail({ errMsg }) 并 reject（与官方 Promise 化行为一致）。
 * @returns {Promise<{tapIndex: number}>}
 */
export function showActionSheet(opts) {
  const o = opts || {}
  const itemList = (o.itemList || []).map(label => ({ label }))
  return sheet({ itemList }).then(tapIndex => {
    if (tapIndex >= 0) {
      const r = { tapIndex }
      if (typeof o.success === 'function') o.success(r)
      if (typeof o.complete === 'function') o.complete(r)
      return r
    }
    const err = { errMsg: 'showActionSheet:fail cancel' }
    if (typeof o.fail === 'function') o.fail(err)
    if (typeof o.complete === 'function') o.complete(err)
    return Promise.reject(err)
  })
}
