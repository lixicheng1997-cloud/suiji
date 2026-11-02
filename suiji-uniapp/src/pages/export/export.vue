<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回 + display 标题；导出按钮移至底部通栏 pg-btn） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">导出成长档案</text>
    </view>

    <view class="content">
      <!-- 导出说明（v2 pg-hint：cream 底虚线边） -->
      <!-- <view class="pg-hint">生成成长档案 PDF · 自动包含免责声明 · 默认不含健康记录</view> -->

      <view class="pg-sec"><text>导出内容</text></view>

      <!-- 章节勾选列表（v2 pg-field：白底 line 边 28rpx 圆角；勾选框用 sj-checkbox 封装控件） -->
      <view
        class="pg-field c-item"
        v-for="(s, i) in EXPORT_SECS"
        :key="i"
        hover-class="hover-press"
        :hover-stay-time="80"
        @click="toggleSec(i)"
      >
        <!-- 勾选框本体（u-checkbox 内部 tap.stop，点击不冒泡到行；行点击仍走 toggleSec） -->
        <sj-checkbox :checked="secs[i]" @change="v => (secs[i] = v)" />
        <view class="c-info">
          <view class="c-title">
            <text>{{ s.t }}</text>
            <text v-if="s.t === '健康记录页'" class="c-req">可选</text>
          </view>
          <text class="c-desc">{{ s.d }}</text>
        </view>
      </view>

      <!-- 合成进度（v2 grow-card + sj-progress：轨道/渐变填充组件内置，height 按 v2 设计 10px=20rpx） -->
      <view class="grow-card" v-if="progress !== null">
        <view class="gc-head">
          <text class="gc-title">生成进度</text>
          <text class="gc-sub">PDF</text>
        </view>
        <sj-progress :percent="progress" :height="10" />
        <text class="pg-text">{{ progressText }}</text>
      </view>

      <!-- 导出按钮（v2 pg-btn 通栏：primary 渐变白字 900） -->
      <sj-button
        class="pg-btn"
        block
        size="lg"
        :text="busy ? '生成中' : '导出 PDF'"
        @click="startExport"
      />

      <view class="pg-hint hint-gap">勾选「健康记录页」才会包含喂养 / 睡眠 / 测量摘要 · 分享前请确认接收人</view>
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import { EXPORT_SECS } from '@/utils/mock.js'
import * as ui from '@/utils/ui.js'
import { play } from '@/utils/sound.js'

export default {
  data() {
    return {
      EXPORT_SECS,
      /* 各章节勾选态，初值取 mock 的 on */
      secs: EXPORT_SECS.map(s => s.on),
      progress: null,
      timer: null,
      /* 真实落盘阶段：进度条跑完后 exportArchive 仍在拼 HTML + 写文件，此时才算真等待 */
      writing: false,
      statusBarHeight: 20
    }
  },

  computed: {
    busy() {
      return this.progress !== null && (this.progress < 100 || this.writing)
    },
    progressText() {
      if (this.progress < 100) return '正在合成档案 · ' + this.progress + '%'
      return this.writing ? '正在生成并保存档案文件…' : '已完成 · 档案已生成 · 已保存到文件'
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

    toggleSec(i) {
      this.secs[i] = !this.secs[i]
    },

    /* 导出流程：进度条每 240ms +20，到 100 后真实生成档案落盘 */
    startExport() {
      if (this.busy) return
      this.progress = 0
      this.timer = setInterval(() => {
        this.progress = Math.min(100, this.progress + 20)
        if (this.progress >= 100) {
          clearInterval(this.timer)
          this.timer = null
          this.finish()
        }
      }, 240)
    },

    async finish() {
      this.writing = true
      const ld = ui.loading('正在生成档案文件…', { sub: '保持应用打开，勿切后台' })
      try {
        await api.exportArchive()
        /* PDF 成长档案导出完成：播 E09 */
        play('E09')
        this.$refs.ntf.show({ type: 'ok', message: '档案已生成 · 已保存到文件' })
      } catch (e) {
        /* 失败时进度条已跑到 100，不能再显示「已完成」误导用户 */
        this.progress = null
        ui.error(e, '导出失败')
      } finally {
        ld.close()
        this.writing = false
      }
    }
  }
}
</script>

<style lang="scss" scoped>
/* 页面底：v2 奶油色；正文用圆润显示字族体系 */
.page {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  position: relative;
  z-index: 0;
  min-height: 100vh;
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
  font-family: var(--sj-font-body);
}

/* ---------- 顶栏（v2 pg-back：sticky 奶油渐隐 + 圆形返回钮） ---------- */
.pg-back {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding-left: 32rpx;
  padding-right: 32rpx;
  padding-bottom: 24rpx;
  position: sticky;
  top: 0;
  z-index: 10;
  background: linear-gradient(var(--sj-cream) 82%, transparent);
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
.bk-ic { width: 36rpx; height: 36rpx; }
.pg-title {
  flex: 1;
  font-family: var(--sj-font-display);
  font-size: 40rpx;
  font-weight: 900;
  color: var(--sj-ink);
}

/* ---------- 内容区 ---------- */
.content { padding: 0 32rpx 48rpx; }

/* 提示文案行（v2 pg-hint：cream 底 + 虚线边） */
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
.hint-gap { margin-top: 24rpx; margin-bottom: 0; }

/* 分组小标题（v2 pg-sec：前置圆角短条 + 小字） */
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

/* 章节勾选行（v2 pg-field：毛玻璃面 + 半透高光描边 + 28rpx 圆角；玻璃配方见 App.vue --sj-glass*） */
.pg-field {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: var(--sj-glass);
  border: 2rpx solid var(--sj-glass-line);
  border-radius: 28rpx;
  box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
  padding: 24rpx 28rpx;
  margin-bottom: 16rpx;
  font-size: 27rpx;
}
.c-item:active { transform: scale(0.98); }

.c-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6rpx; }
.c-title { display: flex; align-items: center; font-size: 27rpx; font-weight: 800; color: var(--sj-ink); }
/* 「可选」小徽标：未默认包含的章节 */
.c-req {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--sj-sub);
  background: var(--sj-cream);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-pill);
  padding: 2rpx 16rpx;
  margin-left: 12rpx;
}
.c-desc { font-size: 22rpx; color: var(--sj-sub); line-height: 1.6; }

/* 进度卡（v2 grow-card + sj-progress） */
.grow-card {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 28rpx 32rpx;
  margin: 24rpx 0;
  box-shadow: var(--sj-sh-sm);
}
.gc-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 16rpx;
}
.gc-title { font-size: 29rpx; font-weight: 900; color: var(--sj-ink); }
.gc-sub { font-size: 22rpx; font-weight: 700; color: var(--sj-sub); }
.pg-text { display: block; font-size: 22rpx; color: var(--sj-sub); margin-top: 12rpx; }
/* 主按钮：外观由 sj-button（block size=lg）统一提供，此处仅保留布局 */
.pg-btn {
  display: flex;
  margin-top: 40rpx;
}
</style>
