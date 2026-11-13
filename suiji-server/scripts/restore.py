"""从备份恢复数据库与加密密钥（P0 配套：可恢复才算备份有效）。

安全约定：
  - 恢复前**自动先备份当前库**到 `pre-restore-<时间戳>`，防止覆盖后无法回退；
  - 默认 dry-run，只打印将要执行的动作；加 `--confirm` 才真正写库/写密钥；
  - 恢复前请先停止应用进程（避免连接占用 / 边恢复边写入）；恢复后启动服务，
    由 Alembic 迁移对齐表结构（RUN_MIGRATIONS=1）。

用法（在 suiji-server 目录下）：
    python scripts/restore.py --list                      # 列出可用备份
    python scripts/restore.py --backup backup-20261113-100000            # dry-run
    python scripts/restore.py --backup backup-20261113-100000 --confirm  # 执行恢复
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
import backup as backup_lib  # noqa: E402

BACKUP_PREFIX = "backup-"
PRE_RESTORE_PREFIX = "pre-restore-"


def _backup_root() -> Path:
    return settings.media_dir.parent / "backups"


def _load_manifest(backup_dir: Path) -> dict:
    return json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))


def _resolve_backup(name_or_dir: str) -> Path:
    root = _backup_root()
    p = Path(name_or_dir)
    if p.is_dir():
        return p
    candidate = root / name_or_dir
    if candidate.is_dir():
        return candidate
    raise SystemExit(f"找不到备份目录：{name_or_dir}（在 {root} 下也未命中）")


def list_backups() -> None:
    root = _backup_root()
    if not root.exists():
        print("（暂无备份目录）")
        return
    dirs = sorted(
        (p for p in root.iterdir() if p.is_dir() and p.name.startswith(BACKUP_PREFIX)),
        key=lambda p: p.name,
        reverse=True,
    )
    if not dirs:
        print("（暂无备份）")
        return
    for d in dirs:
        try:
            m = _load_manifest(d)
            db = m["db"]
            print(f"{d.name}  {m['created_at']}  {db['dialect']}  "
                  f"{db['file']['name']} ({db['file']['size']} bytes)")
        except Exception as exc:
            print(f"{d.name}  manifest 读取失败：{exc}")


def _restore_sqlite(backup_db: Path, target_url: str, confirm: bool) -> list[str]:
    target = Path(make_url(target_url).database)
    actions = [f"SQLite 目标库：{target}"]
    if not confirm:
        actions.append("  [dry-run] 将用备份 db.sqlite 在线一致覆盖目标库")
        return actions
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(backup_db))
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    actions.append("  SQLite 库已还原")
    return actions


def _restore_postgres(backup_gz: Path, target_url: str, confirm: bool) -> list[str]:
    url = make_url(target_url)
    psql = shutil.which("psql")
    if not psql:
        raise RuntimeError("未找到 psql：请在 PATH 中提供 PostgreSQL 客户端工具")
    plain = backup_gz.with_suffix("")  # 去掉 .gz
    with gzip.open(backup_gz, "rb") as f_in, plain.open("wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    actions = [
        f"PostgreSQL 目标：{url.render_as_string(hide_password=True)}",
        f"  执行 psql 导入：{plain.name}",
    ]
    if not confirm:
        plain.unlink(missing_ok=True)
        actions.append("  [dry-run] 未真正导入")
        return actions
    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = url.password
    cmd = [
        psql,
        f"--host={url.host or 'localhost'}",
        f"--port={url.port or 5432}",
        f"--username={url.username or 'suiji'}",
        f"--dbname={url.database or 'suiji'}",
        "-v", "ON_ERROR_STOP=1",
        "-f", str(plain),
    ]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    plain.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"psql 恢复失败（exit {proc.returncode}）：{proc.stderr.strip()}")
    actions.append("  PostgreSQL 库已还原")
    return actions


def _restore_crypto(backup_dir: Path, manifest: dict, confirm: bool) -> list[str]:
    mapping = {
        "rsa_private": Path(settings.crypto_key_file),
        "field_key": Path(settings.field_key_file),
    }
    actions: list[str] = []
    for entry in manifest.get("crypto", []):
        label = entry.get("label")
        if label not in mapping or not entry.get("present"):
            continue
        target = mapping[label]
        src = backup_dir / "crypto" / entry["name"]
        actions.append(f"密钥 {label}：{target}")
        if confirm:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            actions.append("  已还原")
        else:
            actions.append("  [dry-run] 未写入")
    return actions


def restore(backup_dir: Path, confirm: bool) -> int:
    from app.core.db import engine

    manifest = _load_manifest(backup_dir)
    dialect = manifest["db"]["dialect"]
    current_url = str(engine.url)
    current_dialect = engine.dialect.name
    if dialect != current_dialect:
        raise SystemExit(
            f"备份方言（{dialect}）与当前配置（{current_dialect}）不一致，拒绝跨方言恢复。"
        )

    print(f"将从备份恢复：{backup_dir.name}（{manifest['created_at']}）")
    if not confirm:
        print("（dry-run：加 --confirm 才真正写库/写密钥）")

    # 恢复前先把当前库备一份，便于回退
    if confirm:
        print("恢复前自动备份当前库 …")
        pre = backup_lib.run_backup(_backup_root(), keep=0, rotate=False)
        print(f"  当前库已备份到：{pre.name}")

    db_file = backup_dir / manifest["db"]["file"]["name"]
    if dialect == "sqlite":
        actions = _restore_sqlite(db_file, current_url, confirm)
    elif dialect == "postgresql":
        actions = _restore_postgres(db_file, current_url, confirm)
    else:
        raise SystemExit(f"暂不支持的方言：{dialect}")
    actions += _restore_crypto(backup_dir, manifest, confirm)

    for line in actions:
        print(line)
    print("完成后请启动应用；如表结构落后，由 Alembic 迁移对齐（RUN_MIGRATIONS=1）。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="岁记备份恢复")
    parser.add_argument("--list", action="store_true", help="列出可用备份")
    parser.add_argument("--backup", help="备份目录名或完整路径")
    parser.add_argument("--confirm", action="store_true", help="真正执行恢复（默认 dry-run）")
    args = parser.parse_args()

    if args.list:
        list_backups()
        return 0
    if not args.backup:
        parser.error("需要 --backup <目录名> 或 --list")
    try:
        return restore(_resolve_backup(args.backup), args.confirm)
    except Exception as exc:
        print(f"[恢复失败] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
