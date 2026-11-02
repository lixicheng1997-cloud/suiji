/**
 * 岁记 · 录音适配层（UI 只认这一层的 start/stop）
 *
 * 一次录音 = 一个文件：没有暂停，也就没有分段续录，界面只有「开始 / 结束」两个动作。
 * 结果仍以 segments[] 输出（恒为一段），与历史的多段数据共用同一条上传/回放链路。
 *
 * 平台差异只有两处：
 *   1) 录音通道 —— 小程序/App 用 uni.getRecorderManager()；H5 用 getUserMedia + MediaRecorder。
 *   2) 振幅（驱动球体律动）来源 —— H5 用 AnalyserNode 时域 RMS；
 *      小程序/App 的 onFrameRecorded 给的是编码后字节，只能拿「帧字节数 / 标称帧长」
 *      当语音能量代理（VAD 常用套路），动效只需要一个相对量。
 */

import { audioCaptureHooks } from '@/infra/platform.js'

const WAVE_BUCKETS = 48
const WAVE_STEP_MS = 200
const FRAME_SIZE_KB = 1

/* 帧能量代理：帧越大说明这一刻的语音信息量越高 */
function frameLevel(byteLength, frameSizeKB) {
  const expect = Math.max(1, frameSizeKB) * 1024
  return Math.min(1, Math.max(0, (byteLength / expect - 0.25) * 1.6))
}

function extOf(mime) {
  const m = String(mime || '')
  if (m.indexOf('mp4') >= 0) return 'm4a'
  if (m.indexOf('ogg') >= 0) return 'ogg'
  if (m.indexOf('mpeg') >= 0) return 'mp3'
  return 'webm'
}

/**
 * @param {object} opts
 * @param {number} [opts.limit] 上限秒数（默认 180s，到点自动 stop）
 * @param {(v:number)=>void} [opts.onLevel] 0~1 振幅，驱动球体缩放/表情/声波条
 * @param {(t:{elapsed:number,segCount:number})=>void} [opts.onTick] 约 200ms 一次
 * @param {(r:object)=>void} [opts.onEnd] 停止后回调 { duration, wave, segments, url, path }
 * @param {(msg:string)=>void} [opts.onError]
 */
export function createVoiceRecorder(opts) {
  const o = opts || {}
  const limit = o.limit > 0 ? o.limit : 180

  let state = 'idle' /* idle | rec */
  let startedAt = 0
  let tick = 0
  let coarse = 0
  let segStart = 0

  const wave = new Array(WAVE_BUCKETS).fill(0)
  const segs = []

  function elapsed() {
    if (!startedAt) return 0
    return Math.max(0, Math.min(limit, (Date.now() - startedAt) / 1000))
  }

  function openSegment() {
    segStart = elapsed()
    segs.push({ start: segStart, dur: null, url: '', path: '', ext: '' })
  }

  /* 封口「当前正在录的那一段」 */
  function sealSegment() {
    const cur = segs[segs.length - 1]
    if (cur && cur.dur === null) { cur.dur = Math.max(0, elapsed() - cur.start); cur.end = elapsed() }
  }

  function pushWave(level) {
    const i = Math.min(WAVE_BUCKETS - 1, Math.floor((elapsed() / limit) * WAVE_BUCKETS))
    if (level > wave[i]) wave[i] = level
  }

  function startTick() {
    stopTick()
    tick = setInterval(() => {
      if (state !== 'rec') return
      coarse += 100
      if (coarse >= WAVE_STEP_MS) {
        coarse = 0
        if (o.onTick) o.onTick({ elapsed: elapsed(), segCount: segs.length })
      }
      if (elapsed() >= limit) stop()
    }, 100)
  }

  function stopTick() {
    if (tick) { clearInterval(tick); tick = 0 }
  }

  /* 收尾：封住末段，丢掉空段，产出统一结果对象 */
  function finish(extra) {
    stopTick()
    sealSegment()
    const dur = elapsed()
    const list = segs.filter(s => s.dur > 0 && (s.url || s.path))
    const result = {
      duration: Math.round(dur * 10) / 10,
      limit,
      wave: wave.map(v => Math.round(v * 40)),
      segments: list,
      /* 只有一段时给个直达字段，UI 与历史数据都读它 */
      url: list.length === 1 ? list[0].url : '',
      path: list.length === 1 ? list[0].path : ''
    }
    if (extra) Object.keys(extra).forEach(k => { result[k] = extra[k] })
    state = 'idle'
    startedAt = 0; segStart = 0
    if (o.onEnd) o.onEnd(result)
    return result
  }

  function fail(msg) {
    stopTick()
    state = 'idle'
    if (o.onError) o.onError(msg || '录音失败，请检查麦克风权限')
  }

  // #ifdef H5
  const hooks = audioCaptureHooks()
  let stream = null
  let actx = null
  let analyser = null
  let raf = 0
  let rec = null
  let chunks = []
  let closing = false /* true = 这次 stop 是整条录音结束 */

  function meterLoop() {
    if (!analyser) return
    const buf = new Uint8Array(analyser.fftSize)
    const step = () => {
      if (state !== 'rec') { raf = 0; return }
      analyser.getByteTimeDomainData(buf)
      let sum = 0
      for (let i = 0; i < buf.length; i++) { const d = (buf[i] - 128) / 128; sum += d * d }
      const level = Math.min(1, Math.sqrt(sum / buf.length) * 5)
      if (o.onLevel) o.onLevel(level)
      pushWave(level)
      raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
  }

  function newRecorder() {
    const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
    const supported = types.filter(t => window.MediaRecorder && window.MediaRecorder.isTypeSupported && window.MediaRecorder.isTypeSupported(t))
    const mimeType = supported[0] || ''
    rec = mimeType ? new window.MediaRecorder(stream, { mimeType }) : new window.MediaRecorder(stream)
    chunks = []
    rec.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunks.push(e.data) }
    rec.onstop = () => {
      const blob = new Blob(chunks, { type: rec.mimeType || mimeType || 'audio/webm' })
      const cur = segs[segs.length - 1]
      chunks = []
      if (cur) {
        cur.url = hooks.createURL(blob)
        cur.ext = extOf(blob.type)
        if (cur.dur === null) sealSegment()
      }
      if (closing) { closing = false; finish({ mime: blob.type, platform: 'h5' }) }
    }
  }

  function releaseCapture() {
    if (raf) { cancelAnimationFrame(raf); raf = 0 }
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null }
    if (actx) { actx.close().catch(() => {}); actx = null }
    analyser = null
  }

  function platformStart() {
    if (!hooks) return fail('当前环境不支持录音，请换用较新的浏览器')
    return hooks.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      .then(s => {
        stream = s
        if (hooks.AudioContextCtor) {
          actx = new hooks.AudioContextCtor()
          analyser = actx.createAnalyser()
          analyser.fftSize = 512
          actx.createMediaStreamSource(s).connect(analyser)
        }
        wave.fill(0)
        segs.length = 0
        startedAt = Date.now()
        state = 'rec'
        openSegment()
        newRecorder()
        rec.start(250)
        meterLoop()
        startTick()
      })
      .catch(e => {
        releaseCapture()
        fail(String(e && e.name) === 'NotAllowedError' ? '没有麦克风权限，请在浏览器设置里允许' : '无法打开麦克风')
      })
  }

  function platformStop() {
    if (closing) return /* 「停止」被连点两次：MediaRecorder 重复 stop 会抛 InvalidStateError */
    if (rec && rec.state !== 'inactive') { closing = true; rec.stop() }
    else { finish({ platform: 'h5' }) }
    releaseCapture()
  }

  function platformDestroy(revoke) {
    stopTick()
    if (raf) cancelAnimationFrame(raf)
    /* 正常结束不回收：结果里的 blob url 就是这段录音本体，取消时才释放 */
    if (revoke) segs.forEach(s => { if (s.url) hooks && hooks.revokeURL(s.url) })
    releaseCapture()
    state = 'idle'
  }
  // #endif

  // #ifndef H5
  let rm = null
  let lastFrame = 0
  let hb = 0
  let mpClosing = false

  const RECORDER_OPTS = {
    duration: limit * 1000,
    sampleRate: 44100,
    numberOfChannels: 1,
    encodeBitRate: 96000,
    /* format 有效值仅 aac/mp3/wav（官方文档），m4a 不在列、App 端 start 直接失败；
       aac 在 iOS/App 实际封装为 .m4a 容器，扩展名以 onStop 回调的 fileType 为准 */
    format: 'aac',
    frameSize: FRAME_SIZE_KB
  }

  function ensureManager() {
    if (rm) return rm
    rm = uni.getRecorderManager()
    rm.onStart(() => { startedAt = startedAt || Date.now() })
    rm.onFrameRecorded((res) => {
      if (state !== 'rec' || !res.frameBuffer) return
      lastFrame = frameLevel(res.frameBuffer.byteLength || 0, FRAME_SIZE_KB)
      if (o.onLevel) o.onLevel(lastFrame)
      pushWave(lastFrame)
    })
    rm.onError(() => fail('录音出错，请重试'))
    rm.onStop((res) => {
      const recDur = res && res.duration ? Math.round(res.duration) / 1000 : 0
      const cur = segs[segs.length - 1]
      if (cur && res && res.tempFilePath) {
        cur.path = res.tempFilePath
        cur.ext = res.fileType || 'm4a'
        /* 段界用全局时钟算，和 cur.start 同一刻度（历史多段数据也走这条换算） */
        if (cur.dur === null) cur.dur = Math.max(0, elapsed() - cur.start)
      }
      if (mpClosing) {
        mpClosing = false
        const extra = { platform: 'mp', fileSize: res ? res.fileSize : 0, fileType: res ? res.fileType : '' }
        /* onStop 的 duration 是录音器实测真值，用它校准总时长（多段历史数据仍以时钟为准） */
        if (segs.length <= 1 && recDur > 0) extra.duration = Math.round(recDur * 10) / 10
        finish(extra)
      }
    })
    return rm
  }

  /* 帧回调之间让球体缓慢回落，否则停在上一帧高度上很僵 */
  function meterHeartbeat() {
    clearInterval(hb)
    hb = setInterval(() => {
      if (state !== 'rec') { clearInterval(hb); hb = 0; return }
      lastFrame = Math.max(0, lastFrame - 0.12)
      if (o.onLevel) o.onLevel(lastFrame)
    }, 90)
  }

  /* 权限门：uni.authorize 是小程序 API，App 端不支持——直接调用会异常，
     被上层 Promise 吞掉后表现为「点录音没反应」。
     Android 走 plus 主动申请 RECORD_AUDIO（拒绝时给提示），
     iOS 由首次录音自动弹系统框（NSMicrophoneUsageDescription 已在 manifest 配置）。 */
  function ensureRecordAuth() {
    // #ifdef APP-PLUS
    return new Promise(resolve => {
      try {
        if (typeof plus !== 'undefined' && plus.os && plus.os.name === 'Android' && plus.android && plus.android.requestPermissions) {
          plus.android.requestPermissions(['android.permission.RECORD_AUDIO'], res => {
            const denied = ((res && res.deniedPresent) || []).concat((res && res.deniedAlways) || [])
            if (denied.length) { fail('麦克风权限被拒绝，请到系统设置中开启'); resolve(false); return }
            resolve(true)
          }, () => resolve(true))
          return
        }
      } catch (e) { /* plus 异常时直接录音，由系统弹窗兜底 */ }
      resolve(true)
    })
    // #endif
    // #ifndef APP-PLUS
    return new Promise(resolve => {
      uni.authorize({ scope: 'scope.record', success: () => resolve(true), fail: () => resolve(true) })
    })
    // #endif
  }

  function platformStart() {
    return ensureRecordAuth().then(ok => {
      if (!ok) return
      const m = ensureManager()
      wave.fill(0)
      segs.length = 0
      startedAt = Date.now()
      state = 'rec'
      openSegment()
      try { m.start(RECORDER_OPTS) } catch (e) { return fail('当前设备不支持录音') }
      startTick()
      meterHeartbeat()
    })
  }

  function platformStop() {
    if (mpClosing) return /* 连点两次「停止」：重复 stop 在部分机型会报错 */
    if (!rm) return finish({ platform: 'mp' })
    mpClosing = true
    try {
      rm.stop()
    } catch (e) {
      mpClosing = false
      finish({ platform: 'mp' })
    }
    if (hb) { clearInterval(hb); hb = 0 }
  }

  function platformDestroy() {
    stopTick()
    if (hb) clearInterval(hb)
    state = 'idle'
  }
  // #endif

  return {
    start() { if (state === 'idle') return platformStart() },
    stop() { if (state !== 'idle') return platformStop() },
    destroy(revoke) { platformDestroy(revoke) },
    elapsed,
    segCount: () => segs.length,
    get state() { return state }
  }
}
