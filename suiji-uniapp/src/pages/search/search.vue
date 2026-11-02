<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back）：圆形返回按钮 + 标题 -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">搜索</text>
    </view>

    <view class="content">
      <!-- 搜索栏（sj-search 封装）：放大镜 + 输入 + 清除，keyword 过滤由 computed 实时生效 -->
      <sj-search class="s-bar" v-model="q" placeholder="关键词 / 类型 / 日期，如「翻身」「10月19」" />

      <!-- 类型筛选 chips（v2 pg-chips 胶囊） -->
      <view class="pg-chips">
        <sj-tag
          v-for="t in typeChips"
          :key="t.k"
          variant="chip"
          pressable
          :active="type === t.k"
          :text="t.l"
          @click="type = t.k"
        />
      </view>

      <!-- 结果计数行（v2 pg-sec：前置 primary 短条） -->
      <view v-if="items.length" class="pg-sec"><text>结果 · 已加载 {{ items.length }} 条</text></view>

      <!-- 结果区 -->
      <view v-if="!items.length && !loadingMore" class="empty">
        <!-- 空态（v2 S1）：圆形浅底 + 放大镜图标 + 主副文案 -->
        <view class="ee-ava"><sj-icon name="24-fn-search" :size="128" /></view>
        <text class="ee-title">没有匹配的记录</text>
        <text class="ee-sub">换个关键词或调整类型筛选</text>
      </view>
      <view v-else>
        <!-- 结果行（v2 rec-card）：左类型图标块 + 中标题（命中词高亮）/元信息 + 右缩略图 -->
        <view
          class="rec-card"
          v-for="r in items"
          :key="r.id"
          :style="{ borderLeftColor: TYPES[r.type].color }"
          hover-class="hover-press"
          :hover-stay-time="80"
          @click="openDetail(r)"
        >
          <view class="rec-ic" :style="{ background: TYPES[r.type].tint }">
            <sj-icon :name="TYPES[r.type].png" :size="56" />
          </view>
          <view class="rec-info">
            <view class="rec-title">
              <text v-for="(seg, si) in splitHl(r.title)" :key="si" :class="{ hl: seg.hit }">{{ seg.t }}</text>
            </view>
            <text class="rec-meta">{{ r.day }} {{ r.time }} · {{ TYPES[r.type].label }} · {{ whoOf(r) }}</text>
          </view>
          <image v-if="r.photo" class="rec-photo" :src="r.photo" mode="aspectFill" lazy-load />
        </view>

        <!-- 触底分页提示（与首页同款）：加载中→弹跳；还有更多→下箭头；全部加载完→对勾（到底啦） -->
        <view class="scroll-end">
          <image class="se-ic" :class="{ bounce: loadingMore }" :src="scrollEndIcon" />
          <text>{{ loadingMore ? '正在加载更多…' : hasMore ? '上拉加载更多' : '· 已经到底啦 ·' }}</text>
        </view>
      </view>
    </view>

    <!-- 浮层宿主：接口报错等提示由它渲染 -->
    <sj-ui-host />
  </view>
</template>

<script>
import { TYPES } from '@/utils/mock.js'
import * as api from '@/utils/api.js'

export default {
  data() {
    return {
      TYPES,
      q: '',
      type: 'all',
      /* 服务端游标分页（GET /entries/search，与首页 /timeline 同款交互）：
         items=已加载的 view item（occurred_at 倒序），cursor=下一页游标 */
      items: [],
      cursor: '',
      hasMore: false,
      pageSize: 10,
      loadingMore: false,
      statusBarHeight: 20
    }
  },

  computed: {
    typeChips() {
      return [{ k: 'all', l: '全部类型' }].concat(Object.keys(TYPES).map(k => ({ k, l: TYPES[k].label })))
    },
    /* 底部提示卡通图标（与首页同款 ctl 库语义）：加载中→46-loading；还有更多→60-more；到底啦→66-ok */
    scrollEndIcon() {
      const base = '/static/icons/ctl/' + this.__theme + '/'
      if (this.loadingMore) return base + '192/46-ctl-loading.png'
      if (this.hasMore) return base + '56/60-ctl-nav-more.png'
      return base + '64/66-ctl-modal-ok.png'
    }
  },

  watch: {
    /* 关键词防抖 300ms 重搜；类型切换立即重搜（都从第一页重新开始） */
    q() {
      clearTimeout(this._qTimer)
      this._qTimer = setTimeout(() => this.search(), 300)
    },
    type() { this.search() }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  onShow() {
    /* 每次进入都重拉第一页（数据可能被编辑/新增过） */
    this.search()
  },

  /* 上滑触底：按游标请求下一页（触底距离见 pages.json onReachBottomDistance） */
  onReachBottom() {
    this.loadMore()
  },

  methods: {
    /* 关键词归一化：「10月19」「2026年10月」→「10-19」「2026-10」，可命中 ISO occurred_at 子串 */
    normQ() {
      return this.q.trim().replace(/[年月日]/g, '-').replace(/-+$/, '')
    },
    /* 重置游标拉第一页：q 为空时即最近记录分页（旧版空关键词展示全部记录） */
    search() {
      this.cursor = ''
      this.hasMore = false
      this.loadingMore = true
      api.fetchSearch({ q: this.normQ(), type: this.type, limit: this.pageSize }).then(p => {
        this.items = p.items
        this.cursor = p.next_cursor
        this.hasMore = p.has_more
        this.loadingMore = false
      }).catch(() => { this.loadingMore = false /* 失败保留当前列表 */ })
    },
    /* 触底加载下一页：按游标请求 /entries/search */
    loadMore() {
      if (this.loadingMore || !this.hasMore) return
      this.loadingMore = true
      api.fetchSearch({ q: this.normQ(), type: this.type, cursor: this.cursor, limit: this.pageSize }).then(p => {
        this.items = this.items.concat(p.items)
        this.cursor = p.next_cursor
        this.hasMore = p.has_more
        this.loadingMore = false
      }).catch(() => { this.loadingMore = false })
    },
    /* 记录人展示：与宝宝关系在前、昵称在后（「妈妈 · 小熊妈妈」）；按 creator_id 解析成员 */
    whoOf(e) {
      return api.creatorLabel(e)
    },
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },
    openDetail(r) {
      uni.navigateTo({ url: '/pages/detail/detail?id=' + r.id })
    },
    /* 标题按关键词拆段（大小写不敏感）：命中段 hit=true 供 .hl 高亮渲染 */
    splitHl(title) {
      const s = String(title == null ? '' : title)
      const kw = this.q.trim()
      if (!kw || !s) return [{ t: s, hit: false }]
      const out = []
      const lower = s.toLowerCase()
      const lowerKw = kw.toLowerCase()
      let i = 0
      while (i < s.length) {
        const idx = lower.indexOf(lowerKw, i)
        if (idx < 0) {
          out.push({ t: s.slice(i), hit: false })
          break
        }
        if (idx > i) out.push({ t: s.slice(i, idx), hit: false })
        out.push({ t: s.slice(idx, idx + kw.length), hit: true })
        i = idx + kw.length
      }
      return out
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
  padding-left: 32rpx;
  padding-right: 32rpx;
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
.content { padding: 0 32rpx 48rpx; }

/* 搜索栏改用 sj-search 封装，仅保留与 chips 行的间距（原 .s-field 的 margin-bottom） */
.s-bar { margin-bottom: 24rpx; }

/* 类型 chips：胶囊外观由 sj-tag（variant=chip）提供 */
.pg-chips { display: flex; flex-wrap: wrap; gap: 16rpx; margin-bottom: 28rpx; }

/* 结果计数行：pg-sec（前置 primary 短条） */
.pg-sec {
  display: flex;
  align-items: center;
  gap: 12rpx;
  font-size: 24rpx;
  color: var(--sj-faint);
  font-weight: 900;
  margin: 4rpx 0 16rpx;
}
.pg-sec::before {
  content: "";
  width: 10rpx;
  height: 28rpx;
  border-radius: 6rpx;
  background: var(--sj-primary);
  flex: none;
}

/* 结果行：v2 rec-card（与首页时间轴卡同款观感） */
.rec-card {
  display: flex;
  align-items: center;
  gap: 24rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-left: 8rpx solid var(--sj-primary);
  border-radius: var(--sj-r-md);
  padding: 24rpx 28rpx;
  margin-bottom: 20rpx;
  box-shadow: var(--sj-sh-sm);
}
.rec-card:active { transform: scale(0.97); }
.rec-ic {
  width: 88rpx;
  height: 88rpx;
  border-radius: 28rpx;
  padding: 6rpx;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.rec-info { flex: 1; min-width: 0; }
.rec-title {
  font-size: 28rpx;
  font-weight: 800;
  color: var(--sj-ink);
  line-height: 1.4;
}
/* 命中词高亮：暖黄底圆角小片 */
.hl {
  background: #FFE3A6;
  border-radius: 8rpx;
  color: var(--sj-ink);
}
.rec-meta {
  display: block;
  font-size: 23rpx;
  color: var(--sj-sub);
  margin-top: 6rpx;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rec-photo {
  width: 96rpx;
  height: 96rpx;
  border-radius: 20rpx;
  flex: none;
  border: 4rpx solid #fff;
  box-shadow: var(--sj-sh-sm);
}

/* 空态：v2 S1（圆形浅底 + 放大镜 + 主副文案） */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 96rpx 40rpx;
}
.ee-ava {
  width: 184rpx;
  height: 184rpx;
  border-radius: 50%;
  background: var(--sj-primary-soft);
  display: flex;
  align-items: center;
  justify-content: center;
}
/* 图标图片圆角与外圈曲线平行（同心）：外圈正圆 92 - 间隙 28 = 64rpx（即图片整圆） */
.ee-ava .sj-icon { border-radius: 50%; }
.ee-title {
  font-family: var(--sj-font-display);
  font-size: 36rpx;
  font-weight: 900;
  color: var(--sj-ink);
  margin-top: 28rpx;
}
.ee-sub { font-size: 25rpx; color: var(--sj-sub); margin-top: 12rpx; }

/* 底部说明：pg-hint */
.pg-hint {
  font-size: 23rpx;
  color: var(--sj-sub);
  background: var(--sj-cream);
  border: 2rpx dashed var(--sj-line);
  border-radius: 24rpx;
  padding: 16rpx 24rpx;
  margin-top: 28rpx;
  line-height: 1.5;
}

/* 触底分页提示（与首页同款） */
.scroll-end {
  display: flex; align-items: center; justify-content: center; gap: 12rpx;
  font-size: 22rpx; color: var(--sj-faint); padding: 24rpx 0 16rpx; letter-spacing: 4rpx;
}
.se-ic { width: 44rpx; height: 44rpx; flex: none; }
/* 加载中：卡通图标上下弹跳（与首页同款） */
.se-ic.bounce { animation: seBounce 0.8s ease-in-out infinite; }
@keyframes seBounce {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(8rpx) scale(1.08); }
}
</style>
