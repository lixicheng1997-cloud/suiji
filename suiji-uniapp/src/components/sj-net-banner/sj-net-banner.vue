<template>
  <view class="sj-nbnet">
    <view class="nb-bar" :class="['nb-bar--' + mode, { 'nb-bar--show': mode !== '' }]" :style="barStyle">
      <view class="nb-dot" />
      <text class="nb-msg">{{ mode === 'down' ? '网络已断开，内容可能不是最新' : '网络已恢复' }}</text>
    </view>
  </view>
</template>

<script>
/**
 * 岁记 · 全局离线横幅（easycom 自动注册，挂在 sj-ui-host 内即全页面覆盖）
 * 订阅 infra/net.js 的 'sj-net-change' 广播：
 *   断网 → 常驻 warn 细条（#FFF3C4/#B47714，对齐 sj-notify 语义色对）；
 *   恢复 → 切 ok 色（#E2F5EA/#2E7D4F）显示「网络已恢复」约 2.2s 后自动收起。
 * 定位与 sj-notify 共用 infra/layout.js 的 notifyTop()（状态栏/原生导航栏避让）；
 * 显隐经 uni.$emit('sj-net-banner', { on }) 通知 sj-notify 下移避让，避免两条 fixed 重叠。
 * 持久全局态：不加栈顶守卫（与 sj-loading 同理），后台页 host 同样镜像最新网络态。
 * 多实例注意：每个页面一个 host → 28 实例并存，$on/$off 必须存 handler 引用精确注销。
 */
import { netInfo } from '@/infra/net.js'
import { notifyTop } from '@/infra/layout.js'

/* 「网络已恢复」停留时长（ms），到点收起 */
const RECOVER_MS = 2200

export default {
  name: 'SjNetBanner',
  data() {
    return {
      /* ''=隐藏 / down=断网常驻 / up=恢复提示倒计时收起 */
      mode: '',
      barStyle: null
    }
  },
  created() {
    this.barStyle = notifyTop(16)
    /* 初值：进页前就已断网（如切后台断网后返回）直接呈现，不等下一次变化事件 */
    if (!netInfo().connected) this.show('down')
    this._onChange = (info) => {
      if (!info) return
      if (!info.connected) {
        this.show('down')
        return
      }
      /* 恢复：仅在断网横幅在场时切「网络已恢复」倒计时；从未断过则静默 */
      if (this.mode === 'down') this.show('up')
      else this.hide()
    }
    uni.$on('sj-net-change', this._onChange)
  },
  beforeUnmount() {
    uni.$off('sj-net-change', this._onChange)
    clearTimeout(this._timer)
  },
  methods: {
    show(mode) {
      const was = this.mode
      this.mode = mode
      clearTimeout(this._timer)
      if (mode === 'up') this._timer = setTimeout(() => this.hide(), RECOVER_MS)
      if (!was) this.notifyHosts(true)
    },
    hide() {
      clearTimeout(this._timer)
      this._timer = null
      if (this.mode === '') return
      this.mode = ''
      this.notifyHosts(false)
    },
    /* 通知本页 sj-notify 下移/回位（NET_BANNER_H + 8rpx 间隙） */
    notifyHosts(on) {
      uni.$emit('sj-net-banner', { on })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 弹层包裹：横幅根为 fixed 定位，此层不占布局 */
.sj-nbnet {
  width: 0;
  height: 0;
}

/* ===== 细条横幅：与 sj-notify 同锚点、更薄（高 64rpx = layout.js NET_BANNER_H） ===== */
.nb-bar {
  position: fixed;
  left: 24rpx;
  right: 24rpx;
  top: calc(var(--window-top, 0px) + var(--status-bar-height, 0px) + 16rpx);
  z-index: 10075;
  height: 64rpx;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  padding: 0 24rpx;
  border-radius: var(--sj-r-pill);
  box-shadow: var(--sj-sh-sm);
  /* 隐藏态：整体推出视口上方，spring 滑入（与 sj-notify 同款动效） */
  transform: translateY(-160%);
  opacity: 0;
  pointer-events: none;
  transition: transform 0.35s var(--sj-spring), opacity 0.2s linear;
}
.nb-bar--show {
  transform: translateY(0);
  opacity: 1;
  pointer-events: auto;
}
/* 状态圆点：断网橙黄 / 恢复绿（双主题写死，同语义色对） */
.nb-dot {
  flex: none;
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  margin-right: 14rpx;
}
.nb-msg {
  flex: 1;
  font-size: 24rpx;
  font-weight: 800;
  line-height: 64rpx;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 断网：warn 色对 #FFF3C4/#B47714（对齐 sj-notify .nt-bar--warn） */
.nb-bar--down {
  background: #FFF3C4;
}
.nb-bar--down .nb-dot {
  background: #B47714;
}
.nb-bar--down .nb-msg {
  color: #B47714;
}
/* 恢复：ok 色对 #E2F5EA/#2E7D4F（对齐 sj-notify .nt-bar--ok） */
.nb-bar--up {
  background: #E2F5EA;
}
.nb-bar--up .nb-dot {
  background: #2E7D4F;
}
.nb-bar--up .nb-msg {
  color: #2E7D4F;
}
</style>
