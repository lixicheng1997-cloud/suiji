<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：奶油渐隐 sticky + 圆形返回钮 + 显示字族标题） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">宝宝档案管理</text>
    </view>

    <view class="list-wrap">
      <view class="pg-hint">轻点档案查看 / 编辑，快速记录与时光轴始终归属当前宝宝</view>

      <!-- 档案卡列表（v2 grow-card：当前档案金边 + 出生数据 pg-field 摘要行） -->
      <view
        class="grow-card"
        :class="{ current: b.is_active }"
        v-for="b in babies"
        :key="b.id"
        hover-class="hover-press"
        :hover-stay-time="80"
        @click="edit(b)"
      >
        <view class="gc-row">
          <!-- 头像（v2 pg-ava：primary-soft 圆底白描边；非当前档案 blush-soft） -->
          <view class="pg-ava" :class="{ blush: !b.is_active }">
            <image class="ava-img" :src="avSrc(b.avatar) || ('/static/icons/ctl/' + __theme + '/128/45-ctl-avatar.png')" :mode="avSrc(b.avatar) ? 'aspectFill' : 'aspectFit'" />
          </view>
          <view class="gc-info">
            <view class="gc-name-row">
              <text class="gc-name">{{ b.name }}</text>
              <text v-if="b.is_active" class="ms-badge">当前</text>
            </view>
            <text class="gc-sub">{{ b.gender === 'girl' ? '女宝' : '男宝' }} · {{ b.birth_date }} 出生 · {{ b.age }}</text>
          </view>
          <view
            v-if="!b.is_active"
            class="bc-switch"
            hover-class="hover-press"
            :hover-stay-time="80"
            @click.stop="switchTo(b)"
          ><text>设为当前</text></view>
          <image v-else class="gc-chev" src="/static/icons/chevron-right.svg" />
        </view>

        <!-- 当前档案的出生数据 / 过敏史摘要（v2 pg-field，仅展示已有字段） -->
        <view v-if="b.is_active && (b.birth_length || b.birth_weight)" class="pg-field bc-data">
          <text class="pf-label">出生身长</text>
          <text class="pf-val">{{ b.birth_length ? b.birth_length + 'cm' : '—' }}</text>
          <text class="pf-label pf-label-n">体重</text>
          <text class="pf-val">{{ b.birth_weight ? b.birth_weight + 'kg' : '—' }}</text>
        </view>
        <view v-if="b.is_active && b.allergy" class="pg-field bc-data">
          <text class="pf-label">过敏史</text>
          <text class="pf-val">{{ b.allergy }}</text>
        </view>
      </view>

      <!-- 空态（sj-empty：主题图标 primary-soft 圆底 + 主/副文案，外观对齐 v2 pg-empty） -->
      <sj-empty v-if="!babies.length" icon="29-fn-babies" text="还没有宝宝档案" sub="创建第一份档案开始记录吧" />

      <!-- 新建入口（v2 虚线 pg-field：+ 新建宝宝档案） -->
      <view class="add-field" hover-class="hover-press" :hover-stay-time="80" @click="addNew">
        <text>+ 新建宝宝档案</text>
      </view>

      <view class="pg-hint">每个宝宝的档案互不影响 · 建档前需监护人同意</view>
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import { play } from '@/utils/sound.js'

export default {
  data() {
    return {
      babies: [],
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

  methods: {
    refresh() {
      this.babies = api.getBabies()
    },
    /* 头像展示源：/files 文件 URL 解析为带 token 直链，未设置留空（模板回退本地图标占位） */
    avSrc(a) {
      return api.fileSrc(a)
    },
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },
    /* 查看 / 编辑指定档案 */
    edit(b) {
      uni.navigateTo({ url: '/pages/baby/baby?id=' + b.id })
    },
    /* 切换当前宝宝：记录归属与快速记录默认对象随之改变 */
    switchTo(b) {
      api.setActiveBaby(b.id)
      this.$refs.ntf.show({ type: 'ok', message: '已切换为「' + b.name + '」' })
      this.refresh()
      play('S10') // 宝宝切换完成音效（震动自动配对）
      /* ensureVaccineSchedule 变异步：后台刷新该宝宝疫苗/里程碑缓存 */
      api.ensureVaccineSchedule()
    },
    addNew() {
      uni.navigateTo({ url: '/pages/baby/baby?new=1' })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 页面底：v2 奶油色（themeVars 由全局混入注入到根节点） */
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

/* ---------- 列表内容区 ---------- */
.list-wrap { padding: 8rpx 32rpx 80rpx; }

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

/* 档案卡（v2 grow-card：白底 line 边 r-md；当前档案金边高亮） */
.grow-card {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 28rpx 32rpx;
  margin-bottom: 24rpx;
  box-shadow: var(--sj-sh-sm);
}
.grow-card.current { border-color: var(--sj-gold); }
.grow-card:active { transform: scale(0.98); }
.gc-row { display: flex; align-items: center; gap: 24rpx; }

/* 头像（v2 pg-ava：primary-soft 圆底 + 白描边；非当前 blush-soft） */
.pg-ava {
  width: 112rpx;
  height: 112rpx;
  border-radius: 50%;
  background: var(--sj-primary-soft);
  border: 4rpx solid #fff;
  box-shadow: var(--sj-sh-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex: none;
}
.pg-ava.blush { background: var(--sj-blush-soft); }
.ava-img { width: 100%; height: 100%; }

.gc-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8rpx; }
.gc-name-row { display: flex; align-items: center; gap: 16rpx; }
.gc-name { font-family: var(--sj-font-display); font-size: 32rpx; font-weight: 900; color: var(--sj-ink); }
/* 「当前」金标（v2 ms-badge） */
.ms-badge {
  font-size: 21rpx;
  font-weight: 800;
  color: #B47714;
  background: var(--sj-surface);
  border-radius: var(--sj-r-pill);
  padding: 6rpx 20rpx;
  box-shadow: var(--sj-sh-sm);
  flex: none;
}
.gc-sub {
  font-size: 23rpx;
  color: var(--sj-sub);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 切换按钮（v2 软底描边胶囊） */
.bc-switch {
  flex: none;
  font-size: 23rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  border: 2rpx solid var(--sj-primary);
  padding: 12rpx 28rpx;
  border-radius: var(--sj-r-pill);
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.bc-switch:active { transform: scale(0.95); }
.gc-chev { width: 32rpx; height: 32rpx; flex: none; opacity: 0.5; }

/* 卡内字段行（v2 pg-field：毛玻璃面 + 半透高光描边 + 28rpx 圆角，label 灰粗 / val 墨色特粗） */
.pg-field {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: var(--sj-glass);
  border: 2rpx solid var(--sj-glass-line);
  border-radius: 28rpx;
  box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
  padding: 20rpx 28rpx;
  font-size: 27rpx;
}
.pf-label { color: var(--sj-sub); font-weight: 700; flex: none; width: 148rpx; }
.pf-label-n { width: 84rpx; }
.pf-val { flex: 1; color: var(--sj-ink); font-weight: 800; min-width: 0; }
.bc-data { margin: 20rpx 0 0; }

/* 新建入口（主题主色虚线胶囊：primary-soft 底 + primary 虚线边 + primary-deep 文字） */
.add-field {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--sj-primary-soft);
  border: 2rpx dashed var(--sj-primary);
  border-radius: 28rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 24rpx;
  font-size: 27rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  transition: transform 0.2s var(--sj-spring);
}
.add-field:active { transform: scale(0.98); }
</style>
