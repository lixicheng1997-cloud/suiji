"""数据库 + 加密密钥备份脚本（P0：防止单点数据丢失）。

备份内容：
  1. 业务数据库：
     - SQLite：用 sqlite3 online backup API 做一致拷贝（WAL 下也不拷到中间态）；
     - PostgreSQL：调用 pg_dump 导出 plain SQL（再 gzip）；pg_dump 不在 PATH 时
       明确报错退出，不允许“备份成功但其实没导出”。
  2. 加密密钥目录：RSA 私钥 / 字段加密密钥（**不随数据库 dump**，丢了密文无法解密，
     必须单独备份并随 DB 一起恢复）。
  3. manifest.json：时间、方言、脱敏连接串、文件清单、大小与 sha256、媒体后端说明。

媒体字节（图片/视频/附件）体量大，本脚本不打包；manifest 里记录后端与目录，
本地磁盘媒体需另走文件级备份，MinIO/云 OSS 需走存储侧快照或生命周期策略。

用法（在 suiji-server 目录下）：
    python scripts/backup.py                 # 备份到 data/backups，保留最近 7 份
    python scripts/backup.py --keep 14       # 保留最近 14 份
    python scripts/backup.py --out-dir D:/backup/suiji
    python scripts/backup.py --print-manifest

退出码：0 成功；1 备份失败（PG 客户端缺失 / 数据库不可达 / 写盘失败等）。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402

DEFAULT_KEEP = 7
BACKUP_PREFIX = "backup-"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _mask_url(url: str) -> str:
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "<unparsable>"


def _backup_sqlite(src_url: str, dest: Path) -> dict:
    """在线一致拷贝 SQLite 库；返回产物文件信息。"""
    src_path = Path(make_url(src_url).database)
    if not src_path.exists():
        # 库文件还没生成（全新环境）：备份一个空库，避免恢复时找不到基准
        src_path.parent.mkdir(parents=True, exist_ok=True)
        sqlite3.connect(str(src_path)).close()
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / "db.sqlite"
    src = sqlite3.connect(str(src_path))
    try:
        dst = sqlite3.connect(str(out))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return {"name": out.name, "size": out.stat().st_size, "sha256": _sha256_file(out)}


def _backup_postgres(src_url: str, dest: Path) -> dict:
    """pg_dump 导出并 gzip 压缩。"""
    url = make_url(src_url)
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise RuntimeError(
            "未找到 pg_dump：请在 PATH 中提供 PostgreSQL 客户端工具 "
            "（容器内 postgres 镜像自带；本机可装 postgresql-client）"
        )
    plain = dest / "db.sql"
    gz = dest / "db.sql.gz"
    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = url.password
    cmd = [
        pg_dump,
        f"--host={url.host or 'localhost'}",
        f"--port={url.port or 5432}",
        f"--username={url.username or 'suiji'}",
        f"--dbname={url.database or 'suiji'}",
        "--no-owner",
        "--no-privileges",
        "--file=" + str(plain),
    ]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump 失败（exit {proc.returncode}）：{proc.stderr.strip()}")
    # gzip 压缩，删掉中间 plain 文件
    with plain.open("rb") as f_in, gzip.open(gz, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    plain.unlink(missing_ok=True)
    return {"name": gz.name, "size": gz.stat().st_size, "sha256": _sha256_file(gz)}


def _backup_crypto(dest: Path) -> list[dict]:
    """复制 RSA 私钥与字段加密密钥；不存在的条目跳过并在 manifest 标注。"""
    crypto_dir = dest / "crypto"
    crypto_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict] = []
    for label, key_file in (
        ("rsa_private", settings.crypto_key_file),
        ("field_key", settings.field_key_file),
    ):
        src = Path(key_file)
        if not src.exists():
            files.append({"label": label, "name": src.name, "present": False})
            continue
        out = crypto_dir / src.name
        shutil.copy2(src, out)
        files.append({
            "label": label,
            "name": out.name,
            "present": True,
            "size": out.stat().st_size,
            "sha256": _sha256_file(out),
        })
    return files


def _media_summary() -> dict:
    if settings.media_backend == "minio":
        return {
            "backend": "minio",
            "note": "对象在 MinIO/OSS 桶内，本脚本不复制字节；需走存储侧快照/复制策略。",
        }
    media_dir = settings.media_dir
    count = 0
    total = 0
    if media_dir.exists():
        for p in media_dir.rglob("*"):
            if p.is_file():
                count += 1
                total += p.stat().st_size
    return {
        "backend": "local",
        "dir": str(media_dir),
        "file_count": count,
        "bytes": total,
        "note": "本地媒体未纳入本次备份；需另行文件级备份。",
    }


def _rotate(backup_root: Path, keep: int) -> list[str]:
    """保留最近 keep 份，删除更早的备份目录。返回被删除的目录名。"""
    dirs = sorted(
        (p for p in backup_root.iterdir() if p.is_dir() and p.name.startswith(BACKUP_PREFIX)),
        key=lambda p: p.name,
    )
    removed: list[str] = []
    for old in dirs[:-keep] if keep > 0 else dirs:
        shutil.rmtree(old, ignore_errors=True)
        removed.append(old.name)
    return removed


def run_backup(out_dir: Path, keep: int, rotate: bool = True) -> Path:
    # 以运行时实际 engine 为准：跟随数据库不可用时的 SQLite 降级，避免备份到配置串里
    # 一个连不上的库。
    from app.core.db import engine

    db_url = str(engine.url)
    dialect = engine.dialect.name
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = out_dir / f"{BACKUP_PREFIX}{stamp}"
    dest.mkdir(parents=True, exist_ok=True)

    started = time.time()
    if dialect == "sqlite":
        db_entry = _backup_sqlite(db_url, dest)
    elif dialect == "postgresql":
        db_entry = _backup_postgres(db_url, dest)
    else:
        raise RuntimeError(f"暂不支持的数据库方言：{dialect}")
    crypto_entries = _backup_crypto(dest)

    manifest = {
        "app": "suiji-server",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.time() - started, 3),
        "db": {"dialect": dialect, "url_masked": _mask_url(db_url), "file": db_entry},
        "crypto": crypto_entries,
        "media": _media_summary(),
    }
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    removed = _rotate(out_dir, keep) if rotate else []
    manifest["rotated_away"] = removed
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="岁记数据库与加密密钥备份")
    parser.add_argument("--out-dir", default=str(settings.media_dir.parent / "backups"),
                        help="备份根目录（默认 data/backups）")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP, help="保留最近 N 份（默认 7）")
    parser.add_argument("--print-manifest", action="store_true", help="打印 manifest")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        dest = run_backup(out_dir, args.keep)
    except Exception as exc:
        print(f"[备份失败] {exc}", file=sys.stderr)
        return 1

    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    print(f"[备份完成] {dest}")
    print(f"  数据库：{manifest['db']['dialect']} → {manifest['db']['file']['name']} "
          f"({manifest['db']['file']['size']} bytes)")
    present = [c['name'] for c in manifest['crypto'] if c.get('present')]
    print(f"  密钥：{', '.join(present) if present else '无可用密钥文件'}")
    print(f"  媒体：{manifest['media']['backend']}（未打包字节，见 manifest 说明）")
    if manifest.get("rotated_away"):
        print(f"  轮转清理：{', '.join(manifest['rotated_away'])}")
    if args.print_manifest:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
