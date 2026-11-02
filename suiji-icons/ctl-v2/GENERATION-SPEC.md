# 岁记 ctl 控件图标 · 批量生成规格（v2 · 参考图模式）

## 输出
每张调用一次 ImageGen，必须带 `images` 参考图、`size="1024x1024"`、`name="<ip>-<编号>"`（如 `bear-45-ctl-avatar`）。
落盘到 `D:\project\traeData\suiji\vibe_images\` 即可，**不要**自己移动、改名、裁剪。后处理脚本统一收口。

参考图（`images` 参数，只传 1 张）：
- Bear 系列：`D:/project/traeData/suiji/suiji-icons/ctl-v2/rail/bear/40-ctl-btn-confirm.jpg`
- Duck 系列：`D:/project/traeData/suiji/suiji-icons/ctl-v2/rail/duck/40-ctl-btn-confirm.jpg`

## Bear prompt 模板
把 `{PROP}` 换成英文道具句，`{BGNAME}`/`{HEX}` 换成表中底色。其余逐字照抄，不要改写措辞。

```
Use case: app icon for a kawaii baby-growth app, part of an existing icon set
Input images: Image 1: style reference only — borrow its character design, line weight, palette and framing; do NOT copy its prop or its background color

Primary request: a new icon of the same baby bear character
Subject: a chubby cream-white baby bear, very large round head about half the total height, short wide muzzle with a small dark-brown oval nose, two tiny dark-brown dot eyes set wide apart, round pink blush circles on both cheeks, small round ears with peach-pink inner ears, tiny stubby arms and legs, plain cream feet with no paw pads; {PROP}
Style/medium: flat storybook vector-like sticker, thick even dark-brown outline of uniform weight, soft pastel palette, minimal shading
Composition/framing: subject centered, only about 55 percent of the canvas height, generous margin on all four sides
Scene/backdrop: solid flat pastel {BGNAME} {HEX} filling the entire square edge to edge, perfectly uniform, no gradient, no texture
Constraints: no border, no frame, no rounded-corner card, no drop shadow, no text, no letters, no signature, no watermark; square 1:1
```

## Duck prompt 模板
```
Use case: app icon for a kawaii baby-growth app, part of an existing icon set
Input images: Image 1: style reference only — borrow its character design, line weight, palette and framing; do NOT copy its prop or its background color

Primary request: a new icon of the same baby duck character
Subject: a chubby snow-white baby duck, round fluffy body slightly smaller than the head, a small tuft of three soft feathers on top of the head, two tiny dark-brown dot eyes set wide apart, short rounded orange beak, round pink blush circles on both cheeks, a light-blue bow scarf tied around the neck, tiny rounded orange webbed feet; {PROP}
Style/medium: flat storybook vector-like sticker, thick even dark-brown outline of uniform weight, soft pastel palette, minimal shading
Composition/framing: subject centered, only about 55 percent of the canvas height, generous margin on all four sides
Scene/backdrop: solid flat pastel {BGNAME} {HEX} filling the entire square edge to edge, perfectly uniform, no gradient, no texture
Constraints: no border, no frame, no rounded-corner card, no drop shadow, no text, no letters, no signature, no watermark; square 1:1
```

{PROP} 用第三人称单句，以 `it stands upright and ...` / `it sits ...` 开头，描述角色怎么持/推/指该道具；duck 用 wing 代替 hand/paw。

## 条目表

| 编号 | 控件 | 底色名 | HEX | 小熊道具 | 小鸭道具 |
|---|---|---|---|---|---|
| 44-ctl-badge-dot | 徽标红点 | apricot | #FBE6D3 | 已完成 | 已完成 |
| 45-ctl-avatar | 头像 | clay | #FBDBC6 | 双手捧一面白色圆形相框，框内是自己的笑脸 | 双翅捧一面白色圆形相框，框内是自己的笑脸 |
| 46-ctl-loading | 加载中 | lime | #D2F8BB | 绕着一圈三个渐变小圆点追跑，身体侧倾跑动 | 绕着一圈三个渐变小圆点快跑，身体侧倾 |
| 47-ctl-input | 输入框 | cream | #FDF6E6 | 坐姿握一支铅笔在白色圆角卡片上书写 | 握一支铅笔在白色圆角卡片上书写 |
| 48-ctl-clear | 清除输入 | sage-green | #DAE7E0 | 一爪按下白色圆形按钮上的珊瑚红叉号 | 翅尖按下白色圆形按钮上的珊瑚红叉号 |
| 49-ctl-search-voice | 语音搜索 | mint-aqua | #8AFFDE | 对着一支圆润天蓝麦克风张嘴说话，嘴边有两条声波弧 | 对着一支圆润天蓝麦克风张嘴，嘴边有两条声波弧 |
| 50-ctl-switch | 开关 | mint-green | #B4FBD1 | 一爪按压一枚横放的薄荷绿胶囊开关，白色圆钮在右侧 | 一翅按压一枚横放的薄荷绿胶囊开关，白色圆钮在右侧 |
| 51-ctl-checkbox | 复选框 | lilac | #CBBAEE | 举一爪在白色圆角方框里画蜂蜜橙对勾 | 举翅在白色圆角方框里画蜂蜜橙对勾 |
| 52-ctl-radio | 单选框 | sky-blue | #C1F2FF | 单爪尖按下一枚天蓝色圆点单选钮，圆点已填实 | 翅尖按下一枚天蓝色圆点单选钮，圆点已填实 |
| 53-ctl-slider | 滑块 | tangerine | #FBC98C | 坐在一根白色滑杆上，双手扶蜂蜜橙圆形滑块 | 坐在一根白色滑杆上，双翅扶蜂蜜橙圆形滑块 |
| 54-ctl-numberbox | 步进器 | greige | #EBE7E6 | 左右爪各按一枚大号圆形按钮，左减号右加号 | 双翅各按一枚大号圆形按钮，左减号右加号 |
| 55-ctl-rate | 评分 | coral-pink | #FF9597 | 闭眼抱一颗大红色爱心，脸颊贴住爱心 | 闭眼抱一颗大红色爱心，脸颊贴住爱心 |
| 56-ctl-segment | 分段器 | sand-yellow | #FAEDC3 | 双爪推动一枚白色三段胶囊分段器，选中段蜂蜜橙 | 双翅推一枚白色三段胶囊分段器，选中段蜂蜜橙 |
| 57-ctl-picker | 选择器 | violet | #D1C0F6 | 侧身用一爪拨动竖向三列圆角滚轮，中间行高亮 | 侧身用翅拨动竖向三列圆角滚轮，中间行高亮 |
| 58-ctl-upload | 图片上传 | coral-red | #FF948E | 双手把一张白色圆角照片举过头顶 | 双翅把一张白色圆角照片举过头顶 |
| 59-ctl-nav-back | 导航返回 | pink | #FCC4D1 | 侧身一爪指向左侧一枚蜂蜜橙大箭头（箭头指向画面左方） | 侧身一翅指向左侧一枚蜂蜜橙大箭头（箭头指向画面左方） |
| 60-ctl-nav-more | 导航更多 | olive | #DBD6AE | 已完成 | 已完成 |
| 61-ctl-tabs | 选项卡 | amber | #FFCB85 | 已完成 | 已完成 |
| 62-ctl-steps | 步骤条 | light-cyan | #C8EDF3 | 已完成 | 已完成 |
| 63-ctl-cell | 单元格 | tan | #EDC9A5 | 双爪推一行白色圆角长条卡片，卡片右端有蜂蜜橙箭头 | 双翅推一行白色圆角长条卡片，右端蜂蜜橙箭头 |
| 64-ctl-modal-warn | 警示对话框 | rose | #F8BCBC | 举一块珊瑚红圆角三角警示牌，牌中白色感叹号 | 举一块珊瑚红圆角三角警示牌，牌中白色感叹号 |
| 65-ctl-modal-info | 信息对话框 | ice-blue | #BAE8FF | 抱一个天蓝色圆角对话气泡，气泡中白色小写字母 i | 抱一个天蓝色圆角对话气泡，气泡中白色小写字母 i |
| 66-ctl-modal-ok | 成功对话框 | pale-green | #CBFFD6 | 举一面薄荷绿圆角小旗，旗上白色对勾 | 举一面薄荷绿圆角小旗，旗上白色对勾 |
| 67-ctl-popup | 底部面板 | soft-apricot | #FFD5AF | 从一块白色圆角面板后探出上半身，一爪举起打招呼 | 从一块白色圆角面板后探出身子，一翅举起打招呼 |
| 68-ctl-toast | 轻提示 | blush-pink | #FFE1E4 | 头顶浮出一个白色圆角小气泡，气泡里一颗蜂蜜橙对勾 | 头顶浮出一个白色圆角小气泡，里面蜂蜜橙对勾 |
| 69-ctl-empty | 空状态 | ice-blue-cyan | #CBEFFF | 掀开一只空奶纸箱的盖子往里张望，箱子是空的 | 掀开一只空奶纸箱的盖子往里张望，箱子是空的 |
| 70-ctl-skeleton | 骨架屏 | warm-cream | #FDF6E6 | 抱一张由虚线圆角灰条组成的空白卡片轮廓 | 抱一张由虚线圆角灰条组成的空白卡片轮廓 |
| 71-ctl-progress | 进度条 | khaki | #ECE9C0 | 双爪用力推一条白色圆角进度条，已填充段蜂蜜橙 | 双翅推一条白色圆角进度条，已填充段蜂蜜橙 |
| 72-ctl-ring | 环形进度 | soft-pink | #FEDFE5 | 坐在一个大圆环中央，圆环一段是蜂蜜橙进度 | 坐在一个大圆环中央，圆环一段是蜂蜜橙进度 |
| 73-ctl-calendar | 日历单选 | pale-yellow | #FEEDA5 | 已完成 | 抱白色圆角日历卡，蜂蜜橙顶栏，翅尖指向单个被圈选的日期 |
| 74-ctl-calendar-range | 日历区间 | cream-gold | #FDE8BD | 双手拉开一条白色日历带，两端各钉一枚蜂蜜橙圆钉 | 双翅拉开一条白色日历带，两端各钉一枚蜂蜜橙圆钉 |

## 注意
- 标「已完成」的**不要**重复生成。
- 符号类道具（对勾 / 加号 / 减号 / 感叹号 / 字母 i）写成 `a white check-mark shape` / `a rounded plus sign` / `a rounded minus sign` / `a white exclamation-mark shape` / `a small white letter i glyph`。
- 每张只调一次 ImageGen，不要评估、不要重试。
