/**
 * 岁记 · v2 设计令牌（单一来源）
 * 森林绘本 Kawaii 双 IP 主题：bear（小熊·蜂蜜暖棕）/ duck（小鸭·奶油明黄）
 * 单位规则：原型 px × 2 → rpx。
 * 小程序端不支持运行时改 :root，故：
 *   - bear 默认值在 App.vue 的 page,:root 静态声明（H5/App 兜底 + 全局 var() 可用）
 *   - duck 切换通过页面根节点 :style="themeVars"（buildCssVars 生成）覆盖同名变量
 * 类别色与 utils/mock.js TYPES 必须同步。
 */

export const DEFAULT_THEME = 'bear'
export const THEME_LABELS = {
  bear: '小熊 · 蜂蜜暖棕',
  duck: '小鸭 · 奶油明黄'
}

/* 两套主题共享的基础令牌（bear 即基准） */
const BASE = {
  /* 品牌 */
  'primary': '#F7A15C', 'primary-deep': '#E07E33', 'primary-soft': '#FFEBD8',
  'accent': '#FFB86B', 'accent-soft': '#FFEBD8', 'gold': '#F5B32C',
  'duck': '#F5B32C', 'duck-soft': '#FFF3C4', 'blush': '#FF8FAB', 'blush-soft': '#FFE7EE',
  /* IP（身体/描边 + 面部细节：与 static/anim/{bear|duck}-face.svg 同色，
     canvas 端复刻吉祥物时取这里，页面不各写一套色值） */
  'bear-body': '#D99E63', 'bear-line': '#6B4A3A', 'duck-body': '#FFD85C', 'duck-line': '#D98E1F',
  'eye-ink': '#4A3226', 'bear-muzzle': '#F7E3C8', 'ear-inner': '#F7B8C4', 'duck-beak': '#FF9E4A', 'cheek': '#F9A8B8',
  /* 类别色 ×10 */
  'c-feeding': '#F7A15C', 'c-sleep': '#8FA8DC', 'c-milestone': '#F5B32C', 'c-photo': '#FF8FAB',
  'c-measure': '#5FC08C', 'c-poop': '#C49066', 'c-temp': '#FF7B6B', 'c-med': '#A994D8',
  'c-mood': '#E86FA0', 'c-voice': '#6FBDE0',
  /* 类别浅底 ×10 */
  'tint-feeding': '#FFEBD8', 'tint-sleep': '#E9EEFB', 'tint-milestone': '#FFF3C4', 'tint-photo': '#FFE7EE',
  'tint-measure': '#E2F5EA', 'tint-poop': '#F5E9DC', 'tint-temp': '#FFE7E2', 'tint-med': '#F0EAFB',
  'tint-mood': '#FDE9F2', 'tint-voice': '#E4F3FB',
  /* 中性（surface 为「面板级」半透白：所有白色块共用，比表单玻璃 --sj-glass 更实，保长文可读） */
  'ink': '#5B4636', 'sub': '#9C8878', 'faint': '#C7B6A8',
  'cream': '#FFF8F0', 'surface': 'rgba(255,253,251,.84)', 'white': '#FFFFFF', 'line': '#F3E4D3',
  /* 玻璃表单面（性能版：暖白半透 .78 + 顶沿内高光，无 backdrop-filter 模糊）：只用于表单域，卡片仍用 surface。
     高光用 px 绝对值——duck 换肤时这些令牌经 :style 内联下发，rpx 在 H5/App webview 不被识别。 */
  'glass': 'rgba(255,253,251,.78)', 'glass-line': 'rgba(255,255,255,.72)',
  'glass-hi': 'inset 0 1px 2px rgba(255,255,255,.85)',
  /* 浮层遮罩（v2 .sheet-mask 暖可可半透，双主题同值） */
  'mask': 'rgba(74,50,38,.42)',
  /* 语义 */
  'ok': '#5FC08C', 'warn': '#F6B23C', 'bad': '#EF7A7A',
  /* 圆角 */
  'r-sm': '24rpx', 'r-md': '40rpx', 'r-lg': '56rpx', 'r-pill': '999rpx',
  /* 阴影 */
  'sh-sm': '0 4rpx 20rpx rgba(214,158,99,.12)',
  'sh-md': '0 20rpx 56rpx rgba(214,158,99,.16)',
  'sh-lg': '0 40rpx 96rpx rgba(180,110,60,.22)',
  /* 缓动 */
  'spring': 'cubic-bezier(.34,1.56,.64,1)', 'smooth': 'cubic-bezier(.22,.8,.3,1)',
  /* 字体 */
  'font-display': '"Yuanti SC","YouYuan","幼圆","PingFang SC","Microsoft YaHei",sans-serif',
  'font-body': '"PingFang SC","HarmonyOS Sans SC","MiSans","Microsoft YaHei",sans-serif'
}

/* duck 主题仅主色族不同（对齐 v2 body[data-theme=duck] 覆盖） */
const DUCK = {
  'primary': '#F5B32C', 'primary-deep': '#D9911B', 'primary-soft': '#FFF3C4',
  'accent': '#FFD85C', 'accent-soft': '#FFF3C4'
}

export const THEMES = {
  bear: { ...BASE },
  duck: { ...BASE, ...DUCK }
}

/* 取某主题的扁平令牌对象 */
export function palette(name) {
  return THEMES[name] || THEMES[DEFAULT_THEME]
}

/* 纪念卡皮肤（card · P32 · FR-43）：卡片是「当前主题 IP 的实物化」，
   卡面渐变 / 描边 / 图章掌印 / 点缀彩带的色值全部随 bear·duck 切换。
   页面预览与 canvas 导出共用这一份，避免两处各写一套金色。
   glyph：bear 小熊掌印 / duck 小鸭掌蹼（canvas 端按此分支程序化绘制，
         小程序 canvas 画 SVG 不可靠，故不引图片资源）。 */
const CARD_SKINS = {
  bear: {
    bgFrom: '#FFF8E3', bgTo: '#FFEFD3',
    edge: '#F5D888', edgeIn: 'rgba(255,255,255,.72)',
    tint: '#FFF3D6',
    glyph: 'paw',
    /* 点缀色：蜂蜜金星光 */
    spark: '#F5B32C',
    confetti: ['#F7A15C', '#F5B32C', '#FF8FAB', '#8FA8DC', '#5FC08C']
  },
  duck: {
    bgFrom: '#FFFEE8', bgTo: '#FFF2BE',
    edge: '#FFD75E', edgeIn: 'rgba(255,255,255,.8)',
    tint: '#FFF8DA',
    glyph: 'web',
    /* 点缀色：池塘水纹（与 sj-bg duck 涟漪同色族） */
    spark: 'rgba(111,189,224,.55)',
    confetti: ['#F5B32C', '#FFD85C', '#FF8FAB', '#6FBDE0', '#5FC08C']
  }
}

export function cardSkin(name) {
  return CARD_SKINS[name] || CARD_SKINS[DEFAULT_THEME]
}

/* #RRGGBB → rgba()：预览卡要保留 .84 半透（贴在氛围背景上的面板级玻璃），
   canvas 导出用实色。令牌仍是一份，只是透明度按载体不同。 */
export function withAlpha(color, alpha) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(color || '').trim())
  if (!m) return color
  const n = parseInt(m[1], 16)
  return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + alpha + ')'
}

/* uview-plus 弹窗遮罩内联样式：库的 custom-class 在 Vue3 不落到 DOM，
   CSS 选不到遮罩节点，只能通过 u-popup 的 overlayStyle 下发（值同 --sj-mask） */
export const POPUP_MASK_STYLE = { 'background-color': BASE['mask'] }

/* 生成可直接用于 :style 绑定的 CSS 自定义属性映射（--sj-*） */
export function buildCssVars(name) {
  const t = palette(name)
  const vars = {}
  for (const k in t) vars['--sj-' + k] = t[k]
  return vars
}
