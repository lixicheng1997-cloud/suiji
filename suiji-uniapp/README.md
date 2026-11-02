# 岁记 · 宝宝成长记录 App（uni-app 单机版）

依据《岁记 PRD v1.0》与《技术设计文档 TDD v2.0（uniapp 单机版）》实现。纯本地存储、零网络依赖（除用户显式配置的 AI 日记模型调用），支持 H5 / App / 小程序。

## 快速开始

```bash
npm install
npm run dev:h5      # H5 开发（默认 http://localhost:5173）
npm run build:h5    # H5 发行构建
```

首次启动为空库：先在引导/同意页创建宝宝档案，再从首页记录数据。

## 目录结构

```
src/
├── pages/              # 10 个页面（Vue3 Options API，模板与样式为设计定稿，不可随意改动）
│   ├── index/          # 时光轴首页（今日概览 + 按日分组记录 + 快速记录入口）
│   ├── editor/         # 记录表单（8 类记录 Schema 驱动，支持编辑回填）
│   ├── detail/         # 记录详情（编辑/删除）
│   ├── grow/           # 生长曲线（WHO 百分位带 SVG）+ 测量列表 + 里程碑清单
│   ├── diary/          # AI 成长日记（草稿生成/归档）
│   ├── family/         # 家庭空间（本机联系人 + 由记录派生的动态）
│   ├── vaccine/        # 疫苗接种时间表
│   ├── me/             # 我的（设置开关/备份导出/AI 配置）
│   ├── onboard/        # 首次引导三步
│   └── consent/        # 监护人同意分项（建档前置）
├── utils/
│   ├── api.js          # ★ 数据门面：页面层唯一数据入口
│   └── mock.js         # 展示元数据（类型色板/徽标文案/头像/静态文案），不含业务数据
├── domain/             # 领域层：纯函数，零平台依赖，可单测
│   ├── shared/id.js    # genId(prefix)
│   ├── shared/date.js  # fmt/parse/now/dayKey/dayLabel/ageText/ageMonths（早产按 37 周矫正）
│   ├── growth.js       # WHO 2006 标准 P3–P97 锚点表 + 线性插值百分位 + 曲线数据
│   ├── summary.js      # 记录 → 标题/副文案/徽标（summarize）
│   ├── stats.js        # 今日概览统计（只读 occurred_at）
│   └── diary.js        # 事实提取/模板日记/禁词表/三重校验（scanBanned/checkCitations/checkFactWhitelist）
├── infra/              # 基础设施层：平台差异全部收口于此
│   ├── platform.js     # 唯一允许触碰 plus.* / DOM 的文件（KV/文件/选图/toast）
│   ├── db.js           # 本地仓储：JSON 表 + schema_version + 快照提交回滚 + 备份快照
│   ├── backup.js       # 备份包：AES-256-CBC + PBKDF2 加密信封、sha256 校验、自动备份滚动 7 份
│   └── ai/llmClient.js # OpenAI 兼容 /chat/completions 客户端（30s 超时）+ 日记 JSON 解析
├── App.vue             # onLaunch 调 api.init()
├── uni.scss            # 设计令牌（$sj-*），禁止页面散落硬编码色值
└── pages.json          # 路由与 tabBar
```

## 分层硬约束（TDD §4.2）

```
pages/*  ──只调用──▶  utils/api.js  ──▶  domain/*（纯函数）
                          │
                          └──▶  infra/*（存储/加密/网络/平台 API）
```

- 页面不得 import domain/infra 内部模块，只认 api.js 的函数契约。
- domain 层不得出现 uni.*/plus.*/DOM。
- infra/platform.js 是全工程唯一允许 plus.* 与裸 DOM 的文件。

## 数据模型与存储

存储后端为 `uni.setStorageSync`，每表一个 JSON 数组键，前缀 `sj_`：

| 键 | 内容 | 关键字段 |
|---|---|---|
| `sj_baby` | 宝宝档案 | birth_date、gestational_weeks、gender、is_active |
| `sj_entry` | 时光轴记录 | **occurred_at**（统计口径）/created_at 分离、payload、badge、photo |
| `sj_entry_media` | 照片记录媒体 | entry_id、local_path |
| `sj_measurement` | 测量点 | metric(height/weight/head)、value、entry_id |
| `sj_milestone_record` | 里程碑清单 | name、domain、done、achieved_at、source_entry_id |
| `sj_vaccine` | 疫苗时间表 | n、dose、age_months、plan_date、done、done_date |
| `sj_member` | 家庭成员（本机联系人） | name、role、color |
| `sj_ai_journal` | 日记草稿/归档 | range、paras[{text,src,entryIds}]、status、model_version |
| `sj_app_setting` | 设置聚合 | account/switches/family/consent/ai/backup |
| `sj_schema_version` | 库版本号 | 首建建表；升级前自动存 pre_migration_backup |
| `sj_auto_backups` | 自动备份信封 | 滚动 7 份 |

App 端可将 db.js 后端替换为 `plus.sqlite`，api.js 契约不变。

## 核心机制

- **记录保存**（`api.saveEntry`）：payload → `summary.js` 生成标题/徽标；measure 同快照写入 measurement 行并计算百分位徽标；milestone 联动 milestone_record 打卡；photo 写 entry_media。多表经 `db.commit` 快照提交，失败整体回滚。`family.readOnly` 开启时拒绝写入。
- **生长曲线**（`domain/growth.js`）：0–24 月龄 P3/P15/P50/P85/P97 锚点表，月龄分段线性插值；实测值反向插值得百分位并夹紧 0.1–99.9。早产儿按 37 周回拨矫正月龄。
- **AI 日记管线**（`api.generateDiary`）：近 7 天事实提取 →（配置了 Key 且勾选同意时调 LLM，输出经禁词/引用完整性/事实白名单三重校验，失败重生成 1 次）→ 模板兜底。无任何记录时不生成草稿。禁词表拦截一切医学判断与夸大用语。
- **备份**（`infra/backup.js`）：单 JSON 信封（偏离 TDD 的 ZIP，自用场景简化），PBKDF2(SHA256,10000) 派生密钥 + AES-256-CBC + sha256 完整性校验；API Key 不进包。导入按 id 合并（同 id 取 updated_at 新者），导入前自动全量备份可回滚。
- **API Key 安全**：`getAiConfig` 只返回 `hasKey`，不回显密钥。

## 已知限制

- editor 表单沿用原型 UI，部分展示值（温度 37°C、用时 12 分钟、剂量等）无编辑控件，按显示值入库。
- 备份导入的文件选择入口仅 H5 可用，其余端不支持导入。
- PDF 导出、健康日志可见性等原型「示意」行保留 toast，未实现。
- 头像与示例图为文生图占位 URL，正式版需替换为 OSS 资源。
