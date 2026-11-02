<script>
import { init, startEventsPolling, stopEventsPolling } from '@/utils/api.js'
import { installFamilyGuard } from '@/utils/first-run.js'
import { paintNavigationBar } from '@/infra/platform.js'
import * as notify from '@/infra/notify.js'

export default {
  onLaunch() {
    // 手势导航真机的底部白带落在 webview 之外，只能把原生导航条底色设成页面底色（见 infra/platform.js）
    paintNavigationBar('#FFF8F0')
    // 家庭强制门控：已登录但未关联家庭的账号，任何跳转都会被改写到 pages/family-setup
    installFamilyGuard()
    // 关闭原生启动画面，交由 pages/splash/splash 自定义动画接管
    // #ifdef APP-PLUS
    plus.navigator.closeSplashscreen()
    // #endif

    // 云端版（TDD v3.0）：已登录则拉 bootstrap 灌内存缓存；未登录由 splash 跳登录页。
    // init() 内部已捕获网络异常，不会 reject；门控路由由 pages/splash 负责。
    // silent：启动预拉取失败由 splash 统一给出友好提示，避免冷启动重复弹窗。
    try {
      init({ silent: true })
    } catch (e) {
      // 崩溃保护：异常写本地日志，下次启动提示（TDD §12）
      try { uni.setStorageSync('sj_crash_log', String(e && e.message || e)) } catch (err) { /* ignore */ }
    }

    // 系统通知：拉起通知权限、注册点击直达、按本地账本恢复图标角标
    try { notify.init() } catch (e) { /* ignore */ }
  },
  onShow() {
    // 回前台按未读通知数刷新应用图标角标
    notify.refreshBadge()
    // 家人动态前台轮询（方案 A）：按 config/app.js 的 MESSAGE_POLL_INTERVAL 探测 /events/count，
    // 家庭有新记录则静默重拉 bootstrap，弹窗走本地账本去重
    startEventsPolling()
  },
  onHide() {
    // 退后台停轮询：省电省流量；被杀场景靠下次启动补弹兜底
    stopEventsPolling()
  }
}
</script>

<style>
/* ============ 全局基础（此文件 style 为全局，不加 scoped） ============ */

/* uview-plus 主题：组件库 CSS 变量统一引用岁记 v2 令牌 var(--sj-*)，
 * 页面根节点 themeVars 覆盖 --sj-* 后，库组件（弹窗/工具栏/文字色）随主题实时换肤。
 * 兜底值即下方 bear 静态 --sj-*。 */
page, :root {
  --up-primary: var(--sj-primary);
  --up-primary-dark: var(--sj-primary-deep);
  --up-primary-disabled: #FFC9A0;
  --up-primary-light: var(--sj-primary-soft);
  --up-error: var(--sj-bad);
  --up-success: var(--sj-ok);
  --up-warning: var(--sj-warn);
  --up-main-color: var(--sj-ink);
  --up-content-color: var(--sj-ink);
  --up-tips-color: var(--sj-sub);
  --up-light-color: var(--sj-faint);
  --up-border-color: var(--sj-line);
  --up-bg-color: var(--sj-cream);

  /* 岁记 v2 设计令牌（bear 默认；duck 由页面根节点 :style="themeVars" 覆盖，见 theme/useTheme.js） */
  --sj-primary: #F7A15C; --sj-primary-deep: #E07E33; --sj-primary-soft: #FFEBD8;
  --sj-accent: #FFB86B; --sj-accent-soft: #FFEBD8; --sj-gold: #F5B32C;
  --sj-duck: #F5B32C; --sj-duck-soft: #FFF3C4; --sj-blush: #FF8FAB; --sj-blush-soft: #FFE7EE;
  --sj-ink: #5B4636; --sj-sub: #9C8878; --sj-faint: #C7B6A8;
  --sj-cream: #FFF8F0; --sj-surface: rgba(255,253,251,.84); --sj-white: #FFFFFF; --sj-line: #F3E4D3; --sj-mask: rgba(74,50,38,.42);
  /* 玻璃表单面（性能版）：App 端 WebView 的 backdrop-filter 会对每个毛玻璃元素每帧重采样背景，
     * 卡片一多滚动就掉帧，故取消模糊、改用半透暖白平铺（表单 .78 / 卡片 .84）+ 顶沿内高光模拟玻璃观感。
     * 高光一律用 px 绝对值：Chromium 对 backdrop-filter 里的 var() 只认绝对长度（rem 会算成 0），
     * 阴影内衬也需 px 才能在 computed 层保留几何值。 */
  --sj-glass: rgba(255,253,251,.78);
  --sj-glass-line: rgba(255,255,255,.72);
  --sj-glass-hi: inset 0 1px 2px rgba(255,255,255,.85);
  --sj-ok: #5FC08C; --sj-warn: #F6B23C; --sj-bad: #EF7A7A;
  /* 类别色 ×10 + 浅底（与 theme/theme.js、mock.js TYPES 同步；双主题共用） */
  --sj-c-feeding: #F7A15C; --sj-c-sleep: #8FA8DC; --sj-c-milestone: #F5B32C; --sj-c-photo: #FF8FAB;
  --sj-c-measure: #5FC08C; --sj-c-poop: #C49066; --sj-c-temp: #FF7B6B; --sj-c-med: #A994D8;
  --sj-c-mood: #E86FA0; --sj-c-voice: #6FBDE0;
  --sj-tint-feeding: #FFEBD8; --sj-tint-sleep: #E9EEFB; --sj-tint-milestone: #FFF3C4; --sj-tint-photo: #FFE7EE;
  --sj-tint-measure: #E2F5EA; --sj-tint-poop: #F5E9DC; --sj-tint-temp: #FFE7E2; --sj-tint-med: #F0EAFB;
  --sj-tint-mood: #FDE9F2; --sj-tint-voice: #E4F3FB;
  --sj-r-sm: 24rpx; --sj-r-md: 40rpx; --sj-r-lg: 56rpx; --sj-r-pill: 999rpx;
  --sj-sh-sm: 0 4rpx 20rpx rgba(214,158,99,.12); --sj-sh-md: 0 20rpx 56rpx rgba(214,158,99,.16); --sj-sh-lg: 0 40rpx 96rpx rgba(180,110,60,.22);
  --sj-spring: cubic-bezier(.34,1.56,.64,1); --sj-smooth: cubic-bezier(.22,.8,.3,1);
  --sj-font-display: "Yuanti SC","YouYuan","幼圆","PingFang SC","Microsoft YaHei",sans-serif;
  --sj-font-body: "PingFang SC","HarmonyOS Sans SC","MiSans","Microsoft YaHei",sans-serif;
}

page {
  background-color: #FFF8F0;
  color: #5B4636;
  font-family: "PingFang SC", "HarmonyOS Sans SC", "MiSans", "Source Han Sans SC", "Microsoft YaHei", sans-serif;
  font-size: 28rpx;
  line-height: 1.5;
}

/* ============ sj-subsection（分段器）内部节点覆盖 ============
 * 必须放在全局样式里：组件 SFC 的「非 scoped 块」在 H5 / App 端也会被编译器追加 [data-v]，
 * 而 uview-plus 内部节点只带库自身作用域，覆盖会全部失效（只剩白底滑块 + 白字 → 选中项看不见）。
 * 本文件样式不加作用域，三端（H5 / App / MP）一致命中。选择器与库同权重，关键声明用 !important。 */
/* 容器：v2 .pg-seg —— 白底 + line 描边 + 胶囊圆角 + 8rpx 内衬，高度随内容；
 * overflow 置 visible：库默认 hidden 会把滑块暖橙投影裁在容器内边，设计稿投影外露 */
.sj-ss .u-subsection.u-subsection--button {
  height: auto !important;
  padding: 8rpx !important;
  border-radius: var(--sj-r-pill) !important;
  border: 2rpx solid var(--sj-line) !important;
  overflow: visible !important;
}
/* 滑块：库 button 模式默认白底，覆盖为 v2 选中块主色底 + 胶囊圆角 + 暖橙投影；
 * 位移缓动换 --sj-spring（弹性收尾），translateX/宽高仍由库内联计算；
 * 左右 4rpx 透明边框 + background-clip:padding-box 复刻设计稿 8rpx 项间 gap
 *（库内联 width 为格宽，border-box 下可见胶囊 = 格宽 - 8rpx，居中且位移不偏移） */
.sj-ss .u-subsection .u-subsection--button__bar {
  box-sizing: border-box !important;
  border-left: 4rpx solid transparent;
  border-right: 4rpx solid transparent;
  background-clip: padding-box;
  background-color: var(--sj-primary) !important;
  border-radius: var(--sj-r-pill) !important;
  box-shadow: 0 8rpx 24rpx rgba(247, 161, 92, 0.35) !important;
  transition-timing-function: cubic-bezier(.34, 1.56, .64, 1) !important;
}
/* 项：v2 .pg-seg i 上下 14rpx(7px) 内衬，撑出滑块高度 */
.sj-ss .u-subsection__item {
  padding: 14rpx 0;
}
/* 文字：26rpx 特粗（字号/行高/字重是库内联或默认，需 !important 压过），
 * 颜色由库按选中态内联下发（选中 #FFF / 未选中 #9C8878） */
.sj-ss .u-subsection__item__text {
  font-size: 26rpx !important;
  line-height: 34rpx !important;
  font-weight: 800 !important;
}

/* 按压反馈：小程序端用 hover-class（对应原型 :active / ripple） */
.hover-press {
  transform: scale(0.95) !important;
}

/* ============ 毛玻璃表单：玻璃卡内的输入槽 ============
 * sj-input variant=box 自带 --sj-glass 底；嵌在玻璃卡（.fs-card / .lg-card）
 * 里会形成「玻璃叠玻璃」的糊面，且小程序端多层模糊开销明显。此处降级为透明浅白槽：
 * 只留描边与轻微底色拉开层次，聚焦时提亮并转主色边（:focus-within 在小程序端不支持，
 * 静默降级为常态观感，不影响输入）。选择器需压过组件内单类 !important，
 * 故叠 .sj-in + .fs-card / .lg-card 祖先（组件 scoped 属性在此不生效，全局声明最稳）。 */
.fs-card .sj-in--box .u-input.u-input,
.lg-card .sj-in--box .u-input.u-input {
  background: rgba(255, 255, 255, 0.34) !important;
  border: 2rpx solid rgba(255, 255, 255, 0.55) !important;
  box-shadow: none !important;
  transition: background-color 0.2s var(--sj-smooth), border-color 0.2s var(--sj-smooth);
}
.fs-card .sj-in--box:focus-within .u-input.u-input,
.lg-card .sj-in--box:focus-within .u-input.u-input {
  background: rgba(255, 255, 255, 0.62) !important;
  border-color: var(--sj-primary) !important;
}

/* ============ 面板级玻璃（性能版）：直接坐在页面氛围背景（sj-bg / 页面底色）上的白色块 ============
 * 原配方为半透暖白 + backdrop-filter 模糊；App 端 WebView 对每个毛玻璃元素每帧重采样背景，
 * 列表页一屏十几个卡片会直接拖垮滚动帧率。现统一去掉模糊，--sj-surface 提到 .92 接近实色，
 * 顶沿 --sj-glass-hi 内高光 + 投影维持「玻璃」观感。
 * 只列「贴页面背景」的类；弹层壳（.u-popup__content）、弹窗（.md-card）、玻璃卡内条目
 * （.as-item / .as-cancel）不在列内，保持不透明以免叠玻璃发浑或压不住底下内容。 */
.rec-card, .rec-milestone, .grow-card, .entry-card, .info-card, .now-card, .member-card, .fam-card,
.set-group, .uk-group, .audit-row, .nt-item, .v-row, .v-summary, .vp-item,
.pg-vrow, .elder-row, .tr-btn, .d-row, .baby-chip, .ds-chip, .dr-count, .ms-badge,
.rchip, .metric-tab, .nt-tabs, .bk, .back-btn, .bk-exit, .bk-skip, .bk-hud,
.me-avatar, .mc-photo, .album-img, .cmp-slot, .cmp-thumb, .sj-cell, .sj-nb--plain, .mem-card,
.sj-vs {
  box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
}
/* 底栏导航条滚动时叠在内容之上，补同款玻璃 + 更实的面色（.80 叠内容偏透） */
.sj-nb--plain {
  background: rgba(255, 253, 251, 0.92);
}

.hover-dim {
  background-color: rgba(255, 255, 255, 0.7);
}

/* ============ tab 页滑动切换过渡（utils/tabSwipe.js 的 swipeClass 消费） ============
 * 只做退场动画：当前页朝滑动方向轻滑 12% + 淡出后换页，目标页直接呈现
 * （app 端目标页 webview 已渲染，补进场动画会先露静态帧再跳变，像加载两次）；
 * 时长固定 .18s，与 tabSwipe.js 的 OUT_MS 一致；缓动复用 --sj-smooth */
.ts-out-slide-left  { animation: tsOutSlideL .18s var(--sj-smooth) both; }
.ts-out-slide-right { animation: tsOutSlideR .18s var(--sj-smooth) both; }
@keyframes tsOutSlideL { to { transform: translateX(-12%); opacity: 0; } }
@keyframes tsOutSlideR { to { transform: translateX(12%); opacity: 0; } }

/* H5 端可额外引入 ripple 指令还原波纹效果（小程序端不支持动态 DOM，已省略） */
</style>
