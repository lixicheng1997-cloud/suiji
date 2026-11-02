<template>
  <view v-if="sources.length" class="sj-vp" :class="{ 'vp-sm': compact }" hover-class="hover-press" :hover-stay-time="80" @click.stop="toggle">
    <!-- 播放键：主题主色实心圆，播放中换成两条竖杠并随节拍呼吸 -->
    <view class="vp-btn" :class="{ on: playing }">
      <view v-if="!playing" class="vp-tri"></view>
      <view v-else class="vp-pz"><view class="vp-pz-b"></view><view class="vp-pz-b"></view></view>
    </view>

    <view class="vp-body">
      <view class="vp-wave" :class="{ run: playing }">
        <view
          v-for="(b, i) in bars"
          :key="i"
          class="vp-bar"
          :class="{ div: b.div, vb: !b.div, past: b.past, now: b.now }"
          :style="b.div ? null : { height: b.h + 'rpx', animationDelay: b.d }"
        ></view>
      </view>
      <view class="vp-line">
        <text class="vp-t">{{ playing || pos > 0 ? fmt(pos) + ' / ' + fmt(total) : fmt(total) }}</text>
        <text v-if="compact" class="vp-s">{{ playing ? '播放中' : '点按播放' }}</text>
        <text v-else-if="!compact && sources.length > 1" class="vp-s">{{ sources.length }} 段连播 · 点按{{ playing ? '停止' : '播放' }}</text>
      </view>
    </view>
  </view>
</template>

<script>
/**
 * 岁记 · 语音回放条（easycom 自动注册 <sj-voice-play>）
 *
 * 一条录音可能是 N 个文件（见 utils/voicePlayback.js 的按段排队）。
 * 波形来自录入时记录的 48 格振幅包络（payload.wave），没有包络的老数据画一条均分占位波形。
 * 段与段之间画一道分隔，让人看得出「这条由 N 段拼成」。
 *
 * 播放态的动效全部交给 CSS（波形起伏 + 按钮呼吸），JS 只按整秒推进 pos：
 * 一屏多条语音时，只有正在播的那一条会重算 bars，其余组件不参与刷新。
 * 配色走 --sj-primary 令牌族，换肤（bear/duck）时整条语音条跟着变色。
 *
 * @props segments [{url|path,dur}] / duration 总秒数 / wave [48]×0..40 / compact 时光轴紧凑态
 */
import { createVoicePlayer } from '@/utils/voicePlayback.js'

const BOUNCE_STEPS = 7 /* 波形弹跳的错峰档数：同档柱子同相位，看起来像水波掠过 */

export default {
  name: 'SjVoicePlay',
  props: {
    segments: { type: Array, default: () => [] },
    /* 单段旧数据（mock / 历史条目）只给 url，同样能播 */
    url: { type: String, default: '' },
    duration: { type: [Number, String], default: 0 },
    wave: { type: Array, default: () => [] },
    compact: { type: Boolean, default: false }
  },
  data() {
    return { playing: false, pos: 0 }
  },
  computed: {
    total() {
      return Math.max(0, Math.round(Number(this.duration) || 0))
    },
    sources() {
      const list = (this.segments || []).filter(s => s && (s.url || s.path))
      if (list.length || !this.url) return list
      return [{ start: 0, dur: this.total, url: this.url }]
    },
    bars() {
      const n = this.compact ? 18 : 32
      const src = this.wave && this.wave.length ? this.wave : null
      const env = []
      for (let i = 0; i < n; i++) {
        if (src) {
          /* 48 格包络按目标根数取样，避免拉伸变形 */
          const j = Math.min(src.length - 1, Math.floor((i / n) * src.length))
          env.push(Math.max(0.14, (Number(src[j]) || 0) / 40))
        } else {
          env.push(0.3 + 0.5 * Math.abs(Math.sin(i * 0.9)))
        }
      }
      const lim = this.total || 1
      /* 段起点换算成柱子下标：跨过该下标时插一条分隔，段边界一眼可见 */
      const marks = {}
      if (!this.compact) this.sources.slice(1).forEach(s => { marks[Math.floor(((Number(s.start) || 0) / lim) * n)] = true })
      /* pos 是整秒，播头（now）取覆盖该秒的那根柱：1Hz 刷新，柱子列表不重排 */
      const cur = this.playing || this.pos > 0 ? Math.min(this.pos, lim) : -1
      const head = cur < 0 ? -1 : Math.min(n - 1, Math.floor((cur / lim) * n))
      const out = []
      for (let i = 0; i < n; i++) {
        out.push({
          h: Math.round((this.compact ? 20 : 46) * env[i]) + 4,
          past: cur > 0 && ((i + 1) / n) * lim <= cur,
          now: i === head,
          d: (i % BOUNCE_STEPS) * 0.09 + 's'
        })
        if (marks[i + 1]) out.push({ div: true })
      }
      return out
    }
  },
  beforeUnmount() {
    if (this.player) { this.player.destroy(); this.player = null }
  },
  methods: {
    fmt(s) {
      const m = Math.floor(s / 60)
      const x = Math.floor(s % 60)
      return m + ':' + (x < 10 ? '0' : '') + x
    },
    toggle() {
      if (!this.player) this.player = createVoicePlayer()
      if (this.playing) {
        this.player.stop()
        this.playing = false
        this.pos = 0
        return
      }
      this.playing = true
      this.pos = 0
      this.player.play(this.sources, {
        /* onIndex(-1) = 本条被别处打断（另一条语音起播）或已停：跟着复位，否则按钮一直亮着 */
        onIndex: i => { if (i < 0) { this.playing = false; this.pos = 0 } },
        /* 只取整秒：秒级以下的高度/颜色变化交给 CSS 动画，避免每 250ms 一次 setData */
        onProgress: t => { const s = Math.floor(t); if (s !== this.pos) this.pos = s },
        onFinish: () => { this.playing = false; this.pos = 0 },
        onError: () => { this.playing = false; this.pos = 0 }
      }, this.total)
    }
  }
}
</script>

<style lang="scss" scoped>
.sj-vp {
  display: flex; align-items: center; gap: 16rpx;
  padding: 16rpx 20rpx;
  background: var(--sj-primary-soft);
  border: 1px solid var(--sj-line);
  border-radius: var(--sj-r-md);
}
.vp-sm { padding: 8rpx 14rpx; gap: 12rpx; border-radius: var(--sj-r-pill); }

.vp-btn {
  flex: none;
  display: flex; align-items: center; justify-content: center;
  width: 64rpx; height: 64rpx; border-radius: 50%;
  background: linear-gradient(145deg, var(--sj-primary), var(--sj-primary-deep));
  box-shadow: var(--sj-sh-sm);
}
.vp-sm .vp-btn { width: 44rpx; height: 44rpx; }
.vp-btn.on { background: var(--sj-primary-deep); animation: sjVpBeat 1.05s var(--sj-smooth) infinite; }
@keyframes sjVpBeat {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.07); }
}
.vp-tri {
  width: 0; height: 0; margin-left: 6rpx;
  border-left: 20rpx solid #fff;
  border-top: 12rpx solid transparent;
  border-bottom: 12rpx solid transparent;
}
.vp-sm .vp-tri { border-left-width: 14rpx; border-top-width: 9rpx; border-bottom-width: 9rpx; margin-left: 4rpx; }
.vp-pz { display: flex; gap: 6rpx; }
.vp-pz-b { width: 8rpx; height: 24rpx; border-radius: 4rpx; background: #fff; }
.vp-sm .vp-pz-b { width: 6rpx; height: 16rpx; border-radius: 3rpx; }

.vp-body { flex: 1; min-width: 0; }
.vp-wave { display: flex; align-items: center; height: 56rpx; gap: 4rpx; overflow: hidden; }
.vp-sm .vp-wave { height: 26rpx; }
.vp-bar {
  flex: 1; max-width: 8rpx; border-radius: 4rpx;
  background: var(--sj-primary);
  opacity: .34;
  transform-origin: 50% 50%;
  transition: opacity .2s var(--sj-smooth), background-color .2s var(--sj-smooth);
}
/* 播过的柱子实心、正在播的那根最深；整列错峰上下弹，静止的包络看起来在"呼吸" */
.vp-bar.past { opacity: .95; }
.vp-bar.now { opacity: 1; background: var(--sj-primary-deep); }
.vp-wave.run .vb { animation: sjVpBounce .92s var(--sj-smooth) infinite alternate; }
@keyframes sjVpBounce {
  from { transform: scaleY(.55); }
  to { transform: scaleY(1.15); }
}
.vp-bar.div { flex: none; width: 3rpx; height: 34rpx; border-radius: 2rpx; background: var(--sj-faint); }
.vp-line { display: flex; align-items: baseline; gap: 12rpx; margin-top: 4rpx; }
.vp-t { font-family: var(--sj-font-display); font-size: 24rpx; font-weight: 900; color: var(--sj-primary-deep); }
.vp-sm .vp-t { font-size: 20rpx; }
.vp-s { font-size: 19rpx; font-weight: 700; color: var(--sj-sub); }
</style>
