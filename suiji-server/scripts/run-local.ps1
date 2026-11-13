# 本地直连启动（不依赖 Docker / PostgreSQL / MinIO）：
#   SQLite 库 ./data/suiji.db，媒体落 ./data/media，Redis 走进程内存降级。
# 与 .env（面向 compose/生产）互不覆盖：这里只在本进程内注入环境变量。
# 用法：在 suiji-server 目录执行  pwsh scripts/run-local.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

$env:DATABASE_URL      = 'sqlite:///./data/suiji.db'
$env:MEDIA_BACKEND     = 'local'
$env:REDIS_URL         = ''
$env:SUIJI_ALLOW_FALLBACK = '1'
$env:RUN_MIGRATIONS   = '0'
$env:PORT              = '30080'
$env:RELOAD            = '0'
$env:HOST              = '127.0.0.1'

& .\.venv\Scripts\python.exe app/main.py