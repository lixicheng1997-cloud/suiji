"""存量媒体迁移：MinIO → 腾讯云 COS（storage_key 保持不变，台账行无需改动）。

背景：存储后端从同机 MinIO 切到 COS 后，迁移前已落在 MinIO 的旧对象需要搬到 COS，
否则切后端后旧记录读不到。存量体量很小（生产约 6 个对象 / 2.36MB），脚本按台账
`file_object` 逐条搬运，幂等可重跑，**不删除源对象**（验证通过后再另行清理 MinIO）。

用法（在 suiji-server 目录下，容器或宿主机带齐 MINIO_* 与 COS_* 环境变量）：

    # 先只读核对：列清单、检查源对象存在性与台账大小/sha256，不写 COS
    python scripts/migrate_minio_to_cos.py --dry-run

    # 正式搬运：源字节写入 COS 同名 key；已存在且大小一致则跳过
    python scripts/migrate_minio_to_cos.py --apply

退出码：0 全部成功（含跳过）；1 有失败对象。
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.models import FileObject  # noqa: E402
from app.media.store import CosMediaStore, MinioMediaStore  # noqa: E402


def _build_source() -> MinioMediaStore:
    return MinioMediaStore(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
        region=settings.minio_region,
        public_url=settings.minio_public_url,
    )


def _build_target() -> CosMediaStore:
    return CosMediaStore(
        endpoint=settings.cos_endpoint,
        access_key=settings.cos_access_key,
        secret_key=settings.cos_secret_key,
        bucket=settings.cos_bucket,
        region=settings.cos_region,
        public_url=settings.cos_public_url,
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def migrate(apply: bool) -> int:
    src = _build_source()
    dst = _build_target()

    db = SessionLocal()
    try:
        rows = db.query(FileObject).filter(FileObject.deleted_at.is_(None)).all()
    finally:
        db.close()

    print(f"台账待迁移对象：{len(rows)} 个（模式：{'APPLY 写入 COS' if apply else 'DRY-RUN 只读核对'}）")
    ok = skip = fail = 0
    failures: list[str] = []

    for row in rows:
        key = (row.storage_key or "").replace("\\", "/")
        if not key:
            print(f"  [跳过] {row.id}：storage_key 为空")
            skip += 1
            continue
        label = f"{key}（台账 {row.size}B / {row.content_type or '?'}）"

        try:
            stream = src.open_stream(key)
            if stream is None:
                raise RuntimeError("源对象不可读")
            data = b"".join(stream)
        except Exception as exc:
            print(f"  [失败] {label}：源读取失败：{exc}")
            fail += 1
            failures.append(key)
            continue

        if row.size and len(data) != row.size:
            print(f"  [警告] {label}：源字节 {len(data)} 与台账 size {row.size} 不一致")
        if row.sha256:
            actual = _sha256(data)
            if actual != row.sha256:
                print(f"  [警告] {label}：sha256 不一致（台账 {row.sha256[:12]}… / 实得 {actual[:12]}…）")

        if not apply:
            print(f"  [核对] {label}：源可读 {len(data)}B")
            ok += 1
            continue

        # 幂等：目标已存在且大小一致则跳过
        if dst.exists(key) and dst.size(key) == len(data):
            print(f"  [跳过] {label}：COS 已存在且大小一致")
            skip += 1
            continue

        ct = row.content_type or "application/octet-stream"
        dst._client.put_object(
            Bucket=dst.bucket,
            Key=key,
            Body=data,
            ContentType=ct,
            ContentLength=len(data),
        )
        if dst.size(key) != len(data):
            raise RuntimeError("写入后大小核对不符")
        print(f"  [已迁移] {label} → COS {len(data)}B")
        ok += 1

    print(f"\n汇总：成功 {ok}，跳过 {skip}，失败 {fail}")
    if failures:
        print("失败清单：")
        for k in failures:
            print(f"  - {k}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MinIO → COS 存量媒体迁移")
    parser.add_argument("--apply", action="store_true", help="真正写入 COS；缺省为 dry-run 只读核对")
    parser.add_argument("--dry-run", action="store_true", help="只读核对，不写 COS（默认）")
    args = parser.parse_args()
    return migrate(apply=args.apply)


if __name__ == "__main__":
    sys.exit(main())
