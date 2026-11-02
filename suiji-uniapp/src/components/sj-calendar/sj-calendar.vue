<template>
  <view class="sj-cl">
    <!-- 交互内核交给 uview-plus u-calendar（月视图渲染/区间两次点选/翻月/禁用拦截由库保证） -->
    <u-calendar
      :show="show"
      :mode="mode"
      :defaultDate="defaultDate"
      :minDate="innerMin"
      :maxDate="innerMax"
      :allowSameDay="allowSameDay"
      :monthSwitch="true"
      :color="themeColor"
      :todayColor="todayColor"
      round="48rpx"
      confirmText="确定"
      startText="开始"
      endText="结束"
      @confirm="onConfirm"
      @close="onClose"
    />
  </view>
</template>

<script>
/**
 * 岁记 · 日历弹层（uview-plus u-calendar 封装，easycom 自动注册）
 * 外观严格对齐 v2 .cu-cal（components.html L600-638「月视图单选 / 区间选择 / 用法速查」；
 * styles.css L825-843）：选中态主色实心圆白字特粗 + 暖橙投影（d-sel）、
 * 区间中间日主色浅底带（库 rangeMiddleColor 自动取主色 90% 浅化 ≈ --sj-primary-soft）、
 * 今日文字 primary-deep（todayColor prop）；底部弹层圆角 24px→48rpx（round prop）、
 * 遮罩对齐 v2 popup 规范（暖可可半透，命名空间覆盖 u-overlay）。
 * 库主题 prop 名为 color（对底部确定按钮与选中日期生效），传 palette 主色随换肤；
 * monthSwitch=true 开启单月视图 + 头部 ‹ › 翻月/翻年箭头（库默认 false 为长列表滚动模式，
 * 无箭头即"不能切换年月"的根因）；配合默认放宽的 ±3/+2 年范围，年月切换自由；
 * 确定按钮经命名空间升级为 v2 pg-btn 145deg 主色渐变（库仅内联单色底）。
 * confirm 事件按库原样日期数据透传（单选 [date]/区间 [start,end,...]）。
 * 用法：<sj-calendar :show="calShow" mode="single" :defaultDate="today"
 *        :maxDate="maxPlus30" @confirm="onCal" @close="calShow=false" />
 */
import { palette } from '@/theme/theme.js'

export default {
  name: 'SjCalendar',
  props: {
    /* 显隐（父页面控制，库 close/confirm 后由父置 false） */
    show: { type: Boolean, default: false },
    /* 'single' 单选 | 'range' 区间 */
    mode: { type: String, default: 'single' },
    /* 默认选中日期：String('YYYY-MM-DD') 或 Array（range 必须数组） */
    defaultDate: { type: [Array, String, Date], default: null },
    /* 最小可选日期（时间戳或 'YYYY-MM-DD'；0 = 默认往前 3 年，保证可翻到往年） */
    minDate: { type: [String, Number], default: 0 },
    /* 最大可选日期（时间戳或 'YYYY-MM-DD'；0 = 默认往后 2 年，保证可翻到未来年月） */
    maxDate: { type: [String, Number], default: 0 },
    /* 区间模式允许起止同一天 */
    allowSameDay: { type: Boolean, default: false }
  },
  emits: ['confirm', 'close'],
  computed: {
    /* 主题色（选中日/确定按钮）取当前主题 primary，库 prop 只接受静态色值 */
    themeColor() {
      return palette(this.__theme)['primary']
    },
    /* 今日文字高亮 = v2 d-today 的 primary-deep */
    todayColor() {
      return palette(this.__theme)['primary-deep']
    },
    /* 修复库默认范围过窄（仅今天~+2 月、无法翻往年/未来月）：
       未显式传值时默认「往前 3 年 ~ 往后 2 年」，月份轴覆盖 5 年，翻年月自由 */
    innerMin() {
      if (this.minDate) return this.minDate
      const d = new Date()
      d.setFullYear(d.getFullYear() - 3)
      return d.getTime()
    },
    innerMax() {
      if (this.maxDate) return this.maxDate
      const d = new Date()
      d.setFullYear(d.getFullYear() + 2)
      return d.getTime()
    }
  },
  methods: {
    /* 库 confirm 载荷（日期数据数组）原样透传；父页面负责关闭 */
    onConfirm(dates) {
      this.$emit('confirm', dates)
    },
    onClose() {
      this.$emit('close')
    }
  }
}
</script>

<style lang="scss" scoped>
/* 弹层包裹：u-calendar 根为 fixed 弹窗，此层不占布局 */
.sj-cl {
  width: 0;
  height: 0;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-cl 命名空间覆盖 u-calendar 内部节点 ============
 * 对齐 v2 .cu-cal 与 popup 规范；色值走 var(--sj-*) 令牌随换肤。 */
.sj-cl {
  /* 遮罩（v2 sheet 规范：暖可可半透，同 sj-datetime-picker） */
  .u-overlay {
    background: rgba(74, 50, 38, 0.42) !important;
  }
  /* 面板底色 = surface */
  .u-popup__content {
    background: rgba(255, 253, 251, 0.94) !important;
  }
  /* 头部标题：display 字体 ink（v2 .cu-cal-hd b） */
  .u-calendar-header__title,
  .u-calendar-header__subtitle {
    font-family: var(--sj-font-display);
    color: var(--sj-ink);
    font-weight: 700;
  }
  /* 星期行：faint 特粗（v2 .cu-cal-wk span） */
  .u-calendar-header__weekdays__weekday {
    color: var(--sj-faint);
    font-weight: 800;
  }
  /* 选中日：字重 900 + 暖橙投影（v2 .d-sel；底色/白字由库 color prop 内联保证） */
  .u-calendar-month__days__day__select--selected .u-calendar-month__days__day__select__info,
  .u-calendar-month__days__day__select__info--selected {
    font-weight: 900;
  }
  .u-calendar-month__days__day__select--selected {
    box-shadow: 0 8rpx 20rpx rgba(247, 161, 92, 0.35);
  }
  /* 确定按钮：库单色内联底之上叠 v2 pg-btn 主色渐变 */
  .u-calendar__confirm .u-button {
    background-image: linear-gradient(145deg, var(--sj-primary), var(--sj-primary-deep)) !important;
    box-shadow: 0 12rpx 28rpx rgba(224, 126, 51, 0.35);
    font-weight: 900;
  }
}
</style>
