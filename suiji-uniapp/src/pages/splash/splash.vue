<template>
  <view class="splash" :class="{ out: leaving }" :style="themeVars" @click="skip">
    <!-- 微信端氛围层动效暂不生效，启动页先只留静态底色（.splash / .scene 自带渐变兜住），
         不渲染这层会「定格成满屏静态小图标」的动态图层；H5 / App 保持原样 -->
    <!-- #ifndef MP-WEIXIN -->
    <sj-bg />
    <!-- #endif -->
    <view class="scene" :class="phases">

      <!-- ① 滴落（蜂蜜滴 / 水珠，随主题换色；App 端不支持内联 svg，改 image + data URI） -->
      <view class="drop">
        <image class="m-img" :src="dropSrc" mode="aspectFit" />
      </view>
      <!-- ② 涟漪 -->
      <view class="ripple"><i></i><i></i><i></i></view>

      <!-- ③ 吉祥物弹出（呼吸/眨眼动画内置于 face svg 文件） -->
      <view class="mascot">
        <image class="m-img" :src="faceSrc" mode="aspectFit" />
      </view>

      <!-- ⑤ 粒子绽放（静态 svg 文件；位移量用 px，内联 style 的 rpx 不会被编译转换） -->
      <view class="fx">
        <i style="--tx:-50px;--ty:-37px;--rot:-18deg;--sc:1;--dl:0s;width:24px;height:24px"><image class="sym" src="/static/anim/sym-heart.svg" /></i>
        <i style="--tx:52px;--ty:-39px;--rot:14deg;--sc:1;--dl:.05s;width:22px;height:22px"><image class="sym" src="/static/anim/sym-star.svg" /></i>
        <i style="--tx:-64px;--ty:-4px;--rot:0deg;--sc:.8;--dl:.1s;width:20px;height:20px"><image class="sym" src="/static/anim/sym-paw.svg" /></i>
        <i style="--tx:63px;--ty:-2px;--rot:20deg;--sc:.9;--dl:.15s;width:22px;height:22px"><image class="sym" src="/static/anim/sym-paw.svg" /></i>
        <i style="--tx:-39px;--ty:26px;--rot:10deg;--sc:.7;--dl:.2s;width:20px;height:20px"><image class="sym" src="/static/anim/sym-star.svg" /></i>
        <i style="--tx:0px;--ty:-64px;--rot:0deg;--sc:1;--dl:.08s;width:20px;height:20px"><image class="sym" src="/static/anim/sym-heart.svg" /></i>
        <i style="--tx:-59px;--ty:22px;--rot:-8deg;--sc:.65;--dl:.24s;width:16px;height:16px"><image class="sym" src="/static/anim/sym-heart.svg" /></i>
        <i style="--tx:59px;--ty:24px;--rot:8deg;--sc:.7;--dl:.26s;width:16px;height:16px"><image class="sym" src="/static/anim/sym-star.svg" /></i>
      </view>

      <!-- ④ 品牌落版 -->
      <view class="logo">
        <text class="lg lg1">岁</text><text class="lg lg2">记</text>
        <image class="uline" :src="ulineSrc" />
      </view>
      <text class="tagline">记录成长的每一岁</text>

      <!-- ⑥ 采集加载（仅文字提示） -->
      <view class="loader">
        <text class="lt">正在为你收集今天的成长…</text>
      </view>
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import * as guide from '@/utils/first-run.js'
import { palette } from '@/theme/theme.js'

/* 启动加载动画：应用启动默认页 / 「我的 → 启动加载动画（演示）」入口
 * v2 IP 启动动效（蜂蜜苏醒 / 池塘破水），按主题渲染熊/鸭，分镜压缩至 ≈2.2s；轻点任意处跳过。
 * 演示入口（from=me）返回来源页，启动则进首页。
 * 云端门控（TDD v3.0）：
 *   未登录 → 直接进登录（首次安装引导入口已移除，onboard 页面暂保留）；
 *   已登录 → await bootstrap 灌缓存后逐级判定：无家庭 → 创建/加入引导页；
 *   无宝宝 → 新建档案页；未留痕同意 → 隐私页。
 * 安卓适配：App 端不支持内联 <svg> 标签，图形一律走 <image>（静态文件或 data URI，
 * 主题色在 JS 内烘焙）；keyframes / 内联 style 不使用 rpx（不会被编译转换）。 */
export default {
  data() {
    return {
      leaving: false,
      from: '',
      timer: null,
      phases: [],
      animTimers: []
    }
  },

  computed: {
    /* 吉祥物头像（呼吸/眨眼动画内置于 SVG 文件） */
    faceSrc() {
      const t = this.themeName === 'duck' ? 'duck' : 'bear'
      return `/static/anim/${t}-face.svg`
    },
    /* 滴落：主题主色烘焙进 data URI */
    dropSrc() {
      const c = palette(this.themeName)
      const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 30">' +
        `<path d="M12 1C7 8 4 13 4 18a8 8 0 0 0 16 0C20 13 17 8 12 1z" fill="${c.primary}" stroke="${c['primary-deep']}" stroke-width="2"/>` +
        '<circle cx="9" cy="17" r="2.2" fill="#fff" opacity=".55"/></svg>'
      return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
    },
    /* 品牌下划线：描线动画内置，主题色烘焙 */
    ulineSrc() {
      const c = palette(this.themeName)
      const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 14">' +
        '<style>.u{stroke-dasharray:150;stroke-dashoffset:150;animation:ujd .6s ease .3s forwards}' +
        '@keyframes ujd{to{stroke-dashoffset:0}}</style>' +
        `<path class="u" d="M6 9 q36 -8 68 -3 t70 -1" fill="none" stroke="${c.primary}" stroke-width="5" stroke-linecap="round"/></svg>`
      return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
    }
  },

  onLoad(query) {
    this.from = (query && query.from) || ''
  },

  onReady() {
    this.playAnim()
    this.timer = setTimeout(this.skip, 2200)
  },

  onUnload() {
    clearTimeout(this.timer)
    this.animTimers.forEach(clearTimeout)
    this.animTimers = []
  },

  methods: {
    /* 相位时间轴（1× 速度，毫秒） */
    playAnim() {
      const sched = [
        [0, 'ph-drop'], [150, 'ph-ripple'], [240, 'ph-bear'], [600, 'ph-blink'],
        [660, 'ph-logo'], [860, 'ph-burst'], [950, 'ph-load'], [1300, 'ph-exit']
      ]
      sched.forEach(([t, c]) => {
        this.animTimers.push(setTimeout(() => { this.phases.push(c) }, t))
      })
    },

    skip() {
      if (this.leaving) return
      this.leaving = true
      this.animTimers.forEach(clearTimeout)
      this.animTimers = []
      /* 演示入口（from=me）：直接返回来源页，不做登录门控 */
      if (this.from === 'me' && getCurrentPages().length > 1) {
        setTimeout(() => uni.navigateBack(), 450)
        return
      }
      /* 未登录：直接进登录（首次安装引导入口已移除） */
      if (!api.isLoggedIn()) {
        setTimeout(() => uni.reLaunch({ url: '/pages/login/login' }), 450)
        return
      }
      /* 已登录：等待全量缓存就绪再决定去向（与 App.vue 的 init 共享同一在途请求）
       * silent：不可达时只弹本页这条提示，避免与 http 层兜底提示重复 */
      const p = api.init({ silent: true })
      /* init 通常早已在途、此处瞬间返回；慢网下品牌动效已播完却仍卡在末帧，
       * 超过 400ms 未就绪才叠一层全屏 loading 兜住这段「切换页面的空隙」 */
      let settled = false
      let ld = null
      const wait = setTimeout(() => {
        if (settled) return
        ld = ui.loading('正在准备你的成长记录…', { sub: '首次进入需要一点时间' })
      }, 400)
      p.then(ok => {
        settled = true
        clearTimeout(wait)
        if (ld) ld.close()
        setTimeout(() => {
          if (!ok) {
            this.$refs.ntf.show({ type: 'err', message: '网络连接不上，请检查手机网络后重试' })
            uni.reLaunch({ url: '/pages/login/login' })
          } else {
            /* 无家庭 → 引导页；无宝宝 → 建档页；未留痕 → 隐私页；否则进首页 */
            guide.goAfterLogin()
          }
        }, 450)
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.splash {
  position: fixed;
  left: 0; right: 0; top: 0; bottom: 0;
  background: var(--sj-cream);
  opacity: 1;
  transition: opacity 0.45s cubic-bezier(.22,.8,.3,1);
}
.splash.out { opacity: 0; }

.scene {
  position: absolute;
  left: 0; right: 0; top: 0; bottom: 0;
  overflow: hidden;
  /* 只留中心暖光晕：奶油底与漂浮光斑由全局 <sj-bg /> 图层提供（不透明底会盖住它） */
  background: radial-gradient(920rpx 680rpx at 50% 26%, var(--sj-primary-soft), transparent 72%);
}

/* ① 滴落 */
.drop { position: absolute; left: 50%; top: 30%; width: 52rpx; height: 68rpx; opacity: 0; transform: translate(-50%, -340rpx); }
.drop .m-img { width: 100%; height: 100%; }
.ph-drop .drop { animation: sp-dropFall .52s cubic-bezier(.5,0,.85,.4) forwards; }
@keyframes sp-dropFall {
  0% { opacity:1; transform: translate(-50%,-170px) scale(.8,1.15); }
  62% { opacity:1; transform: translate(-50%,0) scale(.95,1.05); }
  78% { opacity:1; transform: translate(-50%,6px) scale(1.35,.6); }
  100% { opacity:0; transform: translate(-50%,8px) scale(1.6,.35); }
}

/* ② 涟漪 */
.ripple { position: absolute; left: 50%; top: calc(30% + 34rpx); }
.ripple i { position: absolute; border: 6rpx solid var(--sj-primary); border-radius: 50%; opacity: 0; transform: translate(-50%,-50%) scale(.1); }
.ripple i:nth-child(1), .ripple i:nth-child(2), .ripple i:nth-child(3) { width: 240rpx; height: 240rpx; }
.ph-ripple .ripple i { animation: sp-rip .8s cubic-bezier(.22,.8,.3,1) forwards; }
.ph-ripple .ripple i:nth-child(2) { animation-delay: .14s; }
.ph-ripple .ripple i:nth-child(3) { animation-delay: .28s; }
@keyframes sp-rip { 0%{ transform: translate(-50%,-50%) scale(.12); opacity:.85;} 100%{ transform: translate(-50%,-50%) scale(1.7); opacity:0;} }

/* ③ 吉祥物 */
.mascot { position: absolute; left: 50%; top: 42%; width: 424rpx; height: 424rpx; opacity: 0; transform: translate(-50%,-50%) scale(0); }
.mascot .m-img { width: 100%; height: 100%; }
.ph-bear .mascot { animation: sp-pop .72s cubic-bezier(.34,1.56,.64,1) forwards; }
@keyframes sp-pop { 0%{ opacity:0; transform: translate(-50%,-50%) scale(0);} 55%{ opacity:1;} 100%{ opacity:1; transform: translate(-50%,-50%) scale(1);} }

/* ④ LOGO */
.logo { position: absolute; left: 50%; top: 60%; transform: translate(-50%,-50%); text-align: center; white-space: nowrap; }
.logo .lg { display: inline-block; font-family: var(--sj-font-display); font-size: 104rpx; font-weight: 900; letter-spacing: 12rpx; color: var(--sj-ink); opacity: 0; transform: scale(0); }
.ph-logo .lg1 { animation: sp-charPop .5s cubic-bezier(.34,1.56,.64,1) both; }
.ph-logo .lg2 { animation: sp-charPop .5s cubic-bezier(.34,1.56,.64,1) .12s both; }
@keyframes sp-charPop { 0%{ opacity:0; transform: scale(0) rotate(-10deg);} 55%{ opacity:1; transform: scale(1.22) rotate(3deg);} 100%{ opacity:1; transform: scale(1) rotate(0);} }
.logo .uline { display: block; margin: 4rpx auto 0; width: 300rpx; height: 28rpx; }
.tagline { position: absolute; left: 50%; top: calc(60% + 116rpx); transform: translate(-50%, 20rpx); font-size: 28rpx; letter-spacing: 8rpx; color: var(--sj-sub); opacity: 0; font-weight: 700; }
.ph-logo .tagline { animation: sp-fadeUp .55s cubic-bezier(.22,.8,.3,1) .4s both; }
@keyframes sp-fadeUp { to { opacity: 1; transform: translate(-50%, 0); } }

/* ⑤ 粒子 */
.fx { position: absolute; left: 50%; top: 42%; width: 0; height: 0; }
.fx i { position: absolute; left: 0; top: 0; opacity: 0; transform: translate(-50%,-50%) scale(.2); }
.fx .sym { display: block; width: 100%; height: 100%; }
.ph-burst .fx i { animation: sp-burst .95s cubic-bezier(.22,.8,.3,1) var(--dl) forwards; }
@keyframes sp-burst {
  0% { opacity:0; transform: translate(-50%,-50%) scale(.2) rotate(0); }
  18% { opacity:1; }
  100% { opacity:0; transform: translate(calc(-50% + var(--tx)), calc(-50% + var(--ty))) scale(var(--sc)) rotate(var(--rot)); }
}

/* ⑥ 采集加载 */
.loader { position: absolute; left: 50%; top: 76%; transform: translate(-50%,-50%); display: flex; flex-direction: column; align-items: center; gap: 8rpx; opacity: 0; }
.loader .lt { font-size: 23rpx; color: var(--sj-faint); letter-spacing: 4rpx; }
.ph-load .loader { animation: sp-fadeUp .4s cubic-bezier(.22,.8,.3,1) both; }

/* ⑦ 收束 → 交接 */
.ph-exit .mascot { animation: sp-zoomOut .55s cubic-bezier(.22,.8,.3,1) forwards; }
@keyframes sp-zoomOut { 0%{ opacity:1; transform: translate(-50%,-50%) scale(1);} 100%{ opacity:0; transform: translate(-50%,-56%) scale(1.9);} }
.ph-exit .logo, .ph-exit .tagline, .ph-exit .loader, .ph-exit .ripple { animation: sp-fadeOut .4s ease both; }
@keyframes sp-fadeOut { to { opacity: 0; } }

@media (prefers-reduced-motion: reduce) {
  .ph-drop .drop, .ph-ripple .ripple i, .ph-bear .mascot,
  .ph-logo .lg1, .ph-logo .lg2,
  .ph-logo .tagline, .ph-burst .fx i, .ph-load .loader,
  .ph-exit .mascot { animation: none; }
  .ph-bear .mascot, .ph-logo .lg { opacity: 1; transform: translate(-50%,-50%) scale(1); }
}
</style>
