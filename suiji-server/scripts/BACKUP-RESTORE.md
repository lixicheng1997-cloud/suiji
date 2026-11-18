# 备份与恢复演练手册（P0）

> 配套脚本：`scripts/backup.py`（备份）、`scripts/restore.py`（恢复）。
> 原则：**能恢复才算备份有效**。每次变更部署、升级迁移后都应做一次恢复演练。

## 1. 备份范围

| 类别 | 是否纳入备份 | 说明 |
|---|---|---|
| 业务数据库（PostgreSQL / SQLite） | ✅ | PG 走 `pg_dump` 导出 SQL 并 gzip；SQLite 走 online backup API 一致拷贝 |
| 加密密钥（RSA 私钥、字段加密密钥） | ✅ | 不随数据库 dump，单独复制；**丢了密文无法解密**，必须与 DB 同批备份 |
| 媒体字节（图片/视频/附件） | ❌ 本次不打包 | 体量大；本地磁盘走文件级备份，COS/OSS 走存储侧快照/复制/生命周期策略 |
| 配置文件 `.env.dev` / `.env.prod` | ❌ 脚本不复制 | 含明文密钥，应纳入受控的密钥管理/离线备份，不与数据备份混放 |

每份备份生成 `manifest.json`：时间、数据库方言、脱敏连接串、文件清单、大小、sha256、媒体后端说明。

## 2. 日常备份

在 `suiji-server` 目录下执行：

```bash
# 备份到 data/backups，保留最近 7 份
python scripts/backup.py

# 保留最近 14 份，指定备份目录
python scripts/backup.py --keep 14 --out-dir /var/backup/suiji
```

### 定时执行

**Linux / 容器（cron）**——每天 02:30 备份：

```cron
30 2 * * *  cd /app && python scripts/backup.py --keep 14 >> /var/log/suiji-backup.log 2>&1
```

**未来 k3s / 容器编排**：用 CronJob 挂载备份卷，同一镜像执行 `python scripts/backup.py`；备份卷独立于应用容器生命周期。

**Windows 本机**：任务计划程序调用 `python scripts\backup.py`，工作目录设为 `suiji-server`。

### 备份保留与异地

- 本地轮转只解决磁盘膨胀；**必须有一份异地/离线副本**（对象存储、另一台机器、压缩归档），防主机损坏或误删。
- 定期校验 `manifest.json` 中 sha256 与文件大小未损坏。

## 3. 恢复步骤

### 3.1 列出可用备份

```bash
python scripts/restore.py --list
```

### 3.2 先 dry-run 核对

```bash
python scripts/restore.py --backup backup-YYYYMMDD-HHMMSS
```

### 3.3 正式恢复

1. **先停止应用进程**（避免连接占用、边恢复边写入）；
2. 执行恢复（`--confirm`）：

```bash
python scripts/restore.py --backup backup-YYYYMMDD-HHMMSS --confirm
```

脚本会在恢复前**自动把当前库再备一份**到 `pre-restore-<时间戳>`，便于回退；
恢复后启动应用，如表结构落后，由 Alembic 迁移对齐（`RUN_MIGRATIONS=1`）。

### 3.4 方言一致性

备份方言（sqlite / postgresql）必须与当前 `DATABASE_URL` 一致，脚本拒绝跨方言恢复。
如需从 SQLite 迁到 PostgreSQL，走专门的迁移流程，不用本恢复脚本。

## 4. 恢复演练验证清单

每季度（或重大升级后）至少演练一次，逐项勾选：

- [ ] 在隔离环境（不接生产库）用最近一份备份完成恢复；
- [ ] 数据库可打开，表数量 / 记录数与备份时点大致吻合；
- [ ] 加密密钥还原后，宝宝姓名、记录备注等密文可正常解密显示；
- [ ] 抽几条媒体记录：记录存在，对象链接/文件可访问；
- [ ] 应用启动无密钥/解密类报错，`/readyz` 返回就绪；
- [ ] 记录演练日期、备份编号、恢复耗时、发现的问题。

## 5. 常见问题

- **PG 提示找不到 `pg_dump` / `psql`**：容器内 postgres 镜像自带；本机需安装 postgresql-client 并加入 PATH。
- **SQLite 恢复后旧连接仍占用文件**：先停应用再恢复；WAL 文件（`-wal`/`-shm`）由 backup API 一致处理，无需手工拷贝。
- **密钥恢复后解密失败**：确认恢复的是与该批数据库**同一备份**里的 `crypto/` 目录；跨备份混用密钥会导致字段密文无法解密。
- **媒体文件缺失**：本脚本不含媒体字节；需从文件级备份或对象存储快照单独恢复。
