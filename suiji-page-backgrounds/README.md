# 岁记 · 页面背景套图（bear / duck / pony）

按 App 已有的三个形象，各出 5 个主页面背景，共 **15 张**。风格与图标库对齐：扁平 kawaii 卡通矢量、粗描边、平涂色块、圆润造型（**不是**早期那版水彩手绘）。

> 本目录是独立新增资产，`suiji-uniapp` / `suiji-icons` 里的既有文件一个都没动。

## 一、需求落地

| 要求 | 落地方式 |
| --- | --- |
| 三个形象各一套 | `bear`（森林）/ `duck`（池塘）/ `pony`（樱花牧场），每套 5 张 |
| 形象的生活环境 | 树屋与树洞卧室 / 红顶小屋与草窝 / 红谷仓与薰衣草房，角色只在底角小面积点缀 |
| 不能压住页面内容 | 构图统一：中间 20%–75% 高度是 `#FFF8F0` 纯色留白，景物只压在顶边和底部 22% |
| 尺寸规格 | 1440×2560（iPhone 竖屏 9:16），投放 JPG + PNG 母版双份 |
| 格式 | `app/*.jpg`（q88 progressive，平均 360KB）+ `master/*.png`（无损母版） |
| 风格贴合图标 | 与 `suiji-icons` 同色板同描边，pony 套沿用 `#F58FB6 / #D9628F / #C6A8F0` |

## 二、目录结构

```
suiji-page-backgrounds/
├── raw/        15 张生成原图（1024×1792，带右下角水印，仅作管线输入）
├── master/     15 张 PNG 母版 1440×2560（二次加工、出 WebP 都用它）
├── app/        15 张投放 JPG 1440×2560（q88 progressive，进 App 的就是这批）
├── tools/
│   └── build_backgrounds.py   去水印 + 归一尺寸 + 双格式导出
├── snippets/
│   └── sj-photo-bg.vue        新增组件（图片版背景，与既有 sj-bg 用法一致）
└── preview-backgrounds.html   15 张套手机框 + 模拟 UI 遮挡的预览页
```

## 三、页面 → 场景映射

| 页面 | 路由 | bear | duck | pony |
| --- | --- | --- | --- | --- |
| 首页 · 时光轴 | `pages/index/index` | `bg-bear-home.jpg` 240KB<br>森林树屋、吊桥、松果小径 | `bg-duck-home.jpg` 358KB<br>红顶小屋、鸟巢、白栅栏 | `bg-pony-home.jpg` 315KB<br>樱花、红灯笼、干草车 |
| 成长 | `pages/grow/grow` | `bg-bear-grow.jpg` 353KB<br>年轮身高尺、树桩板凳 | `bg-duck-grow.jpg` 343KB<br>稻穗、木桩身高尺、梯子 | `bg-pony-grow.jpg` 419KB<br>苹果树、身高尺、草垛 |
| 家庭 | `pages/family/family` | `bg-bear-family.jpg` 575KB<br>大树、蜂巢、蘑菇丛 | `bg-duck-family.jpg` 314KB<br>芦苇、蜻蜓、睡莲 | `bg-pony-family.jpg` 388KB<br>牧场栅栏、远处红谷仓 |
| 我的 | `pages/me/me` | `bg-bear-me.jpg` 277KB<br>树洞卧室、月亮窗、串灯 | `bg-duck-me.jpg` 383KB<br>草窝卧室、油灯、稻草枕 | `bg-pony-me.jpg` 300KB<br>薰衣草房、马鞍挂架、书架 |
| 启动页 | `pages/splash/splash` | `bg-bear-splash.jpg` 478KB<br>晨光林间小屋 | `bg-duck-splash.jpg` 425KB<br>日出池塘、荷花 | `bg-pony-splash.jpg` 396KB<br>太阳、樱花、薰衣草田 |

投放包合计 **5.5MB / 15 张**；单 IP 五张约 1.6–1.9MB，换 IP 时才需要另一批。

## 四、出图管线

1. `ImageGen` 出 1024×1792 原图 → `raw/`（prompt 明确 `NO watercolor / NO paper grain / NO painterly texture`，景物只压顶边与底部 22%，角色露头不超 1/10 画布宽）。
2. `python tools/build_backgrounds.py [ip]` → 去水印 → 放大到 1440×2560 → 写 `master/*.png` + `app/*.jpg`。

### 水印处理

生成图右下角固定有一行半透明「Qoder AI生成」。逐像素检测（灰阶阈值、局部中值对比、饱和度抑制、纹理平坦度）在草地、水面这类纹理上都不可靠，实测只有约一半图能检出，且框不稳。因此改成两步走：

- **几何框**：`WM_BOX = (0.780, 0.943, 1.0, 1.0)`，是 15 张实测水印位置的并集外框（226×103，约占画面 1.2%）。
- **双路镜像补绘**：竖向镜像取自矩形正上方、横向镜像取自正左方，两路按到各自接缝的距离做反距离加权。接缝处像素天然连续，所以四边不留矩形痕迹；水面、木地板这类场景补出来直接就是倒影。

改框或重跑：编辑 `tools/build_backgrounds.py` 里的 `WM_BOX` 后执行 `python tools/build_backgrounds.py`。

## 五、接入方式（只新增，不改既有文件）

```bash
cd suiji-page-backgrounds
# 1) 拷投放图：每个 IP 一个目录，文件名用页面名
for ip in bear duck pony; do
  mkdir -p ../suiji-uniapp/src/static/backgrounds/$ip
  for pg in home grow family me splash; do
    cp app/bg-$ip-$pg.jpg ../suiji-uniapp/src/static/backgrounds/$ip/$pg.jpg
  done
done
# 2) 拷新组件（easycom 自动注册，无需 import）
mkdir -p ../suiji-uniapp/src/components/sj-photo-bg
cp snippets/sj-photo-bg.vue ../suiji-uniapp/src/components/sj-photo-bg/
```

页面里与 `sj-bg` 同位置使用（`sj-bg` 是 CSS 光斑，两者可共存或互换）：

```html
<sj-photo-bg :ip="currentIp" page="home" />
```

> ⚠️ 上面这行要落到 `pages/*/*.vue` 里，属于**修改既有页面文件**，按约定先等你确认。确认后可以一次性给 5 个主页面加上，`:ip` 从主题里取。

## 六、后续可扩展

- **另外 5 个高频页**：`editor`（手账内页，留白要更大）、`detail`、`diary`、`vaccine`、`remind`，同一套构图规则直接续出 15 张。
- **通用内页背景**：把底部景物压到 12%，一张通吃所有二级页，省包体。
- **夜间/助眠模式**：同一构图压暗换色（`#2A2438` 底 + 低饱和景物），每个 IP 再出 5 张。
- **WebP**：`master/*.png` 转 WebP（q80）约再省 35%，H5 端建议走这条，App 端保持 JPG。

## 七、预览

浏览器打开 `preview-backgrounds.html`：15 个手机框叠了状态栏、导航标题、卡片和悬浮底栏，可切换「只看背景」和「对齐到顶部」两种看法，用来判断景物会不会压住真实内容。
