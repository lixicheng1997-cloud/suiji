<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back）：圆形返回按钮 + 标题 + 三点更多（自定义导航，padding-top 让出状态栏） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">记录详情</text>
      <!-- 三点「更多」：ctl-v2 60 去底切图（举三点指示牌小熊） -->
      <view class="bk-act" hover-class="hover-press" :hover-stay-time="80" @click="onMore">
        <!-- <image class="bk-act-ic" :src="'/static/icons/ctl/' + __theme + '/56/60-ctl-nav-more.png'" mode="aspectFit" /> -->
      </view>
    </view>

    <view class="detail-wrap" v-if="entry">
      <!-- 详情头区（v2 grow-card 居中卡）：浅底按类型 tint + 居中图标 + 标题 + 副行 + 徽标 -->
      <view class="grow-card" :style="{ background: TYPES[entry.type].tint }">
        <sj-icon :name="TYPES[entry.type].png" :size="116" />
        <text class="gc-title">{{ entry.title }}</text>
        <text class="gc-sub">{{ entry.time }} · {{ TYPES[entry.type].label }} · {{ whoOf(entry) }}记录</text>
        <!-- 徽标（补记 / 里程碑 / 进行中 / 百分位）：ms-badge 金色胶囊 -->
        <text v-if="entry.badge" class="ms-badge">{{ BADGES[entry.badge] }}</text>
      </view>

      <!-- 语音回放（类型=voice）：段间自动衔接，段边界在波形上画分隔 -->
      <view v-if="entry.type === 'voice'" class="detail-voice">
        <sj-voice-play
          :segments="voice.segments"
          :url="voice.url"
          :duration="voice.duration"
          :wave="voice.wave"
        />
      </view>

      <!-- 照片（如有）：多张横向滚动查看，点击全屏预览 -->
      <scroll-view v-if="photoList.length" class="detail-photos" scroll-x :show-scrollbar="false">
        <view class="dp-track">
          <image
            v-for="(p, i) in photoList"
            :key="i"
            class="detail-photo"
            :src="p"
            mode="aspectFill"
            @click="openPhotoPreview(i)"
          />
        </view>
      </scroll-view>
      <view v-if="photoList.length > 1" class="dp-hint"><text>{{ photoList.length }} 张照片 · 左右滑动查看</text></view>

      <!-- 视频（如有）：单一大封面 —— 显示当前段首帧，点击全屏播放；多段有切换按钮 -->
      <view v-if="videoList.length" class="detail-videos">
        <!-- 播放态 -->
        <view v-if="playing" class="dp-video-wrap">
          <video
            class="dp-video"
            :src="videoList[currentIdx].url"
            :poster="videoList[currentIdx].thumb"
            :controls="true"
            :autoplay="true"
            :show-center-play-btn="true"
            :enable-progress-gesture="true"
            :object-fit="'cover'"
          />
          <view class="dp-video-collapse" @click="playing = false"><text>收起</text></view>
        </view>
        <!-- 封面态：当前段首帧 + 中央播放钮 + 明显切换按钮 -->
        <view v-else class="dp-video-wrap" hover-class="hover-press" @click="openVideoPreview">
          <video
            class="dp-video"
            :src="videoList[currentIdx].url"
            :poster="videoList[currentIdx].thumb"
            :controls="false"
            :autoplay="false"
            :show-center-play-btn="false"
            :show-play-btn="false"
            :object-fit="'cover'"
          />
          <view class="dp-video-mask" />
          <view class="dp-video-play">
            <view class="dp-tri" />
          </view>
          <text v-if="videoList.length > 1" class="dp-video-num">{{ currentIdx + 1 }} / {{ videoList.length }}</text>
        </view>
        <!-- 多段：底部明显切换行 -->
        <view v-if="videoList.length > 1 && !playing" class="dp-switch-bar">
          <view class="dp-switch-btn" hover-class="hover-press" :class="{ off: currentIdx === 0 }" @click.stop="prevVideo">
            <text class="dp-switch-arrow">‹</text>
            <text class="dp-switch-text">上一段</text>
          </view>
          <view class="dp-switch-btn" hover-class="hover-press" :class="{ off: currentIdx === videoList.length - 1 }" @click.stop="nextVideo">
            <text class="dp-switch-text">下一段</text>
            <text class="dp-switch-arrow">›</text>
          </view>
        </view>
      </view>

      <!-- 备注引用块（如有）：cream 底 + 虚线描边圆角块 -->
      <view v-if="entry.note" class="detail-note"><text>{{ entry.note }}</text></view>

      <!-- 信息卡（v2 pg-field 行式）：白底线边圆角，label 粗灰 / val 特粗墨色 -->
      <view class="pg-field">
        <text class="pf-label">记录时间</text>
        <text class="pf-val">{{ day }} {{ entry.time }}</text>
      </view>
      <view class="pg-field">
        <text class="pf-label">记录人</text>
        <text class="pf-val">{{ whoOf(entry) }}</text>
      </view>

      <!-- 操作区（v2）：一行两个 ghost 按钮 + 通栏 danger 删除 + pg-hint 留痕说明。
           两角色模型：非创建者仅本人记录可操作，他人记录不显示入口（服务端 403 兜底） -->
      <view v-if="canEdit" class="act-row">
        <sj-button
          class="pg-btn"
          variant="ghost"
          block
          size="lg"
          text="编辑"
          @click="onEdit"
        />
      </view>
      <sj-button
        v-if="canEdit"
        class="pg-btn pg-del"
        variant="danger"
        block
        size="lg"
        text="删除记录"
        @click="onDelete"
      />
      <view v-if="canEdit" class="pg-hint"><text>删除后进入回收站，30 天内可恢复 · 操作会被记录</text></view>
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />

    <!-- 全屏媒体预览（图片/视频共用） -->
    <sj-media-preview v-model:show="previewShow" :items="previewItems" :current="previewCurrent" />
  </view>
</template>

<script>
import { TYPES, BADGES } from '@/utils/mock.js'
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import { play } from '@/utils/sound.js'

export default {
  data() {
    return {
      TYPES,
      BADGES,
      entry: null,
      day: '',
      entryId: '',
      statusBarHeight: 20,
      /* 视频：currentIdx 指向当前段；playing=true 时展开成内联播放 */
      playing: false,
      currentIdx: 0,
      /* 全屏媒体预览 */
      previewShow: false,
      previewItems: [],
      previewCurrent: 0
    }
  },

  computed: {
    /**
     * 照片列表归一：优先 entry.photos（多张），回退 entry.photo（单张）。
     * video 类型的 entry.photo 是视频封面地址（不是图片），不能塞进 <image>，跳过。
     */
    photoList() {
      const e = this.entry
      if (!e) return []
      if (e.type === 'video') return []
      if (Array.isArray(e.photos) && e.photos.length) return e.photos
      return e.photo ? [e.photo] : []
    },

    /** 当前用户能否改/删本条记录：创建者任意，成员仅本人记录 */
    canEdit() {
      return api.canEditEntry(this.entry)
    },

    /**
     * 视频列表：从 payload.videos 取（saveEntry 上传后落库的形状），
     * URL 已经在 toViewItem/fetchEntry 里 resolveUrl 过带 token。
     */
    videoList() {
      const e = this.entry
      if (!e) return []
      const list = (e.payload && Array.isArray(e.payload.videos)) ? e.payload.videos : []
      return list
        .map(v => v && v.url ? {
          url: v.url,
          duration: Number(v.duration) || 0,
          thumb: v.thumb || ''
        } : null)
        .filter(Boolean)
    },

    /**
     * 语音字段归一：新数据平铺在 payload 上，历史/mock 可能嵌一层 payload.voice，
     * 也可能只有单段 url。统一成 { segments, url, duration, wave } 给回放条。
     */
    voice() {
      const raw = (this.entry && this.entry.payload) || {}
      const p = raw.voice || raw
      return {
        segments: Array.isArray(p.segments) ? p.segments : [],
        url: p.url || '',
        duration: Number(p.duration) || 0,
        wave: Array.isArray(p.wave) ? p.wave : []
      }
    }
  },

  async onLoad(query) {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }

    if (query && query.id) {
      this.entryId = query.id
      try {
        const e = await api.fetchEntry(query.id)
        if (e) {
          this.entry = e
          this.day = e.day || ''
        }
      } catch (err) { /* 按不存在处理 */ }
    }
    if (!this.entry) {
      /* onLoad 期间 ref 未就绪：nextTick 等首渲染后再弹横幅 */
      this.$nextTick(() => this.$refs.ntf.show({ type: 'err', message: '记录不存在' }))
      setTimeout(() => this.goBack(), 800)
    }
  },

  onShow() {
    /* 编辑页保存后 navigateBack 回本页不会重跑 onLoad：按 id 重取缓存，避免详情停留在旧数据 */
    if (!this.entryId || !this.entry) return
    api.fetchEntry(this.entryId).then(e => {
      if (e) {
        this.entry = e
        this.day = e.day || ''
      }
    }).catch(() => { /* 保留当前展示 */ })
  },

  methods: {
    /* 记录人展示：与宝宝关系 + 昵称（与主页列表同口径，不展示登录账号）；按 creator_id 解析成员 */
    whoOf(e) {
      return api.creatorLabel(e)
    },
    goBack() {
      if (getCurrentPages().length > 1) uni.navigateBack()
      else uni.reLaunch({ url: '/pages/index/index' })
    },
    openPhotoPreview(i) {
      this.previewItems = this.photoList.map(u => ({ type: 'image', url: u }))
      this.previewCurrent = i || 0
      this.previewShow = true
    },
    openVideoPreview() {
      this.previewItems = this.videoList.map(v => ({ type: 'video', url: v.url, thumb: v.thumb }))
      this.previewCurrent = this.currentIdx
      this.previewShow = true
    },
    prevVideo() {
      if (!this.videoList.length || this.currentIdx === 0) return
      this.currentIdx--
    },
    nextVideo() {
      if (!this.videoList.length || this.currentIdx >= this.videoList.length - 1) return
      this.currentIdx++
    },
    formatDur(s) {
      s = Math.max(0, Math.round(Number(s) || 0))
      const m = Math.floor(s / 60)
      const r = s % 60
      return m ? m + ':' + (r < 10 ? '0' : '') + r : r + ' 秒'
    },
    onMore() {
      ui.showActionSheet({
        itemList: ['导出此记录', '举报'],
        success: res => {
          if (res.tapIndex === 0) {
            const e = this.entry
            const data = [
              '时间：' + (this.day ? this.day + ' ' : '') + e.time,
              '类型：' + (TYPES[e.type] ? TYPES[e.type].label : e.type),
              '标题：' + e.title,
              '备注：' + (e.note || '无'),
              '记录人：' + api.creatorLabel(e)
            ].join('\n')
            uni.setClipboardData({ data })
            this.$refs.ntf.show({ type: 'ok', message: '已复制到剪贴板' })
          } else {
            this.$refs.ntf.show({ type: 'warn', message: '举报需接入后端（开发中）' })
          }
        }
      }).catch(() => {})
    },
    onEdit() {
      uni.navigateTo({ url: '/pages/editor/editor?type=' + this.entry.type + '&id=' + this.entry.id })
    },
    onShare() {
      this.$refs.ntf.show({ type: 'warn', message: '分享到家庭动态需接入后端（开发中）' })
    },
    onDelete() {
      play('S08') // 删除记录危险确认弹出音效
      ui.showModal({
        title: '删除记录',
        content: '确定删除这条记录吗？删除后进入回收站，保留 30 天。',
        danger: true,
        success: res => {
          if (!res.confirm) return
          api.deleteEntry(this.entry.id)
            .then(() => {
              this.$refs.ntf.show({ type: 'ok', message: '已删除 · 进入回收站' })
              setTimeout(() => this.goBack(), 600)
            })
            .catch(e => {
              ui.error(e, '删除失败')
            })
        }
      })
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
.bk-act {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  padding: 16rpx;
  flex: none;
}
.bk-act:active { transform: scale(0.9); }
.bk-act-ic { width: 56rpx; height: 56rpx; }

/* ---------- 详情内容区 ---------- */
.detail-wrap { padding: 8rpx 32rpx 48rpx; }

/* 详情头区：类型浅底居中卡 */
.grow-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 36rpx 32rpx;
  margin-bottom: 24rpx;
  box-shadow: var(--sj-sh-sm);
}
.gc-title {
  font-family: var(--sj-font-display);
  font-size: 32rpx;
  font-weight: 900;
  color: var(--sj-ink);
  margin-top: 12rpx;
}
.gc-sub { font-size: 24rpx; color: var(--sj-sub); margin-top: 8rpx; }
/* 徽标：金色胶囊（与首页 ms-badge 同款观感） */
.ms-badge {
  font-size: 21rpx;
  font-weight: 800;
  color: #B47714;
  background: var(--sj-surface);
  border-radius: var(--sj-r-pill);
  padding: 8rpx 20rpx;
  box-shadow: var(--sj-sh-sm);
  margin-top: 16rpx;
}

/* 照片：横向滚动查看，点击全屏预览 */
.detail-photos {
  width: 100%;
  margin-bottom: 28rpx;
  white-space: nowrap;
}
.dp-track {
  display: inline-flex;
  gap: 20rpx;
  padding: 4rpx 0 12rpx;
}
.detail-photo {
  /* 与其他组件同宽：detail-wrap 左右各 32rpx 内边距后的内容宽 */
  width: 686rpx;
  height: 480rpx;
  box-sizing: border-box;
  flex: none;
  border-radius: 32rpx;
  border: 6rpx solid #fff;
  box-shadow: var(--sj-sh-md);
}
.dp-hint {
  font-size: 23rpx;
  color: var(--sj-sub);
  text-align: center;
  margin: -16rpx 0 28rpx;
}

/* 视频：折叠式 —— 默认封面横滑，点击展开播放 */
.detail-videos { margin-bottom: 28rpx; }
.dp-video-wrap {
  position: relative;
  width: 686rpx;
  height: 480rpx;
  border-radius: 32rpx;
  overflow: hidden;
  margin-bottom: 20rpx;
  background: #000;
}
.dp-video { width: 100%; height: 100%; display: block; }
.dp-video-bg { width: 100%; height: 100%; }
.dp-video-bg-ph {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #5FB0A8, #3F8F84);
  color: #fff;
}
.dp-video-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.25);
}
.dp-video-play {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 0;
  height: 0;
  transform: translate(-50%, -50%);
}
.dp-tri {
  width: 0;
  height: 0;
  border-left: 36rpx solid #fff;
  border-top: 24rpx solid transparent;
  border-bottom: 24rpx solid transparent;
  margin-left: 8rpx;
  filter: drop-shadow(0 4rpx 8rpx rgba(0, 0, 0, 0.4));
}
.dp-video-collapse {
  position: absolute;
  right: 16rpx;
  top: 16rpx;
  padding: 6rpx 20rpx;
  border-radius: 24rpx;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 22rpx;
  font-weight: 700;
  z-index: 2;
}
/* 多段提示：右下角胶囊 */
.dp-video-count {
  position: absolute;
  right: 16rpx;
  bottom: 16rpx;
  padding: 4rpx 16rpx;
  border-radius: 20rpx;
  background: rgba(0, 0, 0, 0.65);
  color: #fff;
  font-size: 22rpx;
  font-weight: 700;
}
/* 段数数字：左上角白色粗字 */
.dp-video-num {
  position: absolute;
  left: 20rpx;
  top: 16rpx;
  padding: 4rpx 16rpx;
  border-radius: 20rpx;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 24rpx;
  font-weight: 800;
  z-index: 2;
}
/* 切换按钮行：封面下方左右两个实色胶囊 */
.dp-switch-bar {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
  margin-top: 16rpx;
}
.dp-switch-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  height: 72rpx;
  border-radius: 36rpx;
  background: var(--sj-primary, #FF6B8B);
  color: #fff;
  font-size: 26rpx;
  font-weight: 700;
  box-shadow: var(--sj-sh-sm);
}
.dp-switch-btn.off {
  background: var(--sj-line, #E8E0DA);
  color: var(--sj-sub, #999);
  box-shadow: none;
}
.dp-switch-arrow {
  font-size: 32rpx;
  font-weight: 800;
  line-height: 1;
}
.dp-switch-text { font-size: 26rpx; font-weight: 700; }

/* 语音回放条：与下方描述/照片拉开间距（与页面其他块 28rpx 节奏一致） */
.detail-voice { margin-bottom: 28rpx; }

/* 备注引用块 */
.detail-note {
  background: var(--sj-cream);
  border: 2rpx dashed var(--sj-line);
  border-radius: var(--sj-r-sm);
  padding: 24rpx 28rpx;
  font-size: 26rpx;
  line-height: 1.7;
  color: var(--sj-ink);
  margin-bottom: 28rpx;
}

/* 信息卡：pg-field 行式（毛玻璃面；玻璃配方见 App.vue --sj-glass*） */
.pg-field {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: var(--sj-glass);
  border: 2rpx solid var(--sj-glass-line);
  border-radius: 28rpx;
  box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
  padding: 20rpx 28rpx;
  margin-bottom: 20rpx;
}
.pf-label {
  color: var(--sj-sub);
  font-weight: 700;
  font-size: 27rpx;
  flex: none;
  width: 148rpx;
}
.pf-val {
  flex: 1;
  color: var(--sj-ink);
  font-weight: 800;
  font-size: 27rpx;
}

/* 操作区 */
.act-row { display: flex; gap: 20rpx; margin-top: 8rpx; }
/* 主按钮：外观由 sj-button（block size=lg）统一提供，此处仅保留布局 */
.pg-btn {
  display: flex;
  flex: 1;
}
/* 删除按钮与上方操作行的间距（原 .pg-btn.danger 上的 margin-top） */
.pg-del { margin-top: 20rpx; }

/* 底部留痕提示 */
.pg-hint {
  font-size: 23rpx;
  color: var(--sj-sub);
  background: var(--sj-cream);
  border: 2rpx dashed var(--sj-line);
  border-radius: 24rpx;
  padding: 16rpx 24rpx;
  margin-top: 24rpx;
  line-height: 1.5;
}
</style>
