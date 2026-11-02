<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回 + display 标题 + 项数 + 清空文字按钮） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">回收站</text>
      <text v-if="trash.length" class="tr-count">{{ trash.length }} 项</text>
      <text class="bk-act" hover-class="hover-press" :hover-stay-time="80" @click="clearAll">清空</text>
    </view>

    <view class="content">
      <!-- 留存规则说明（v2 pg-hint：cream 底虚线边） -->
      <view class="pg-hint">删除的记录保留 30 天 · 到期自动清理 · 恢复后回到时光轴原位置</view>

      <!-- 空态（sj-empty 封装：primary-soft 圆底大图标 + 主副文案） -->
      <sj-empty
        v-if="!trash.length"
        icon="27-fn-trash"
        text="回收站是空的"
        sub="删除的记录会先进入这里"
      />

      <!-- 回收站列表（v2 rec-card：类别色左竖条 + tint 圆底 png 图标 + 「剩 N 天 · 删除人」副文案 + 恢复/删除文字钮） -->
      <view v-else>
        <view
          class="rec-card"
          v-for="t in trash"
          :key="t.id"
          :style="{ '--rc': 'var(--sj-c-' + tokenKey(t.type) + ')', '--rs': 'var(--sj-tint-' + tokenKey(t.type) + ')' }"
        >
          <view class="rec-ic">
            <sj-icon :name="TYPES[t.type].png" :size="44" />
          </view>
          <view class="rec-info">
            <text class="ri-name">{{ typeLabel(t.type) }} · {{ t.title }}</text>
            <text class="ri-desc">剩 {{ t.daysLeft }} 天 · <text v-if="t.by">{{ t.by }} </text>删除</text>
          </view>
          <view class="tr-btn" hover-class="hover-press" :hover-stay-time="80" @click="restore(t)">
            <text>恢复</text>
          </view>
          <view class="tr-del" hover-class="hover-press" :hover-stay-time="80" @click="purge(t)">
            <text>删除</text>
          </view>
        </view>
      </view>

      <view class="scroll-end"><text>· 彻底删除后不可恢复 ·</text></view>
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import { TYPES } from '@/utils/mock.js'
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import { play } from '@/utils/sound.js'

export default {
  data() {
    return {
      TYPES,
      trash: [],
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
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    /* 展示层：note 为 mood 的历史别名，归一后才能拼出 v2 类别色/浅底令牌 */
    tokenKey(type) {
      return type === 'note' ? 'mood' : type
    },

    typeLabel(type) {
      const t = TYPES[type]
      return t ? t.label : '记录'
    },

    refresh() {
      this.trash = api.listTrash()
    },

    /* 恢复到时光轴原位置 */
    async restore(t) {
      try {
        await api.restoreEntry(t.id)
        play('S09') // 恢复成功音效（震动自动配对）
        this.refresh()
        this.$refs.ntf.show({ type: 'ok', message: '已恢复到时光轴' })
      } catch (e) {
        ui.error(e, '恢复失败')
      }
    },

    /* 彻底删除：二次确认 */
    purge(t) {
      play('S08') // 危险确认弹出音效
      ui.showModal({
        title: '彻底删除',
        content: '彻底删除后不可恢复',
        confirmText: '彻底删除',
        danger: true,
        success: async res => {
          if (!res.confirm) return
          try {
            await api.purgeEntry(t.id)
            this.refresh()
            this.$refs.ntf.show({ type: 'ok', message: '已彻底删除 · 不可恢复' })
          } catch (e) {
            this.refresh()
            ui.error(e, '删除失败')
          }
        }
      })
    },

    /* 一键清空：无数据不响应，有数据二次确认 */
    clearAll() {
      if (!this.trash.length) return
      play('S08') // 清空回收站危险确认弹出音效
      ui.showModal({
        title: '清空回收站',
        content: '将彻底删除 ' + this.trash.length + ' 条记录 · 不可恢复',
        confirmText: '清空',
        danger: true,
        success: async res => {
          if (!res.confirm) return
          try {
            await api.clearTrash()
            this.refresh()
            this.$refs.ntf.show({ type: 'ok', message: '回收站已清空' })
          } catch (e) {
            this.refresh()
            ui.error(e, '清空失败')
          }
        }
      })
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
.tr-count { font-size: 22rpx; font-weight: 700; color: var(--sj-sub); flex: none; }
.bk-act {
  flex: none;
  font-size: 26rpx;
  font-weight: 800;
  color: var(--sj-bad);
  padding: 8rpx 4rpx;
}
.bk-act:active { transform: scale(0.94); }

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

/* 回收站卡片行（v2 rec-card：白底 line 边 + 类别色左竖条 + r-md + sh-sm） */
.rec-card {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-left: 8rpx solid var(--rc, var(--sj-primary));
  border-radius: var(--sj-r-md);
  padding: 24rpx 28rpx;
  margin-bottom: 20rpx;
  box-shadow: var(--sj-sh-sm);
}
/* 图标底：v2 .rec-ic 是「tint 背景 + padding 内嵌 png」，非 flex 居中容器 */
.rec-ic {
  width: 88rpx;
  height: 88rpx;
  box-sizing: border-box;
  border-radius: 28rpx;
  padding: 16rpx;
  background: var(--rs, var(--sj-primary-soft));
  flex: none;
}
.rec-info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.ri-name {
  font-size: 28rpx;
  font-weight: 800;
  color: var(--sj-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ri-desc {
  font-size: 22rpx;
  color: var(--sj-sub);
  margin-top: 4rpx;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 恢复按钮（v2 ms-badge 观感：白底金字小胶囊） */
.tr-btn {
  flex: none;
  font-size: 22rpx;
  font-weight: 800;
  color: #B47714;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-pill);
  padding: 10rpx 24rpx;
  box-shadow: var(--sj-sh-sm);
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.tr-btn:active { transform: scale(0.94); }

/* 彻底删除（文字钮，bad 红语义） */
.tr-del {
  flex: none;
  font-size: 22rpx;
  font-weight: 800;
  color: var(--sj-bad);
  background: var(--sj-cream);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-pill);
  padding: 10rpx 24rpx;
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.tr-del:active { transform: scale(0.94); background: #FDF0F0; }

/* 空态改用 sj-empty 封装（外观对齐 v2 pg-empty），局部样式已移除 */

/* 底部说明 */
.scroll-end {
  text-align: center;
  font-size: 22rpx;
  color: var(--sj-faint);
  padding: 24rpx 0 16rpx;
  letter-spacing: 4rpx;
}
</style>
