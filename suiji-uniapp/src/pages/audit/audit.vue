<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形白底返回 + display 标题） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">操作记录</text>
    </view>

    <view class="content">
      <!-- 留痕规则说明（v2 pg-hint：cream 底虚线边） -->
      <view class="pg-hint">记录新增 / 加入 / 退出 / 角色变更 / 删除 / 导出等关键操作 · 保留 180 天 · 全员可查看</view>

      <!-- 留痕列表（服务端 audit_log · 只读；v2 pg-vrow 观感：白底 line 边 28rpx 圆角，色点 + 事件 tag + 操作人 + 内容 + 时间） -->
      <view class="audit-row" v-for="a in rows" :key="a.id">
        <view class="a-dot" :style="{ background: a.color }" />
        <view class="a-body">
          <view class="a-top">
            <text class="a-tag" :style="{ color: a.color, background: a.color + '1A' }">{{ a.tag }}</text>
            <text class="a-who">{{ a.who }}</text>
          </view>
          <text class="a-text">{{ a.text }}</text>
        </view>
        <text class="a-time">{{ a.time }}</text>
      </view>

      <!-- 空态（sj-empty 封装：primary-soft 圆底大图标 + 主副文案） -->
      <sj-empty
        v-if="loaded && !rows.length"
        icon="35-fn-audit"
        text="还没有操作记录"
        sub="家庭里的新增 / 加入 / 退出 / 角色变更 / 删除 / 导出会实时记录在这里"
      />

      <view class="scroll-end" v-if="rows.length">
        <!-- 触底分页提示（与首页同款）：加载中→弹跳；还有更多→下箭头；全部加载完→对勾（到底啦） -->
        <image class="se-ic" :class="{ bounce: loadingMore }" :src="scrollEndIcon" />
        <text>{{ loadingMore ? '正在加载更多…' : (noMore ? '· 已经到底啦 ·' : '上拉加载更多') }}</text>
      </view>
    </view>

    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'

export default {
  data() {
    return {
      rows: [],
      loaded: false,
      loadingMore: false,
      noMore: false,
      pageSize: 10,
      statusBarHeight: 20
    }
  },

  computed: {
    /* 底部提示卡通图标（与首页同款 ctl 库语义）：加载中→46-loading；还有更多→60-more；到底啦→66-ok */
    scrollEndIcon() {
      const base = '/static/icons/ctl/' + this.__theme + '/'
      if (this.loadingMore) return base + '192/46-ctl-loading.png'
      if (this.noMore) return base + '64/66-ctl-modal-ok.png'
      return base + '56/60-ctl-nav-more.png'
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

  /* 上滑触底：自动加载下一页（触底距离见 pages.json onReachBottomDistance） */
  onReachBottom() {
    this.loadMore()
  },

  methods: {
    /** 拉取家庭真实操作留痕首页（GET /family/audit，近 180 天） */
    load() {
      /* 服务端实拉，进入页面到列表渲染之间是空白区，全屏阻断给出等待反馈 */
      const ld = ui.loading('正在读取操作记录…')
      return api.getAudit(0, this.pageSize)
        .then(rows => { this.rows = rows; this.noMore = rows.length < this.pageSize })
        .catch(() => { this.rows = []; this.noMore = true })
        .then(() => { this.loaded = true; ld.close() })
    },

    /** 上滑加载下一页：offset=已加载条数，返回不足一页即末页 */
    loadMore() {
      if (this.loadingMore || this.noMore || !this.loaded) return
      this.loadingMore = true
      const ld = ui.loading('正在加载更多…')
      api.getAudit(this.rows.length, this.pageSize)
        .then(rows => {
          /* 期间新写入的留痕会让分页窗口漂移，按 id 去重防重复行 */
          const seen = new Set(this.rows.map(r => r.id))
          this.rows = this.rows.concat(rows.filter(r => !seen.has(r.id)))
          if (rows.length < this.pageSize) this.noMore = true
        })
        .catch(() => { this.noMore = true })
        .then(() => { this.loadingMore = false; ld.close() })
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

/* 留痕行（v2 pg-vrow 观感：白底 line 边 28rpx 圆角 + sh-sm） */
.audit-row {
  display: flex;
  align-items: flex-start;
  gap: 24rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: 28rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 16rpx;
  box-shadow: var(--sj-sh-sm);
}
.a-dot {
  width: 20rpx;
  height: 20rpx;
  border-radius: 50%;
  margin-top: 12rpx;
  flex: none;
}
.a-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8rpx; }
.a-top { display: flex; align-items: center; gap: 12rpx; }
/* 事件类型徽标：颜色由服务端事件数据驱动 */
.a-tag {
  font-size: 20rpx;
  font-weight: 900;
  border-radius: var(--sj-r-pill);
  padding: 4rpx 16rpx;
}
.a-who { font-size: 24rpx; font-weight: 800; color: var(--sj-ink); }
.a-text { font-size: 23rpx; color: var(--sj-sub); line-height: 1.6; }
.a-time { font-size: 20rpx; color: var(--sj-faint); flex: none; margin-top: 6rpx; }

/* 空态改用 sj-empty 封装（外观对齐 v2 pg-empty），局部样式已移除 */

/* 底部说明 */
.scroll-end {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  font-size: 22rpx;
  color: var(--sj-faint);
  padding: 24rpx 0 16rpx;
  letter-spacing: 4rpx;
}
.se-ic { width: 44rpx; height: 44rpx; flex: none; }
/* 加载中：卡通图标上下弹跳（与首页同款） */
.se-ic.bounce { animation: seBounce 0.8s ease-in-out infinite; }
@keyframes seBounce {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(8rpx) scale(1.08); }
}
</style>
