# 岁记 (suiji)

**岁记**是一款宝宝成长记录 App：用时光轴记录喂养、睡眠、辅食、里程碑、身高体重、照片视频等成长点滴，支持多家庭成员共享、家庭动态通知、AI 成长日记与数据导出。

🌐 **在线官网**：<http://xichengli.cloud:30080/suiji-website/>

---

## ✨ 功能特性

- **时光轴主页**：按日聚合的成长动态流，当日记录一目了然
- **全维度记录**：喂养、睡眠、换尿布、辅食、用药、体温、身高体重、里程碑、照片视频
- **家庭共享**：家庭邀请码机制，家人各自登录、共享同一份成长档案
- **家人动态通知**：家人新增记录时自动推送（服务端落库，读后即焚）
- **AI 成长日记**：基于当日记录由 LLM 生成育儿日记草稿，可编辑归档
- **回收站**：删除内容 30 天内可恢复，超期自动物理清理
- **数据安全**：JWT 鉴权 + Redis 会话撤销账本、敏感接口应用层端到端加密（RSA-OAEP-256 + AES-256-CBC）、nginx 限流与日志脱敏
- **多端支持**：Android App（APK 下载见官网）、H5、微信小程序（uni-app 一码多端）

## 🏗️ 技术架构

| 层 | 技术 |
|---|---|
| 客户端 | uni-app（Vue 3 + Vite + uview-plus），一套代码编译 App / H5 / 小程序 |
| 服务端 | Python 3.12+ · FastAPI · SQLAlchemy 2 · Alembic 迁移 |
| 数据库 | PostgreSQL 16（业务数据）· Redis 7（幂等去重 + 会话撤销） |
| 文件存储 | 腾讯云 COS（S3 兼容对象存储，可切换本地磁盘） |
| 接入层 | nginx 统一入口（限流、日志脱敏、静态官网、TLS 可选） |
| 部署 | Docker Compose 一键编排（db + redis + api + nginx） |

## 📁 目录结构

```
suiji/
├── suiji-server/            # FastAPI 服务端（含 alembic 迁移、nginx 配置、compose 编排）
│   ├── app/                 # 应用代码（api / models / services / core）
│   ├── alembic/             # 数据库迁移
│   ├── nginx/               # 反向代理配置模板
│   ├── static/suiji-website/# 官网静态资源（由 nginx 直接对外提供）
│   ├── docker-compose.yml   # 一键部署编排
│   └── API-CONTRACT.md      # 前后端接口契约文档
├── suiji-uniapp/            # uni-app 客户端（Vue3 时光轴首页）
├── suiji-icons/             # 图标库与生成脚本
├── suiji-page-backgrounds/  # 页面背景资源
├── suiji-sound-design/      # 音效资源
└── suiji-website-v4/        # 官网源码
```

## 🚀 快速开始

### 服务端（Docker Compose，开发 / 生产两套环境）

编排按三层拆分：`docker-compose.yml`（公共底座）+ `docker-compose.dev.yml`（开发覆盖）/
`docker-compose.prod.yml`（生产覆盖），凭据分别走 `.env.dev` / `.env.prod`。

**开发环境**（源码热更新、数据走 Docker 具名卷不落地项目目录、放开 CORS 与 swagger、允许降级）：

```bash
cd suiji-server
cp .env.dev.example .env.dev   # 开发弱凭据已内置，按需调整
docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up -d
curl http://localhost:30000/healthz
```

**生产环境**（镜像内代码冻结、关闭降级、收紧文档白名单与 CORS、自动迁移）：

```bash
cd suiji-server
cp .env.prod.example .env.prod
# 逐项替换所有 REPLACE_ME_*：POSTGRES_PASSWORD / REDIS_PASSWORD /
# COS_ACCESS_KEY / COS_SECRET_KEY / JWT_SECRET / ADMIN_INIT_PASSWORD
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d
curl http://localhost:30080/healthz
```

开发环境宿主端口从 `30000` 起顺延（容器内端口不变）：

| 服务 | 宿主端口 | 容器端口 |
|---|---|---|
| nginx 统一入口 | `30000` | 80 |
| api（调试用，正常走 nginx） | `30001` | 8000 |
| PostgreSQL | `30002` | 5432 |
| Redis | `30003` | 6379 |

开发环境入口（生产默认仍为 `30080`，以 `.env.prod` 的 `NGINX_PORT` 为准）：

- API 地址：`http://localhost:30000/api/v1`
- 接口文档：`http://localhost:30000/docs`（生产默认仅本机可访问，在 env 的 `NGINX_ADMIN_ALLOW` 配白名单）
- 官网：`http://localhost:30000/suiji-website/`

> 常用配置：`DATA_DIR` 更改数据落盘目录、`NGINX_PORT` 更改对外端口、`RUN_MIGRATIONS=1` 使每次启动自动执行 Alembic 迁移。全部配置项及联动关系见 `.env.dev.example` / `.env.prod.example` 内注释。

#### 开发 / 生产差异对照

| 项 | 开发（dev） | 生产（prod） |
|---|---|---|
| 源码卷 / 热重载 | 挂载 `./app`，uvicorn `--reload` | 不挂源码卷，镜像内代码冻结 |
| 数据存储 | Docker 具名卷（`suiji-dev-*`，不写入项目目录）；`dev-init` 一次性容器在 api 启动前把卷属主交给运行用户 `suiji(1000)` | `./data` bind mount（正式数据，需备份） |
| 依赖降级 `SUIJI_ALLOW_FALLBACK` | `1`（可回退 SQLite / 本地磁盘） | `0`（依赖故障直接报错） |
| CORS | 放开 H5 开发服务器 5173/5174 | 留空，不开放宽松跨域 |
| 文档白名单 `NGINX_ADMIN_ALLOW` | `all`（局域网调试） | `127.0.0.1`（可配固定 IP/CIDR） |
| 传输加密 `CRYPTO_MODE` | `optional` | 客户端全量升级后改 `required` |
| 进程 | uvicorn `--reload` | 单 worker `--workers 1` |

### 客户端（uni-app，dev / prod 双环境）

前端按编译模式自动选后端地址，配置集中在 `src/config/app.js`：

| 编译命令 | 环境 | 默认后端地址 | 服务器切换器 |
|---|---|---|---|
| `npm run dev:h5` / `dev:mp-weixin` | dev | `http://localhost:30000/api/v1`（本地 Docker） | 开启，可手动切到云端 |
| `npm run build:h5` / `build:mp-weixin` | prod | `http://49.233.77.155:30080/api/v1`（云服务） | 关闭，固定云端 |

```bash
cd suiji-uniapp
npm install

# H5 开发调试（连本地 Docker 开发环境）
npm run dev:h5

# 微信小程序（生成到 dist/dev/mp-weixin，用微信开发者工具打开）
npm run dev:mp-weixin

# 生产构建（连云端）
npm run build:h5
npm run build:mp-weixin
```

- 环境判定依据 uni 注入的 `process.env.NODE_ENV`：`uni`（dev 命令）= development，`uni build` = production；地址与端口改动只改 `src/config/app.js`。
- H5 dev 端口固定为 `5173`（`vite.config.js` 里 `server.port` + `strictPort`）：端口被占时直接报错退出，不再静默漂移到 5174 等其他端口；若提示端口占用，先关掉残留的旧 dev 进程再启动。
- dev 包保留切换器，调试时可在登录页/「我的」页临时切到云端；prod 包隐藏切换入口。
- App 打包：用 HBuilderX 打开 `suiji-uniapp` 目录进行云打包/本地打包；prod 包默认云端地址，无需首次手动配置。

### 直连运行（开发调试，不依赖 Docker）

```bash
cd suiji-server
pip install -r requirements.txt
# .env 中 DATABASE_URL 可指向本机 PostgreSQL 或 sqlite
python app/main.py
```

## 📚 文档

- [接口契约 API-CONTRACT.md](suiji-server/API-CONTRACT.md)
- 产品需求文档（PRD）与技术设计文档（TDD）见仓库根目录

## 🔒 安全设计要点

- **端口收敛**：除 nginx 外，PostgreSQL / Redis / API 全部只绑 `127.0.0.1`，不经公网暴露
- **无弱密码兜底**：所有密码类变量缺失时容器直接拒绝启动，不会退化为公开占位密码
- **传输加密**：可选应用层端到端加密（`CRYPTO_MODE=required`），敏感接口密文上链路
- **限流与脱敏**：注册/登录/上传分接口限流；nginx 日志脱敏；`/docs` IP 白名单
- **会话撤销**：登出/改密即时生效（Redis 黑名单），JWT 不长期有效

## 🤝 参与贡献

欢迎 Issue 与 PR。提交前请运行服务端测试：

```bash
cd suiji-server && python -m pytest
```

## 📄 License

[Apache License 2.0](LICENSE)
