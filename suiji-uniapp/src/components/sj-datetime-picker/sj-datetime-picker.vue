<template>
  <view class="sj-dtp" @click="open">
    <!-- 默认 slot：页面传入触发器（如 <text class="time-input">…</text>） -->
    <slot />

    <!-- 点击冒泡需拦截，避免面板内点击重新触发 open -->
    <view class="sj-dtp-pop" @click.stop>
      <!-- 弹层外壳（遮罩 / 圆角 48rpx / 把手 / 滑入动画）统一走 sj-popup（同 sj-picker），
           头部条自绘以便前置 ctl-v2 切图 -->
      <sj-popup
        v-model:show="visible"
        title=""
        left-text=""
        right-text=""
        :safe-area-inset-bottom="false"
        @close="visible = false"
      >
        <!-- 头部条（v2 .pk-bar：取消 · 图标+标题(实时回显已选值) · 确定，2rpx 虚线分隔） -->
        <view class="pk-bar">
          <view class="pk-bar__side" @click="onCancelTap">
            <text class="pk-bar__btn" hover-class="pk-bar__btn--press" :hover-stay-time="80">取消</text>
          </view>
          <view class="pk-bar__mid">
            <!-- 标题前置图标：ctl-v2 去底切图（date 73 举日历牌 / time 57 举旗滚轮，56rpx） -->
            <image v-if="barIconSrc" class="pk-bar__ic" :src="barIconSrc" mode="aspectFit" />
            <text class="pk-bar__title">{{ displayTitle }}</text>
          </view>
          <view class="pk-bar__side pk-bar__side--right" @click="onConfirmTap">
            <text class="pk-bar__btn" hover-class="pk-bar__btn--press" :hover-stay-time="80">确定</text>
          </view>
        </view>

        <!-- 滚轮交给 uview-plus（pageInline：只出滚轮本体，弹层由 sj-popup 承载） -->
        <view class="pk-wheel">
          <!-- 每列独立主题浅底高亮带（3 行×44px 的居中行，纯视觉无事件） -->
          <view class="sj-dtp-bands">
            <view v-for="n in colCount" :key="n" class="sj-dtp-band" />
          </view>
          <view class="pk-wheel__layer">
            <u-datetime-picker
              ref="dtp"
              pageInline
              :show="true"
              :showToolbar="false"
              :mode="mode === 'date' ? 'date' : 'time'"
              :modelValue="dtpValue"
              :minDate="mode === 'date' ? minTs : undefined"
              :maxDate="mode === 'date' ? maxTs : undefined"
              :itemHeight="44"
              :visibleItemCount="3"
              :maskStyle="maskStyle"
              @confirm="onConfirm"
              @change="onPickChange"
            />
          </view>
        </view>
      </sj-popup>
    </view>
  </view>
</template>

<script>
/**
 * 岁记 · 滚轮日期/时间选择器（easycom 自动注册）
 * 弹层外壳走 sj-popup（遮罩 / 顶部圆角 48rpx / 把手条 / 滑入动画，同 sj-picker），
 * 滚轮仍由 uview-plus u-datetime-picker 提供（pageInline 内嵌，工具栏关掉换成自绘头部），
 * 跨端滚轮行为（选中高亮/回弹/惯性）由库保证；「确定」经 ref 调库 confirm()，
 * 载荷与库工具栏按钮完全一致。
 * 外观 1:1 对齐 v2 .cu-pick 选择器卡（components.html L332-341；styles.css L802-807，px×2→rpx）：
 * 头部「取消 · 图标+标题(实时回显已选值) · 确定」（26rpx/800、取消/确定 sub 色、
 * 标题 primary-deep；2rpx 虚线分隔），滚轮行高 44px→itemHeight=44、可见 3 行
 * （v2 132px/44px），每列满宽 primary-soft 高亮带圆角 16rpx，选中行 ink/900、
 * 未选 faint/700（v2 无上下渐变遮罩，maskStyle 置 none）；色值走 var(--sj-*) 令牌随换肤。
 * 头部条标题默认前置 ctl-v2 去底切图（date → 73-ctl-calendar 举日历牌，
 * time → 57-ctl-picker 举旗滚轮，56rpx，scripts/cut-ctl-icons.py 生成到
 * /static/icons/ctl/{theme}/56/），bar-icon 传 '' 可关、传名可换。
 * 用法：<sj-datetime-picker mode="date" :value="birthDate" @change="onDateChange">
 *         <text class="time-input">{{ birthDate }} ▾</text>
 *       </sj-datetime-picker>
 * change 事件负载 { detail: { value } }，与原生 picker 处理器签名完全兼容。
 */

const pad = n => String(n).padStart(2, '0')

export default {
  name: 'SjDatetimePicker',
  props: {
    /* 'date' | 'time' */
    mode: { type: String, default: 'date' },
    /* 'YYYY-MM-DD' 或 'HH:mm'，空/非法则回落到今天/当前时间 */
    value: { type: String, default: '' },
    /* 面板标题，缺省按 mode 取「选择日期 / 选择时间」 */
    title: { type: String, default: '' },
    /* 头部条标题前置 ctl-v2 切图名（'' = 按 mode 自动取 73/57；传 'none' 关闭） */
    barIcon: { type: String, default: '' },
    /* 可选范围（'YYYY-MM-DD'，仅 date 模式生效）：
       默认上限是「今年+10」，预产期/生日一类的页面必须自己收成「今天」，
       否则能选出未来的出生日期，年龄与生长曲线全算反 */
    min: { type: String, default: '' },
    max: { type: String, default: '' }
  },
  data() {
    return {
      visible: false,
      /* 弹层当前基准值：打开时取自 value prop；用户滚动不回填
         （由库内部 innerValue 跟踪），避免 watch 反复重建列 */
      dtpValue: '',
      /* 标题实时回显的已选值文案（对齐设计稿 refreshTitle） */
      selText: ''
    }
  },
  computed: {
    titleText() {
      return this.title || (this.mode === 'date' ? '选择日期' : '选择时间')
    },
    displayTitle() {
      return this.titleText + (this.selText ? ' · ' + this.selText : '')
    },
    colCount() {
      return this.mode === 'date' ? 3 : 2
    },
    /* 头部条前置切图：显式传名优先，'' 按 mode 自动（date 73 / time 57），'none' 关闭 */
    barIconSrc() {
      const name = this.barIcon || (this.mode === 'date' ? '73-ctl-calendar' : '57-ctl-picker')
      if (name === 'none') return ''
      return `/static/icons/ctl/${this.__theme}/56/${name}.png`
    },
    /* v2 .cu-pick .pk-wheel 无上下渐变遮罩（仅 overflow 裁切 + 明暗字色分层），清掉平台默认 mask */
    maskStyle() {
      return 'background: none;'
    },
    minTs() {
      return this.toTs(this.min) || new Date(2000, 0, 1).getTime()
    },
    maxTs() {
      return this.toTs(this.max) || new Date(new Date().getFullYear() + 10, 11, 31, 23, 59).getTime()
    }
  },
  methods: {
    /* 'YYYY-MM-DD' → 本地时间戳；空/非法返回 0（调用方按「未设置」处理） */
    toTs(s) {
      const mt = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s || ''))
      if (!mt) return 0
      const t = new Date(+mt[1], +mt[2] - 1, +mt[3]).getTime()
      return isNaN(t) ? 0 : t
    },
    clampTs(t) {
      return Math.max(Math.min(t, this.maxTs), this.minTs)
    },
    open() {
      const v = this.innerValueFromProp()
      this.dtpValue = this.mode === 'date' ? this.clampTs(v) : v
      this.selText = this.fmtSel(this.dtpValue)
      this.visible = true
    },
    /* u-datetime-picker 约定：date 模式用时间戳，time 模式用 'HH:mm' 字符串 */
    innerValueFromProp() {
      if (this.mode === 'date') {
        const mt = /^(\d{4})-(\d{2})-(\d{2})$/.exec(this.value || '')
        if (mt) {
          const t = new Date(+mt[1], +mt[2] - 1, +mt[3]).getTime()
          if (!isNaN(t)) return t
        }
        return Date.now()
      }
      const mt = /^(\d{2}):(\d{2})$/.exec(this.value || '')
      if (mt) return this.value
      const now = new Date()
      return pad(now.getHours()) + ':' + pad(now.getMinutes())
    },
    /* 已选值 → 标题回显文案（date: 2026年10月23日 / time: 14:30） */
    fmtSel(v) {
      if (this.mode === 'date') {
        const d = new Date(v)
        if (isNaN(d.getTime())) return ''
        return d.getFullYear() + '年' + (d.getMonth() + 1) + '月' + d.getDate() + '日'
      }
      return typeof v === 'string' ? v : ''
    },
    /* 滚动选择时实时回显标题 */
    onPickChange(e) {
      this.selText = this.fmtSel(e.value)
    },
    /* 头部「取消」：收起面板（不回填值） */
    onCancelTap() {
      this.visible = false
    },
    /* 头部「确定」：调库 confirm() 触发 confirm 事件（载荷与库工具栏按钮一致） */
    onConfirmTap() {
      const dtp = this.$refs.dtp
      if (dtp && dtp.confirm) dtp.confirm()
      else this.visible = false
    },
    /* 库 confirm 事件：关面板并按 v2 契约格式化回传 */
    onConfirm(e) {
      this.visible = false
      let value
      if (this.mode === 'date') {
        const d = new Date(e.value)
        value = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
      } else {
        /* time 模式 confirm 载荷已是 'HH:mm' */
        value = e.value
      }
      this.$emit('change', { detail: { value } })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：不破坏页面原 flex 布局（MP 不支持 display:contents，用普通 view，类名可被页面样式覆盖） */
.sj-dtp { display: inline-flex; }
/* 弹层包裹：sj-popup 根为 fixed 弹层，此层不占布局 */
.sj-dtp-pop { width: 0; height: 0; }
/* 头部条（v2 .pk-bar：padding 12px 16px→24/32rpx、13px→26rpx/800，虚线分隔） */
.pk-bar {
  display: flex;
  align-items: center;
  padding: 20rpx 32rpx;
  font-size: 26rpx;
  font-weight: 800;
  color: var(--sj-sub);
  border-bottom: 2rpx dashed var(--sj-line);
}
/* 两侧等宽占位，保证标题居中 */
.pk-bar__side {
  flex: 1;
  display: flex;
}
.pk-bar__side--right {
  justify-content: flex-end;
}
.pk-bar__btn {
  padding: 8rpx 12rpx;
  transition: transform 0.2s var(--sj-spring);
}
.pk-bar__btn--press {
  opacity: 0.55;
}
/* 标题区：前置图标 + 标题整体居中 */
.pk-bar__mid {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
}
.pk-bar__ic {
  width: 56rpx;
  height: 56rpx;
  margin-right: 12rpx;
  flex: none;
}
.pk-bar__title {
  color: var(--sj-primary-deep);
  text-align: center;
}
/* 滚轮区：v2 .pk-wheel 满宽，底部留白由外壳安全区接续 */
.pk-wheel {
  position: relative;
  padding-bottom: 24rpx;
}
/* 每列独立高亮带（3 行×44px 的居中行 44~88px），纯视觉无事件 */
.sj-dtp-bands {
  position: absolute;
  z-index: 0;
  left: 0;
  right: 0;
  top: 44px;
  height: 44px;
  display: flex;
  pointer-events: none;
}
.sj-dtp-band {
  flex: 1;
  background: var(--sj-primary-soft);
  border-radius: 16rpx;
}
/* 滚轮抬到色带之上，保证选中文字不被遮挡 */
.pk-wheel__layer {
  position: relative;
  z-index: 1;
}
</style>

<style lang="scss">
/* ============ 非 scoped：uview-plus 滚轮条目样式 ============
 * u-datetime-picker 内部节点无法被 scoped 样式命中，以 .sj-dtp-pop 为命名空间覆盖，
 * 色值走 var(--sj-*) 令牌（随页面根节点 themeVars 实时换肤）。
 * v2 .pk-wheel：13.5px→27rpx/700 faint；选中 .sel ink/900 */
.sj-dtp-pop {
  .u-picker__view__column__item {
    font-size: 27rpx !important;
    font-weight: 700 !important;
    color: var(--sj-faint) !important;
  }
  .u-picker__view__column__item--selected {
    font-weight: 900 !important;
    color: var(--sj-ink) !important;
  }
}
</style>
