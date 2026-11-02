<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回按钮 + display 标题） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">成长视频</text>
    </view>

    <view class="content">
      <!-- 本地合成说明（v2 pg-hint 虚线提示；合规文案原样保留） -->
      <view class="pg-hint"><text>30–90 秒成长视频 · 仅使用你的照片与视频 · 在手机里制作，不会上传</text></view>

      <!-- 时间范围（v2 pg-sec + pg-chips 胶囊） -->
      <view class="pg-sec"><text>时间范围</text></view>
      <view class="pg-chips">
        <sj-tag
          v-for="(r, i) in VIDEO_RANGES"
          :key="i"
          variant="chip"
          pressable
          :active="range === i"
          :text="r"
          @click="pickRange(i)"
        />
      </view>

      <!-- 背景音乐（v2 pg-vrow 单选行 + sj-checkbox 勾选方块） -->
      <view class="pg-sec"><text>背景音乐（内置）</text></view>
      <view class="music-list">
        <view
          class="pg-vrow"
          :class="{ on: music === i }"
          v-for="(m, i) in VIDEO_MUSIC"
          :key="i"
          hover-class="hover-press"
          :hover-stay-time="80"
          @click="pickMusic(i)"
        >
          <!-- 勾选框本体（单选语义：选中即排他走 pickMusic，取消点击忽略；u-checkbox 内部 tap.stop 不冒泡到行） -->
          <sj-checkbox :checked="music === i" @change="v => v && pickMusic(i)" />
          <text class="v-name">{{ m.n }}</text>
          <text class="v-sub">{{ m.d }}</text>
        </view>
      </view>

      <!-- 合成进度（v2 grow-card + sj-progress 进度条 + pg-quota 配额行） -->
      <view class="grow-card" v-if="progress !== null">
        <view class="gc-head">
          <text class="gc-title">制作进度</text>
          <text class="gc-tag">手机制作</text>
        </view>
        <sj-progress class="mc-prog" :percent="progress" :height="10" />
        <view class="pg-quota">
          <text>{{ progressText }}</text>
          <text class="q-pct">{{ progress }}%</text>
        </view>
      </view>

      <!-- 合成主按钮（v2 pg-btn 渐变） -->
      <sj-button
        class="pg-btn"
        block
        size="lg"
        :text="busy ? '制作中…' : '生成视频'"
        @click="startVideo"
      />
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import { VIDEO_RANGES, VIDEO_MUSIC } from '@/utils/mock.js'
import { play } from '@/utils/sound.js'

export default {
  data() {
    return {
      VIDEO_RANGES,
      VIDEO_MUSIC,
      range: 1,
      music: 0,
      progress: null,
      timer: null,
      statusBarHeight: 20
    }
  },

  computed: {
    busy() {
      return this.progress !== null && this.progress < 100
    },
    progressText() {
      if (this.progress >= 100) return '已完成 · 已保存到相册'
      const sec = Math.max(1, Math.round((100 - this.progress) / 25)) * 3
      return '正在手机上制作 · ' + this.progress + '% · 预计 ' + sec + ' 秒'
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  onUnload() {
    if (this.timer) { clearInterval(this.timer); this.timer = null }
  },

  methods: {
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    pickRange(i) { this.range = i },
    pickMusic(i) { this.music = i },

    /* 合成流程：进度条每 300ms +25，到 100 完成（本机合成为原型演示语义） */
    startVideo() {
      if (this.busy) return
      this.progress = 0
      this.timer = setInterval(() => {
        this.progress = Math.min(100, this.progress + 25)
        if (this.progress >= 100) {
          clearInterval(this.timer)
          this.timer = null
          /* 视频合成完成：播 E08（合成过程中不播任何进度音） */
          play('E08')
          this.$refs.ntf.show({ type: 'ok', message: '视频已合成 · 已保存到相册' })
        }
      }, 300)
    }
  }
}
</script>

<style lang="scss" scoped>
.page {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  position: relative;
  z-index: 0;

  min-height: 100vh;
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
}

/* ---------- 顶栏 pg-back ---------- */
.pg-back {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding-left: 24rpx;
  padding-right: 24rpx;
  padding-bottom: 24rpx;
}
.bk {
  width: 68rpx;
  height: 68rpx;
  border-radius: 50%;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--sj-sh-sm);
  flex: none;
}
.bk:active { transform: scale(0.92); }
.bk-ic { width: 40rpx; height: 40rpx; }
.pg-title {
  flex: 1;
  font-family: var(--sj-font-display);
  font-size: 40rpx;
  font-weight: 900;
  color: var(--sj-ink);
}

/* ---------- 内容区 ---------- */
.content { padding: 8rpx 32rpx 48rpx; }

/* 虚线提示行（v2 pg-hint） */
.pg-hint {
  font-size: 23rpx;
  color: var(--sj-sub);
  background: var(--sj-cream);
  border: 2rpx dashed var(--sj-line);
  border-radius: 24rpx;
  padding: 16rpx 24rpx;
  margin-bottom: 24rpx;
  line-height: 1.5;
}
.pg-hint.tail { margin-top: 8rpx; margin-bottom: 0; }

/* 小节标题（v2 pg-sec） */
.pg-sec {
  display: flex;
  align-items: center;
  gap: 12rpx;
  font-size: 24rpx;
  font-weight: 900;
  color: var(--sj-faint);
  margin: 28rpx 0 16rpx;
}
.pg-sec::before {
  content: "";
  width: 10rpx;
  height: 28rpx;
  border-radius: 6rpx;
  background: var(--sj-primary);
  flex: none;
}

/* 时间范围胶囊（v2 pg-chips） */
.pg-chips { display: flex; flex-wrap: wrap; gap: 16rpx; margin-bottom: 8rpx; }

/* 音乐单选行（v2 pg-vrow：白底卡行 + sj-checkbox 勾选方块） */
.music-list { margin-bottom: 8rpx; }
.pg-vrow {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: 28rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 16rpx;
  box-shadow: var(--sj-sh-sm);
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.pg-vrow:active { transform: scale(0.98); }
.pg-vrow.on { border-color: var(--sj-primary); }
.v-name { flex: 1; font-size: 26rpx; font-weight: 800; color: var(--sj-ink); }
.v-sub { font-size: 21rpx; color: var(--sj-faint); flex: none; max-width: 320rpx; }

/* 合成进度卡（v2 grow-card + sj-progress + pg-quota） */
.grow-card {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  box-shadow: var(--sj-sh-sm);
  padding: 28rpx;
  margin-top: 20rpx;
}
.gc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
}
.gc-title { font-size: 26rpx; font-weight: 900; color: var(--sj-ink); }
.gc-tag { font-size: 21rpx; font-weight: 700; color: var(--sj-faint); }
/* sj-progress 与下方配额行的间距（原自绘进度条 margin-bottom 语义保留） */
.mc-prog { margin-bottom: 12rpx; }
.pg-quota {
  display: flex;
  justify-content: space-between;
  font-size: 22rpx;
  color: var(--sj-sub);
  font-weight: 700;
}
.q-pct { color: var(--sj-primary-deep); }
/* 主按钮：外观由 sj-button（block size=lg）统一提供，此处仅保留布局 */
.pg-btn {
  display: flex;
  margin-top: 40rpx;
}
</style>
