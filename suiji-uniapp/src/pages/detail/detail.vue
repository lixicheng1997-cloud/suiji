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
            @click="previewPhoto(i)"
          />
        </view>
      </scroll-view>
      <view v-if="photoList.length > 1" class="dp-hint"><text>{{ photoList.length }} 张照片 · 左右滑动查看</text></view>

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

      <!-- 操作区（v2）：一行两个 ghost 按钮 + 通栏 danger 删除 + pg-hint 留痕说明 -->
      <view class="act-row">
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
        class="pg-btn pg-del"
        variant="danger"
        block
        size="lg"
        text="删除记录"
        @click="onDelete"
      />
      <view class="pg-hint"><text>删除后进入回收站，30 天内可恢复 · 操作会被记录</text></view>
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
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
      statusBarHeight: 20
    }
  },

  computed: {
    /**
     * 照片列表归一：优先 entry.photos（多张），回退 entry.photo（单张）。
     */
    photoList() {
      const e = this.entry
      if (!e) return []
      if (Array.isArray(e.photos) && e.photos.length) return e.photos
      return e.photo ? [e.photo] : []
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
    previewPhoto(index) {
      uni.previewImage({ urls: this.photoList, current: index })
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
