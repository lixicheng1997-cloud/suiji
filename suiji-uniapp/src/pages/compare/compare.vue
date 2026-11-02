<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回按钮 + display 标题） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">同月龄对比</text>
    </view>

    <view class="content">
      <!-- 隐私边界提示（v2 pg-hint.ok 绿色虚线；合规文案原样保留） -->
      <view class="pg-hint ok"><text>仅使用你账号里同一个宝宝的旧照片 · 不使用人脸识别</text></view>

      <!-- 月龄切换（v2 pg-chips 胶囊；由真实照片记录的月龄派生） -->
      <view class="pg-chips" v-if="ages.length">
        <sj-tag
          v-for="(a, i) in ages"
          :key="a"
          variant="chip"
          pressable
          :active="age === i"
          :text="a"
          @click="pickAge(i)"
        />
      </view>

      <!-- 左右对比框（v2 pg-photo 白底卡：line 边 + 圆角 + 角标图标） -->
      <view class="cmp-grid">
        <view class="cmp-slot" v-for="(slot, si) in [0, 1]" :key="si">
          <view class="slot-frame">
            <image
              v-if="slotPhoto(si)"
              class="slot-img"
              :src="slotPhoto(si).url"
              mode="aspectFill"
            />
            <view v-else class="cmp-empty">
              <sj-icon name="04-photo" :size="56" />
              <text>点击下方照片 选择对比</text>
            </view>
            <!-- 已选照片右上角小图标（对齐 P31 原型 pg-photo img 角标） -->
            <view v-if="slotPhoto(si)" class="slot-badge">
              <sj-icon name="04-photo" :size="40" />
            </view>
          </view>
          <text class="cmp-label">{{ (si ? '右侧' : '左侧') + ' · ' + (slotPhoto(si) ? slotPhoto(si).date : '未选择') }}</text>
        </view>
      </view>

      <!-- 该月龄照片条（v2 pg-sec + 网格缩略图；无记录显示空态） -->
      <view class="pg-sec" v-if="ages.length"><text>{{ ages[age] }}的照片</text></view>
      <view class="cmp-strip" v-if="list.length">
        <image
          class="cmp-thumb"
          :class="{ on: sel.indexOf(i) > -1 }"
          v-for="(p, i) in list"
          :key="i"
          :src="p.url"
          mode="aspectFill"
          lazy-load
          hover-class="hover-press"
          :hover-stay-time="80"
          @click="pick(i)"
        />
      </view>
      <view class="pg-hint" v-else-if="ages.length"><text>该月龄还没有照片记录</text></view>
      <view class="pg-hint" v-else><text>还没有照片记录 · 在首页添加照片后即可按同月龄对比</text></view>
    </view>

    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'

/* 照片发生时间相对出生日期的整月龄（与原型 ageFromBirth 同口径：日不足借上月） */
function ageMonthsAt(birthDate, occurredAt) {
  const b = new Date(birthDate + 'T00:00:00')
  const p = new Date(occurredAt)
  if (isNaN(b.getTime()) || isNaN(p.getTime())) return -1
  let m = (p.getFullYear() - b.getFullYear()) * 12 + (p.getMonth() - b.getMonth())
  if (p.getDate() < b.getDate()) m -= 1
  return m < 0 ? 0 : m
}

export default {
  data() {
    return {
      /* ages=真实照片派生的月龄 tab；groups=月龄 → 照片列表 */
      ages: [],
      groups: {},
      age: 0,
      /* sel[0]=左框选中的照片下标，sel[1]=右框；-1 表示未选 */
      sel: [-1, -1],
      statusBarHeight: 20
    }
  },

  computed: {
    list() {
      return this.groups[this.ages[this.age]] || []
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
    /* 拉取当前宝宝真实照片记录，按拍摄时月龄分组（替代原型假照片集） */
    const b = api.getBaby()
    api.fetchEntries({ type: 'photo' }).then(gs => {
      const map = {}
      gs.forEach(g => g.items.forEach(i => {
        if (!i.photo) return
        const m = b && b.birth_date ? ageMonthsAt(b.birth_date, i.occurred_at) : -1
        const label = m >= 0 ? m + ' 个月' : '未设出生日期'
        if (!map[label]) map[label] = []
        map[label].push({ url: i.photo, date: [i.day, api.creatorLabel(i)].filter(Boolean).join(' · ') })
      }))
      const ages = Object.keys(map).sort((x, y) => (parseInt(x) || 0) - (parseInt(y) || 0))
      this.groups = map
      this.ages = ages
      this.age = 0
      this.sel = ages.length && map[ages[0]].length ? [0, -1] : [-1, -1]
    }).catch(() => { /* 拉取失败保持空态 */ })
  },

  methods: {
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    pickAge(i) {
      this.age = i
      this.sel = this.list.length ? [0, -1] : [-1, -1]
    },

    slotPhoto(si) {
      const idx = this.sel[si]
      return idx >= 0 ? this.list[idx] : null
    },

    /* 点选照片：已选则取消；否则先填左框，再填右框 */
    pick(i) {
      const at = this.sel.indexOf(i)
      if (at > -1) {
        this.sel[at] = -1
      } else if (this.sel[0] < 0) {
        this.sel[0] = i
      } else {
        this.sel[1] = i
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

/* ---------- 内容区 ---------- */
.content { padding: 8rpx 32rpx 48rpx; }

/* 虚线提示行（v2 pg-hint，ok 为绿色变体） */
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
.pg-hint.ok { color: #2E7D4F; border-color: #BFE6CF; background: #EDF9F2; }

/* 月龄胶囊（v2 pg-chips） */
.pg-chips { display: flex; flex-wrap: wrap; gap: 16rpx; margin-bottom: 24rpx; }

/* 小节标题（v2 pg-sec） */
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

/* 左右对比框（v2 pg-photo：白底卡 + line 边 + 大圆角） */
.cmp-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20rpx;
  margin-bottom: 8rpx;
}
.cmp-slot {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  overflow: hidden;
  box-shadow: var(--sj-sh-sm);
}
.slot-frame { position: relative; }
.slot-img { width: 100%; height: 440rpx; display: block; background: var(--sj-cream); }
.cmp-empty {
  height: 440rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  text-align: center;
  font-size: 22rpx;
  color: var(--sj-faint);
  padding: 0 20rpx;
  line-height: 1.7;
  background: linear-gradient(135deg, #E9EEFB, #F0EAFB);
}
.slot-badge {
  position: absolute;
  top: 16rpx;
  right: 16rpx;
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--sj-sh-sm);
  padding: 4rpx;
  box-sizing: border-box;
}
/* 图标图片圆角与外圈曲线平行（同心）：外圈正圆 28 - 间隙 8 = 20rpx（即图片整圆） */
.slot-badge .sj-icon { border-radius: 50%; }
.cmp-label {
  display: block;
  font-size: 21rpx;
  font-weight: 700;
  color: var(--sj-sub);
  padding: 16rpx 20rpx;
  text-align: center;
  border-top: 2rpx dashed var(--sj-line);
}

/* 照片条（v2 缩略图：白描边 + sh-sm，选中 primary 描边 + soft 光环） */
.cmp-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20rpx;
  margin-bottom: 28rpx;
}
.cmp-thumb {
  width: 100%;
  height: 192rpx;
  border-radius: var(--sj-r-sm);
  border: 6rpx solid #fff;
  box-shadow: var(--sj-sh-sm);
  background: var(--sj-surface);
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.cmp-thumb:active { transform: scale(0.95); }
.cmp-thumb.on {
  border-color: var(--sj-primary);
  box-shadow: 0 0 0 6rpx var(--sj-primary-soft), var(--sj-sh-sm);
}
</style>
