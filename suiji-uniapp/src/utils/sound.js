/**
 * 岁记 · 交互音效引擎（App + 微信小程序双端兼容）
 * - 播放：uni.createInnerAudioContext，实例按文件缓存复用，降低起播延迟
 * - 震动：App 端走 infra/platform.js 的原生通道（uni.vibrateShort 在 App 端会丢掉强度参数）；
 *         小程序端 uni.vibrateShort(type)，需基础库 ≥2.13.0，失败静默降级
 * - 开关：sj_sound_on / sj_vibrate_on 两个独立开关，本地持久化，默认开；音效关闭时震动仍可独立播
 * - 去重：同一场景 800ms 内不重复触发（需求表 §2.3，防连点叠音）
 * - 变体：S-03 随机交替；E-01 按里程碑 key 绑定变体且当日不重复上一条；E-07 按百日/周岁绑定
 */

import { vibratePattern } from '@/infra/platform.js'

const SOUND_DIR = '/static/sounds/'
const KEY_SOUND = 'sj_sound_on'
const KEY_VIBRATE = 'sj_vibrate_on'
const KEY_E01 = 'sj_e01_last' // { date: 'YYYY-MM-DD', idx: number }

/* ---------- 震动模式（需求表 §五） ----------
 * 每段三种写法对应不同端，由 vibrate() 选择：
 *   ms/amp  App 端（Android VibrationEffect 的原始量纲：时长 ms + 幅度 0–255）
 *   type    小程序端（wx.vibrateShort 只认强度档位，不认时长）
 *   delay   该段相对触发的起点，多段波形靠它拉开间隔
 */
const VIB_PATTERNS = {
  /* 无振动 */
  none: null,
  /* confirm_light：单次轻击 20ms @120 */
  confirm_light: [{ delay: 0, type: 'light', ms: 20, amp: 120 }],
  /* neutral_soft：单次中击 40ms @90（比 confirm_light 长而弱，中性不带惩罚感） */
  neutral_soft: [{ delay: 0, type: 'medium', ms: 40, amp: 90 }],
  /* block：双短振 20-60-20 @150 */
  block: [{ delay: 0, type: 'light', ms: 20, amp: 150 }, { delay: 80, type: 'light', ms: 20, amp: 150 }],
  /* danger_double：双段重振 60-80-60 @200 */
  danger_double: [{ delay: 0, type: 'heavy', ms: 60, amp: 200 }, { delay: 140, type: 'heavy', ms: 60, amp: 200 }],
  /* rise_milestone：三段渐强 30-40-50 @100→180 */
  rise_milestone: [
    { delay: 0, type: 'light', ms: 30, amp: 100 },
    { delay: 70, type: 'medium', ms: 40, amp: 140 },
    { delay: 150, type: 'heavy', ms: 50, amp: 180 }
  ],
  /* settle：双段郑重落定 40-60 @140 */
  settle: [{ delay: 0, type: 'medium', ms: 40, amp: 140 }, { delay: 100, type: 'medium', ms: 60, amp: 140 }],
  /* silent_tick：三段 40ms 渐弱（夜间 T-04 纯振动路径的唯一反馈，首段力度上浮） */
  silent_tick: [
    { delay: 0, type: 'heavy', ms: 40, amp: 110 },
    { delay: 90, type: 'medium', ms: 40, amp: 80 },
    { delay: 180, type: 'light', ms: 40, amp: 55 }
  ],
  /* 双短振（T-02/T-03） */
  double_light: [{ delay: 0, type: 'light', ms: 20, amp: 120 }, { delay: 80, type: 'light', ms: 20, amp: 120 }]
}

/* ---------- 场景表：音效 ID → 文件（含变体）+ 震动模式 ---------- */
const SCENES = {
  /* S 组 · 交互音 */
  S01: { files: ['suiji_s01_fab_open.mp3'], vib: 'none' },            // FAB 面板展开
  S02: { files: ['suiji_s02_type_pick.mp3'], vib: 'none' },           // 选中记录类型
  S03: { files: ['suiji_s03_save_ok_v1.mp3', 'suiji_s03_save_ok_v2.mp3'], vib: 'confirm_light' }, // 保存成功(服务端确认后)
  S04: { files: ['suiji_s04_field_block.mp3'], vib: 'block' },        // 表单校验拦截
  S05: { files: ['suiji_s05_save_fail.mp3'], vib: 'block' },          // 保存失败/无网络
  S06: { files: ['suiji_s06_shutter.mp3'], vib: 'confirm_light' },    // 拍照快门
  S08: { files: ['suiji_s08_danger_confirm.mp3'], vib: 'danger_double' }, // 危险操作二次确认
  S09: { files: ['suiji_s09_restore.mp3'], vib: 'confirm_light' },    // 回收站恢复成功
  S10: { files: ['suiji_s10_baby_switch.mp3'], vib: 'confirm_light' }, // 宝宝切换完成
  S11: { files: ['suiji_s11_switch_toggle.mp3'], vib: 'none' },       // 开关拨动
  /* T 组 · 计时音 */
  T01: { files: ['suiji_t01_timer_start.mp3'], vib: 'confirm_light' }, // 计时开始
  T02: { files: ['suiji_t02_timer_pause.mp3'], vib: 'double_light' },  // 计时暂停
  T03: { files: ['suiji_t03_timer_resume.mp3'], vib: 'double_light' }, // 计时恢复
  T04: { files: ['suiji_t04_timer_end.mp3'], vib: 'silent_tick' },     // 计时结束（夜间可只振不响，传 { vibrateOnly: true }）
  /* E 组 · 成就/情感音 */
  E01: { files: [
    'suiji_e01_milestone_v1.mp3', 'suiji_e01_milestone_v2.mp3', 'suiji_e01_milestone_v3.mp3',
    'suiji_e01_milestone_v4.mp3', 'suiji_e01_milestone_v5.mp3'
  ], vib: 'rise_milestone' },                                          // 里程碑首次达成（opts.key 绑定变体）
  E03: { files: ['suiji_e03_curve_point.mp3'], vib: 'none' },         // 生长曲线数据点落位
  E04: { files: ['suiji_e04_journal_ready.mp3'], vib: 'settle' },     // AI 日记生成成功
  E05: { files: ['suiji_e05_journal_basic.mp3'], vib: 'neutral_soft' }, // AI 降级基础版（中性）
  E06: { files: ['suiji_e06_journal_archive.mp3'], vib: 'settle' },   // AI 日记归档
  E07: { files: ['suiji_e07_card_v1.mp3', 'suiji_e07_card_v2.mp3'], vib: 'settle' }, // 纪念卡（opts.key: 'hundred'|'year'）
  E08: { files: ['suiji_e08_video_done.mp3'], vib: 'settle' },        // 成长视频合成完成
  E09: { files: ['suiji_e09_pdf_export_done.mp3'], vib: 'neutral_soft' }, // PDF 导出完成
  E10: { files: ['suiji_e10_member_joined.mp3'], vib: 'settle' }      // 家人加入成功
}

/* ---------- 开关持久化 ---------- */
function _getFlag(key) {
  try {
    const v = uni.getStorageSync(key)
    return v === '' ? true : !!v // 未设置过默认开
  } catch (e) { return true }
}
function _setFlag(key, val) {
  try { uni.setStorageSync(key, !!val) } catch (e) { /* ignore */ }
}

export function isSoundOn() { return _getFlag(KEY_SOUND) }
export function setSoundOn(v) { _setFlag(KEY_SOUND, v) }
export function isVibrateOn() { return _getFlag(KEY_VIBRATE) }
export function setVibrateOn(v) { _setFlag(KEY_VIBRATE, v) }

/* ---------- 临时诊断（真机定位后整体删除） ---------- */
const _dbg = { vib: '-', audio: '-', src: '-' }
export function debugSnapshot() {
  return 'vib=' + _dbg.vib + ' | audio=' + _dbg.audio + ' | src=' + _dbg.src
}

/* ---------- 震动 ---------- */
/** 按模式名播放震动；开关关闭或模式为 none 时静默 */
export function vibrate(patternName) {
  if (!_getFlag(KEY_VIBRATE)) { _dbg.vib = 'switch_off'; return }
  const pattern = VIB_PATTERNS[patternName]
  if (!pattern) { _dbg.vib = 'no_pattern'; return }
  /* App 端优先走原生通道：uni.vibrateShort 在 App runtime 里写死成 15ms 且丢强度，
   * 只有这里能还原 §五 的时长与幅度（见 infra/platform.js 的说明） */
  const native = vibratePattern(pattern)
  if (native) { _dbg.vib = native; return }
  pattern.forEach(step => {
    const fire = () => {
      try {
        uni.vibrateShort({
          type: step.type,
          success: () => { _dbg.vib = 'ok(' + step.type + ')' },
          fail: (e) => {
            _dbg.vib = 'fail:' + ((e && e.errMsg) || JSON.stringify(e))
            /* 低版本不支持 type 参数时降级为默认短振 */
            try {
              uni.vibrateShort({
                success: () => { _dbg.vib = 'fallback_ok' },
                fail: (e2) => { _dbg.vib = 'fallback_fail:' + ((e2 && e2.errMsg) || '') }
              })
            } catch (err) { _dbg.vib = 'fallback_throw:' + err.message }
          }
        })
      } catch (e) { _dbg.vib = 'throw:' + e.message }
    }
    if (step.delay > 0) setTimeout(fire, step.delay)
    else fire()
  })
}

/* ---------- 音频实例缓存 ---------- */
const _ctxCache = {}
function _getCtx(file) {
  if (!_ctxCache[file]) {
    const ctx = uni.createInnerAudioContext()
    ctx.src = SOUND_DIR + file
    ctx.volume = 1.0
    /* iOS 静音键下仍出声；App 端(Android)该属性是只读的，直接赋值会抛异常，必须 try 保护 */
    try { ctx.obeyMuteSwitch = false } catch (e) { /* ignore */ }
    ctx.onError((e) => { _dbg.audio = 'err:' + ((e && (e.errMsg || e.code)) || JSON.stringify(e)) })
    ctx.onCanplay(() => { _dbg.audio = 'canplay' })
    /* App 端坑：对从未播放过的实例调用 stop() 会让后续 play() 静默失败，
     * 用 _played 标记只在"播过之后"才 stop 复位 */
    ctx._played = false
    ctx.onPlay(() => { ctx._played = true; _dbg.audio = 'play_ok' })
    ctx.onStop(() => { ctx._played = false })
    ctx.onEnded(() => { ctx._played = false })
    _ctxCache[file] = ctx
  }
  return _ctxCache[file]
}

/* ---------- 变体选择 ---------- */
let _s03Last = -1
function _pickFile(scene, opts) {
  const files = scene.files
  if (files.length === 1) return files[0]
  /* E-07：按纪念卡类型绑定（百日 v1 / 周岁 v2） */
  if (opts.key === 'hundred') return files[0]
  if (opts.key === 'year') return files[1]
  /* E-01：同一里程碑永远绑定同一变体（key 哈希）；无 key 时随机且当日不重复上一条 */
  if (opts.key) {
    let h = 0
    const s = String(opts.key)
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
    return files[h % files.length]
  }
  /* S-03 等：随机交替，避免连续两次同变体 */
  let idx = Math.floor(Math.random() * files.length)
  if (files.length === 2) {
    idx = _s03Last === 0 ? 1 : 0
    _s03Last = idx
  }
  return files[idx]
}

/* ---------- 同类去重（800ms） ---------- */
const _lastPlay = {}

/**
 * 播放场景音效 + 配对震动（主入口）
 * @param {string} id  场景 ID（SCENES 键，如 'S03'）
 * @param {object} [opts]
 *   - key          变体绑定键：E-07 传 'hundred'/'year'；E-01 传里程碑标识
 *   - vibrateOnly  仅振动不发声（T-04 夜间路径）
 *   - force        跳过 800ms 去重（如试听）
 */
export function play(id, opts) {
  opts = opts || {}
  const scene = SCENES[id]
  if (!scene) return

  /* 去重：连点/列表复用防叠音 */
  const now = Date.now()
  if (!opts.force && _lastPlay[id] && now - _lastPlay[id] < 800) return
  _lastPlay[id] = now

  /* 震动：独立开关，音效关闭时仍可播 */
  vibrate(scene.vib)

  /* 音效：夜间纯振动路径或音效开关关闭时跳过 */
  if (opts.vibrateOnly) { _dbg.audio = 'vibrate_only'; return }
  if (!_getFlag(KEY_SOUND)) { _dbg.audio = 'switch_off'; return }
  try {
    const file = _pickFile(scene, opts)
    _dbg.src = file
    _dbg.audio = 'calling'
    const ctx = _getCtx(file)
    if (ctx._played) { try { ctx.stop() } catch (e) { /* ignore */ } } // 播过才复位，支持未播完时重触发
    ctx.play()
  } catch (e) { _dbg.audio = 'throw:' + e.message }
}
