<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形白底返回 + display 标题 + 右侧文字按钮） -->
    <view class="nt-bar" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="back-btn" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="back-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="nt-title">消息中心</text>
      <!-- 「全部已读」只对通知有效：待办是实时派生事项，处理完才消失，没有已读态 -->
      <text v-if="tab === 'notice'" class="nt-all" :class="{ off: !unreadCount }" hover-class="hover-press" :hover-stay-time="80" @click="markAll">全部已读</text>
    </view>

    <!-- 通知 / 待办 切换（v2 pg-seg 分段控件：白底胶囊容器，选中 primary 底白字） -->
    <view class="nt-tabs">
      <view class="nt-tab" :class="{ on: tab === 'notice' }" hover-class="hover-press" :hover-stay-time="80" @click="switchTab('notice')">
        <text>通知</text>
        <text v-if="unreadCount" class="nt-num">{{ unreadCount }}</text>
      </view>
      <view class="nt-tab" :class="{ on: tab === 'todo' }" hover-class="hover-press" :hover-stay-time="80" @click="switchTab('todo')">
        <text>待办</text>
        <!-- 待办胶囊是「待处理条数」，不是未读数，用浅底中性色区分 -->
        <text v-if="todos.length" class="nt-num cnt">{{ todos.length }}</text>
      </view>
    </view>

    <!-- 列表 -->
    <view class="nt-list">
      <view v-if="!list.length" class="nt-empty">
        <text>暂无{{ tab === 'todo' ? '待办' : '通知' }}</text>
      </view>

      <view
        v-for="item in pagedList"
        :key="item.id"
        class="nt-item"
        :class="{ read: item.read }"
        hover-class="hover-press"
        :hover-stay-time="80"
        @click="onItem(item)"
      >
        <!-- 图标块：旧 iconKey 经映射表换成 v2 png 图标 + 类别浅底 -->
        <view class="nt-ic" :style="{ background: iconMeta(item).tint }">
          <sj-icon :name="iconMeta(item).png" :size="48" />
        </view>
        <view class="nt-main">
          <view class="nt-line1">
            <text class="nt-name">{{ item.title }}</text>
            <text class="nt-time">{{ item.time }}</text>
          </view>
          <text class="nt-desc">{{ item.desc }}</text>
          <view class="nt-tail">
            <text v-if="tab === 'notice'" class="nt-tag" :class="{ gray: item.read }">{{ item.read ? '已读' : '未读' }}</text>
            <text v-if="item.btn" class="nt-go">{{ item.btn }} ›</text>
            <!-- 通知项「知道了」：点击删除该条消息（本地账本 + 家人动态服务端行） -->
            <text v-if="tab === 'notice'" class="nt-ack" hover-class="hover-press" :hover-stay-time="80" @click.stop="ackItem(item)">知道了</text>
          </view>
        </view>
      </view>

      <!-- 触底分页提示（与首页同款）：还有更多→下箭头；全部加载完→对勾（到底啦） -->
      <view v-if="list.length" class="scroll-end">
        <image class="se-ic" :src="scrollEndIcon" />
        <text>{{ hasMore ? '上拉加载更多' : '· 已经到底啦 ·' }}</text>
      </view>
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'

/**
 * 旧 SVG iconKey → v2 png 图标映射（Phase 5 换肤）
 * 取值来自 api.getNotices / api.getTodos 实际下发的 icon 字段：
 *   gift=疫苗提醒/待接种  sparkles=每日提醒  heart=纪念日等系统提醒
 *   users=家人动态/里程碑  pencil=AI 日记  alert=删除恢复/逾期疫苗  trash=回收站
 * 浅底统一取对应 --sj-tint-* / --sj-primary-soft 令牌；映射不到兜底 25-fn-notify。
 */
const NOTICE_ICONS = {
  gift: { png: '34-fn-vaccine', tint: 'var(--sj-tint-milestone)' },
  alert: { png: '34-fn-vaccine', tint: 'var(--sj-tint-temp)' },
  sparkles: { png: '21-fn-remind', tint: 'var(--sj-primary-soft)' },
  heart: { png: '21-fn-remind', tint: 'var(--sj-tint-feeding)' },
  users: { png: '28-fn-invite', tint: 'var(--sj-tint-sleep)' },
  pencil: { png: '20-fn-diary', tint: 'var(--sj-tint-mood)' },
  trash: { png: '27-fn-trash', tint: 'var(--sj-tint-poop)' }
}

export default {
  data() {
    return {
      statusBarHeight: 20,
      /* notice = 系统通知账本；todo = 疫苗/日记/回收站派生（无已读态，处理完才消失） */
      tab: 'notice',
      notices: [],
      todos: [],
      /* 触底分页（与首页一致，每页 10 条）：shown=已展示条数，对当前 tab 列表本地切片 */
      pageSize: 10,
      shown: 10
    }
  },

  computed: {
    list() {
      return this.tab === 'todo' ? this.todos : this.notices
    },
    /* 只有通知有未读概念（待办不计角标，也不参与「全部已读」） */
    unreadCount() {
      return this.notices.filter(n => !n.read).length
    },
    /* 当前页渲染列表：list（当前 tab 全量）按 shown 截断，触底增量追加 */
    pagedList() {
      return this.list.slice(0, this.shown)
    },
    hasMore() {
      return this.shown < this.list.length
    },
    /* 底部提示卡通图标（与首页同款 ctl 库语义）：还有更多→60-more；到底啦→66-ok */
    scrollEndIcon() {
      const base = '/static/icons/ctl/' + this.__theme + '/'
      if (this.hasMore) return base + '56/60-ctl-nav-more.png'
      return base + '64/66-ctl-modal-ok.png'
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  onShow() {
    this.refresh()
  },

  /* 上滑触底：本地切片追加下一页（与首页同款交互，触底距离见 pages.json onReachBottomDistance） */
  onReachBottom() {
    if (this.hasMore) this.shown += this.pageSize
  },

  methods: {
    refresh() {
      this.notices = api.getNotices()
      this.todos = api.getTodos()
    },

    switchTab(t) {
      this.tab = t
      /* 切换分组即重置分页，从第一页重新展示 */
      this.shown = this.pageSize
    },

    /* 列表项图标：按映射表取 v2 png 名与浅底，未收录的 key 兜底消息铃铛 */
    iconMeta(item) {
      return NOTICE_ICONS[item.icon] || { png: '25-fn-notify', tint: 'var(--sj-primary-soft)' }
    },

    /* 清空通知分组的未读（待办分组没有已读态，故顶栏按钮只出现在通知 tab） */
    markAll() {
      if (!this.unreadCount) return
      api.markAllNoticesRead()
      this.refresh()
      this.$refs.ntf.show({ type: 'ok', message: '通知已全部清除' })
    },

    /* 点击即已读并直达对应功能页；待办点进去就是「去处理」，不在本机留已读态 */
    onItem(item) {
      if (this.tab === 'notice') api.markNoticeRead(item.id)
      this.refresh()
      if (item.go) {
        /* 体检提示等目标可能是 tab 页：navigateTo 打不开，需 switchTab */
        const tabs = ['/pages/index/index', '/pages/grow/grow', '/pages/family/family', '/pages/me/me']
        if (tabs.indexOf(item.go) >= 0) uni.switchTab({ url: item.go })
        else uni.navigateTo({ url: item.go })
      }
    },

    /* 「知道了」：删除该条通知消息（本地账本 + 家人动态服务端行），再刷新列表与角标 */
    ackItem(item) {
      api.removeNotice(item.id)
      this.refresh()
    },

    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
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
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
}

/* ---------- 顶栏（v2 pg-back） ---------- */
.nt-bar {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding-left: 32rpx;
  padding-right: 32rpx;
  padding-bottom: 24rpx;
}
.back-btn {
  width: 68rpx;
  height: 68rpx;
  flex: none;
  border-radius: 50%;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--sj-sh-sm);
}
.back-ic { width: 40rpx; height: 40rpx; }
.nt-title {
  flex: 1;
  font-family: var(--sj-font-display);
  font-size: 40rpx;
  font-weight: 900;
  color: var(--sj-ink);
}
.nt-all {
  font-size: 26rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  padding: 8rpx 4rpx;
}
.nt-all.off { color: var(--sj-faint); }

/* ---------- 分组切换（v2 pg-seg） ---------- */
.nt-tabs {
  display: flex;
  gap: 8rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-pill);
  padding: 8rpx;
  margin: 0 32rpx 24rpx;
}
.nt-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26rpx;
  font-weight: 800;
  color: var(--sj-sub);
  border-radius: var(--sj-r-pill);
  padding: 14rpx 0;
  transition: background 0.25s cubic-bezier(.34,1.56,.64,1), color 0.25s cubic-bezier(.22,.8,.3,1);
}
/* 选中态：primary 底白字 + 品牌色投影 */
.nt-tab.on {
  color: #fff;
  background: var(--sj-primary);
  box-shadow: 0 8rpx 24rpx rgba(247, 161, 92, 0.35);
}
/* 未读数小胶囊：未选中 tab 用 bad 红底白字；选中 tab 反白 */
.nt-num {
  margin-left: 10rpx;
  min-width: 36rpx;
  text-align: center;
  font-size: 22rpx;
  font-weight: 800;
  color: #fff;
  background: var(--sj-bad);
  border-radius: var(--sj-r-pill);
  padding: 2rpx 10rpx;
}
.nt-tab.on .nt-num { color: var(--sj-primary-deep); background: var(--sj-surface); }
/* 待办条数胶囊：中性浅底，避免被读成「未读提醒」 */
.nt-num.cnt { color: var(--sj-primary-deep); background: var(--sj-primary-soft); }
.nt-tab.on .nt-num.cnt { color: var(--sj-primary-deep); background: var(--sj-surface); }

/* ---------- 列表 ---------- */
.nt-list { padding: 0 32rpx 48rpx; }
.nt-empty { text-align: center; font-size: 26rpx; color: var(--sj-faint); padding: 120rpx 0; }

/* 卡片：白底 line 边 r-md + 左侧 primary 竖条表未读 */
.nt-item {
  display: flex;
  align-items: flex-start;
  gap: 24rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-left: 8rpx solid var(--sj-primary);
  border-radius: var(--sj-r-md);
  padding: 24rpx 28rpx;
  margin-bottom: 20rpx;
  box-shadow: var(--sj-sh-sm);
}
/* 已读整卡降饱和：cream 底 + line 竖条 */
.nt-item.read { border-left-color: var(--sj-line); background: var(--sj-cream); }
.nt-ic {
  width: 72rpx;
  height: 72rpx;
  border-radius: var(--sj-r-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.nt-main { flex: 1; min-width: 0; }
.nt-line1 { display: flex; align-items: baseline; gap: 16rpx; }
.nt-name { flex: 1; min-width: 0; font-size: 28rpx; font-weight: 800; color: var(--sj-ink); }
.nt-item.read .nt-name { font-weight: 600; color: var(--sj-sub); }
.nt-time { flex: none; font-size: 22rpx; color: var(--sj-faint); }
.nt-desc { display: block; font-size: 24rpx; color: var(--sj-sub); line-height: 1.6; margin-top: 8rpx; }
.nt-tail { display: flex; align-items: center; gap: 20rpx; margin-top: 14rpx; }
.nt-tag {
  font-size: 21rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  border-radius: var(--sj-r-pill);
  padding: 4rpx 18rpx;
}
.nt-tag.gray { color: var(--sj-faint); background: var(--sj-line); }
.nt-go { font-size: 23rpx; font-weight: 800; color: var(--sj-primary-deep); }
/* 「知道了」删除按钮：primary-soft 浅底胶囊，主色深字，与已读标签同排 */
.nt-ack {
  margin-left: auto;
  font-size: 22rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  border-radius: var(--sj-r-pill);
  padding: 8rpx 24rpx;
}

.scroll-end {
  display: flex; align-items: center; justify-content: center; gap: 12rpx;
  font-size: 22rpx; color: var(--sj-faint); padding: 24rpx 0 16rpx; letter-spacing: 4rpx;
}
.se-ic { width: 44rpx; height: 44rpx; flex: none; }
</style>
