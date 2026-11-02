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
| 文件存储 | MinIO（S3 兼容对象存储，可切换本地磁盘） |
| 接入层 | nginx 统一入口（限流、日志脱敏、静态官网、TLS 可选） |
| 部署 | Docker Compose 一键编排（db + redis + minio + api + nginx） |

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

### 服务端（Docker Compose 一键部署）

```bash
cd suiji-server

# 1. 准备环境变量（必须配置所有密码类变量与 JWT_SECRET，缺失时拒绝启动）
cp .env.example .env
#    编辑 .env，设置 POSTGRES_PASSWORD / REDIS_PASSWORD /
#    MINIO_ROOT_PASSWORD / MINIO_SECRET_KEY / JWT_SECRET 等强随机凭据

# 2. 启动（首次会自动构建 api 镜像）
docker compose up -d

# 3. 验证网关
curl http://localhost:30080/healthz
```

启动后统一入口为 nginx（默认 `30080` 端口）：

- API 地址：`http://<host>:30080/api/v1`
- 接口文档：`http://<host>:30080/docs`（默认仅容器内可访问，可在 `.env` 中配置白名单）
- 官网：`http://<host>:30080/suiji-website/`

> 常用配置：`DATA_DIR` 更改数据落盘目录、`NGINX_PORT` 更改对外端口、`RUN_MIGRATIONS=1` 使每次启动自动执行 Alembic 迁移。全部配置项及联动关系见 `.env.example` 内注释。

### 客户端（uni-app）

```bash
cd suiji-uniapp
npm install

# H5 开发调试
npm run dev:h5

# 微信小程序（生成到 dist/dev/mp-weixin，用微信开发者工具打开）
npm run dev:mp-weixin

# 生产构建
npm run build:h5
npm run build:mp-weixin
```

App 打包：用 HBuilderX 打开 `suiji-uniapp` 目录进行云打包/本地打包；首次启动后在登录页配置服务器地址 `http://<host>:30080/api/v1`。

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

- **端口收敛**：除 nginx 外，PostgreSQL / Redis / MinIO / API 全部只绑 `127.0.0.1`，不经公网暴露
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
