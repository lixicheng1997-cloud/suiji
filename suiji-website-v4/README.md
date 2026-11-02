# 岁记官网 v4

「岁记」宝宝成长记录 App 产品官网。零构建、零依赖，双击 `index.html` 即可打开。

---

## 目录结构

```
suiji-website-v4/
├── index.html              页面结构（含内嵌真机原型）
├── assets/
│   ├── css/
│   │   ├── phone.css       组件层：手机壳 / App 内页 / 令牌（源自 v2，已剥离 UI 预览残留）
│   │   └── site.css        站点层：布局 / 响应式 / 动效（全站类名 sj- 前缀）
│   ├── js/
│   │   ├── config.js       站点配置（改地址、版本号只动这里）
│   │   ├── phone.js        组件层交互（真机原型内部逻辑）
│   │   └── site.js         站点层交互（25+ 交互效果）
│   ├── icons/bear|duck/    60 枚双主题图标
│   ├── background/         Hero 场景背景
│   ├── qr/                 Android / iOS 下载二维码
│   ├── logo-192-rounded.png 导航 / 页脚 / 下载区 logo（圆角）
│   ├── logo.svg            logo 矢量版（squircle）
│   ├── logo-square.svg     logo 矢量版（方角）
│   ├── icon-192.png        favicon 192
│   ├── favicon-32.png      favicon 32
│   ├── icon-512.png        社交分享 og:image
│   └── apple-touch-icon.png  iOS 添加到主屏 180
├── downloads/
│   └── suiji-v1.0.0.apk    真实安装包（15.6 MB，源自 uniapp 打包产物）
└── tools/
    ├── build-assets.py     资源构建：二维码 / APK / Logo 同步
    └── build-logo.py       Logo 各尺寸导出（源：icon/app-icon.png）
```

---

## 上线前必改项

**1. 真实下载地址** → `assets/js/config.js`

```js
download: {
  android: 'downloads/suiji-v1.0.0.apk',  // 换成 CDN 直链更稳
  ios: '',                                  // 上架后填 App Store 链接
}
```

**2. 换域名后重新生成二维码** → 改 `tools/build-assets.py` 的 `SITE_BASE_URL` 后执行：

```bash
python tools/build-assets.py --base-url https://你的域名
```

**3. 备案号 / 页脚** → `index.html` 的 `.sj-foot-bottom`

**4. 换 Logo** → 替换 `icon/app-icon.png` 后执行：

```bash
python tools/build-logo.py
```

会重新导出导航圆角版、favicon、apple-touch 与 og:image 全套尺寸。

### Logo 方案
采用品牌「岁记」粉橙渐变字标（源：`icon/app-icon.png`，1024×1024）：

| 用途 | 资源 | 说明 |
|---|---|---|
| 导航 / 页脚 / 下载区 | `logo-192-rounded.png` | squircle 圆角，与 App 图标视觉一致 |
| 浏览器标签页 | `favicon-32.png` | 方角，32px 下「岁记」仍可辨识 |
| iOS 添加到主屏 | `apple-touch-icon.png` | 180×180，iOS 自带圆角遮罩 |
| 社交分享 | `icon-512.png` | og:image 首选尺寸 |
| 矢量 | `logo.svg` / `logo-square.svg` | 任意尺寸无损缩放 |

换 Logo 只需替换源文件后重跑 `tools/build-logo.py`，全套尺寸自动重新导出。

---

## 核心设计决策

### 简约的实现方式
不靠删内容，靠**层级与留白**：

- 主标题 1 句 + 副标题 1 句 + 4 个信任标签，其余信息全部下沉到交互层
- 每个区块只保留「标题 + 一句话」，功能细节交给真机演示，不做文字罗列
- 图标替代文字：10 类记录用走马灯图标条呈现，不写一段话解释
- 配色克制：单主色 + 语义色，暖奶油底色贯穿全站

### 动态手机：放，且放两处
| 位置 | 形态 | 作用 |
|---|---|---|
| Hero 右侧 | 轻量演示手机 | 首屏建立「这是真产品」的直觉，FAB 可点、能实时新增记录 |
| 真机体验区 | 完整可交互原型 | 10 个页面、51 个 id 全套交互，可切页、可记录、可庆祝 |

Hero 用轻量版是为了不抢真机区的注意力；真机区才是主菜。

### 响应式三档
移动优先，`.sj-wrap` 统一容器宽；关键断点：

- `≤640px`：单列、抽屉导航、常驻下载条、按钮全宽
- `≤920px`：Hero 转单列居中、真机区侧栏下移
- `≤1080px`：真机区转单列、Hero 漂浮卡收位

真机缩放由 JS 按「容器宽 + 视口高」双约束计算（`--sj-scale`），保证任何屏幕下都完整可见不裁切。

---

## 交互清单（25+）

**导航层**：滚动进度条、吸顶阴影、当前区块高亮、移动抽屉、ESC 关闭、回顶按钮、常驻下载条

**真机层**：10 页切换、底部 Tab、记录类型面板（含拖拽下滑关闭）、新增记录实时插入时光轴、里程碑全屏庆祝 + 彩带、语音三态（录音 → 实时转写 → 试听预览）、宝宝档案切换、长辈模式、同步动画、状态栏实时时钟、睡眠/喂奶计时器、10 类动态表单

**内容层**：滚动揭示、数字滚动、卡片 3D 倾斜、鼠标光晕跟随、按钮涟漪、彩带粒子、爱心粒子、吉祥物眼睛跟随、吉祥物连点彩蛋、标题下划线动画

**功能层**：双主题切换（配色 + 60 枚图标 + localStorage 持久化）、二维码放大弹窗、下载链接复制、设备识别推荐角标、FAQ 手风琴、走马灯悬停暂停 / 拖拽滚动

**无障碍**：`prefers-reduced-motion` 全局降级、`:focus-visible` 焦点环、`aria-*` 标注、ESC 关闭弹层

---

## 本地预览

```bash
cd suiji-website-v4
python -m http.server 8899
# 打开 http://127.0.0.1:8899/index.html
```

直接双击 `index.html` 也能打开，但用本地服务可保证二维码弹窗等行为正常。

---

## 已知边界

- **iOS 版尚无安装包**：`manifest.json` 已配 iOS 隐私描述与权限，但尚无 IPA 产物。官网已按「即将上架」诚实标注，二维码指向订阅页而非商店。
- **APK 直链为相对路径**：换 CDN 后需同步改 `config.js`。
- **二维码内容含域名**：换域名务必重跑 `build-assets.py`。
- **真机原型为演示**：数据为写死样例，不连后端。
