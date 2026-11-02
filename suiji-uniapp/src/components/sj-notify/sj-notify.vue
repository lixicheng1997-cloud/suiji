<template>
  <view class="sj-nt">
    <!-- 自组 fixed 横幅：u-notify 为全宽贴边通栏（无圆角/阴影、iconfont 图标、文案居中），
         与设计稿 .cu-notify「圆角卡 + 侧图标 + 间隙」属结构性偏差，命名空间覆盖压不过形态差异
         （参照 sj-modal/sj-empty 先例改自组），定时器自动收起与顶部滑入动画在此自理 -->
    <view
      class="nt-bar"
      :class="['nt-bar--' + semKey, { 'nt-bar--show': visible }]"
      :style="barStyle"
    >
      <image class="nt-ic" :src="iconSrc" mode="aspectFit" />
      <text class="nt-msg">{{ message }}</text>
    </view>
  </view>
</template>

<script>
/**
 * 岁记 · 顶部通知栏（自组 fixed 横幅，easycom 自动注册）
 * 外观对齐 v2 .cu-notify 三语义横幅（components.html L657-659「轻提示/通知栏」；
 * styles.css L872-875，px×2→rpx）：圆角 24rpx(12px) + 内距 20rpx 28rpx(10px 14px) +
 * 文案 25rpx(12.5px)/800，浅底深字 ——
 * ok #E2F5EA/#2E7D4F、warn #FFF3C4/#B47714、err #FDF0F0/#B04A4A（双主题相同，写死）。
 * 与稿面唯一偏差：设计稿侧图标为 40rpx(20px) fn 砖图，IP 角色缩到 20px 语义符号不可辨，
 * 改用 ctl-v2 切图并放大到 64rpx（间隙 20rpx）。
 * App 内位置：fixed 顶部，左右留 24rpx 边距、上缘避开状态栏（created 取 JS 实际 statusBarHeight
 * +24rpx，App 端 CSS 变量为固定 25px 不可靠）；暖棕大投影 --sj-sh-md；入场从顶部滑入
 * （缓动 --sj-spring 弹性收尾），duration 后自动收起。
 * 选型说明：此前走 u-notify 覆盖库内部类，但库通栏贴边形态（无圆角/阴影/侧图标排布）
 * 与设计稿圆角卡结构差异过大、覆盖不可控，改自组。
 * 图标：ctl-v2 控件图标的透明底切图（scripts/cut-ctl-icons.py 按显示尺寸生成到
 * /static/icons/ctl/{theme}/64/），三语义就近取反馈类概念图 —— ok 66-ctl-modal-ok（对勾小旗）、
 * warn 64-ctl-modal-warn（三角感叹号）、err 48-ctl-clear（圆钮叉号）。
 * 原图是角色占画布约 55% 的圆角砖图，砖底色与横幅语义底色相冲，故去底 + 按主体包围盒
 * 裁切后重切到 168px（64rpx 在 3x 屏约 106 物理像素，留余量）。
 * 挂载用法：<sj-notify ref="ntf" />，页面里 this.$refs.ntf.show({ type:'ok', message:'已保存' })，
 * 亦可 this.$refs.ntf.close() 手动收起（duration 默认 2500ms）。
 */
/* 三语义 png 名（浅底色对见 scoped 样式 .nt-bar--*，v2 .cu-notify n-ok/n-warn/n-err） */
const SEM = {
  ok: '66-ctl-modal-ok',
  warn: '64-ctl-modal-warn',
  err: '48-ctl-clear'
}
/* 使用默认原生导航栏的页面（pages.json 未设 navigationStyle:custom）：
 * fixed 坐标已从导航栏下缘起算，再叠加 statusBarHeight 会导致横幅整体偏下 */
const NATIVE_NAV_ROUTES = ['pages/grow/grow', 'pages/family/family', 'pages/me/me']

export default {
  name: 'SjNotify',
  data() {
    return {
      visible: false,
      message: '',
      semKey: 'ok',
      barStyle: null,
      timer: null
    }
  },
  computed: {
    /* 当前主题下的切图路径（64rpx 规格目录；彩色绘本图，不走 color 重染） */
    iconSrc() {
      return `/static/icons/ctl/${this.__theme}/64/${SEM[this.semKey]}.png`
    }
  },
  created() {
    /* 状态栏避让：CSS 变量 --status-bar-height 在 App 端为固定 25px，
     * 高状态栏/刘海机型横幅顶边会被系统状态栏压住；改用 JS 实际像素值定位，
     * 呼吸间距由 16rpx 提到 24rpx（整体下移一点）。H5 端 sb=0 回落样式内 CSS 变量。
     * 默认原生导航栏页面（成长/家庭/我的）例外：fixed 坐标已在导航栏之下，
     * 小程序/App 端不能再叠加 statusBarHeight，否则横幅偏下约一个状态栏高度 */
    let sb = 0
    let route = ''
    try {
      const info = (uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()) || {}
      sb = info.statusBarHeight || 0
      const pages = getCurrentPages()
      const cur = pages[pages.length - 1]
      route = (cur && cur.route) || ''
    } catch (e) { /* 取不到时走 CSS 变量兜底 */ }
    if (NATIVE_NAV_ROUTES.indexOf(route) !== -1) {
      // #ifndef H5
      this.barStyle = { top: uni.upx2px(24) + 'px' }
      // #endif
      return
    }
    if (sb > 0) this.barStyle = { top: (sb + uni.upx2px(24)) + 'px' }
  },
  beforeUnmount() {
    if (this.timer) clearTimeout(this.timer)
  },
  methods: {
    /**
     * 弹出通知
     * @param {Object} opt { type: 'ok'|'warn'|'err'(默认 ok), message: String, duration: Number(默认 2500ms) }
     */
    show(opt = {}) {
      const key = SEM[opt.type] ? opt.type : 'ok'
      this.semKey = key
      this.message = opt.message || ''
      /* 重入时先清旧定时器，再复位隐藏态确保动画每次完整播放 */
      if (this.timer) clearTimeout(this.timer)
      this.visible = false
      this.$nextTick(() => {
        this.visible = true
        const d = opt.duration != null ? opt.duration : 2500
        if (d > 0) {
          this.timer = setTimeout(() => {
            this.close()
          }, d)
        }
      })
    },
    /* 立即收起 */
    close() {
      if (this.timer) clearTimeout(this.timer)
      this.timer = null
      this.visible = false
    }
  }
}
</script>

<style lang="scss" scoped>
/* 弹层包裹：横幅根为 fixed 定位，此层不占布局 */
.sj-nt {
  width: 0;
  height: 0;
}

/* ===== 横幅（v2 .cu-notify：圆角 12px→24rpx、内距 10px 14px→20rpx 28rpx） ===== */
.nt-bar {
  position: fixed;
  left: 24rpx;
  right: 24rpx;
  /* 上缘避开状态栏（uni 全局变量，MP 端为 0 即正确）与默认导航栏（--window-top：
   * H5 端默认导航栏为 fixed 盖在视口顶部，需一并避让；MP/App/custom 导航栏端为 0），再留 16rpx 呼吸 */
  top: calc(var(--window-top, 0px) + var(--status-bar-height, 0px) + 16rpx);
  z-index: 10076;
  display: flex;
  align-items: center;
  padding: 20rpx 28rpx;
  border-radius: 24rpx;
  box-shadow: var(--sj-sh-md);
  /* 隐藏态：整体推出视口上方（-160% 含自身高度与 top 偏移余量），spring 滑入 */
  transform: translateY(-160%);
  opacity: 0;
  pointer-events: none;
  transition: transform 0.35s var(--sj-spring), opacity 0.2s linear;
}
.nt-bar--show {
  transform: translateY(0);
  opacity: 1;
  pointer-events: auto;
}
/* 侧图标：ctl-v2 切图 64rpx（切图自带约 11% 留白，角色视觉尺寸约 57rpx），
   与文字间隙 20rpx（margin 代替 gap，兼容旧 webview 内核） */
.nt-ic {
  flex: none;
  width: 64rpx;
  height: 64rpx;
  margin-right: 20rpx;
}
/* 文案：25rpx(12.5px)/800，深字色随语义 */
.nt-msg {
  flex: 1;
  font-size: 25rpx;
  font-weight: 800;
  line-height: 40rpx;
}
/* 三语义浅底深字（双主题相同，写死） */
.nt-bar--ok {
  background: #E2F5EA;
}
.nt-bar--ok .nt-msg {
  color: #2E7D4F;
}
.nt-bar--warn {
  background: #FFF3C4;
}
.nt-bar--warn .nt-msg {
  color: #B47714;
}
.nt-bar--err {
  background: #FDF0F0;
}
.nt-bar--err .nt-msg {
  color: #B04A4A;
}
</style>
