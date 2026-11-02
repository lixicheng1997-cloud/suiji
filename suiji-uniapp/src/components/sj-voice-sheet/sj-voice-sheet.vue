<template>
  <view class="sj-vs">
    <!-- 类目识别 + 上限：语音蓝 chip 不抢 IP 注意力，上限胶囊与试玩台同规则 -->
    <view class="vs-hd">
      <view class="vs-chip"></view>
      <view class="vs-lim" :class="{ lock: readonly || state === 'rec' }">
        <view
          v-for="l in LIMITS"
          :key="l.s"
          class="vs-limb"
          :class="{ on: limit === l.s }"
          hover-class="hover-press"
          @click="pickLimit(l.s)"
        ><text>{{ l.t }}</text></view>
      </view>
    </view>

    <!-- 果冻形象球：点球=开始录音，录音中再点=结束录音 -->
    <view class="vs-orb" :class="'s-' + state" hover-class="hover-press" @click="onBallTap">
      <view v-if="state === 'rec'" class="vs-bubs">
        <view v-for="(b, i) in BUBBLES" :key="i" class="vs-bub" :style="bubStyle(b, i)"></view>
      </view>
      <view class="vs-spokes">
        <view
          v-for="(h, i) in bars"
          :key="i"
          class="vs-spoke"
          :style="{ transform: 'rotate(' + i * SPOKE_STEP + 'deg)' }"
        >
          <view class="vs-bar" :style="{ height: h + 'rpx', opacity: 0.42 + h / 120 }"></view>
        </view>
      </view>
      <view class="vs-ball" :style="ballStyle">
        <view class="vs-jelly" :class="{ run: state === 'rec' }">
          <image class="vs-face" :src="faceCalm" mode="aspectFit" />
          <image class="vs-face vs-face-loud" :src="faceLoud" mode="aspectFit" :style="{ opacity: loud ? 1 : 0 }" />
        </view>
        <view v-if="state !== 'idle'" class="vs-badge" :class="'b-' + state">
          <view v-if="state === 'rec'" class="g-dot"></view>
          <text>{{ state === 'done' ? '试听' : 'REC' }}</text>
        </view>
      </view>
    </view>

    <!-- 计时挪到球下方：形象脸上不压字，剩余/上限同屏 -->
    <view class="vs-timer" :class="{ warn: nearEnd }">
      <text class="vs-timer-n">{{ fmt(elapsed) }}</text>
      <text class="vs-timer-s">/ {{ fmt(limit) }}</text>
    </view>

    <view class="vs-seg">
      <text class="vs-seg-t">{{ segText }}</text>
    </view>

    <view class="vs-hint">
      <text class="vs-hint-t">{{ hintText }}</text>
      <text class="vs-hint-s">{{ hintSubText }}</text>
    </view>

    <!-- 试听：波形跟着播放进度点亮，播的时候整列错峰起伏 -->
    <view v-if="state === 'done'" class="vs-prev">
      <view class="vs-wave" :class="{ run: playing >= 0 }">
        <view
          v-for="(w, i) in waveBars"
          :key="i"
          class="vs-wave-b"
          :class="{ div: w.div, wb: !w.div, lit: w.lit, now: w.now }"
          :style="w.div ? null : { height: (w.h * 38 + 8) + 'rpx', animationDelay: w.d }"
        ></view>
      </view>
      <view class="vs-meta"><text>{{ metaText }}</text></view>
      <view class="vs-play" hover-class="hover-press" @click="preview">
        <image class="vs-ic vs-ic-play" :src="playing < 0 ? icTri : icPauseDeep" />
        <text>{{ playing < 0 ? '先听一遍' : ('播放中 · ' + fmt(pos)) }}</text>
      </view>
    </view>

    <!-- 控制行：待录给「取消 / 开始」，录音中给「取消 / 结束」，试听给「重录 / 保留」 -->
    <view v-if="!readonly" class="vs-ctrls">
      <view v-if="state !== 'done'" class="vs-cb" hover-class="hover-press" @click="cancel">
        <view class="vs-cb-i n1"><image class="vs-ic" :src="icX" /></view>
        <text class="vs-cb-t">取消</text>
      </view>
      <view v-if="state === 'idle'" class="vs-cb" hover-class="hover-press" @click="start">
        <view class="vs-cb-i n2"><image class="vs-ic vs-ic-mic" :src="icMic" /></view>
        <text class="vs-cb-t">开始录音</text>
      </view>
      <view v-if="state === 'rec'" class="vs-cb" hover-class="hover-press" @click="stop">
        <view class="vs-cb-i n3"><image class="vs-ic" :src="icStopW" /></view>
        <text class="vs-cb-t">结束录音</text>
      </view>
      <view v-if="state === 'done'" class="vs-cb" hover-class="hover-press" @click="cancel">
        <view class="vs-cb-i n1"><image class="vs-ic" :src="icX" /></view>
        <text class="vs-cb-t">重录</text>
      </view>
      <view v-if="state === 'done'" class="vs-cb" hover-class="hover-press" @click="keep">
        <view class="vs-cb-i n3"><image class="vs-ic" :src="icOkW" /></view>
        <text class="vs-cb-t">已保留这段语音</text>
      </view>
    </view>

    <view v-if="tip" class="vs-tip" :class="{ bad: tipBad }"><text>{{ tip }}</text></view>
  </view>
</template>

<script>
/**
 * 岁记 · 语音录入面板（easycom 自动注册 <sj-voice-sheet>）
 * 设计稿：suiji-voice-record-design/jelly-mascot-v2.html（果冻形象球，形象背后不放圆环）
 *
 * 交互只有两个动作：开始录音 / 结束录音（形象球与控制行都是这两态）。
 * 分工：录音通道与平台差异全在 utils/voiceRecorder.js，本组件只管状态机与动效；
 * 振幅来自 onLevel（H5 为 AnalyserNode RMS，小程序/App 为编码帧字节代理）。
 *
 * v-model 输出：{ duration, wave:[48], segments:[{start,dur,url,path,ext}], url, path, platform }
 * url/path 为本地待上传引用（H5 是 blob:，App/小程序是 tempFilePath），上传后由 api 换回云端 url。
 * segments 仍按段数组输出：一次录音就是一段，历史数据可能是多段（试听兼容）。
 */
import { createVoiceRecorder } from '@/utils/voiceRecorder.js'
import { createVoicePlayer } from '@/utils/voicePlayback.js'
import { palette, withAlpha } from '@/theme/theme.js'

const SPOKES = 24
const BASE_BAR = 12
const BOUNCE_STEPS = 6

export default {
  name: 'SjVoiceSheet',
  props: {
    modelValue: { type: Object, default: null },
    /* 只读模式（详情页）不给控制行 */
    readonly: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change'],
  data() {
    return {
      LIMITS: [{ s: 15, t: '15s' }, { s: 60, t: '60s' }, { s: 180, t: '3min' }],
      BUBBLES: [[18, 10], [30, 4], [52, 16], [68, 8], [40, 22]],
      SPOKE_STEP: 360 / SPOKES,
      state: 'idle',
      limit: 180,
      elapsed: 0,
      level: 0,
      bars: new Array(SPOKES).fill(BASE_BAR),
      wave: new Array(48).fill(0),
      segs: [],
      result: null,
      tip: '',
      tipBad: false,
      loud: false,
      /* 试听进度：-1 未在播，否则为当前段序号 */
      playing: -1,
      /* 试听已播秒数（整秒，驱动波形点亮与计时文字） */
      pos: 0
    }
  },
  computed: {
    faceCalm() {
      return '/static/anim/' + (this.__theme === 'duck' ? 'duck' : 'bear') + '-face.svg'
    },
    faceLoud() {
      return '/static/anim/' + (this.__theme === 'duck' ? 'duck' : 'bear') + '-face-loud.svg'
    },
    ballStyle() {
      /* 振幅只作用于外层球，律动 keyframes 在内层 .jelly，两层 transform 不冲突；
         光晕取当前主题的 primary-deep，换肤时球跟着变色 */
      const x = 1 + this.level * 0.06
      const y = 1 - this.level * 0.045
      const glow = withAlpha(palette(this.__theme)['primary-deep'], (0.18 + this.level * 0.22).toFixed(2))
      return {
        transform: 'scale(' + x.toFixed(3) + ',' + y.toFixed(3) + ')',
        boxShadow: '0 18rpx ' + Math.round(30 + this.level * 60) + 'rpx ' + glow
      }
    },
    nearEnd() {
      return this.state === 'rec' && this.limit - this.elapsed < 30
    },
    segText() {
      if (this.state === 'idle') return '最长 ' + this.limit + 's · 一次录完'
      if (this.state === 'done') return '已录 ' + this.fmt(this.elapsed)
      return '剩 ' + Math.max(0, Math.ceil(this.limit - this.elapsed)) + 's'
    },
    hintText() {
      if (this.state === 'rec') return this.loud ? '声音好大！' + this.ipName + '眼睛都眯起来了' : '球在跟着声音一压一回弹 · 再点一下结束'
      if (this.state === 'done') return '这条语音录好了'
      return '轻触' + this.ipName + '，录下宝宝的声音'
    },
    hintSubText() {
      if (this.state === 'rec') return '点' + this.ipName + '或下方「结束录音」保存这条'
      if (this.state === 'done') return '保存后上传，回放按录制波形显示进度'
      return '语音最长 3 分钟'
    },
    ipName() {
      return this.__theme === 'duck' ? '叽叽' : '岁岁'
    },
    metaText() {
      const r = this.result || {}
      const dur = r.duration || 0
      const kb = Math.round(dur * 12) /* m4a/opus 约 96~128kbps ≈ 12KB/s */
      const ext = (r.segments && r.segments[0] && r.segments[0].ext) || 'm4a'
      const seg = this.segs.length > 1 ? ' · ' + this.segs.length + ' 段' : ''
      return '时长 ' + this.fmt(dur) + seg + ' · ' + ext + ' · 约 ' + kb + ' KB'
    },
    /* 控制行图标：data-URI SVG 切图（与首页同步图标同方案）。
       此前用 view 画的几何图标在三端渲染不一致（各端 view 默认 box-sizing 不同、
       细条 rotate 后 rpx 取整错位），改用设计稿 jelly-mascot-v2.html 的路径图标；
       data-URI 是独立文档不吃 CSS 变量，颜色经 palette 按当前主题烘进 stroke/fill */
    icX() { return this.svgIcon('<path d="M7 7l10 10M17 7L7 17"/>', palette(this.__theme)['sub']) },
    icMic() {
      return this.svgIcon('<path d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3Z"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><path d="M12 19v3"/>', palette(this.__theme)['primary-deep'])
    },
    icPauseDeep() { return this.svgIcon('<rect x="6.5" y="5" width="4.6" height="14" rx="2.3"/><rect x="12.9" y="5" width="4.6" height="14" rx="2.3"/>', palette(this.__theme)['primary-deep'], 'fill') },
    icTri() { return this.svgIcon('<path d="M8 5.2v13.6L19.4 12z"/>', palette(this.__theme)['primary-deep'], 'fill') },
    icStopW() { return this.svgIcon('<rect x="6.5" y="6.5" width="11" height="11" rx="3.4"/>', '#FFFFFF', 'fill') },
    icOkW() { return this.svgIcon('<path d="M5 12.5l4.5 4.5L19 7.5"/>', '#FFFFFF') },
    /* 试听波形：播过的柱子点亮、正在播的那根最深；未在播时整列都是录制结果 */
    waveBars() {
      const total = Math.max(0.1, (this.result && this.result.duration) || this.limit)
      const bounds = this.segs.slice(0, -1).map(s => Math.round(((s.start + s.dur) / total) * 48))
      const air = this.playing >= 0 ? Math.min(this.pos, total) : -1
      const head = air < 0 ? -1 : Math.min(47, Math.floor((air / total) * 48))
      const out = []
      this.wave.forEach((v, i) => {
        out.push({
          h: Math.max(0.12, v / 40),
          lit: air < 0 || ((i + 1) / 48) * total <= air,
          now: i === head,
          d: (i % BOUNCE_STEPS) * 0.1 + 's'
        })
        if (bounds.indexOf(i + 1) >= 0) out.push({ div: true })
      })
      return out
    }
  },
  watch: {
    modelValue(v) {
      /* 编辑回填：外部塞进一个已存在的 voice 就切到试听态 */
      if (v && v.duration && this.state !== 'done') this.restore(v)
      if (!v && this.state === 'done') this.reset()
    }
  },
  mounted() {
    if (this.modelValue && this.modelValue.duration) this.restore(this.modelValue)
  },
  beforeUnmount() {
    this.destroyRecorder()
    if (this.player) { this.player.destroy(); this.player = null }
  },
  methods: {
    /* 拼 data-URI SVG：描边图标默认 2.4 圆头线宽；填充图标传 mode='fill' */
    svgIcon(inner, color, mode) {
      const attrs = mode === 'fill'
        ? 'fill="' + color + '" stroke="none"'
        : 'fill="none" stroke="' + color + '" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"'
      const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" ' + attrs + '>' + inner + '</svg>'
      return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
    },
    fmt(s) {
      const m = Math.floor(s / 60)
      const x = Math.floor(s % 60)
      return (m < 10 ? '0' : '') + m + ':' + (x < 10 ? '0' : '') + x
    },
    bubStyle(b, i) {
      const size = Math.round(b[1] * 1.6 + 10)
      return {
        left: b[0] + '%',
        width: size + 'rpx',
        height: size + 'rpx',
        animationDelay: (i * 0.7).toFixed(2) + 's'
      }
    },
    ensureRecorder() {
      if (this.rec) return this.rec
      this.rec = createVoiceRecorder({
        limit: this.limit,
        onLevel: v => this.onLevel(v),
        onTick: t => { this.elapsed = t.elapsed },
        onEnd: r => this.onEnd(r),
        onError: msg => {
          this.state = 'idle'
          this.setTip(msg, true)
          this.destroyRecorder()
        }
      })
      return this.rec
    },
    /* 60ms 节流：小程序 setData 有成本，动效靠 CSS transition 补间 */
    onLevel(v) {
      const now = Date.now()
      if (now - this._lastLevel < 60) return
      this._lastLevel = now
      const next = this.level + (v - this.level) * 0.35
      this.level = next
      this.loud = next > 0.55
      const bars = this.bars.slice()
      bars.push(BASE_BAR + next * 72)
      bars.shift()
      this.bars = bars
    },
    /* 球即主按钮：待录=开始，录音中=结束，试听=重听 */
    onBallTap() {
      if (this.readonly) { this.preview(); return }
      if (this.state === 'idle') this.start()
      else if (this.state === 'rec') this.stop()
      else if (this.state === 'done') this.preview()
    },
    start() {
      if (this.readonly) return
      const rec = this.ensureRecorder()
      this.segs = []
      this.wave = new Array(48).fill(0)
      this.elapsed = 0
      this.result = null
      this.setTip('')
      const p = rec.start()
      if (p && typeof p.then === 'function') {
        /* H5 取麦克风是异步的：拿到流并真正进入 rec 态才切界面（授权失败时适配层已回调 onError） */
        p.then(() => { if (rec.state === 'rec') this.state = 'rec' }).catch(() => {})
      } else {
        this.state = 'rec'
      }
    },
    stop() {
      if (this.state !== 'rec') return
      this.rec.stop()
      /* onEnd 里落最终状态；H5 的 onstop 是异步的，先给个过渡提示 */
      this.setTip('正在收尾…')
    },
    onEnd(r) {
      this.destroyRecorder()
      this.wave = r.wave && r.wave.length === 48 ? r.wave : this.wave
      this.segs = (r.segments || []).map(s => ({ ...s }))
      this.elapsed = r.duration || 0
      if (!r.segments || !r.segments.length) {
        this.state = 'idle'
        this.setTip('录音太短，没有保存', true)
        this.emit(null)
        return
      }
      this.level = 0
      this.loud = false
      this.bars = new Array(SPOKES).fill(BASE_BAR)
      this.result = r
      this.state = 'done'
      this.setTip('')
      this.emit(r)
    },
    keep() {
      this.setTip('已保留 · 点底部「保存记录」入库')
    },
    cancel() {
      /* 丢弃：把已生成的 blob url 一并释放 */
      this.destroyRecorder(true)
      this.reset()
      this.emit(null)
    },
    reset() {
      if (this.player) this.player.stop()
      this.playing = -1
      this.pos = 0
      this.state = 'idle'
      this.elapsed = 0
      this.level = 0
      this.loud = false
      this.segs = []
      this.result = null
      this.wave = new Array(48).fill(0)
      this.bars = new Array(SPOKES).fill(BASE_BAR)
      this.setTip('')
    },
    pickLimit(s) {
      if (this.readonly) return
      if (this.state === 'rec') {
        this.setTip('录音中不能改时长上限', true)
        return
      }
      this.limit = s
      /* 未开录的通道要重建才能带上新上限；已录好的结果（done）保留，不因改档位被清空 */
      if (this.state !== 'done') this.destroyRecorder(true)
    },
    preview() {
      const list = (this.result && this.result.segments) || []
      if (!list.length) return this.setTip('本地文件已失效，请重录', true)
      if (!this.player) this.player = createVoicePlayer()
      /* 再点一次 = 停下 */
      if (this.player.playing) {
        this.player.stop()
        this.playing = -1
        this.pos = 0
        this.setTip('')
        return
      }
      this.pos = 0
      const ok = this.player.play(list, {
        onIndex: i => { this.playing = i },
        /* 整秒才赋值：波形点亮交给 CSS，48 根柱子不必每 250ms 重排一次 */
        onProgress: t => { const s = Math.floor(t); if (s !== this.pos) this.pos = s },
        onFinish: () => { this.playing = -1; this.pos = 0; this.setTip('') },
        onError: () => { this.playing = -1; this.pos = 0; this.setTip('这段暂时放不出来', true) }
      }, (this.result && this.result.duration) || 0)
      if (!ok) return this.setTip('本地文件已失效，请重录', true)
      this.setTip(list.length > 1 ? '按段顺序连播 · 共 ' + list.length + ' 段' : '正在试听')
    },
    emit(r) {
      const val = r ? {
        duration: r.duration,
        wave: r.wave,
        segments: r.segments,
        url: r.url || '',
        path: r.path || '',
        platform: r.platform || ''
      } : null
      this.$emit('update:modelValue', val)
      this.$emit('change', val)
    },
    restore(v) {
      /* 云端已上传的语音（url 是 /api/...）不能当本地录音恢复录制通道，只恢复展示 */
      this.result = { duration: v.duration, wave: v.wave, segments: v.segments || [], url: v.url, path: v.path }
      this.wave = v.wave && v.wave.length === 48 ? v.wave : new Array(48).fill(0.3)
      this.segs = (v.segments && v.segments.length) ? v.segments : [{ start: 0, dur: v.duration }]
      this.elapsed = v.duration || 0
      this.state = 'done'
    },
    destroyRecorder(revoke) {
      if (this.rec) {
        this.rec.destroy(!!revoke)
        this.rec = null
      }
    },
    setTip(msg, bad) {
      this.tip = msg || ''
      this.tipBad = !!bad
    }
  }
}
</script>

<style lang="scss" scoped>
.sj-vs {
  position: relative;
  padding: 24rpx 16rpx 8rpx;
  background: var(--sj-glass);
  border: 1px solid var(--sj-glass-line);
  border-radius: var(--sj-r-lg);
}
/* 头行 */
.vs-hd { display: flex; align-items: center; justify-content: space-between; padding: 0 8rpx; }
.vs-lim { display: flex; gap: 10rpx; }
.vs-lim.lock { opacity: .38; }
.vs-limb {
  font-size: 19rpx; font-weight: 800; color: var(--sj-sub);
  background: #fff; border: 1px solid var(--sj-line); border-radius: var(--sj-r-pill); padding: 4rpx 18rpx;
}
.vs-limb.on { color: #fff; background: var(--sj-primary); border-color: transparent; }

/* 形象球 */
.vs-orb {
  position: relative;
  width: 392rpx; height: 392rpx;
  margin: 8rpx auto 0;
  display: flex; align-items: center; justify-content: center;
}
.vs-ball {
  position: relative;
  width: 372rpx; height: 372rpx;
  border-radius: 50%;
  transition: transform .1s var(--sj-smooth), box-shadow .18s var(--sj-smooth);
}
.vs-jelly { position: absolute; inset: 0; transform-origin: 50% 90%; }
.vs-jelly.run { animation: sjVsJelly 1.15s ease-in-out infinite; }
@keyframes sjVsJelly {
  0%, 100% { transform: scale(1, 1); }
  22% { transform: scale(1.055, .95); }
  46% { transform: scale(.965, 1.045); }
  70% { transform: scale(1.03, .98); }
}
.vs-face { position: absolute; left: 0; top: 0; width: 100%; height: 100%; transition: opacity .16s linear; }
.s-done .vs-ball { width: 248rpx; height: 248rpx; opacity: .96; }

/* 声波条：高度由 JS 每帧给，transition 补间，避免小程序端 setData 频率过高 */
.vs-spokes { position: absolute; left: 50%; top: 50%; width: 0; height: 0; }
.vs-spoke { position: absolute; left: 0; top: 0; width: 0; height: 0; }
.vs-bar {
  position: absolute;
  left: -3rpx; bottom: 150rpx;
  width: 6rpx; height: 12rpx;
  border-radius: 4rpx;
  background: linear-gradient(180deg, var(--sj-primary), var(--sj-primary-deep));
  transition: height .09s linear, opacity .12s linear;
}

/* 气泡 */
.vs-bubs { position: absolute; inset: 0; pointer-events: none; }
.vs-bub {
  position: absolute; bottom: 120rpx;
  border-radius: 50%;
  background: radial-gradient(circle at 34% 30%, rgba(255, 255, 255, .95), var(--sj-primary-soft));
  opacity: 0;
  animation: sjVsBub 3.4s ease-in infinite;
}
@keyframes sjVsBub {
  0% { transform: translateY(0) scale(.5); opacity: 0; }
  18% { opacity: .85; }
  100% { transform: translateY(-104px) scale(1.12); opacity: 0; }
}

/* 徽标：贴在耳侧，不遮脸 */
.vs-badge {
  position: absolute; right: 4rpx; top: 26rpx;
  display: flex; align-items: center; gap: 8rpx;
  font-size: 18rpx; font-weight: 900; letter-spacing: 2rpx; color: #fff;
  border-radius: var(--sj-r-pill); padding: 4rpx 16rpx;
  z-index: 3;
}
.vs-badge text { font-size: 18rpx; }
.b-rec { background: var(--sj-bad); box-shadow: 0 6rpx 16rpx rgba(239, 122, 122, .4); }
.b-done { background: var(--sj-ok); box-shadow: 0 6rpx 16rpx rgba(95, 192, 140, .4); }
.g-dot { width: 12rpx; height: 12rpx; border-radius: 50%; background: #fff; animation: sjVsBlink 1.1s ease-in-out infinite; }
@keyframes sjVsBlink { 0%, 100% { opacity: 1; } 50% { opacity: .3; } }

/* 计时 */
.vs-timer {
  display: flex; align-items: baseline; justify-content: center; gap: 6rpx;
  font-family: var(--sj-font-display);
  color: var(--sj-primary-deep);
  line-height: 1.1;
}
.vs-timer-n { font-size: 76rpx; font-weight: 900; letter-spacing: 2rpx; }
.vs-timer-s { font-size: 26rpx; font-weight: 800; color: var(--sj-faint); }
.vs-timer.warn { color: var(--sj-warn); }
.vs-timer.warn .vs-timer-s { color: var(--sj-warn); opacity: .7; }
.vs-seg { display: flex; align-items: center; justify-content: center; gap: 12rpx; margin-top: 6rpx; }
.vs-seg-t { font-size: 20rpx; font-weight: 800; color: var(--sj-sub); }

/* 提示文案 */
.vs-hint { text-align: center; margin-top: 12rpx; }
.vs-hint-t { display: block; font-family: var(--sj-font-display); font-size: 25rpx; font-weight: 800; }
.vs-hint-s { display: block; font-size: 19rpx; color: var(--sj-faint); margin-top: 4rpx; }

/* 试听：未播到的段淡、播过的段实，正在播的那根最深；播的时候整列错峰起伏 */
.vs-prev { margin-top: 18rpx; padding: 0 8rpx; }
.vs-wave { display: flex; align-items: center; justify-content: center; height: 76rpx; gap: 4rpx; }
.vs-wave-b {
  flex: 1; max-width: 8rpx; border-radius: 4rpx;
  background: linear-gradient(180deg, var(--sj-primary), var(--sj-primary-deep));
  opacity: .34;
  transform-origin: 50% 50%;
  transition: opacity .2s var(--sj-smooth);
}
.vs-wave-b.lit { opacity: .9; }
.vs-wave-b.now { opacity: 1; background: var(--sj-primary-deep); }
.vs-wave.run .wb { animation: sjVsPrev .9s var(--sj-smooth) infinite alternate; }
@keyframes sjVsPrev {
  from { transform: scaleY(.6); }
  to { transform: scaleY(1.14); }
}
.vs-wave-b.div { max-width: 4rpx; height: 56rpx; background: var(--sj-faint); opacity: .9; }
.vs-meta { text-align: center; font-size: 20rpx; font-weight: 800; color: var(--sj-sub); margin-top: 10rpx; }
.vs-play {
  display: flex; align-items: center; justify-content: center; gap: 10rpx;
  width: 320rpx; margin: 14rpx auto 0; padding: 12rpx 0;
  font-size: 22rpx; font-weight: 800; color: var(--sj-primary-deep);
  background: #fff; border: 2rpx solid var(--sj-primary); border-radius: var(--sj-r-pill);
}
.vs-play text { font-size: 22rpx; }

/* 控制行：图标为 data-URI SVG 切图（computed icX/icMic/...，与设计稿 jelly-mascot-v2.html 同路径） */
.vs-ctrls { display: flex; align-items: flex-start; justify-content: center; gap: 30rpx; margin-top: 20rpx; }
.vs-cb { display: flex; flex-direction: column; align-items: center; gap: 10rpx; }
.vs-cb-t { font-size: 19rpx; font-weight: 700; color: var(--sj-sub); }
.vs-cb-i {
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: #fff;
}
.n1 { width: 72rpx; height: 72rpx; border: 1px solid var(--sj-line); box-shadow: var(--sj-sh-sm); }
.n2 { width: 108rpx; height: 108rpx; border: 3rpx solid var(--sj-primary); box-shadow: 0 14rpx 32rpx rgba(224, 142, 60, .18); }
.n3 { width: 92rpx; height: 92rpx; background: linear-gradient(145deg, var(--sj-primary), var(--sj-primary-deep)); box-shadow: 0 18rpx 40rpx rgba(224, 142, 60, .36); }
/* image 组件需显式宽高；24 viewBox 图标按按钮直径约 4 成缩放 */
.vs-ic { width: 40rpx; height: 40rpx; }
.vs-ic-mic { width: 44rpx; height: 44rpx; }
.vs-ic-play { width: 30rpx; height: 30rpx; }

/* 兜底提示 */
.vs-tip { text-align: center; margin-top: 12rpx; }
.vs-tip text { font-size: 20rpx; font-weight: 700; color: var(--sj-sub); }
.vs-tip.bad text { color: var(--sj-bad); }

@media (prefers-reduced-motion: reduce) {
  .vs-jelly.run, .vs-bub, .g-dot, .vs-timer-n, .vs-wave.run .wb { animation: none; }
}
</style>
