/**
 * 岁记 · 会话内媒体上传任务队列（方案 C：记录先落库，媒体后台上传后回填）。
 *
 * 边界（对齐 PRD ADR-007，本期纯在线，不做跨进程离线队列）：
 * - 任务只存活在本会话内存；App/小程序被杀后任务丢失，记录保留但媒体标「未上传」，
 *   持久化续传属 V1.3 演进，不在本期；
 * - 队列只管任务编排 / 状态机 / 进度 / 重试，不直接碰缓存与 HTTP：
 *   上传器与回填回调由 api.js 注入，避免模块循环依赖。
 *
 * 任务状态机：pending → uploading → done；失败重试 N 次后 → failed（可手动 retry）。
 * 状态：'pending' | 'uploading' | 'done' | 'failed'
 */

const RETRY_TIMES = 2

/* entryId → task[]；task 形状见 enqueueVideo */
const jobs = new Map()

/* 由 api.js 注入：uploadOne(task, onProgress) => Promise<remote>；onSettle(entryId, kind, items) */
let uploadOne = null
let onSettle = null

/**
 * 绑定上传执行器与回填回调（api.js 初始化时调用一次）。
 * @param {{uploadOne?: Function, onSettle?: Function}} handlers
 */
export function bindQueue(handlers) {
  const h = handlers || {}
  uploadOne = typeof h.uploadOne === 'function' ? h.uploadOne : null
  onSettle = typeof h.onSettle === 'function' ? h.onSettle : null
}

/**
 * 入队一段/多段本地媒体。
 * @param {string} entryId 记录 id（落库后才有）
 * @param {'video'} kind 本期仅视频；照片/语音仍走同步上传
 * @param {Array<{index:number, localPath:string, thumbPath?:string, meta?:object}>} items
 * @param {object} ctx 透传给上传器的上下文（如 babyId）
 */
export function enqueue(entryId, kind, items, ctx) {
  if (!entryId || !Array.isArray(items) || !items.length) return
  const list = items.map((it, i) => ({
    entryId,
    kind,
    index: Number(it.index != null ? it.index : i),
    localPath: it.localPath || '',
    thumbPath: it.thumbPath || '',
    meta: it.meta || {},
    ctx: ctx || {},
    status: 'pending',
    progress: 0,
    remote: null,
    retries: 0
  }))
  jobs.set(entryId, list)
  list.forEach(run)
}

function run(task) {
  if (!uploadOne) {
    task.status = 'failed'
    emit(task)
    return
  }
  task.status = 'uploading'
  emit(task)
  const onProgress = p => {
    task.progress = Math.max(0, Math.min(100, Math.round(Number(p) || 0)))
    emit(task)
  }
  Promise.resolve()
    .then(() => uploadOne(task, onProgress))
    .then(remote => {
      task.status = 'done'
      task.progress = 100
      task.remote = remote || null
      emit(task)
    })
    .catch(() => {
      if (task.retries < RETRY_TIMES) {
        task.retries += 1
        task.status = 'pending'
        run(task)
      } else {
        task.status = 'failed'
        emit(task)
      }
    })
}

/* 任一任务状态变化：把该记录整类最新清单回吐给回填回调 */
function emit(task) {
  if (!onSettle) return
  const list = jobs.get(task.entryId) || []
  onSettle(task.entryId, task.kind, list.map(serialize))
}

function serialize(task) {
  return {
    index: task.index,
    status: task.status,
    progress: task.progress,
    remote: task.remote,
    meta: task.meta
  }
}

/** 读某条记录在队列中的任务清单（读侧进度兜底用；正常以缓存 payload 为准） */
export function tasksOf(entryId) {
  return jobs.has(entryId) ? jobs.get(entryId).map(serialize) : []
}

/** 手动重跑该记录所有失败任务（用户在占位失败态点击重传） */
export function retryFailed(entryId) {
  const list = jobs.get(entryId) || []
  list.filter(t => t.status === 'failed').forEach(t => {
    t.retries = 0
    t.status = 'pending'
    run(t)
  })
}

/** 记录被删除时清理在途任务，避免回填到已删记录 */
export function clearEntry(entryId) {
  jobs.delete(entryId)
}
