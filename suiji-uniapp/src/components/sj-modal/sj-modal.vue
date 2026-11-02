<template>
  <view class="sj-md">
    <!-- 遮罩/居中/弹性缩放入场交给 uview-plus u-popup（center 模式）；
         卡片主体完全自组，1:1 对齐设计稿 md-card，避免覆盖库按钮/分隔线结构的偏差 -->
    <u-popup
      :show="show"
      mode="center"
      :zoom="true"
      :round="0"
      bgColor="transparent"
      :overlayStyle="maskStyle"
      :closeOnClickOverlay="false"
      :safeAreaInsetBottom="false"
      @close="onOverlayClose"
    >
      <view class="md-card" :class="{ 'md-card--danger': danger }">
        <!-- 图标圆底（v2 .md-ic：56px→112rpx 圆底；语义图标用 ctl-v2 去底切图 88rpx，
             自定义 png 仍走 v2 砖图 68rpx） -->
        <view v-if="ctlSrc || iconSrc" class="md-ic" :style="{ background: tintBg }">
          <image v-if="ctlSrc" class="md-ctl" :src="ctlSrc" mode="aspectFit" />
          <sj-icon v-else :name="iconSrc" :size="68" />
        </view>
        <text v-if="title" class="md-title">{{ title }}</text>
        <text v-if="content" class="md-desc">{{ content }}</text>
        <!-- 自定义内容区（设计稿「自定义内容对话框」md-body）；
             无描述行时标题与内容间补间距（.md-title 本身无 margin-bottom） -->
        <view v-if="$slots.default" class="md-body" :class="{ 'md-body--gap': !content }">
          <slot />
        </view>
        <!-- 按钮组（v2 .md-btns：等宽胶囊，ghost 取消 + 主色渐变/danger 红确定） -->
        <view class="md-btns">
          <view
            v-if="cancelText"
            class="md-btn md-btn--ghost"
            hover-class="md-btn--press"
            :hover-stay-time="80"
            @click="onCancel"
          ><text>{{ cancelText }}</text></view>
          <view
            class="md-btn"
            :class="danger ? 'md-btn--danger' : 'md-btn--ok'"
            hover-class="md-btn--press"
            :hover-stay-time="80"
            @click="onConfirm"
          ><text>{{ confirmText }}</text></view>
        </view>
      </view>
    </u-popup>
  </view>
</template>

<script>
/**
 * 岁记 · 对话框（uview-plus u-popup center + 自组 md-card，easycom 自动注册）
 * 外观 1:1 对齐 v2 .pg-modal/.md-card（components.html 04 反馈区「危险确认 / 信息成功 /
 * 自定义内容」三卡；styles.css L649-656、L820-822，px×2→rpx）：
 * 卡片 585rpx 宽、圆角 48rpx、sh-lg 大投影、zoom 弹性入场（缓动覆盖为 --sj-spring）；
 * 图标圆底 112rpx（danger #FDF0F0 / info #E8F4FB / ok #E2F5EA），语义切图 88rpx / 自定义 png 68rpx；
 * 标题 display 字体 34rpx ink、描述 24rpx sub 行高 1.55；
 * 按钮组：取消 ghost 白底 line 描边 sub 字、确定主色渐变白字（danger 珊瑚红渐变），
 * 等宽胶囊 22rpx 内距、27rpx/900、按压缩放。
 * 选型说明：此前走 u-modal 覆盖库「文字按钮+u-line 分隔线」结构，hover 灰底/贴边布局
 * 与设计稿偏差且覆盖点过多；改为 u-popup 承载遮罩与入场动画、卡片自组，可控性更高。
 * icon 传 'danger'|'info'|'ok' 时自动配 ctl-v2 控件概念图的去底切图
 * （64 三角警示牌 / 65 气泡 i / 66 对勾小旗，scripts/cut-ctl-icons.py 生成到
 * /static/icons/ctl/{theme}/88/）与圆底色；传其它非空值按 v2 png 图标名使用，
 * 圆底色 danger=true→红底、否则蓝底。
 * 用法：<sj-modal v-model:show="delShow" icon="danger" danger title="确认删除这条记录吗？"
 *        content="删除后将进入回收站，30 天内可恢复。" confirmText="删除" cancelText="取消"
 *        @confirm="doDel" @cancel="..." />
 */
/* 语义关键词 → { ctl-v2 切图名, 圆底色 }（角色道具语义与对话框类型一一对应） */
import { POPUP_MASK_STYLE } from '@/theme/theme.js'

const SEM = {
  danger: { ctl: '64-ctl-modal-warn', tint: '#FDF0F0' },
  info: { ctl: '65-ctl-modal-info', tint: '#E8F4FB' },
  ok: { ctl: '66-ctl-modal-ok', tint: '#E2F5EA' }
}

export default {
  name: 'SjModal',
  props: {
    /* 显隐（v-model:show） */
    show: { type: Boolean, default: false },
    /* 图标：''无 / 'danger'|'info'|'ok' 语义 / 其它为 v2 png 图标名 */
    icon: { type: String, default: '' },
    /* 标题 */
    title: { type: String, default: '' },
    /* 描述文案（自定义内容另走默认 slot） */
    content: { type: String, default: '' },
    /* 确定按钮文案 */
    confirmText: { type: String, default: '确定' },
    /* 取消按钮文案（'' = 单按钮模式） */
    cancelText: { type: String, default: '' },
    /* 危险操作：确定按钮改珊瑚红渐变，图标圆底默认红 */
    danger: { type: Boolean, default: false }
  },
  emits: ['confirm', 'cancel', 'update:show', 'close'],
  computed: {
    /* 遮罩内联样式（--sj-mask 同值，库 custom-class 不生效只能走 prop） */
    maskStyle() {
      return POPUP_MASK_STYLE
    },
    /* 语义图标 → ctl-v2 去底切图（88rpx 规格，彩色绘本图不走 color 重染） */
    ctlSrc() {
      if (!SEM[this.icon]) return ''
      return `/static/icons/ctl/${this.__theme}/88/${SEM[this.icon].ctl}.png`
    },
    /* 自定义图标（非语义且非空）按 v2 png 图标名原样使用 */
    iconSrc() {
      if (!this.icon || SEM[this.icon]) return ''
      return this.icon
    },
    /* 圆底色：语义关键词取对应色；自定义 png 按 danger 取红/蓝底（双主题相同，写死） */
    tintBg() {
      if (SEM[this.icon]) return SEM[this.icon].tint
      return this.danger ? '#FDF0F0' : '#E8F4FB'
    }
  },
  methods: {
    /* 自组卡片：点击按钮后由本组件负责关闭（emit update:show false） */
    onConfirm() {
      this.$emit('update:show', false)
      this.$emit('confirm')
    },
    onCancel() {
      this.$emit('update:show', false)
      this.$emit('cancel')
    },
    onOverlayClose() {
      this.$emit('update:show', false)
      this.$emit('close')
    }
  }
}
</script>

<style lang="scss" scoped>
/* 弹层包裹：u-popup 根为 fixed 弹窗，此层不占布局 */
.sj-md {
  width: 0;
  height: 0;
}

/* ===== 卡片（v2 .md-card：78%→585rpx、圆角 24px→48rpx、padding 22/18/18px→44/36/36rpx） ===== */
.md-card {
  width: 585rpx;
  background: rgba(255, 253, 251, 0.94);
  border-radius: 48rpx;
  padding: 44rpx 36rpx 36rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  box-shadow: var(--sj-sh-lg);
}
/* 图标圆底（v2 .md-ic 56px→112rpx，margin-bottom 10px→20rpx） */
.md-ic {
  width: 112rpx;
  height: 112rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20rpx;
}
/* ctl-v2 语义切图（88rpx，切图自带约 11% 留白，角色视觉尺寸约 78rpx） */
.md-ctl {
  width: 88rpx;
  height: 88rpx;
}
/* 标题（v2 h4：display 字体 17px→34rpx ink） */
.md-title {
  font-family: var(--sj-font-display);
  font-size: 34rpx;
  font-weight: 700;
  color: var(--sj-ink);
}
/* 描述（v2 p：12px→24rpx sub，margin 8px 0 16px → 16rpx 0 32rpx） */
.md-desc {
  font-size: 24rpx;
  color: var(--sj-sub);
  line-height: 1.55;
  margin: 16rpx 0 32rpx;
}
/* 自定义内容区（v2 .md-body：左对齐栅格 gap 8px→16rpx） */
.md-body {
  width: 100%;
  display: grid;
  gap: 16rpx;
  text-align: left;
  margin: -8rpx 0 28rpx;
}
/* 标题直连内容区（无 .md-desc 撑开）：与标题拉开 28rpx */
.md-body--gap {
  margin-top: 28rpx;
}
/* 按钮组（v2 .md-btns：flex gap 10px→20rpx） */
.md-btns {
  width: 100%;
  display: flex;
  gap: 20rpx;
}
/* 胶囊按钮（v2 .md-btns .pg-btn：flex:1、padding 11px→22rpx、13.5px→27rpx） */
.md-btn {
  flex: 1;
  padding: 22rpx 0;
  border-radius: var(--sj-r-pill);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 27rpx;
  font-weight: 900;
  transition: transform 0.2s var(--sj-spring);
}
.md-btn--press {
  transform: scale(0.94);
}
/* 取消 = ghost（白底 line 描边 sub 字） */
.md-btn--ghost {
  background: rgba(255, 253, 251, 0.94);
  border: 3rpx solid var(--sj-line);
  color: var(--sj-sub);
}
/* 确定 = 主色渐变白字（随主题换肤） */
.md-btn--ok {
  background: linear-gradient(145deg, var(--sj-primary), var(--sj-primary-deep));
  color: #fff;
  box-shadow: 0 12rpx 28rpx rgba(224, 126, 51, 0.35);
}
/* danger 变体：珊瑚红渐变 */
.md-card--danger .md-btn--danger {
  background: linear-gradient(145deg, #ef7a7a, #d95a5a);
  color: #fff;
  box-shadow: 0 12rpx 28rpx rgba(217, 90, 90, 0.3);
}
</style>

<style lang="scss">
/* 非 scoped：入场弹性缓动对齐 v2 celIn spring（u-popup 内部 u-transition 承载 center/zoom 动画） */
.sj-md {
  .u-transition {
    transition-timing-function: var(--sj-spring) !important;
  }
}
</style>
