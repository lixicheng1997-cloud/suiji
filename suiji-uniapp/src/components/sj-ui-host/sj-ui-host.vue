<template>
  <view class="sj-ui-host">
    <!-- ================= 居中弹窗（交给 sj-modal：u-popup center + v2 md-card，主题令牌随换肤） ================= -->
    <sj-modal
      :show="dialog.show"
      :icon="dialog.payload.icon || (dialog.payload.danger ? 'danger' : 'info')"
      :title="dialog.payload.title"
      :content="dialog.payload.content"
      :confirmText="dialog.payload.confirmText"
      :cancelText="dialog.payload.showCancel ? dialog.payload.cancelText : ''"
      :danger="dialog.payload.danger"
      @confirm="closeDialog(true)"
      @cancel="closeDialog(false)"
      @close="closeDialog(false)"
    >
      <!-- editable 输入区：sj-input（u-input）box 形态，弹窗显示后由 host 延时置焦 -->
      <sj-input
        v-if="dialog.payload.editable"
        v-model="dialog.input"
        variant="box"
        :focus="dialog.focus"
        :placeholder="dialog.payload.placeholder"
      />
    </sj-modal>

    <!-- ================= 底部动作面板（遮罩/滑入/安全区交给 u-popup，条目按 v2 卡片观感自组） ================= -->
    <u-popup
      :show="sheet.show"
      mode="bottom"
      :round="0"
      bgColor="transparent"
      :overlayStyle="maskStyle"
      :safeAreaInsetBottom="false"
      :closeOnClickOverlay="true"
      @close="closeSheet"
    >
      <view class="asheet">
        <view class="as-grab" />
        <view v-if="sheet.payload.alert" class="as-title">{{ sheet.payload.alert }}</view>
        <view
          v-for="(it, i) in sheet.payload.itemList"
          :key="i"
          class="as-item"
          :class="{ danger: it.danger }"
          hover-class="hover-press"
          :hover-stay-time="80"
          @click="pickSheet(i)"
        >
          <view class="as-main">
            <text class="as-label">{{ it.label }}</text>
            <text v-if="it.sub" class="as-sub">{{ it.sub }}</text>
          </view>
        </view>
        <view class="as-cancel" hover-class="hover-press" :hover-stay-time="80" @click="closeSheet">
          <text>取消</text>
        </view>
      </view>
    </u-popup>

    <!-- ================= 轻提示（sj-notify 顶部横幅，承接 ui.toast 事件） ================= -->
    <sj-notify ref="notify" />

    <!-- ================= 全屏加载（ui.loading() 驱动，见 utils/ui.js） ================= -->
    <sj-loading :show="ld.show" :text="ld.text" :sub="ld.sub" :percent="ld.percent" />
  </view>
</template>

<script>
/**
 * 岁记 · UI 浮层宿主（easycom 自动注册）
 * 单文件承载 弹窗 + ActionSheet + 轻提示横幅 + 全屏加载 四种浮层，配合 utils/ui.js 事件协议：
 *   sj-ui-dialog / sj-ui-sheet / sj-ui-toast / sj-ui-loading 入向，sj-ui-cb 出向。
 * 轻提示由内嵌 sj-notify 渲染（页面内提示请直接挂 <sj-notify ref="ntf" /> 调用，
 * 本宿主仅承接 http.js / ui.error 等非组件场景的兜底提示）。
 * 全屏加载由 ui.loading(text) 调用，页面无需自己铺 <sj-loading> 标签。
 * 控件来源：弹窗走 sj-modal（u-popup center + v2 md-card），动作面板走 u-popup bottom
 * （遮罩/滑入/安全区由库负责，条目按 v2 卡片观感自组），不再自绘 .overlay/.dialog。
 * 多页栈守卫：utils/ui.js 的 pending 按 cbId 一次性消费（get 后 delete），
 * 栈中多个 host 同时响应也只有一个结果生效，无需页面 onShow/onHide 激活标志。
 * 页面用法：在页面模板末尾放 <sj-ui-host /> 即可。
 */
import { POPUP_MASK_STYLE } from '@/theme/theme.js'
import { loadingState } from '@/utils/ui.js'

export default {
  name: 'SjUiHost',
  computed: {
    /* 动作面板遮罩色（与 sj-modal 同一令牌，u-popup 只认 overlayStyle 内联下发） */
    maskStyle() {
      return POPUP_MASK_STYLE
    }
  },
  data() {
    return {
      /* 弹窗状态 */
      dialog: {
        show: false,
        cbId: 0,
        input: '',
        focus: false,
        payload: { title: '', content: '', confirmText: '确定', cancelText: '取消', showCancel: true, danger: false, editable: false, placeholder: '', icon: '' }
      },
      /* 动作面板状态 */
      sheet: {
        show: false,
        cbId: 0,
        payload: { itemList: [], alert: '' }
      },
      /* 全屏加载：镜像 utils/ui.js 的在途任务栈顶项（无任务时 show=false） */
      ld: { show: false, text: '', sub: '', percent: null }
    }
  },
  created() {
    /* 栈顶守卫：uni.$emit 会广播给页面栈中所有 host，若后台页面的 host 也置 show=true，
     * 返回该页时浮层会「自己打开」。仅所在页面仍为栈顶的 host 才响应展示事件。 */
    this._page = getCurrentPages().slice(-1)[0]
    this._isTop = () => {
      const ps = getCurrentPages()
      return ps.length > 0 && ps[ps.length - 1] === this._page
    }
    /* 保存 handler 引用，供 beforeUnmount 精确注销 */
    this._onDialog = ({ payload, cbId }) => {
      if (!this._isTop()) return
      uni.$emit('sj-ui-dialog-ack')   // 告知 utils/ui.js 已有宿主接管
      this.dialog.payload = payload
      this.dialog.cbId = cbId
      this.dialog.input = ''
      this.dialog.focus = false
      this.dialog.show = true
      /* editable 弹窗自动聚焦：需等 sj-modal 的 u-popup 入场动画播完再置 focus，
       * 否则 H5 / 小程序端会把 focus 请求吞掉（对齐 uni.showModal editable 的默认行为） */
      clearTimeout(this._focusTimer)
      if (payload && payload.editable) {
        this._focusTimer = setTimeout(() => { this.dialog.focus = true }, 320)
      }
    }
    this._onSheet = ({ payload, cbId }) => {
      if (!this._isTop()) return
      this.sheet.payload = payload
      this.sheet.cbId = cbId
      this.sheet.show = true
    }
    this._onToast = ({ payload }) => {
      if (!this._isTop()) return
      uni.$emit('sj-ui-toast-ack')   // 告知 utils/ui.js 已有宿主接管
      this.$refs.notify.show({
        type: payload.type || 'ok',
        message: payload.title,
        duration: payload.duration
      })
    }
    /* 全屏加载：不加栈顶守卫——后台页的 host 同样镜像最新状态，
     * 返回该页时才不会顶着一张早已结束的旧遮罩。 */
    this._onLoading = ({ item }) => {
      uni.$emit('sj-ui-loading-ack')
      if (!item) { this.ld.show = false; return }
      this.ld = { show: true, text: item.text, sub: item.sub, percent: item.percent }
    }
    uni.$on('sj-ui-dialog', this._onDialog)
    uni.$on('sj-ui-sheet', this._onSheet)
    uni.$on('sj-ui-toast', this._onToast)
    uni.$on('sj-ui-loading', this._onLoading)
    /* 进入本页前就已打开的全屏加载（如登录 → 首页的 bootstrap 在途）：
     * 新挂载的 host 补一次同步，否则这段等待没有任何反馈。 */
    this._onLoading({ item: loadingState() })
  },
  beforeUnmount() {
    clearTimeout(this._focusTimer)
    uni.$off('sj-ui-dialog', this._onDialog)
    uni.$off('sj-ui-sheet', this._onSheet)
    uni.$off('sj-ui-toast', this._onToast)
    uni.$off('sj-ui-loading', this._onLoading)
  },
  methods: {
    /* 回传结果给 utils/ui.js（一次性消费，重复回传会被忽略） */
    fireCb(cbId, result) {
      uni.$emit('sj-ui-cb', { cbId, result })
    },
    closeDialog(confirm) {
      clearTimeout(this._focusTimer)
      this.dialog.show = false
      this.dialog.focus = false
      this.fireCb(this.dialog.cbId, { confirm, content: this.dialog.input || '' })
    },
    pickSheet(i) {
      this.sheet.show = false
      this.fireCb(this.sheet.cbId, i)
    },
    closeSheet() {
      this.sheet.show = false
      this.fireCb(this.sheet.cbId, -1)
    }
  }
}
</script>

<style lang="scss" scoped>
/* 居中弹窗外观、遮罩与入场动画全部由 sj-modal（u-popup）提供，此处不再自绘。 */

/* ---------- 底部动作面板（面板壳交给 u-popup，条目按 v2 卡片观感自组） ---------- */
.asheet {
  width: 840rpx; max-width: 100%; margin: 0 auto;
  padding: 20rpx 20rpx calc(28rpx + env(safe-area-inset-bottom));
  display: flex; flex-direction: column; gap: 16rpx;
}

.as-grab { width: 72rpx; height: 8rpx; border-radius: 8rpx; background: var(--sj-line); margin: 4rpx auto 12rpx; }
.as-title { font-size: 24rpx; color: var(--sj-faint); text-align: center; padding: 4rpx 0 12rpx; }

.as-item {
  border: 2rpx solid var(--sj-line); background: rgba(255, 253, 251, 0.94); border-radius: var(--sj-r-md);
  box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
  padding: 28rpx 32rpx; display: flex; align-items: center; gap: 24rpx;
  transition: transform 0.15s var(--sj-spring), background 0.2s;
}
.as-item:active { transform: scale(0.98); background: var(--sj-cream); }
.as-main { display: flex; flex-direction: column; align-items: flex-start; }
.as-label { font-size: 28rpx; font-weight: 600; color: var(--sj-ink); }
.as-sub { font-size: 21rpx; font-weight: 400; color: var(--sj-sub); margin-top: 2rpx; }
.as-item.danger .as-label { color: var(--sj-bad); }

.as-cancel {
  background: rgba(255, 253, 251, 0.94); border-radius: var(--sj-r-md);
  box-shadow: var(--sj-glass-hi);
  padding: 28rpx 0; text-align: center;
  font-size: 28rpx; font-weight: 700; color: var(--sj-sub);
}
.as-cancel:active { background: var(--sj-cream); }

</style>

<style lang="scss">
/* 非 scoped：u-popup 面板壳（内容容器）对齐 v2——顶部圆角 36rpx + surface 底。
   遮罩色走 overlayStyle（库的 custom-class 在 Vue3 不落 DOM，CSS 选不到遮罩节点） */
.sj-ui-host {
  .u-popup__content {
    background: rgba(255, 253, 251, 0.94) !important;
    border-radius: 36rpx 36rpx 0 0 !important;
    overflow: hidden;
  }
}
</style>
