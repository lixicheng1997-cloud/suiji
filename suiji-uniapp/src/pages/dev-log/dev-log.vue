<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回 + 标题 + 右侧复制 / 清空文字钮） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">调试日志</text>
      <text class="bk-act" hover-class="hover-press" :hover-stay-time="80" @click="copyAll">复制</text>
      <text v-if="allLogs.length" class="bk-act danger" hover-class="hover-press" :hover-stay-time="80" @click="clearAll">清空</text>
    </view>

    <view class="content">
      <!-- 环境提示：数据只存终端本地，不上报；展示条数与本机占用大小 -->
      <view class="pg-hint">当前环境：{{ envLabel }} · 网络：{{ netText }} · 共 {{ allLogs.length }} 条 · 日志大小 {{ sizeText }}</view>

      <!-- 关键词搜索：本地匹配消息 / 模块标签 -->
      <view class="log-search">
        <sj-input
          :modelValue="keyword"
          variant="box"
          placeholder="搜索消息 / 模块关键词"
          clearable
          :maxlength="30"
          @update:modelValue="onKeyword"
          @confirm="refresh"
          @clear="onKeyword('')"
        />
      </view>

      <!-- 级别筛选（全部 / DEBUG / INFO / WARN / ERROR，带各级条数） -->
      <scroll-view scroll-x class="lv-scroll" :show-scrollbar="false">
        <view class="lv-row">
          <view
            v-for="t in levelTabs"
            :key="t.key"
            class="lv-chip"
            :class="{ on: levelFilter === t.key }"
            hover-class="hover-press"
            :hover-stay-time="80"
            @click="onLevel(t.key)"
          >
            <text>{{ t.label }}</text>
            <text class="lv-count">{{ t.count }}</text>
          </view>
        </view>
      </scroll-view>

      <!-- 模块标签筛选（出现过的 tag；无标签时不展示） -->
      <scroll-view v-if="tagList.length" scroll-x class="lv-scroll" :show-scrollbar="false">
        <view class="lv-row">
          <view
            class="tg-chip"
            :class="{ on: tagFilter === 'all' }"
            hover-class="hover-press"
            :hover-stay-time="80"
            @click="onTag('all')"
          >全部模块</view>
          <view
            v-for="t in tagList"
            :key="t"
            class="tg-chip"
            :class="{ on: tagFilter === t }"
            hover-class="hover-press"
            :hover-stay-time="80"
            @click="onTag(t)"
          >{{ t }}</view>
        </view>
      </scroll-view>

      <!-- 空态 -->
      <sj-empty
        v-if="!allLogs.length"
        icon="24-fn-search"
        text="暂无日志"
        sub="操作 App 后，调试信息会按级别记录在这里"
      />

      <!-- 日志列表（时间正序：旧 → 新；分页切片，触底加载下一页；点击弹详情） -->
      <view v-else>
        <view class="log-card" v-for="item in logs" :key="item.id" hover-class="hover-press" :hover-stay-time="80" @click="openDetail(item)">
          <view class="lc-main">
            <text class="lc-dot" :class="'lv-' + item.level" />
            <text class="lc-time">{{ item.time }}</text>
            <text class="lc-tag">{{ item.tag }}</text>
            <text class="lc-msg">{{ item.msg }}</text>
            <text class="lc-level" :class="'lv-' + item.level">{{ levelLabel(item.level) }}</text>
          </view>
        </view>

        <!-- 触底分页状态：还有更多 → 提示上拉；全部加载完 → 到底 -->
        <view class="scroll-end">
          <text>{{ loadingMore ? '正在加载更多…' : hasMore ? '上拉加载更多' : '· 已经到底啦 ·' }}</text>
        </view>
      </view>
    </view>

    <!-- 日志详情（居中 modal：日期时间 / 平台 / 级别 / 模块 / 消息 / 结构化数据） -->
    <sj-modal v-model:show="detailShow" title="日志详情" confirmText="关闭">
      <scroll-view v-if="current" scroll-y class="dm-scroll">
        <view class="dm-row">
          <text class="dm-k">时间</text>
          <text class="dm-v">{{ detailTime }}</text>
        </view>
        <view class="dm-row">
          <text class="dm-k">平台</text>
          <text class="dm-v">{{ current.platform || 'unknown' }}</text>
        </view>
        <view class="dm-row">
          <text class="dm-k">级别</text>
          <text class="dm-v" :class="'lv-' + current.level">{{ levelLabel(current.level) }}</text>
        </view>
        <view class="dm-row">
          <text class="dm-k">模块</text>
          <text class="dm-v">{{ current.tag }}</text>
        </view>
        <view class="dm-msg">{{ current.msg }}</view>
        <view v-if="detailData" class="dm-data">{{ detailData }}</view>
        <view class="dm-copy" hover-class="hover-press" :hover-stay-time="80" @click="copyOne">复制本条</view>
      </scroll-view>
    </sj-modal>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import logger, { LEVEL_LABEL, LEVEL_ORDER } from '@/utils/logger.js'
import { netLabel } from '@/infra/net.js'
import * as ui from '@/utils/ui.js'

export default {
  data() {
    return {
      statusBarHeight: 20,
      levelFilter: 'all',
      tagFilter: 'all',
      /* 关键词搜索（匹配消息 / 模块标签） */
      keyword: '',
      /* 当前筛选下的全量日志；logs 为分页切片后的可见部分 */
      allLogs: [],
      logs: [],
      counts: { debug: 0, info: 0, warn: 0, error: 0 },
      tagList: [],
      /* 分页 */
      pageSize: 30,
      visibleCount: 30,
      loadingMore: false,
      hasMore: false,
      /* 本机日志大小（字节） */
      sizeBytes: 0,
      /* 当前网络快照标签（WiFi / 4g / 5g / 无网络 / unknown） */
      netText: 'unknown',
      /* 详情弹窗 */
      detailShow: false,
      current: null
    }
  },

  computed: {
    levelTabs() {
      const tabs = [{ key: 'all', label: '全部', count: this.allLogs.length }]
      LEVEL_ORDER.forEach(k => tabs.push({ key: k, label: LEVEL_LABEL[k], count: this.counts[k] || 0 }))
      return tabs
    },
    envLabel() { return logger.appEnv === 'dev' ? '开发' : '正式' },
    sizeText() {
      const b = this.sizeBytes
      if (b < 1024) return b + ' B'
      return (b / 1024).toFixed(1) + ' KB'
    },
    /* 详情完整日期时间（旧条目缺 date 时回退仅时间） */
    detailTime() {
      const x = this.current
      if (!x) return ''
      return x.date ? x.date + ' ' + x.time : x.time
    },
    /* 详情结构化数据：可解析 JSON 缩进美化，失败原样 */
    detailData() {
      return this.current ? logger.formatData(this.current.data) : ''
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
    this.safeRefresh()
  },

  onShow() { this.safeRefresh() },

  /* 触底加载下一页（触底距离见 pages.json onReachBottomDistance） */
  onReachBottom() { this.loadMore() },

  methods: {
    levelLabel(lv) { return LEVEL_LABEL[lv] || lv },

    /* 刷新包异常保护：即便本机日志读取异常，页面仍能打开空态，不致白屏卡住 */
    safeRefresh() {
      try { this.refresh() } catch (e) { logger.error('dev-log', '日志页刷新异常', e) }
    },

    refresh() {
      const tag = this.tagFilter === 'all' ? '' : this.tagFilter
      const q = this.keyword.trim()
      this.allLogs = logger.getLogs({
        level: this.levelFilter === 'all' ? '' : this.levelFilter,
        tag, q
      })
      /* 级别角标按当前模块 / 关键词口径统计；不再叠加当前选中级别，避免其余级别计数归零 */
      this.counts = logger.counts({ tag, q })
      this.tagList = logger.tags()
      this.sizeBytes = logger.sizeBytes()
      this.netText = netLabel()
      this.visibleCount = this.pageSize
      this.applySlice()
    },

    /* 按当前可见条数切片；本地内存数据，同步追加即可 */
    applySlice() {
      this.logs = this.allLogs.slice(0, this.visibleCount)
      this.hasMore = this.visibleCount < this.allLogs.length
    },

    loadMore() {
      if (this.loadingMore || !this.hasMore) return
      this.loadingMore = true
      /* 本地切片无网络耗时，下一帧再放开，让「正在加载更多」态有机会呈现 */
      setTimeout(() => {
        this.visibleCount += this.pageSize
        this.applySlice()
        this.loadingMore = false
      }, 120)
    },

    onLevel(key) { this.levelFilter = key; this.refresh() },
    onTag(tag) { this.tagFilter = tag; this.refresh() },
    onKeyword(v) { this.keyword = v || ''; this.refresh() },

    openDetail(item) {
      this.current = item
      this.detailShow = true
    },

    copyOne() {
      if (!this.current) return
      uni.setClipboardData({
        data: logger.exportLogs([this.current]),
        success: () => this.$refs.ntf.show({ type: 'ok', message: '已复制本条日志' })
      })
    },

    goBack() {
      if (getCurrentPages().length > 1) uni.navigateBack()
      else uni.reLaunch({ url: '/pages/me/me' })
    },

    clearAll() {
      ui.confirm({
        title: '清空调试日志',
        content: '将删除本机留存的全部日志记录，且不可恢复，确定清空吗？',
        confirmText: '清空',
        danger: true
      }).then(r => {
        if (!r.confirm) return
        logger.clear()
        this.current = null
        this.refresh()
        this.$refs.ntf.show({ type: 'ok', message: '日志已清空' })
      })
    },

    copyAll() {
      if (!this.allLogs.length) { this.$refs.ntf.show({ type: 'warn', message: '当前没有可复制的日志' }); return }
      const text = logger.exportLogs(this.allLogs)
      uni.setClipboardData({
        data: text,
        success: () => this.$refs.ntf.show({ type: 'ok', message: '已复制 ' + this.allLogs.length + ' 条日志' })
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.page {
  position: relative;
  z-index: 0;
  min-height: 100vh;
  background: transparent;
}
.content {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
  padding: 0 32rpx 52rpx;
  box-sizing: border-box;
}

/* ---------- 顶栏（对齐 v2 pg-back） ---------- */
.pg-back {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 8rpx 32rpx 20rpx;
}
.bk {
  width: 64rpx;
  height: 64rpx;
  border-radius: var(--sj-r-pill);
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.bk-ic { width: 34rpx; height: 34rpx; }
.pg-title { flex: 1; min-width: 0; font-size: 34rpx; font-weight: 900; color: var(--sj-ink); }
.bk-act {
  flex: none;
  font-size: 25rpx;
  font-weight: 700;
  color: var(--sj-primary-deep);
  padding: 10rpx 20rpx;
}
.bk-act.danger { color: var(--sj-bad); }

/* ---------- 提示条（v2 pg-hint） ---------- */
.pg-hint {
  font-size: 22rpx;
  color: var(--sj-sub);
  background: var(--sj-cream);
  border: 2rpx dashed var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 18rpx 24rpx;
  line-height: 1.5;
}

/* ---------- 关键词搜索 ---------- */
.log-search { width: 100%; }

/* ---------- 筛选胶囊 ---------- */
.lv-scroll { white-space: nowrap; }
.lv-row { display: inline-flex; gap: 16rpx; padding: 4rpx 0; }
.lv-chip, .tg-chip {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-pill);
  padding: 8rpx 18rpx;
  font-size: 21rpx;
  font-weight: 700;
  color: var(--sj-sub);
}
.lv-chip.on, .tg-chip.on {
  background: var(--sj-primary-soft);
  border-color: var(--sj-primary);
  color: var(--sj-primary-deep);
}
.lv-count { font-size: 19rpx; font-weight: 800; opacity: 0.7; }

/* ---------- 日志卡片 ---------- */
.log-card {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 22rpx 24rpx;
  box-shadow: var(--sj-sh-sm);
  margin-bottom: 20rpx;
}
.lc-main {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
}
.lc-dot { width: 16rpx; height: 16rpx; border-radius: 50%; margin-top: 10rpx; flex: none; }
.lc-time { flex: none; font-size: 21rpx; color: var(--sj-faint); font-variant-numeric: tabular-nums; margin-top: 4rpx; }
.lc-tag {
  flex: none;
  font-size: 21rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  border-radius: var(--sj-r-sm);
  padding: 4rpx 12rpx;
  margin-top: 2rpx;
  max-width: 180rpx;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.lc-msg { flex: 1; min-width: 0; font-size: 26rpx; font-weight: 600; color: var(--sj-ink); line-height: 1.5; word-break: break-all; }
.lc-level {
  flex: none;
  font-size: 20rpx;
  font-weight: 800;
  margin-top: 2rpx;
  padding: 4rpx 14rpx;
  border-radius: var(--sj-r-pill);
  line-height: 1.4;
}

/* 左侧圆点：纯色区分级别 */
.lc-dot.lv-debug { background: var(--sj-faint); }
.lc-dot.lv-info { background: var(--sj-primary); }
.lc-dot.lv-warn { background: var(--sj-warn); }
.lc-dot.lv-error { background: var(--sj-bad); }

/* 级别文字标签：深色文字 + 同色系浅底，debug 也保证可读对比度 */
.lc-level.lv-debug { color: var(--sj-sub); background: var(--sj-cream); }
.lc-level.lv-info { color: var(--sj-primary-deep); background: var(--sj-primary-soft); }
.lc-level.lv-warn { color: #B47714; background: var(--sj-tint-milestone); }
.lc-level.lv-error { color: #D95A5A; background: var(--sj-tint-temp); }

/* ---------- 详情弹窗 ---------- */
.dm-scroll { max-height: 50vh; width: 100%; }
.dm-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 12rpx 0;
}
.dm-k { flex: none; width: 96rpx; font-size: 24rpx; font-weight: 700; color: var(--sj-sub); }
.dm-v { flex: 1; min-width: 0; font-size: 25rpx; font-weight: 600; color: var(--sj-ink); word-break: break-all; }
.dm-v.lv-debug { color: var(--sj-sub); }
.dm-v.lv-info { color: var(--sj-primary-deep); }
.dm-v.lv-warn { color: #B47714; }
.dm-v.lv-error { color: #D95A5A; }
.dm-msg {
  margin-top: 8rpx;
  font-size: 26rpx;
  font-weight: 600;
  color: var(--sj-ink);
  line-height: 1.6;
  word-break: break-all;
  text-align: left;
}
.dm-data {
  margin-top: 16rpx;
  padding: 16rpx 20rpx;
  background: var(--sj-cream);
  border-radius: var(--sj-r-sm);
  font-size: 22rpx;
  color: var(--sj-sub);
  line-height: 1.6;
  word-break: break-all;
  white-space: pre-wrap;
  text-align: left;
}
.dm-copy {
  margin: 20rpx auto 0;
  padding: 12rpx 32rpx;
  border-radius: var(--sj-r-pill);
  border: 2rpx solid var(--sj-line);
  background: var(--sj-surface);
  font-size: 24rpx;
  font-weight: 700;
  color: var(--sj-primary-deep);
}

.scroll-end { text-align: center; font-size: 22rpx; color: var(--sj-faint); padding: 24rpx 0 120rpx; letter-spacing: 2rpx; }
</style>
