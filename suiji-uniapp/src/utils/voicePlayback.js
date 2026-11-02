/**
 * 岁记 · 分段语音的顺序播放
 *
 * 一段录音可能落成多个独立文件（早前的「暂停分段」录法、以及单段录音），
 * 服务端（suiji-server）没有 ffmpeg 也不做合并队列，所以播放端按段顺序排队衔接，
 * 形成立即反馈的「整条试听」。
 *
 * 源地址统一过 http.resolveUrl：本地 blob/临时路径原样放行，
 * 云端 /api/v1/files/… 自动补 media token（否则 innerAudioContext 直接 403）。
 */

import { resolveUrl } from '@/api/http.js'

function srcOf(seg) {
  const raw = seg && (seg.url || seg.path)
  return raw ? resolveUrl(String(raw)) : ''
}

/* 全局只有一个在播的实例：时光轴上可能同时躺着几条语音，点新的必须收掉旧的，
   否则两段声音会叠播（各 InnerAudioContext 之间互不感知）。 */
let current = null

/* 起播后这么久都没有任何播放迹象（onPlay / timeupdate 都没来过）＝ 这次没播起来：
   弱网下云端语音文件要下载一会儿，所以给得比较宽；到点就让 UI 复位，别空转。 */
const START_STALL = 12000

/**
 * 创建一个播放器实例（一个页面/组件持有一个，用完记得 destroy）
 */
export function createVoicePlayer() {
  let audio = null
  let list = [] /* [{ src, start, dur }]：start 是该段在整条录音里的起点，用来换算总进度 */
  /* 当前实例上已加载的 src：同一个 src 再播时只需把播放头归零，不要重建实例
     （重建 = 重新拉流，弱网下声音比进度慢，听起来就是「没声音/很快结束」） */
  let curSrc = ''
  let idx = -1
  let onIndex = null
  let onFinish = null
  let playError = null
  let onProgress = null
  /* 进度兜底：onTimeUpdate 在部分端不回调（H5 运行时只调 callback()，不带事件对象），
     所以按「事件参数 → audio.currentTime 属性 → 起播挂钟」三级取值，保证 UI 时间一定在走 */
  let lastEventAt = 0
  let segStartAt = 0
  let lastProp = -1
  let ticker = 0
  /* started：真的起播过（收到 onPlay 或时间推进）；没起播前不许用挂钟编进度 */
  let started = false
  /* progressSeen：本段推进过进度。「刚起播就 ended 且从未推进」＝该端没把播放头归零 */
  let progressSeen = false
  /* 已经靠「重建实例」救过的那一段，避免救不回来时反复重建 */
  let healed = -1

  function emit(t) {
    if (idx < 0 || !onProgress) return
    const seg = list[idx]
    if (!seg) return
    const cur = Number(t)
    if (!(cur >= 0)) return
    if (cur > 0.02) progressSeen = true
    onProgress(Math.min(seg.start + seg.dur, seg.start + cur))
  }

  function readProp() {
    try {
      const v = Number(audio && audio.currentTime)
      return isFinite(v) && v >= 0 ? v : -1
    } catch (e) {
      return -1 /* 该端没有可读的 currentTime 属性 */
    }
  }

  function tick() {
    if (idx < 0 || !onProgress) return
    const now = Date.now()
    if (!started) {
      if (now - segStartAt > START_STALL) fail()
      return /* 还没起播：进度保持 0，别让挂钟把时间跑到声音前面 */
    }
    if (now - lastEventAt < 1200) return /* 事件通路正常时不插手，避免两路数据来回跳 */
    const prop = readProp()
    /* 属性读不到、或连续 1.5s 纹丝不动（假值）：改用挂钟推算，段末由 onEnded 校正 */
    if (prop < 0 || (prop === lastProp && now - segStartAt > 1500)) {
      const seg = list[idx]
      if (seg) emit(Math.min(seg.dur, (now - segStartAt) / 1000))
      return
    }
    lastProp = prop
    emit(prop)
  }

  function startTick() {
    if (ticker) return
    ticker = setInterval(tick, 250)
  }

  function stopTick() {
    if (ticker) { clearInterval(ticker); ticker = 0 }
  }

  function ctx() {
    if (audio) return audio
    const a = uni.createInnerAudioContext()
    audio = a
    a.onPlay(() => {
      if (a !== audio) return
      started = true
      lastEventAt = Date.now()
    })
    a.onTimeUpdate(e => {
      if (a !== audio) return /* 已换实例：旧实例的迟到回调不再影响进度 */
      const t = Number(e && e.currentTime)
      const cur = isFinite(t) && t >= 0 ? t : readProp()
      if (cur < 0) return
      started = true
      lastEventAt = Date.now()
      lastProp = cur
      emit(cur)
    })
    a.onEnded(() => {
      if (a !== audio) return
      if (heal()) return
      if (idx >= 0 && idx < list.length - 1) { playIdx(idx + 1); return }
      const last = list[list.length - 1]
      if (onProgress && last) onProgress(last.start + last.dur)
      finish()
      if (onFinish) onFinish()
    })
    a.onError(() => {
      if (a !== audio) return
      if (heal()) return
      /* 某一段损坏不阻断后续：跳过它继续播，整条队列都失败才报错 */
      if (idx >= 0 && idx < list.length - 1) { playIdx(idx + 1); return }
      fail()
    })
    return a
  }

  /* 起播即失败（秒结束 / 直接报错）：换成新实例再播这一遍，只救一次 */
  function heal() {
    const seg = list[idx]
    if (idx < 0 || !seg || progressSeen || healed === idx) return false
    if (Date.now() - segStartAt >= Math.min(600, seg.dur * 1000)) return false
    release()
    playIdx(idx, true)
    return true
  }

  /* 整条队列起播失败：收掉进度，让调用方复位 UI */
  function fail() {
    const f = playError
    finish()
    if (f) f()
  }

  function playIdx(i, rebuild) {
    idx = i
    segStartAt = Date.now()
    lastProp = -1
    started = false
    progressSeen = false
    healed = rebuild ? i : -1
    if (onIndex) onIndex(i)
    const src = list[i].src
    const same = src === curSrc
    if (rebuild) release()
    const c = ctx()
    curSrc = src
    c.src = src
    /* 同一句重播（听完再点、停止后再点）：对同一个 src 重复赋值不会重新加载，
       播放头仍停在末尾，play() 会立刻 onEnded ——「听一遍后再点就直接结束」的根因。
       stop 归零 + seek 兜底把播放头带回起点；仍然秒结束就由 heal() 换新实例重来。 */
    if (same && !rebuild) {
      try {
        c.stop()
        c.seek(0)
      } catch (e) { /* 该端 stop/seek 不可用：交给 heal() */ }
    }
    c.play()
    startTick()
  }

  /* 丢掉当前音频实例（正常播放路径不会走到这里，只有救场时用） */
  function release() {
    stopTick()
    if (audio) { try { audio.destroy() } catch (e) { /* 已释放 */ } }
    audio = null
    curSrc = ''
  }

  function finish() {
    idx = -1
    stopTick()
    if (onIndex) onIndex(-1)
  }

  /* 播完/出错后让出「当前实例」，本实例的后续回调不再打扰别处 */
  function resetGuard(fn) {
    return () => {
      if (current === self) current = null
      if (fn) fn()
    }
  }

  const self = {
    get count() { return list.length },
    get index() { return idx },
    get playing() { return idx >= 0 },
    /**
     * @param {Array} segments [{url|path, start, dur}]，dur 缺失时按整条时长均分
     * @param {{onIndex?,onFinish?,onError?,onProgress?}} [handlers]
     * @param {number} [total] 整条时长（秒），没有段时长时用来估算进度
     * @returns {boolean} 是否成功起播
     */
    play(segments, handlers, total) {
      const h = handlers || {}
      const picked = (segments || []).map(s => ({ seg: s, src: srcOf(s) })).filter(x => x.src)
      if (!picked.length) { if (h.onError) h.onError(); return false }
      if (current && current !== self) current.stop()
      current = self
      onIndex = h.onIndex || null
      onFinish = resetGuard(h.onFinish)
      playError = resetGuard(h.onError)
      onProgress = h.onProgress || null
      /* 段时长不全（旧数据）时用总时长均分，进度条至少走得均匀 */
      const known = picked.reduce((n, x) => n + (Number(x.seg.dur) || 0), 0)
      const fallback = known > 0 ? 0 : Math.max(0.1, (Number(total) || 0) / picked.length)
      let acc = 0
      list = picked.map(x => {
        const d = Number(x.seg.dur) > 0 ? Number(x.seg.dur) : fallback
        const row = { src: x.src, start: acc, dur: d }
        acc += d
        return row
      })
      playIdx(0)
      return true
    },
    stop() {
      stopTick()
      if (audio) { try { audio.stop() } catch (e) { /* 已停 */ } }
      if (current === self) current = null
      finish()
    },
    destroy() {
      this.stop()
      release()
      list = []
      lastEventAt = 0; segStartAt = 0; lastProp = -1
      onIndex = null; onFinish = null; playError = null; onProgress = null
    }
  }
  return self
}
