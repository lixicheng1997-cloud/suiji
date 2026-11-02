<!--
  sj-bg · 全局氛围背景（按当前形象主题渲染专属动态层）
    bear 森林绘本：小熊掌印沿「左边距下行 → 底部留白带横穿」小径逐个「盖章」前行 + 蜂蜜滴下坠 + 星光呼吸闪烁 + 落叶飘旋 + 爱心上浮
    duck 池塘戏水：水面涟漪层层扩散 + 鸭掌印回程小径 + 气泡上浮破裂 + 羽毛斜飘
  共用层：主题化底色（bear 蜂蜜暖棕 / duck 池塘清亮）+ 2 枚呼吸光斑
  （性能版：删除全屏阳光扫光亮带并精简图层 ~25→~13，减少常驻合成层与 GPU 内存，观感保持）
  用法：放在页面根节点的第一个子节点 <sj-bg />；根节点自身背景需为 transparent，
  本层以 z-index:-1 沉到所有内容之下，页面滚动时保持固定不动。
  切主题时 uni.$emit('sj:theme') → 混入 themeName 变化 → 整层即时重绘，无需重启或刷新页面。
  三端约定：
    1) 动画一律加在 <view> 图层上，<image> 只做静态图形（项目其他动效也从不直接动 image 节点）；
    2) keyframes 内只写 px / 纯数值（安卓 webview 对 keyframes 里的 rpx、var() 解析不稳），位移走 transform；
    3) 位置与尺寸用 rpx/%，写在行内 style（App 端由编译器换算 rpx）。
  微信端注意：小程序 <image> 不渲染 SVG（design-contract-uniapp.md §5），上微信前需把
  static/anim/bg-*.svg 以 3× 同名 PNG 补齐，本层图形只需切换 src 后缀。
-->
<template>
  <view class="sj-bg" :class="'sjb-' + themeName">
    <view class="sjb-wash" />
    <view class="sjb-orb sjb-orb-1" />
    <view class="sjb-orb sjb-orb-2" />

    <!-- ============ bear：小熊主题 ============ -->
    <template v-if="themeName === 'bear'">
      <view v-for="(p, i) in bearTrail" :key="'bp' + i" class="sjb-slot sjb-stamp" :style="layerStyle(p)">
        <image class="sjb-gly" :style="glyStyle(p)" src="/static/anim/bg-paw-bear.svg" mode="aspectFit" />
      </view>
      <view v-for="(h, i) in bearHoney" :key="'bh' + i" class="sjb-slot sjb-drip" :style="layerStyle(h)">
        <image class="sjb-gly" src="/static/anim/bg-honey.svg" mode="aspectFit" />
      </view>
      <view v-for="(l, i) in bearLeaves" :key="'bl' + i" class="sjb-slot sjb-fall" :style="layerStyle(l)">
        <image class="sjb-gly" src="/static/anim/bg-leaf.svg" mode="aspectFit" />
      </view>
      <view v-for="(s, i) in bearStars" :key="'bs' + i" class="sjb-slot sjb-twinkle" :style="layerStyle(s)">
        <image class="sjb-gly" src="/static/anim/sym-star.svg" mode="aspectFit" />
      </view>
      <view class="sjb-slot sjb-riser" :style="layerStyle(bearHeart)">
        <image class="sjb-gly" src="/static/anim/sym-heart.svg" mode="aspectFit" />
      </view>
    </template>

    <!-- ============ duck：小鸭主题 ============ -->
    <template v-else>
      <view v-for="(r, i) in duckRipples" :key="'dr' + i" class="sjb-slot" :style="slotStyle(r)">
        <view class="sjb-ring" :style="beatStyle(r)" />
        <view class="sjb-ring" :style="beatStyle(r, 1.9)" />
      </view>
      <view v-for="(f, i) in duckTrail" :key="'df' + i" class="sjb-slot sjb-stamp" :style="layerStyle(f)">
        <image class="sjb-gly" :style="glyStyle(f)" src="/static/anim/bg-foot-duck.svg" mode="aspectFit" />
      </view>
      <view v-for="(b, i) in duckBubbles" :key="'db' + i" class="sjb-slot" :style="slotStyle(b)">
        <view class="sjb-bubble" :style="beatStyle(b)" />
      </view>
      <view v-for="(w, i) in duckFeathers" :key="'dw' + i" class="sjb-slot sjb-drift" :style="layerStyle(w)">
        <image class="sjb-gly" src="/static/anim/bg-feather.svg" mode="aspectFit" />
      </view>
    </template>
  </view>
</template>

<script>
/**
 * 岁记 · IP 主题动态背景（easycom 自动注册 <sj-bg />）
 * 图形走 /static/anim 下的 SVG 文件（App 端不支持内联 <svg>），动画全部用 CSS keyframes。
 * 每主题约 25 个动画图层，只动 transform 与 opacity，交给 webview 合成层。
 */
const CYCLE = 12 // 掌印小径一轮的秒数：延迟按序号递增，形成连续行走

export default {
  name: 'SjBg',
  data() {
    return {
      /* 掌印小径：先沿左边距向下走，再在底部留白带横向穿越（首页 tabbar 上方留白最完整可见） */
      bearTrail: [
        { left: '-2%', top: '10%', size: 72, rot: 176, at: 0 },
        { left: '-1%', top: '40%', size: 74, rot: 172, at: 1.1 },
        { left: '8%', top: '78%', size: 78, rot: 96, at: 2.2 },
        { left: '40%', top: '78%', size: 82, rot: 98, at: 3.3 },
        { left: '72%', top: '78%', size: 84, rot: 96, at: 4.4 }
      ],
      bearHoney: [
        { left: '70%', top: '3%', size: 46, at: 0, dur: 11 },
        { left: '12%', top: '5%', size: 42, at: 5, dur: 12 }
      ],
      bearLeaves: [
        { left: '84%', top: '2%', size: 54, at: 1, dur: 14 }
      ],
      bearStars: [
        { left: '56%', top: '6%', size: 30, at: 0, dur: 3.6 },
        { left: '92%', top: '62%', size: 28, at: 2.1, dur: 3.9 },
        { left: '34%', top: '80%', size: 34, at: 0.7, dur: 4.6 }
      ],
      bearHeart: { left: '6%', bottom: '5%', size: 56, at: 0, dur: 12 },
      /* 涟漪：两组同心环错开扩散，中心放在顶部与底部留白带 */
      duckRipples: [
        { left: '2%', top: '70%', size: 380, at: 0, dur: 6.4 },
        { left: '64%', top: '4%', size: 260, at: 4.2, dur: 6 }
      ],
      /* 鸭掌印：沿右边距向下，再在底部向左回程 */
      duckTrail: [
        { left: '90%', top: '12%', size: 70, rot: 184, at: 0.3 },
        { left: '92%', top: '44%', size: 72, rot: 188, at: 1.4 },
        { left: '70%', top: '80%', size: 76, rot: -92, at: 2.5 },
        { left: '34%', top: '80%', size: 78, rot: -94, at: 3.6 }
      ],
      duckBubbles: [
        { left: '6%', bottom: '4%', size: 36, at: 0, dur: 8 },
        { left: '38%', bottom: '3%', size: 32, at: 4.4, dur: 8.6 },
        { left: '74%', bottom: '5%', size: 38, at: 3.6, dur: 9.2 }
      ],
      duckFeathers: [
        { left: '18%', top: '2%', size: 54, at: 0, dur: 14 },
        { left: '56%', top: '8%', size: 44, at: 6, dur: 16 }
      ]
    }
  },
  methods: {
    /* 纯几何：容器定位与占位尺寸 */
    slotStyle(i) {
      const s = { width: i.size + 'rpx', height: i.size + 'rpx' }
      if (i.left !== undefined) s.left = i.left
      if (i.right !== undefined) s.right = i.right
      if (i.top !== undefined) s.top = i.top
      if (i.bottom !== undefined) s.bottom = i.bottom
      return s
    },
    /* 动画容器：几何 + 延迟（出场次序）+ 时长（节奏） */
    layerStyle(i) {
      const s = this.slotStyle(i)
      s.animationDelay = (i.at || 0) + 's'
      s.animationDuration = (i.dur || CYCLE) + 's'
      return s
    },
    /* 内层图形：只做静态朝向，transform 动画留给容器，避免两层互相覆盖 */
    glyStyle(i) {
      return i.rot ? { transform: 'rotate(' + i.rot + 'deg)' } : {}
    },
    /* 内层视图（涟漪环、气泡）：延迟与时长 */
    beatStyle(i, extra) {
      const st = { animationDelay: (i.at + (extra || 0)) + 's' }
      st.animationDuration = (i.dur || CYCLE) + 's'
      return st
    }
  }
}
</script>

<style scoped>
.sj-bg {
  position: fixed;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: -1;
  overflow: hidden;
  pointer-events: none;
  background: var(--sj-cream);
}
.sjb-wash { position: absolute; left: 0; top: 0; right: 0; bottom: 0; }
.sjb-slot { position: absolute; }
.sjb-gly { display: block; width: 100%; height: 100%; }

/* —— 底色：bear 蜂蜜暖棕 / duck 池塘清亮 —— */
.sjb-bear .sjb-wash { background: radial-gradient(120% 76% at 18% 0%, #FFF1DA 0%, #FFF8F0 46%, #FCEFE0 100%); }
.sjb-duck .sjb-wash { background: radial-gradient(120% 76% at 82% 0%, #FFF8DA 0%, #FFF9EC 42%, #E9F5F1 100%); }

/* 漂浮光斑 */
.sjb-orb { position: absolute; border-radius: 50%; animation: sjbBreathe 12s ease-in-out infinite; }
.sjb-orb-1 { width: 420rpx; height: 420rpx; left: -140rpx; top: 10%; }
.sjb-orb-2 { width: 240rpx; height: 240rpx; right: 4%; top: 24%; animation-delay: -4s; animation-duration: 14s; }
.sjb-bear .sjb-orb-1 { background: radial-gradient(circle at 35% 35%, #FFE0B8, #FFCE96); }
.sjb-bear .sjb-orb-2 { background: radial-gradient(circle at 35% 35%, #FFDCE7, #FFC2D6); }
.sjb-duck .sjb-orb-1 { background: radial-gradient(circle at 35% 35%, #FFF0B4, #FFE08A); }
.sjb-duck .sjb-orb-2 { background: radial-gradient(circle at 35% 35%, #D9F1EC, #BEE6DE); }

/* —— 掌印 / 鸭掌印：逐个盖章，走完一轮再从头续行 —— */
.sjb-stamp { animation-name: sjbStamp; animation-timing-function: cubic-bezier(.3,1.4,.5,1); animation-iteration-count: infinite; animation-fill-mode: both; }

/* —— bear 专属 —— */
.sjb-drip { animation-name: sjbDrip; animation-timing-function: ease-in; animation-iteration-count: infinite; animation-fill-mode: both; }
.sjb-fall { animation-name: sjbFall; animation-timing-function: ease-in-out; animation-iteration-count: infinite; animation-fill-mode: both; }
.sjb-twinkle { animation-name: sjbTwinkle; animation-timing-function: ease-in-out; animation-iteration-count: infinite; animation-fill-mode: both; }
.sjb-riser { animation-name: sjbRise; animation-timing-function: ease-out; animation-iteration-count: infinite; animation-fill-mode: both; }

/* —— duck 专属 —— */
.sjb-ring {
  position: absolute; left: 0; top: 0; right: 0; bottom: 0;
  border-radius: 50%; border: 6rpx solid rgba(111, 189, 224, .85);
  box-shadow: 0 0 22rpx rgba(111, 189, 224, .35);
  animation-name: sjbRipple; animation-timing-function: ease-out;
  animation-iteration-count: infinite; animation-fill-mode: both;
}
.sjb-bubble {
  position: absolute; left: 0; top: 0; right: 0; bottom: 0;
  border-radius: 50%;
  background: radial-gradient(circle at 32% 28%, rgba(255,255,255,.95), rgba(190,230,222,.55) 62%, rgba(150,205,196,.25));
  border: 2rpx solid rgba(150, 205, 196, .5);
  animation-name: sjbBubble; animation-timing-function: ease-in-out;
  animation-iteration-count: infinite; animation-fill-mode: both;
}
.sjb-drift { animation-name: sjbDrift; animation-timing-function: ease-in-out; animation-iteration-count: infinite; animation-fill-mode: both; }

@keyframes sjbStamp {
  0%, 4% { opacity: 0; transform: scale(.28); }
  12% { opacity: .46; transform: scale(1.22); }
  20% { opacity: .34; transform: scale(1); }
  66% { opacity: .26; transform: scale(1.04); }
  82%, 100% { opacity: 0; transform: scale(.9); }
}
@keyframes sjbDrip {
  0% { opacity: 0; transform: translate(0, -40px) scale(.75) rotate(-8deg); }
  16% { opacity: .5; }
  70% { opacity: .4; transform: translate(14px, 170px) scale(1) rotate(10deg); }
  100% { opacity: 0; transform: translate(22px, 250px) scale(.86) rotate(16deg); }
}
@keyframes sjbFall {
  0% { opacity: 0; transform: translate(0, -30px) rotate(-24deg) scale(.8); }
  14% { opacity: .42; }
  50% { opacity: .34; transform: translate(-52px, 150px) rotate(150deg) scale(1); }
  100% { opacity: 0; transform: translate(16px, 320px) rotate(340deg) scale(.88); }
}
@keyframes sjbTwinkle {
  0%, 100% { opacity: .1; transform: scale(.62) rotate(-8deg); }
  50% { opacity: .62; transform: scale(1.2) rotate(26deg); }
}
@keyframes sjbRise {
  0% { opacity: 0; transform: translate(0, 30px) scale(.7); }
  22% { opacity: .48; }
  70% { opacity: .3; transform: translate(34px, -170px) scale(1.06); }
  100% { opacity: 0; transform: translate(48px, -240px) scale(.9); }
}
@keyframes sjbRipple {
  0% { opacity: 0; transform: scale(.18); }
  14% { opacity: .55; }
  100% { opacity: 0; transform: scale(1.75); }
}
@keyframes sjbBubble {
  0% { opacity: 0; transform: translate(0, 0) scale(.55); }
  14% { opacity: .6; }
  50% { opacity: .5; transform: translate(18px, -160px) scale(.92); }
  84% { opacity: .38; transform: translate(-10px, -270px) scale(1.12); }
  100% { opacity: 0; transform: translate(-16px, -320px) scale(1.4); }
}
@keyframes sjbDrift {
  0% { opacity: 0; transform: translate(-30px, -20px) rotate(-22deg) scale(.85); }
  16% { opacity: .45; }
  55% { opacity: .38; transform: translate(110px, 150px) rotate(38deg) scale(1); }
  100% { opacity: 0; transform: translate(56px, 320px) rotate(96deg) scale(.9); }
}
@keyframes sjbBreathe {
  0%, 100% { opacity: .5; transform: translate(0, 0) scale(1); }
  50% { opacity: .82; transform: translate(-8px, -26px) scale(1.14); }
}

/* 系统「减弱动态效果」时定格为静态氛围层（与 pages/splash 同一约定） */
@media (prefers-reduced-motion: reduce) {
  .sjb-orb, .sjb-stamp, .sjb-drip, .sjb-fall,
  .sjb-twinkle, .sjb-riser, .sjb-drift, .sjb-ring, .sjb-bubble { animation: none; }
  .sjb-orb { opacity: .6; }
  .sjb-stamp, .sjb-drip, .sjb-fall, .sjb-riser, .sjb-drift { opacity: .3; }
  .sjb-twinkle { opacity: .5; }
  .sjb-ring { opacity: .3; transform: scale(1); }
  .sjb-bubble { opacity: .4; }
}
</style>
