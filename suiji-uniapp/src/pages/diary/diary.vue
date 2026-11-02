<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回按钮 + display 标题 + AI 生成标识胶囊） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">AI 成长日记</text>
      <sj-tag class="diary-tag" variant="pill" bg="#F0EAFB" color="#7A5FB0" text="AI 生成" />
    </view>

    <view class="content">
      <!-- AI 生成提示条（v2 pg-hint 虚线提示；合规文案原样保留） -->
      <view class="pg-hint">
        <text>内容由 AI 自动生成，请核对</text>
        <text class="hint-sub">基础版 · 模型降级时按事实模板拼装</text>
      </view>

      <!-- 本周检测：有未归档的本周日记 → 编辑；没有 → 生成 -->
      <sj-button class="d-gen-btn" block size="lg" :text="thisWeekDraftId ? '编辑本周草稿' : '生成本周日记'" @click="goEdit()" />

      <!-- 日记档案：每篇一张卡，预览直接展示最终生成内容 -->
      <view class="pg-sec"><text>日记档案</text></view>
      <view class="d-empty" v-if="!list.length">
        <text>还没有日记，点击上方按钮生成本周成长日记</text>
      </view>
      <view class="grow-card" v-for="d in list" :key="d.id">
        <view class="dc-head">
          <text class="dc-range">{{ d.range || '成长日记' }}</text>
          <text class="d-st-tag" :class="d.status === 'archived' ? 'arch' : 'draft'">{{ d.status === 'archived' ? '已归档' : '草稿 · 待核对' }}</text>
        </view>
        <!-- 折叠态只显示第一段（最多 4 行），查看更多展开全文 -->
        <text class="dc-text" :class="{ clamp: !isExp(d.id) }" v-for="(p, i) in shownParas(d)" :key="i">{{ p.text }}</text>
        <view v-if="hasMore(d)" class="dc-more" hover-class="hover-press" :hover-stay-time="80" @click="toggleExp(d.id)">
          <text>{{ isExp(d.id) ? '收起' : '查看更多' }}</text>
          <image class="dc-more-chev" :class="{ open: isExp(d.id) }" src="/static/icons/chevron-down.svg" />
        </view>
        <view class="dc-foot">
          <text class="dc-date">{{ fmtDate(d.created_at) }} 生成</text>
          <!-- 已归档只能预览；草稿可进生成界面编辑/归档 -->
          <view v-if="d.status !== 'archived'" class="dc-edit" hover-class="hover-press" :hover-stay-time="80" @click="goEdit(d.id)">
            <text>编辑草稿</text>
            <image class="dc-chev" src="/static/icons/chevron-right.svg" />
          </view>
        </view>
      </view>

      <!-- 底部说明（v2 pg-hint；合规文案原样保留） -->
      <view class="pg-hint tail"><text>未归档草稿保留 30 天后自动清理 · 归档后进入成长档案并标注「AI 生成」</text></view>
    </view>

    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'

export default {
  data() {
    return {
      /* 全部日记（草稿+归档），按创建时间倒序 */
      list: [],
      /* 已展开「查看更多」的日记 id */
      expandedIds: [],
      statusBarHeight: 20
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

  computed: {
    /* 本周未归档草稿 id：日记周期（range_start~range_end）覆盖今天才算本周 */
    thisWeekDraftId() {
      const today = new Date().toISOString().slice(0, 10)
      const d = this.list.find(x =>
        x.status !== 'archived' && x.range_start && x.range_end &&
        x.range_start <= today && today <= x.range_end
      )
      return d ? d.id : ''
    }
  },

  methods: {
    async refresh() {
      try {
        this.list = await api.listDiaries()
      } catch (e) { /* 保留当前列表 */ }
    },
    fmtDate(s) {
      return String(s || '').slice(0, 10)
    },
    /* 折叠/展开全文 */
    isExp(id) {
      return this.expandedIds.indexOf(id) > -1
    },
    toggleExp(id) {
      const i = this.expandedIds.indexOf(id)
      if (i > -1) this.expandedIds.splice(i, 1)
      else this.expandedIds.push(id)
    },
    /* 折叠态只渲染第一段，展开态渲染全部 */
    shownParas(d) {
      return this.isExp(d.id) ? d.paras : d.paras.slice(0, 1)
    },
    hasMore(d) {
      if (!d.paras || !d.paras.length) return false
      return d.paras.length > 1 || (d.paras[0].text || '').length > 80
    },
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },
    /* 跳转生成界面：带 id 编辑既有草稿，不带 id 由生成界面新建 */
    goEdit(id) {
      const target = id || this.thisWeekDraftId
      uni.navigateTo({ url: '/pages/diary/edit' + (target ? '?id=' + target : '') })
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
/* AI 标识小胶囊（sj-tag pill，配色经组件 props 下发） */
.diary-tag { flex: none; }

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
.hint-sub {
  display: block;
  font-size: 21rpx;
  color: var(--sj-faint);
  margin-top: 6rpx;
}

/* 生成入口按钮 */
.d-gen-btn { display: flex; margin-bottom: 32rpx; }

/* 小节标题（v2 pg-sec：primary 短竖条 + faint 大字） */
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

/* 空态 */
.d-empty {
  font-size: 24rpx;
  color: var(--sj-faint);
  text-align: center;
  padding: 48rpx 24rpx;
  background: var(--sj-surface);
  border: 2rpx dashed var(--sj-line);
  border-radius: var(--sj-r-md);
}

/* ---------- 日记卡（预览最终生成内容） ---------- */
.grow-card {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  box-shadow: var(--sj-sh-sm);
  padding: 28rpx;
  margin-bottom: 24rpx;
}
.dc-head { display: flex; align-items: center; gap: 16rpx; margin-bottom: 16rpx; }
.dc-range { flex: 1; font-size: 26rpx; font-weight: 800; color: var(--sj-ink); }
.dc-text {
  display: block;
  font-size: 26rpx;
  color: var(--sj-ink);
  line-height: 1.8;
  margin-bottom: 16rpx;
}
/* 折叠态：首段最多显示 4 行 */
.dc-text.clamp {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
  overflow: hidden;
}
/* 查看更多 / 收起 */
.dc-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6rpx;
  font-size: 23rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  padding: 6rpx 0 10rpx;
}
.dc-more-chev {
  width: 24rpx;
  height: 24rpx;
  transition: transform 0.25s cubic-bezier(.22,.8,.3,1);
}
.dc-more-chev.open { transform: rotate(180deg); }
.dc-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding-top: 16rpx;
  border-top: 2rpx dashed var(--sj-line);
}
.dc-date { font-size: 20rpx; color: var(--sj-faint); }
.dc-edit {
  display: flex;
  align-items: center;
  gap: 4rpx;
  font-size: 24rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  flex: none;
}
.dc-chev { width: 24rpx; height: 24rpx; }

/* 状态徽标配色 */
.d-st-tag { font-size: 20rpx; font-weight: 700; padding: 4rpx 16rpx; border-radius: var(--sj-r-pill); flex: none; }
.d-st-tag.draft { color: #B47714; background: #FFF3D6; }
.d-st-tag.arch { color: #2E7D4F; background: #E2F5EA; }
</style>
