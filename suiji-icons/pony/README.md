# 岁记 · pony 小马图标库（第三套 IP）

在 `bear`（蜂蜜暖棕小熊）、`duck`（奶油明黄小鸭）之外新增的一版**卡通小马**图标，
独立目录交付，**未改动任何既有文件**。

| 需求 | 落地情况 |
| --- | --- |
| 图标不要有背景图 | 全部 RGBA 纯透明，无圆角色块底板（bear/duck 旧版带底板，本版已去除）；四角 alpha=0 已校验 |
| 图标大小保持一致 | 统一画布 1024×1024 / 512×512，主体按外接框最长边归一到 880 / 440 后居中，30 张全部一致 |
| 底部导航图标动态 | 4 个 tab 图标各 4 帧 APNG 循环动图，另附单帧与雪碧图兜底方案 |
| 格式尽量 PNG | 全量 PNG（含 APNG），无 SVG/JPG 依赖 |
| 不修改原有文件 | 仅新增 `suiji-icons/pony/` 目录；接入 App 只需再新增一个主题子目录 |

## 设计规格

- **IP**：奶粉色小马，薰衣草→天蓝渐变鬃毛与尾巴，大眼高光 + 粉腮红，粗暖可可描边，扁平赛璐璐上色。
- **色板**：身体 `#FFD9E4` / 腹部 `#FFF3DC` / 鬃毛 `#C6A8F0→#A8D8F0` / 描边 `#7A4A5C`
- **建议主题令牌**（与 `theme/theme.js` 的 bear、duck 并列时可直接取用）：
  `primary #F58FB6`、`primary-deep #D9628F`、`primary-soft #FFEAF2`、`accent #C6A8F0`、`accent-soft #F0EAFF`

## 目录结构

```
pony/
├── 1024/                 30 张源图 1024×1024 RGBA 透明
├── 512/                  30 张投放图 512×512（与 bear/duck 同规格，App 直接用）
├── tab-anim/
│   ├── apng-256/         4 张投放动图 256×256 · 4 帧 · 170ms/帧 · 约 106KB/张   ← App 用
│   ├── apng/             4 张母版 512×512 · 4 帧（无损，体积较大）
│   ├── frames/           16 张单帧 512×512（帧轮播兜底）
│   ├── frames-256/       16 张单帧 256×256（帧轮播兜底 · 投放尺寸）
│   └── sprites/          4 张 2048×512 横向雪碧图（CSS steps() 方案）
├── raw/                  34 张生成原图（白底 + 水印，管线输入，可重跑）
├── tools/
│   ├── normalize.py      去白底 → 透明 → 统一尺寸 → APNG/帧/雪碧图
│   └── build_preview.py  扫描产物生成预览页
├── contact-sheet.png     30 张总览（灰底验证透明度）
├── contact-anim.png      16 帧动画总览
└── preview-pony.html     浏览器预览页（含底栏动效还原）
```

## 命名对照

与 `bear` / `duck` 完全同名，可直接被 `<sj-icon :name="...">` 解析。

- 记录类别 ×10：`01-feeding` 喂养 · `02-sleep` 睡眠 · `03-milestone` 里程碑 · `04-photo` 照片 ·
  `05-measure` 测量 · `06-poop` 便便 · `07-temp` 体温 · `08-med` 用药 · `09-text-mood` 心情 · `09-voice` 语音
- 底部导航 ×4：`10-tab-home` 时光轴 · `11-tab-growth` 成长 · `12-tab-family` 家庭 · `13-tab-me` 我的
- 功能入口 ×16：`20-fn-diary` 日记 · `21-fn-remind` 提醒 · `22-fn-backup` 备份 · `23-fn-privacy` 隐私 ·
  `24-fn-search` 搜索 · `25-fn-notify` 通知 · `26-fn-export` 导出 · `27-fn-trash` 回收站 ·
  `28-fn-invite` 邀请 · `29-fn-babies` 多宝宝 · `30-fn-elder` 长辈模式 · `31-fn-compare` 成长对比 ·
  `32-fn-card` 成长卡片 · `33-fn-video` 视频 · `34-fn-vaccine` 疫苗 · `35-fn-audit` 操作审计

## 接入 App（全部为新增文件，不动既有代码）

1. 把静帧投放到主题图标目录（新增子目录，`sj-icon` 会按 `/static/icons/{theme}/{name}.png` 自动解析）：

   ```bash
   mkdir -p suiji-uniapp/src/static/icons/pony
   cp suiji-icons/pony/512/*.png suiji-uniapp/src/static/icons/pony/
   ```

2. 让底部导航用动图：把 4 张 APNG 覆盖同名静帧即可，`sj-tabbar` 无需改动——
   `sj-icon` 的 `<image>` 直接播放 APNG（H5 / App webview / 微信小程序 image 均支持 APNG）。

   ```bash
   cp suiji-icons/pony/tab-anim/apng-256/*.png suiji-uniapp/src/static/icons/pony/
   ```

3. 若要注册为可切换主题，需要 3 处**增量**改动（涉及修改既有文件，确认后我再执行）：
   - `theme/theme.js`：`THEME_LABELS` 增加 `pony: '小马 · 樱花粉紫'`，`THEMES` 增加 `pony: { ...BASE, ...PONY }`
   - `theme/store.js`：主题枚举里加入 `pony`
   - `pages/me/me.vue`：换肤入口增加第三个选项

### APNG 不可用时的兜底

- **帧轮播**：`tab-anim/frames-256/{name}-f{1..4}.png`，用 `setInterval` 每 170ms 换 `<image :src>`。
- **雪碧图 + CSS**：`tab-anim/sprites/{name}-sheet.png`（2048×512），
  `animation: pony 680ms steps(4) infinite;` 配合 `background-position` 位移。
- **纯 CSS**：现有 `sj-tabbar` 的 `sjTabPop / sjTabFloat` 弹性动画对静帧同样生效，可叠加。

## 重新生成 / 调整管线

```bash
cd suiji-icons/pony
# 单图：去白底 + 统一尺寸（--content 改这个即可整体放大/缩小主体）
python tools/normalize.py --src raw/pony-raw-01-feeding_*.png --out 1024 --canvas 1024 --content 880
# 动图：按连通域拆帧 + 底部对齐 + 输出 frames/apng/sprites
python tools/normalize.py --grid raw/pony-grid-10-tab-home_*.png --out tab-anim/frames --canvas 512 --content 430 --base 10-tab-home --fps-ms 170
# 预览页
python tools/build_preview.py
```

管线细节：白底用**四边洪水填充**去除（保留表盘、奶瓶等主体内部白色块）；右下角生成水印按
浅灰小连通域清除（大面积浅色主体如灰色垃圾桶不会被误删）；动画帧共用同一缩放系数并按
**底部中心**对齐，避免帧间抖动和脚部漂移。
