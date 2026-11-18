<template>
  <view class="page" :style="themeVars">
    <sj-bg />

    <!-- 顶栏（v2 pg-back：圆形白底返回 + display 标题 + 右侧计数） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">共享相册</text>
      <text class="pg-count">{{ filtered.length }} 项</text>
    </view>

    <!-- 类型筛选分段（全部 / 照片 / 视频） -->
    <view class="seg">
      <view
        v-for="t in tabs"
        :key="t.k"
        class="seg-item"
        :class="{ on: filter === t.k }"
        hover-class="hover-press"
        :hover-stay-time="80"
        @click="filter = t.k"
      >{{ t.label }}</view>
    </view>

    <!-- 流式网格：按日期分组，照片 / 视频混排，正方形格子，类手机相册 -->
    <view v-if="filtered.length">
      <view class="group" v-for="g in visibleGroups" :key="g.day">
        <view class="group-title">
          <text>{{ g.day }}</text>
          <text class="group-count">{{ g.total }} 项</text>
        </view>
        <view class="grid">
          <view
            class="cell"
            v-for="m in g.items"
            :key="m.id"
            hover-class="cell-hover"
            :hover-stay-time="80"
            @click="openPreview(m)"
          >
            <!-- 照片：缩略图铺满；视频：封面图或占位兜底，点击进全屏预览 -->
            <image v-if="m.type === 'image'" class="cell-img" :src="m.thumb" mode="aspectFill" lazy-load />
            <sj-video-cover
              v-else
              class="cell-video"
              :thumb="m.thumb"
            />

            <!-- 视频：暗化遮罩 + 中央播放键 + 右下角时长角标 -->
            <template v-if="m.type === 'video'">
              <view class="cell-mask" />
              <view class="cell-play"><view class="tri" /></view>
              <text v-if="m.duration" class="cell-dur">{{ fmtDur(m.duration) }}</text>
            </template>
          </view>
        </view>
      </view>
    </view>

    <!-- 空态 -->
    <sj-empty
      v-if="loaded && !filtered.length"
      icon="04-photo"
      text="相册还没有内容"
      sub="家人记录的照片和视频会汇总在这里"
    />

    <sj-ui-host />

    <!-- 全屏媒体预览（图片 / 视频共用，左右滑动切换） -->
    <sj-media-preview v-model:show="previewShow" :items="previewItems" :current="previewCurrent" />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'

/* 类型分段：all 全部 / image 照片 / video 视频 */
const TABS = [
  { k: 'all', label: '全部' },
  { k: 'image', label: '照片' },
  { k: 'video', label: '视频' }
]

/* 分批渲染：首屏与每次触底追加的格子数；避免一次性创建全部日期组与图片节点 */
const ITEM_PAGE_SIZE = 30

export default {
  data() {
    return {
      tabs: TABS,
      filter: 'all',
      /* 全量相册媒体（照片 + 视频，时间倒序），形状见 api.getFamilyAlbum */
      all: [],
      /* 已渲染的格子数上限；触底按 ITEM_PAGE_SIZE 追加 */
      visibleItemCount: ITEM_PAGE_SIZE,
      loaded: false,
      statusBarHeight: 20,
      /* 全屏媒体预览 */
      previewShow: false,
      previewItems: [],
      previewCurrent: 0
    }
  },

  computed: {
    filtered() {
      if (this.filter === 'all') return this.all
      return this.all.filter(m => m.type === this.filter)
    },
    /* 按日期分组（同一天一组，保持时间倒序）；分组标题 + 网格 */
    grouped() {
      const map = {}
      const order = []
      this.filtered.forEach(m => {
        const k = m.day || '未知日期'
        if (!map[k]) { map[k] = []; order.push(k) }
        map[k].push(m)
      })
      return order.map(k => ({ day: k, items: map[k], total: map[k].length }))
    },
    /* 分批可见分组：按格子累计截断到 visibleItemCount；跨组切分时本组只取余量，标题计数保留全量 */
    visibleGroups() {
      const limit = this.visibleItemCount
      let acc = 0
      const out = []
      for (const g of this.grouped) {
        if (acc >= limit) break
        const room = limit - acc
        out.push({ day: g.day, total: g.total, items: g.items.slice(0, room) })
        acc += g.items.length
      }
      return out
    }
  },

  watch: {
    /* 切换类型筛选：分组口径变化，回到首屏批次 */
    filter() {
      this.visibleItemCount = ITEM_PAGE_SIZE
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  onShow() {
    this.load()
  },

  /* 触底追加下一批格子；全量已渲染完时上限不再增长 */
  onReachBottom() {
    if (this.visibleItemCount < this.filtered.length) {
      this.visibleItemCount += ITEM_PAGE_SIZE
    }
  },

  /* 下拉刷新：强制重拉全家快照后重渲染 */
  onPullDownRefresh() {
    api.bootstrap({ force: true })
      .then(() => this.load())
      .catch(() => { /* 弱网保留本地缓存 */ })
      .then(() => uni.stopPullDownRefresh())
  },

  /* 预览打开时，物理返回键 / 系统返回手势先关预览，不退出页面 */
  onBackPress() {
    if (this.previewShow) {
      this.previewShow = false
      return true
    }
  },

  methods: {
    load() {
      this.all = api.getFamilyAlbum()
      this.visibleItemCount = ITEM_PAGE_SIZE
      this.loaded = true
    },

    /* 点击格子：打开全屏预览，items 为当前筛选后的全量媒体，定位到点击项 */
    openPreview(m) {
      const list = this.filtered
      if (!list.length) return
      this.previewItems = list.map(x => x.type === 'video'
        ? { type: 'video', url: x.url, thumb: x.thumb }
        : { type: 'image', url: x.url })
      this.previewCurrent = Math.max(0, list.indexOf(m))
      this.previewShow = true
    },

    /* 视频时长 → mm:ss（超 1 小时 h:mm:ss） */
    fmtDur(s) {
      const total = Math.max(0, Math.round(Number(s) || 0))
      const h = Math.floor(total / 3600)
      const m = Math.floor((total % 3600) / 60)
      const sec = total % 60
      const mm = String(m).padStart(2, '0')
      const ss = String(sec).padStart(2, '0')
      return h > 0 ? h + ':' + mm + ':' + ss : mm + ':' + ss
    },

    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/family/family' })
      }
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
  background: transparent;
  font-family: var(--sj-font-body);
}

/* ---------- 顶栏（v2 pg-back） ---------- */
.pg-back {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding-left: 32rpx;
  padding-right: 32rpx;
  padding-bottom: 20rpx;
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
.bk-ic { width: 40rpx; height: 40rpx; }
.pg-title {
  flex: 1;
  font-family: var(--sj-font-display);
  font-size: 40rpx;
  font-weight: 900;
  color: var(--sj-ink);
}
.pg-count {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  border-radius: var(--sj-r-pill);
  padding: 8rpx 20rpx;
}

/* ---------- 类型分段 ---------- */
.seg {
  display: flex;
  gap: 16rpx;
  padding: 0 32rpx 24rpx;
}
.seg-item {
  padding: 10rpx 28rpx;
  border-radius: var(--sj-r-pill);
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  font-size: 24rpx;
  font-weight: 700;
  color: var(--sj-sub);
}
.seg-item.on {
  background: var(--sj-primary);
  border-color: var(--sj-primary);
  color: #fff;
}

/* ---------- 按日期分组 ---------- */
.group { padding: 0 32rpx 24rpx; }
.group-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 16rpx 4rpx 16rpx;
}
.group-title > text:first-child {
  font-family: var(--sj-font-display);
  font-size: 28rpx;
  font-weight: 800;
  color: var(--sj-ink);
}
.group-count {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--sj-sub);
}

/* ---------- 流式网格（3 列正方形） ---------- */
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
}
.cell {
  position: relative;
  width: 100%;
  height: 220rpx;
  border-radius: 20rpx;
  overflow: hidden;
  background: var(--sj-cream);
  border: 4rpx solid #fff;
  box-shadow: var(--sj-sh-sm);
  box-sizing: border-box;
}
.cell-hover { transform: scale(0.96); }
.cell-img { width: 100%; height: 100%; }
.cell-video { width: 100%; height: 100%; background: var(--sj-cream); }

/* 视频遮罩 + 播放键 + 时长 */
.cell-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.32);
}
.cell-play {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 0;
  height: 0;
  transform: translate(-50%, -50%);
}
.tri {
  width: 0;
  height: 0;
  border-left: 18rpx solid #fff;
  border-top: 11rpx solid transparent;
  border-bottom: 11rpx solid transparent;
  margin-left: 5rpx;
}
.cell-dur {
  position: absolute;
  right: 10rpx;
  bottom: 8rpx;
  padding: 2rpx 12rpx;
  border-radius: 10rpx;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 19rpx;
  font-weight: 700;
}
</style>
