<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形白底返回 + display 标题） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">备份管理</text>
    </view>

    <view class="content">
      <!-- 云端存储状态（v2 pg-sec + set-group 字段行：左标签右说明，虚线分隔） -->
      <view class="pg-sec"><text>云端存储状态</text></view>
      <view class="set-group">
        <view class="field-row">
          <text class="fr-label">数据存储</text>
          <text class="fr-val">云端加密保存 · 多台设备都能看</text>
        </view>
        <view class="field-row">
          <text class="fr-label">每天自动备份</text>
          <text class="fr-val">{{ info.lastAutoAt || '已开启 · 每日 03:00' }}</text>
        </view>
      </view>

      <!-- 云端数据卡（v2 grow-card；原型假配额/假进度已移除，展示真实记录数） -->
      <view class="grow-card">
        <view class="gc-head">
          <text class="gc-title">云端数据</text>
          <text class="gc-sub">已保存 {{ total }} 条记录 · 加密存储更安全</text>
        </view>
      </view>

      <!-- 导出加密副本（v2 pg-sec + set-group 字段行 + pg-btn 通栏） -->
      <view class="pg-sec"><text>导出数据副本（可选）</text></view>
      <view class="set-group">
        <view class="field-row">
          <text class="fr-label">副本文件</text>
          <text class="fr-val">加密压缩包 · 打开密码不会一起导出</text>
        </view>
        <view class="field-row">
          <text class="fr-label">上次导出</text>
          <text class="fr-val">{{ info.lastExportAt || '尚未导出' }}</text>
        </view>
      </view>
      <sj-button
        class="pg-btn"
        block
        size="lg"
        :loading="busy"
        text="导出数据副本"
        @click="doBackup"
      />

      <!-- 底部合规说明（v2 pg-hint：cream 底虚线边） -->
      <view class="pg-hint hint-gap">换新手机：登录后记录自动恢复 · 副本的打开密码请自行保管，遗失无法找回</view>
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'

export default {
  data() {
    return {
      statusBarHeight: 20,
      /* 导出中：全量快照序列化 + 落盘，期间禁止重复点击生成多份副本 */
      busy: false,
      /* 云端存储/副本导出信息：上次自动备份、上次导出时间 */
      info: api.getBackupInfo(),
      /* 真实记录条数（onShow 从时光轴统计） */
      total: 0
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  onShow() {
    this.info = api.getBackupInfo()
    api.fetchEntries().then(groups => {
      let n = 0
      groups.forEach(g => { n += g.items.length })
      this.total = n
    }).catch(() => { /* 拉取失败保持 0 */ })
  },

  methods: {
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    /* 导出加密副本：从云端缓存快照生成数据副本文件 */
    async doBackup() {
      if (this.busy) return
      this.busy = true
      /* 快照序列化 + 写盘（App 端走 plus.io，H5 端触发下载）整段无反馈，全屏阻断等待 */
      const ld = ui.loading('正在生成数据副本…', { sub: '记录较多时可能需要十几秒' })
      try {
        const r = await api.exportBackup('')
        this.$refs.ntf.show({ type: 'ok', message: '数据副本已生成 · ' + r.filename, duration: 2500 })
        this.info = api.getBackupInfo()
      } catch (e) {
        ui.error(e, '导出失败')
      } finally {
        ld.close()
        this.busy = false
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

/* 分组小标题（v2 pg-sec：前置圆角短条 + 小字） */
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

/* 设置分组（v2 set-group：白底 line 边 r-md + 虚线字段行） */
.set-group {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 12rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: var(--sj-sh-sm);
}
.field-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  padding: 22rpx 4rpx;
  border-top: 2rpx dashed var(--sj-line);
}
.field-row:first-of-type { border-top: none; }
.fr-label { font-size: 26rpx; font-weight: 600; color: var(--sj-ink); flex: none; }
.fr-val { font-size: 23rpx; color: var(--sj-sub); text-align: right; }

/* 云端配额卡（v2 grow-card + pg-prog + pg-quota） */
.grow-card {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 28rpx 32rpx;
  margin-bottom: 24rpx;
  box-shadow: var(--sj-sh-sm);
}
.gc-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 16rpx;
}
.gc-title { font-size: 29rpx; font-weight: 900; color: var(--sj-ink); }
.gc-sub { font-size: 22rpx; font-weight: 700; color: var(--sj-sub); }
/* 主按钮：外观由 sj-button（block size=lg）统一提供，此处仅保留布局 */
.pg-btn { display: flex; }

/* 提示文案行（v2 pg-hint：cream 底 + 虚线边） */
.pg-hint {
  font-size: 23rpx;
  color: var(--sj-sub);
  background: var(--sj-cream);
  border: 2rpx dashed var(--sj-line);
  border-radius: 24rpx;
  padding: 16rpx 24rpx;
  line-height: 1.5;
}
.hint-gap { margin-top: 24rpx; }
</style>
