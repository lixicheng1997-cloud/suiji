# 岁记 · uni-app 设计契约（机器可读交接文档 v1.0）

> 用途：供 AI / 开发者在 uni-app 项目中新增页面时**逐条照抄**的单一事实来源。
> 与 `suiji-prototype/`（HTML 原型）同源；本文件描述的是 uni-app 转换后的实现规范。

## 0. 技术栈与交付

| 字段 | 值 |
|---|---|
| stack | uni-app (Vue 3, Options API) + SCSS |
| delivery | 源码工程（HBuilderX 或 `npx @dcloudio/uvm` + `npm run dev:mp-weixin`） |
| 目标平台 | 微信小程序优先，兼容 H5 / App |
| 单位 | 一律 `rpx`；换算规则：**原型 px × 2 → rpx**（原型 390px 视口 ≈ 375 基准） |

## 1. 设计令牌（`uni.scss`，自动注入，禁止页面内硬编码色值）

### 1.1 色彩

| SCSS 变量 | 值 | 用途 |
|---|---|---|
| `$sj-primary` | `#FF6B8B` | 主色（樱花粉）：FAB 渐变起点、选中描边 |
| `$sj-primary-deep` | `#E84A6F` | 选中文字 / tabBar 选中色 / 记录人高亮 |
| `$sj-accent` | `#FF9E58` | 强调（暖橙）：FAB 渐变终点、note 左边线 |
| `$sj-accent-soft` | `#FFD9BC` | note 引用条 |
| `$sj-gold` | `#FFC24B` | 里程碑金 |
| `$sj-bg` | `#FFF6F0` | 页面底色（奶茶白），`page{}` 与 pages.json `backgroundColor` |
| `$sj-surface` | `rgba(255,253,251,.80)` | 卡片面（v3 起为半透「面板级玻璃」，非纯白；纯白改用 `$sj-white`） |
| `$sj-border` | `#FFE6D8` | 暖粉描边 / 时光轴竖线 |
| `$sj-text` | `#4A3A3E` | 正文（暖炭） |
| `$sj-text-sub` | `#A08A8F` | 次要文字 |
| `$sj-text-faint` | `#C4B2B6` | 弱化文字 / tabBar 未选中 |
| `$sj-success` / `$sj-warning` / `$sj-danger` | `#5FB87A` / `#F5A623` / `#E85D5D` | 语义色 |

#### 1.1b 玻璃面令牌（v3 新增，运行时 CSS 变量，单一来源 `App.vue` + `theme/theme.js`）

| CSS 变量 | 值 | 用途 |
|---|---|---|
| `--sj-glass` | `rgba(255,253,251,.72)` | 表单域面（输入框 / 备注 / 搜索 / 字段行）：最透，能看到氛围背景 |
| `--sj-glass-line` | `rgba(255,255,255,.72)` | 玻璃面描边（白色刃口，替代 `--sj-line`） |
| `--sj-glass-hi` | `inset 0 1px 2px rgba(255,255,255,.85)` | 顶沿内高光，做出玻璃厚度 |
| `--sj-glass-blur` | `blur(8px)` | 背景模糊半径（**必须 px**：Chromium 对 `backdrop-filter: var()` 只认绝对长度，rpx→rem 会算成 0） |
| `--sj-surface` | `rgba(255,253,251,.80)` | 面板级玻璃：白色块（列表卡 / 统计胶囊 / 分组卡）共用底 |
| 面板玻璃写法 | `backdrop-filter: var(--sj-glass-blur); box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);` | 贴在页面氛围背景（`<sj-bg />`）上的块必须自己声明模糊，见 `App.vue` 的 `:is(...)` 面板块 |

**分层规则（防"玻璃叠玻璃"发浑）**：氛围背景上的块用 `--sj-surface`（.80）；块内的表单域用 `--sj-glass`（.72）；
表单壳卡（`.lg-card` / `.fs-card`）用 `--sj-glass`，其内部 `sj-input variant=box` 降级为透明浅白槽
（`rgba(255,255,255,.34)` + 白描边，见 `App.vue`）；弹层壳（`.u-popup__content` / `.md-card` / 动作面板条目）用 .94 近实底。
新增页面若自绘白色块，除 `background: var(--sj-surface)` 外，需把类名补进 `App.vue` 的玻璃面板 `:is(...)` 列表以补齐模糊。

### 1.2 类别色板（7 类；`utils/mock.js` TYPES 与本表**必须同步**）

| type | color | tint（图标块底色） | iconKey |
|---|---|---|---|
| feeding | `#FF9E58` | `#FFF0E2` | bottle |
| sleep | `#8FA8D8` | `#EBF0FA` | moon |
| milestone | `#FFC24B` | `#FFF6DC` | trophy |
| photo | `#FF6B8B` | `#FFE9EF` | camera |
| measure | `#E86FA0` | `#FDE9F2` | ruler |
| poop | `#C9A28B` | `#F3EAE2` | cloud |
| temp | `#FF7B6B` | `#FFE9E5` | thermometer |

### 1.3 圆角 / 阴影 / 缓动 / 字体

| 令牌 | 值 |
|---|---|
| `$sj-r-sm` / `$sj-r-md` / `$sj-r-lg` / `$sj-r-pill` | `24rpx` / `36rpx` / `48rpx` / `999rpx` |
| `$sj-sh-sm` | `0 4rpx 16rpx rgba(255,107,139,.10)` |
| `$sj-sh-md` | `0 16rpx 48rpx rgba(255,107,139,.14)` |
| `$sj-sh-lg` | `0 32rpx 80rpx rgba(232,74,111,.22)`（FAB / 弹层） |
| `$sj-ease-spring` | `cubic-bezier(.34,1.56,.64,1)`（弹出/回弹） |
| `$sj-ease-out` | `cubic-bezier(.22,.8,.3,1)`（入场/位移） |
| 字体栈 | `"PingFang SC","HarmonyOS Sans SC","MiSans","Source Han Sans SC","Microsoft YaHei",sans-serif` |

字号速查（原型 px → rpx）：10→20 / 11→22 / 11.5→23 / 12→24 / 13→26 / 14→28 / 14.5→29 / 15→30 / 17→34。标题字重 700，正文 400，chip/标签 600。

## 2. 工程结构与 App Shell

```
suiji-uniapp/
├─ pages.json      # 4 页面 + 原生 tabBar（仅文字，见 §5 注意）
├─ manifest.json   # vueVersion=3；appid 留空待填
├─ uni.scss        # §1 全部令牌
├─ App.vue         # 全局 page 样式 + hover-class 按压反馈类
├─ main.js         # createSSRApp 标准入口
├─ pages/
│  ├─ index/index.vue   # ✅ 首页完整实现（本契约的参考实现）
│  ├─ grow/grow.vue     # 占位
│  ├─ family/family.vue # 占位
│  └─ me/me.vue         # 占位
├─ utils/
│  ├─ mock.js      # 单一数据源：TYPES / BADGES / DB / BABY_AVATAR
│  └─ api.js       # fetchEntries / saveEntry（Promise stub + TODO 真实路径）
└─ static/icons/   # 13 个描边图标 SVG（stroke 2 / round / 颜色已烘进文件）
```

- 首页 `navigationStyle: custom`，顶栏 `padding-top: calc({statusBarHeight}px + 8rpx)`，`statusBarHeight` 取 `uni.getSystemInfoSync().statusBarHeight`（勿依赖 `--status-bar-height`，小程序端为 0）。
- 其余三页用默认导航栏，`navigationBarBackgroundColor: #FFF6F0`。

## 3. HTML 原型 → uni-app 组件映射

| 原型 | uni-app | 注意 |
|---|---|---|
| `<div>` / `<section>` | `<view>` | 文本必须 `<text>` 包裹（小程序无继承排版） |
| `<img>` | `<image mode="aspectFill">` | 需显式宽高 |
| `<button class="ripple">` | `<view hover-class="hover-press">` | 波纹在小程序端降级为按压缩放（`scale(.94)`，全局类在 App.vue）；H5 端可自加 ripple 指令还原 |
| `overflow-y:auto` 滚动区 | 页面原生滚动 | chips 用 `position:sticky; top:0` |
| chips 横滚 | `<scroll-view scroll-x>` + `white-space:nowrap` | |
| `toast()` DOM | `uni.showToast({icon:'none'})` | |
| 原生 tabbar JS 切换 | `pages.json` `tabBar` 原生 | |
| CSS 变量取色 | 运行时色一律走 `mock.js` TYPES 十六进制 + `:style` 内联 | 小程序不支持运行时改 `:root` 变量 |
| `::before` 伪元素（带动态色） | 真实 `<view class="entry-dot">` + `:style` | 伪元素拿不到内联样式 |

## 4. 关键尺寸速查（rpx，均已按 ×2 换算落进 index.vue）

| 元素 | 值 |
|---|---|
| 页面左右安全边距 | 32rpx |
| 宝宝头像 | 88×88，描边 5rpx #fff + 4rpx 主色环 |
| 顶栏图标按钮 | 80×80 圆，图标 38rpx，红点 16rpx |
| 今日胶囊 | flex:1，内边距 20/24rpx，图标块 60rpx r20 |
| chip | 14/32rpx 内边距，26rpx 字，描边 3rpx |
| 记录卡 | 内边距 28rpx，图标块 84rpx r26，图标 42rpx，照片 128rpx |
| 时光轴 | 左轨 48rpx 缩进，竖线 4rpx 位于 8rpx，节点点 20rpx |
| FAB | 116×116，`right:48rpx bottom:52rpx`（原生 tabBar 在 webview 外，无需再减 tab 高度） |
| 记录面板 | 宽 536rpx，`right:32rpx bottom:192rpx`，3 列磁贴 gap 20rpx，磁贴图标块 76rpx |

## 5. 图标清单与平台注意

`static/icons/`：search / bell / chevron-down（`#4A3A3E`）、plus（`#FFFFFF`，stroke 2.4）、bottle / moon / trophy / camera / ruler / cloud / thermometer / sparkles / image（各自类别色）。全部 24 viewBox、stroke 2、round cap。

> ⚠️ **微信小程序 `<image>` 不渲染 SVG**。当前 SVG 方案在 H5 / App 直接可用；上微信端前需二选一：
> 1. 批量转 PNG（建议 3× 导出 144px，文件名不变）；
> 2. 换 iconfont 字体图标 / uni-icons。
> tabBar 同理：`pages.json` 已省略 `iconPath`（微信允许纯文字 tab），正式图标需 81×81 PNG 补齐 4×2 张（home/trend/users/user，未选中 `#C4B2B6`、选中 `#E84A6F`）。

## 6. Mock schema（`utils/mock.js`）

```ts
TYPES: { [type]: { label: string, iconKey: string, color: '#RRGGBB', tint: '#RRGGBB' } }
BADGES: { milestone:'里程碑', backfill:'补记', ongoing:'进行中', p50:'P50' }
DB.baby: { name, age }
DB.todayStats: [{ icon, num, label, type }]
DB.entries: [{ day: string, items: [{ time:'HH:mm', type, title, meta?, creator, badge?, note?, photo? }] }]
```

API 形状（`utils/api.js`，替换 mock 分支即可接真实后端）：
- `fetchEntries({before?, type?, limit?})` → `GET /api/v1/entries`
- `saveEntry({type, occurred_at, payload, note?, photos?})` → `POST /api/v1/entries`

## 7. 动效规格

| 动效 | 规格 |
|---|---|
| 卡片入场 | `cardIn` 0.5s ease-out，`animation-delay: index*60ms+250ms`，fill `backwards`（勿用 `both`，否则锁死 transform 与按压反馈冲突） |
| 磁贴弹出 | `tilePop` 0.38s spring，delay `i*55ms`，仅 `.sheet.open` 时触发 |
| FAB | 入场 `fabIn`（spring，延迟 0.5s）；展开旋转 45°，加号反向 -45°；脉冲环 `pulse` 2.4s infinite，面板打开时 `v-if` 移除 |
| 按压 | 全局 `.hover-press`（scale .94）+ CSS `:active`（H5 兜底） |

## 8. 页面清单与待办

### 8.1 已实现（v1.0 单机版）

首页时光轴 / 成长（WHO 曲线·里程碑·测量）/ 家庭 / 我的 / 记录编辑（8 类表单，含时间 picker 与真实计时）/ 详情 / 三步引导 / 监护人同意 / AI 成长日记 / 疫苗时间表。

### 8.2 待建页面 / 待接功能（入口已保留，现提示"功能开发中"）

| 入口位置 | 待建内容 | 依赖 |
|---|---|---|
| 首页顶栏搜索按钮 | **搜索页**：按类型 / 日期 / 关键词检索记录 | 无（可本地实现） |
| 首页顶栏铃铛 | **提醒中心页**：疫苗 · 体检 · 纪念日聚合 | 无（可本地实现） |
| 首页记录面板"更多" | 文字心情 / 语音记录类型 | 语音需录音权限 |
| 详情页"分享到家庭动态" | 家人动态流分享 | 需后端/家庭空间 |
| 详情页"更多 → 举报" | 反馈/举报页 | 需后端 |
| 我的 → 导出成长档案 PDF | PDF 生成（含曲线与体检摘要） | 需本地 PDF 库或后端 |
| 微信端图标 | `static/icons/*.svg` 转 PNG 或换 iconfont（§5） | 构建流程 |

新页面规则：色值只用 `uni.scss` 令牌 + `mock.js` TYPES；尺寸按 §4 速查；组件映射按 §3；每页顶部先复制 §2 的状态栏处理方式。
