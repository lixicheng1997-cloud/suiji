<template>
  <view class="page onb" :style="themeVars">
    <sj-bg />
    <!-- 退出按钮（v2 pg-back 圆形钮：让出状态栏） -->
    <view class="bk-exit" :style="{ top: 'calc(' + statusBarHeight + 'px + 24rpx)' }" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
      <image class="ex-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
    </view>

    <!-- 首次引导模式（登录前）：右上角跳过 -->
    <view
      v-if="guide"
      class="bk-skip"
      :style="{ top: 'calc(' + statusBarHeight + 'px + 24rpx)' }"
      hover-class="hover-press"
      :hover-stay-time="80"
      @click="skipGuide"
    ><text>跳过</text></view>

    <!-- 步骤条（v2 pg-step：done 绿圆✓ / now 主色呼吸高亮 / 未来 faint 灰）
         三段对应绘本进程：翻开 → 成长页 → 尾声·建档，由现有 flipped / atEnd 驱动 -->
    <view class="onb-steps" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 24rpx)' }">
      <view class="pg-step">
        <view class="st" :class="{ done: flipped > 0, now: flipped === 0 }">
          <text>{{ flipped > 0 ? '✓' : '1' }}</text>
        </view>
        <view class="ln" />
        <view class="st" :class="{ done: atEnd, now: flipped > 0 && !atEnd }">
          <text>{{ atEnd ? '✓' : '2' }}</text>
        </view>
        <view class="ln" />
        <view class="st" :class="{ now: atEnd }"><text>3</text></view>
      </view>
    </view>

    <!-- 成长之书：封面 → 6 张成长页 → 封底 CTA -->
    <view class="bk-scene">
      <view class="bk-book" @touchstart="onTouchStart" @touchend="onTouchEnd">
        <view
          class="bk-leaf"
          v-for="(p, i) in pages"
          :key="i"
          :class="{ 'bk-cover': i === 0, 'bk-endleaf': i === pages.length - 1, 'bk-flipped': i < flipped }"
          :style="{ zIndex: leafZ(i) }"
        >
          <view class="bk-face bk-front">
            <!-- 封面：吉祥物 + display 大标题 -->
            <block v-if="i === 0">
              <view class="bk-cv-mark"><sj-mascot :size="180" /></view>
              <view class="bk-cv-title"><text>岁记</text><text>成长之书</text></view>
              <view class="bk-cv-sub"><text>从第一声啼哭</text><text>到第一步蹒跚</text></view>
              <text class="bk-cv-hint">← 向左滑动 · 翻开</text>
            </block>
            <!-- 封底：建档 CTA + 信任项 -->
            <block v-else-if="i === pages.length - 1">
              <text class="bk-age bk-age-end">尾声</text>
              <view class="bk-title bk-end-title"><text>接下来的每一页</text><text>由你来写</text></view>
              <view class="bk-desc bk-end-desc">
                <text v-if="guide">登录账号后</text>
                <text v-else>阅读并同意《隐私政策》</text>
                <text>即可为宝宝建立第一份成长档案</text>
              </view>
              <sj-button
                class="pg-btn bk-cta"
                block
                size="lg"
                :text="guide ? '立即开始' : '开始建档'"
                @click="onCta"
              />
              <view class="bk-trusts">
                <view class="bk-trust" v-for="f in trusts" :key="f.t">
                  <image class="tr-ic" :src="'/static/icons/' + f.icon + '.svg'" />
                  <text>{{ f.t }}</text>
                </view>
              </view>
            </block>
            <!-- 成长内页 -->
            <block v-else>
              <text class="bk-age">{{ p.age }}</text>
              <view class="bk-illu" :style="{ background: p.tint }">
                <image class="illu-ic" :src="'/static/icons/' + p.icon + '.svg'" />
              </view>
              <text class="bk-title">{{ p.t }}</text>
              <text class="bk-desc">{{ p.d }}</text>
              <text class="bk-num">{{ i }} / {{ pages.length - 2 }}</text>
              <view class="bk-curl" />
            </block>
          </view>
          <view class="bk-face bk-back"><text class="bk-wm">岁记 · 成长之书</text></view>
        </view>

        <!-- 左右翻页热区（翻到封底后关闭，露出 CTA） -->
        <view class="bk-tap bk-tap-l" v-if="!atEnd" @click="tapPrev" />
        <view class="bk-tap bk-tap-r" v-if="!atEnd" @click="tapNext" />
      </view>
    </view>

    <view class="bk-hud"><text>{{ hudText }}</text></view>

    <sj-ui-host />
  </view>
</template>

<script>
import { WB_PAGES, OW_FEATURES } from '@/utils/mock.js'
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import * as guide from '@/utils/first-run.js'

/* 成长之书：封面 → 6 张成长页 → 封底 CTA
 * 两种入口：
 *  1) 首次安装引导（?guide=1，位于登录之前）：CTA / 跳过 → 落本机安装标记 → 登录页；
 *  2) 「我的 → 首次引导流程（演示）」：已登录，CTA 直接建档 → 隐私同意页。 */
export default {
  data() {
    return {
      guide: false,
      pages: WB_PAGES,
      trusts: OW_FEATURES,
      /* 已翻过的页数：0 = 封面，pages.length-1 = 封底 */
      flipped: 0,
      /* 正在翻动的页：翻动期间抬高层级避免与相邻页穿插 */
      busy: -1,
      swipeAt: 0,
      startX: null,
      statusBarHeight: 20
    }
  },

  computed: {
    atEnd() {
      return this.flipped === this.pages.length - 1
    },
    hudText() {
      const total = this.pages.length - 2
      if (this.flipped === 0) return '向左滑动，翻开第一页'
      if (this.flipped <= total) return `第 ${this.flipped} / ${total} 页 · ${this.pages[this.flipped].age}`
      return '翻到尾声 · 开始你的第一页'
    }
  },

  onLoad(query) {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
    /* ?guide=1 = 登录前的首次安装引导；缺省为「我的」演示入口 */
    this.guide = !!(query && query.guide)
  },

  methods: {
    goBack() {
      /* 引导模式：无上一页，返回即视为结束引导（落标记 → 登录） */
      if (this.guide && getCurrentPages().length <= 1) {
        guide.finishGuide()
        return
      }
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    /* 跳过引导：同样落本机安装标记，下次启动不再进入 */
    skipGuide() {
      guide.finishGuide()
    },

    /* 层叠规则与原型 wbLayout 一致：未翻区从右向左递减、已翻区从左向右递增 */
    leafZ(i) {
      if (i === this.busy) return 999
      const n = this.pages.length
      return i < this.flipped ? i + 1 : (n - i) + 10
    },

    flip(dir) {
      const next = this.flipped + dir
      if (next < 0 || next > this.pages.length - 1) return
      this.busy = dir > 0 ? this.flipped : this.flipped - 1
      this.flipped = next
      setTimeout(() => { this.busy = -1 }, 720)
    },

    onTouchStart(e) {
      this.startX = e.changedTouches[0].clientX
    },

    onTouchEnd(e) {
      if (this.startX === null) return
      const dx = e.changedTouches[0].clientX - this.startX
      this.startX = null
      if (Math.abs(dx) < 24) return
      this.flip(dx < 0 ? 1 : -1)
      /* 滑动后抑制紧随的 click，避免热区重复翻页 */
      this.swipeAt = Date.now()
    },

    tapPrev() {
      if (Date.now() - this.swipeAt < 150) return
      this.flip(-1)
    },

    tapNext() {
      if (Date.now() - this.swipeAt < 150) return
      this.flip(1)
    },

    /* 封底 CTA：引导模式（登录前）→ 落标记进登录；演示模式 → 建档后进《隐私政策》 */
    async onCta() {
      if (this.guide) {
        guide.finishGuide()
        return
      }
      /* 页面无表单：以默认昵称建档；已有宝宝时 onboardBaby 直接返回现有档案。
       * 建档变异步（POST /babies 由服务端排期里程碑/疫苗），失败时停留本页提示重试 */
      try {
        await api.onboardBaby({ name: '宝宝' })
      } catch (e) {
        ui.error(e, '建档失败，请检查网络后重试')
        return
      }
      uni.navigateTo({ url: '/pages/consent/consent' })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 页面底：v2 奶油色全屏绘本舞台 */
.page.onb {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  z-index: 0;
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
  font-family: var(--sj-font-body);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ---------- 退出按钮（v2 pg-back 圆形钮） ---------- */
.bk-exit {
  position: absolute;
  left: 24rpx;
  z-index: 1300;
  width: 68rpx;
  height: 68rpx;
  border-radius: 50%;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  box-shadow: var(--sj-sh-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ex-ic { width: 36rpx; height: 36rpx; }

/* ---------- 跳过（首次引导模式） ---------- */
.bk-skip {
  position: absolute;
  right: 24rpx;
  z-index: 1300;
  padding: 12rpx 32rpx;
  border-radius: var(--sj-r-pill);
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  box-shadow: var(--sj-sh-sm);
  font-size: 25rpx;
  font-weight: 700;
  color: var(--sj-sub);
}

/* ---------- 步骤条（v2 pg-step：done 绿✓ / now 主色呼吸 / 未来灰） ---------- */
.onb-steps {
  flex: none;
  padding-bottom: 8rpx;
}
.pg-step {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
}
.pg-step .st {
  width: 52rpx;
  height: 52rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  font-weight: 900;
  background: var(--sj-surface);
  border: 3rpx solid var(--sj-line);
  color: var(--sj-faint);
  transition: all 0.25s cubic-bezier(.22,.8,.3,1);
}
.pg-step .st.done {
  background: var(--sj-ok);
  border-color: var(--sj-ok);
  color: #fff;
}
.pg-step .st.now {
  background: var(--sj-primary);
  border-color: var(--sj-primary);
  color: #fff;
  animation: sj-glow 2s infinite;
}
.pg-step .ln {
  width: 52rpx;
  height: 4rpx;
  background: var(--sj-line);
  border-radius: 4rpx;
}
/* 当前步呼吸光晕（设计稿 glow：金色扩散环） */
@keyframes sj-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245, 179, 44, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(245, 179, 44, 0); }
}

/* ---------- 书与翻页 ---------- */
.bk-scene {
  flex: 1;
  perspective: 3400rpx;
  display: flex;
}
.bk-book { position: relative; flex: 1; }

.bk-leaf {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  transform-origin: left center;
  transform-style: preserve-3d;
  transition: transform 0.7s cubic-bezier(.22,.8,.3,1);
}
.bk-leaf.bk-flipped { transform: rotateY(-180deg); }

.bk-face {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  backface-visibility: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.bk-front {
  background: linear-gradient(160deg, var(--sj-surface) 0%, var(--sj-cream) 100%);
  padding: 68rpx 60rpx;
  overflow: hidden;
}
/* 书脊阴影（墨色低透明渐变，固定色值） */
.bk-front::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 72rpx;
  pointer-events: none;
  background: linear-gradient(90deg, rgba(91, 70, 54, 0.10), rgba(91, 70, 54, 0));
}
.bk-back {
  transform: rotateY(180deg);
  background: linear-gradient(270deg, var(--sj-cream), var(--sj-surface) 55%);
}
.bk-wm { font-size: 24rpx; letter-spacing: 8rpx; color: var(--sj-faint); opacity: 0.55; }

/* ---------- 封面（主色渐层 + 吉祥物） ---------- */
.bk-cover .bk-front {
  background: linear-gradient(150deg, var(--sj-primary) 8%, var(--sj-primary-deep) 92%);
  color: #fff;
}
.bk-cover .bk-front::before { background: linear-gradient(90deg, rgba(0, 0, 0, 0.16), rgba(0, 0, 0, 0)); }
.bk-cv-mark {
  width: 224rpx;
  height: 224rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.22);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 36rpx;
  overflow: hidden;
}
.bk-cv-title {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-family: var(--sj-font-display);
  font-size: 68rpx;
  font-weight: 900;
  letter-spacing: 12rpx;
  text-align: center;
  line-height: 1.5;
  margin-bottom: 36rpx;
}
.bk-cv-sub {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: 26rpx;
  opacity: 0.88;
  text-align: center;
  line-height: 1.9;
  letter-spacing: 4rpx;
}
.bk-cv-hint {
  margin-top: 32rpx;
  font-size: 24rpx;
  opacity: 0.85;
  border: 2rpx dashed rgba(255, 255, 255, 0.7);
  border-radius: var(--sj-r-pill);
  padding: 8rpx 24rpx;
  animation: bkHint 1.8s cubic-bezier(.22,.8,.3,1) infinite;
}
@keyframes bkHint {
  0%, 100% { transform: translateX(0); opacity: 0.8; }
  50% { transform: translateX(-6px); opacity: 1; }
}

/* ---------- 成长内页 ---------- */
.bk-age {
  font-size: 24rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  border-radius: var(--sj-r-pill);
  padding: 8rpx 28rpx;
}
.bk-illu {
  margin: 52rpx 0 36rpx;
  width: 176rpx;
  height: 176rpx;
  border-radius: var(--sj-r-lg);
  border: 2rpx solid var(--sj-line);
  display: flex;
  align-items: center;
  justify-content: center;
}
.illu-ic { width: 88rpx; height: 88rpx; }
.bk-title {
  font-family: var(--sj-font-display);
  font-size: 38rpx;
  font-weight: 900;
  color: var(--sj-ink);
  text-align: center;
  line-height: 1.7;
}
.bk-desc { font-size: 26rpx; color: var(--sj-sub); text-align: center; line-height: 1.9; margin-top: 24rpx; padding: 0 20rpx; }
.bk-num { position: absolute; right: 36rpx; bottom: 32rpx; font-size: 22rpx; color: var(--sj-faint); }
.bk-curl {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 0;
  height: 0;
  border-style: solid;
  border-width: 0 0 80rpx 80rpx;
  border-color: transparent transparent var(--sj-cream) transparent;
  filter: drop-shadow(-4rpx -4rpx 6rpx rgba(224, 126, 51, 0.18));
  animation: bkCurl 2.2s cubic-bezier(.22,.8,.3,1) infinite;
}
@keyframes bkCurl {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

/* ---------- 封底 CTA ---------- */
.bk-endleaf .bk-front {
  background: linear-gradient(200deg, var(--sj-primary-soft), var(--sj-cream) 70%);
}
.bk-age-end { background: var(--sj-surface); margin-bottom: 32rpx; }
.bk-end-title { font-size: 40rpx; display: flex; flex-direction: column; align-items: center; margin-bottom: 32rpx; }
.bk-end-desc { display: flex; flex-direction: column; align-items: center; margin-top: 0; }
.bk-cta {
  width: 64%;
  margin-top: 20rpx;
}
/* 主按钮：外观由 sj-button（block size=lg）统一提供，此处仅保留布局 */
.pg-btn { display: flex; }
.bk-trusts { display: flex; flex-direction: column; align-items: center; gap: 20rpx; margin-top: 36rpx; }
.bk-trust { display: flex; align-items: center; gap: 16rpx; font-size: 24rpx; color: var(--sj-sub); }
.tr-ic { width: 32rpx; height: 32rpx; }

/* ---------- 翻页热区与 HUD（pg-hint 胶囊观感） ---------- */
.bk-tap {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 40%;
  z-index: 1000;
}
.bk-tap-l { left: 0; }
.bk-tap-r { right: 0; }
.bk-hud {
  position: absolute;
  bottom: 36rpx;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1200;
  pointer-events: none;
  white-space: nowrap;
  font-size: 23rpx;
  color: var(--sj-sub);
  letter-spacing: 2rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-pill);
  padding: 10rpx 28rpx;
  box-shadow: var(--sj-sh-sm);
}
</style>
