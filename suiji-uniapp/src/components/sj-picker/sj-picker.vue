<template>
  <view class="sj-pk" @click="open">
    <!-- 默认 slot：页面传入触发器（如 <text class="pk-trigger">{{ sel }} ▾</text>） -->
    <slot />

    <!-- 点击冒泡需拦截，避免面板内点击重新触发 open -->
    <view class="sj-pk-pop" @click.stop>
      <!-- 弹层外壳（遮罩 / 圆角 48rpx / 把手 / 滑入动画）统一走 sj-popup -->
      <sj-popup
        v-model:show="visible"
        title=""
        left-text=""
        right-text=""
        :safe-area-inset-bottom="false"
        @close="onPopupClose"
      >
        <!-- 头部条（v2 .pk-bar：取消 · 标题(实时回显已选值) · 确定，2rpx 虚线分隔） -->
        <view class="pk-bar">
          <view class="pk-bar__side" @click="onCancelTap">
            <text class="pk-bar__btn" hover-class="pk-bar__btn--press" :hover-stay-time="80">{{ cancelText }}</text>
          </view>
          <view class="pk-bar__mid">
            <!-- 标题前置图标：ctl-v2 去底切图（默认 57 举旗滚轮，56rpx） -->
            <image v-if="barIconSrc" class="pk-bar__ic" :src="barIconSrc" mode="aspectFit" />
            <text class="pk-bar__title">{{ displayTitle }}</text>
          </view>
          <view class="pk-bar__side pk-bar__side--right" @click="onConfirmTap">
            <text class="pk-bar__btn" hover-class="pk-bar__btn--press" :hover-stay-time="80">{{ confirmText }}</text>
          </view>
        </view>

        <!-- 滚轮交给 uview-plus（pageInline：只出滚轮本体，弹层由 sj-popup 承载） -->
        <view class="pk-wheel">
          <view class="pk-wheel__band" />
          <view class="pk-wheel__layer">
            <u-picker
              ref="pk"
              pageInline
              :show="true"
              :showToolbar="false"
              :columns="innerColumns"
              :keyName="keyName"
              :itemHeight="44"
              :visibleItemCount="3"
              :defaultIndex="openIndex"
              :maskStyle="maskStyle"
              :immediateChange="immediateChange"
              :loading="loading"
              :round="0"
              bgColor="transparent"
              :closeOnClickOverlay="false"
              @confirm="onConfirm"
              @change="onChange"
            />
          </view>
        </view>
      </sj-popup>
    </view>
  </view>
</template>

<script>
/**
 * 岁记 · 通用列选择器（easycom 自动注册 <sj-picker>，对齐 v2 components.html「选择器」卡）
 * 弹层外壳统一走 sj-popup（遮罩 --sj-mask / 顶部圆角 48rpx / 把手条 / 滑入动画）；
 * 滚轮仍由 uview-plus u-picker 提供（pageInline 内嵌，只出滚轮本体，工具栏关掉换成自绘头部），
 * 跨端滚轮行为（选中高亮/回弹/惯性）由库保证。
 * 头部 / 滚轮外观沿用 v2 .cu-pick 规范：头部「取消 · 标题(实时回显已选值) · 确定」
 * （26rpx/800、sub 色，标题 primary-deep，2rpx 虚线分隔）；滚轮行高 44px、可见 3 行，
 * primary-soft 高亮带圆角 16rpx，选中行 ink/900、未选 faint/700，无上下渐变遮罩；
 * 色值走 var(--sj-*) 令牌随换肤。
 * 重开面板回到上次停留位置（lastIdx），columns 变化时回落到 defaultIndex。
 * 头部条标题默认前置 ctl-v2 57-ctl-picker 去底切图（举旗滚轮，56rpx，
 * scripts/cut-ctl-icons.py 生成到 /static/icons/ctl/{theme}/56/），bar-icon 传 '' 可关。
 * 用法（单列）：<sj-picker :columns="[['母乳','配方奶','辅食']]" title="喂养方式"
 *                  @confirm="e => (feedType = e.value[0])" />
 * 用法（多列）：<sj-picker :columns="[years, months]" :defaultIndex="[2, 0]" @confirm="onOk" />
 * confirm 事件负载 { value, index, indexs, items }：value 文案数组、index 索引数组、
 * items 原始条目数组（对象列取整对象，便于按 id 取值）。
 */

export default {
  name: 'SjPicker',
  props: {
    /* 每列数据：Array<String> 或 Array<{ text, ... }>（对象列配 keyName） */
    columns: { type: Array, default: () => [] },
    /* 面板标题；缺省按实时回显已选值 */
    title: { type: String, default: '' },
    /* 对象数组取显示文案的属性键名 */
    keyName: { type: String, default: 'text' },
    /* 各列初始滚动索引 */
    defaultIndex: { type: Array, default: () => [] },
    confirmText: { type: String, default: '确定' },
    cancelText: { type: String, default: '取消' },
    /* 列数据异步加载中（库在列区显示 spinner） */
    loading: { type: Boolean, default: false },
    /* 头部条标题前置 ctl-v2 切图名（'' = 无图标） */
    barIcon: { type: String, default: '57-ctl-picker' },
    /* 手指松开即触发 change（默认开，标题实时回显更跟手） */
    immediateChange: { type: Boolean, default: true },
    /* 外部受控：置 true 直接展开面板 */
    show: { type: Boolean, default: false }
  },
  emits: ['confirm', 'cancel', 'change', 'open'],
  data() {
    return {
      visible: false,
      /* 打开时下发给 u-picker 的定位索引（打开期间保持不变，避免滚动中被重置） */
      openIndex: [],
      /* 上次停留 / 确认的索引，重开时恢复位置 */
      lastIdx: [],
      /* 已选值文案（头部标题实时回显） */
      selText: '',
      /* 本次关闭是否由「确定」发起：close 事件据此决定是否再发 cancel */
      confirmed: false
    }
  },
  computed: {
    /* 当前主题下的标题前置切图（彩色绘本图，不走 color 重染） */
    barIconSrc() {
      if (!this.barIcon) return ''
      return `/static/icons/ctl/${this.__theme}/56/${this.barIcon}.png`
    },
    /* 单列数组直接传；页面可能只传 ['a','b']，包成 [['a','b']] 统一成列数组 */
    innerColumns() {
      const c = this.columns
      if (!c.length) return [[]]
      return Array.isArray(c[0]) ? c : [c]
    },
    /* defaultIndex 按各列长度收敛（页面传入可能越界） */
    safeDefaultIndex() {
      const idx = this.defaultIndex || []
      return this.innerColumns.map((col, i) => {
        const n = (col && col.length) || 1
        const d = Number(idx[i]) || 0
        return Math.min(Math.max(d, 0), n - 1)
      })
    },
    /* v2 .cu-pick .pk-wheel 无上下渐变遮罩，清掉平台默认 mask */
    maskStyle() {
      return 'background: none;'
    },
    displayTitle() {
      return this.title + (this.selText ? ' · ' + this.selText : '')
    }
  },
  watch: {
    show(v) {
      if (v) this.open()
      else this.visible = false
    },
    columns() {
      this.lastIdx = []
      this.refreshSel(this.safeDefaultIndex)
    }
  },
  methods: {
    /* 打开位置：上次停留（收敛到当前列长）优先，否则用页面 defaultIndex */
    resolveIndex() {
      const src = this.lastIdx.length ? this.lastIdx : this.safeDefaultIndex
      return this.innerColumns.map((col, i) => {
        const n = (col && col.length) || 1
        const d = Number(src[i]) || 0
        return Math.min(Math.max(d, 0), n - 1)
      })
    },
    open() {
      if (this.visible) return
      this.openIndex = this.resolveIndex()
      this.selText = ''
      this.refreshSel(this.openIndex)
      this.visible = true
      this.$emit('open')
    },
    close() {
      this.visible = false
    },
    itemsOf(indexs) {
      return this.innerColumns.map((col, i) => (col || [])[indexs[i]])
    },
    textOf(it) {
      if (it == null) return ''
      return typeof it === 'object' ? String(it[this.keyName] ?? '') : String(it)
    },
    /* 已选索引 → 标题回显文案（多列以「 / 」分隔） */
    refreshSel(indexs) {
      const parts = this.itemsOf(indexs).map(this.textOf).filter(s => s !== '')
      this.selText = parts.join(' / ')
    },
    /* 头部按钮：取消直接收起（cancel 由 close 统一发），确定走库内 confirm() */
    onCancelTap() {
      this.visible = false
    },
    onConfirmTap() {
      const pk = this.$refs.pk
      if (pk && pk.confirm) pk.confirm()
      else this.onConfirm({ indexs: this.openIndex })
    },
    onChange(e) {
      const idx = e.indexs || []
      this.lastIdx = idx
      this.refreshSel(idx)
      this.$emit('change', { value: e.value, index: idx, items: this.itemsOf(idx) })
    },
    onConfirm(e) {
      const idx = (e && e.indexs) || this.openIndex
      this.lastIdx = idx
      this.confirmed = true
      this.visible = false
      this.$emit('confirm', {
        value: (e && e.value) || this.itemsOf(idx).map(this.textOf),
        index: idx,
        indexs: idx,
        items: this.itemsOf(idx)
      })
    },
    /* 遮罩点击 / 取消按钮 / 外部收起统一走这里；确定关闭不重复发 cancel */
    onPopupClose() {
      const byConfirm = this.confirmed
      this.confirmed = false
      if (!byConfirm) this.$emit('cancel')
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：不破坏页面原 flex 布局（MP 不支持 display:contents） */
.sj-pk { display: inline-flex; }
/* 弹层包裹：sj-popup 根为 fixed 弹层，此层不占布局 */
.sj-pk-pop { width: 0; height: 0; }
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
.pk-bar__btn {
  padding: 8rpx 12rpx;
  transition: transform 0.2s var(--sj-spring);
}
.pk-bar__btn--press {
  opacity: 0.55;
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
/* 选中行整行贯通高亮带（3 行×44px，居中行 44~88px），纯视觉无事件 */
.pk-wheel__band {
  position: absolute;
  z-index: 0;
  left: 0;
  right: 0;
  top: 44px;
  height: 44px;
  background: var(--sj-primary-soft);
  border-radius: 16rpx;
  pointer-events: none;
}
/* 滚轮抬到色带之上，保证选中文字不被遮挡 */
.pk-wheel__layer {
  position: relative;
  z-index: 1;
}
</style>

<style lang="scss">
/* ============ 非 scoped：uview-plus 滚轮条目样式 ============
 * u-picker 内部节点无法被 scoped 样式命中，以 .sj-pk-pop 为命名空间覆盖，
 * 色值走 var(--sj-*) 令牌（随页面根节点 themeVars 实时换肤）。
 * v2 .pk-wheel：13.5px→27rpx/700 faint；选中 .sel ink/900 */
.sj-pk-pop {
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
