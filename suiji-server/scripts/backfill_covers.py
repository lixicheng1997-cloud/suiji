"""历史视频回填封面：为缺少 meta.cover_key 的视频台账补抽首帧 JPEG。

背景：服务端抽帧上线前上传的视频没有封面；本脚本逐条走后台同一套封面生成逻辑
（app.media.jobs._run_cover），幂等——已有 cover_key 的行会被跳过，可重复执行。

用法（在 suiji-server 目录下）：
    python scripts/backfill_covers.py              # 回填全部缺封面的视频
    python scripts/backfill_covers.py --dry-run    # 只列出待回填，不抽帧
    python scripts/backfill_covers.py --limit 20  # 最多处理 20 条

说明：抽帧依赖 ffmpeg（imageio-ffmpeg 静态二进制或 PATH ffmpeg）；本机/容器内
找不到二进制时对应行会静默跳过，日志由 app.media.jobs / app.media.cover 输出。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.db import SessionLocal  # noqa: E402
from app.models import FileObject  # noqa: E402


def _needs_cover(row: FileObject) -> bool:
    if not (row.content_type or "").lower().startswith("video/"):
        return False
    meta = row.meta if isinstance(row.meta, dict) else {}
    return not meta.get("cover_key")


def main() -> int:
    argv = sys.argv[1:]
    dry_run = "--dry-run" in argv
    limit = 0
    if "--limit" in argv:
        try:
            limit = int(argv[argv.index("--limit") + 1])
        except (IndexError, ValueError):
            print("--limit 需要一个整数")
            return 2

    with SessionLocal() as db:
        rows = (db.query(FileObject)
                  .filter(FileObject.deleted_at.is_(None))
                  .order_by(FileObject.created_at.asc())
                  .all())
        pending = [r for r in rows if _needs_cover(r)]
        if limit > 0:
            pending = pending[:limit]

        print(f"待回填视频 {len(pending)} 条" + ("（dry-run，不抽帧）" if dry_run else ""))
        for row in pending:
            print(f"  - {row.id}  {row.original_name or ''}  "
                  f"{row.content_type}  {row.size}B")

        if dry_run or not pending:
            return 0

        # 同步逐条跑封面任务：回填量小（家庭级存量），脚本退出即处理完，便于观察日志
        from app.media.jobs import _run_cover
        done = 0
        for row in pending:
            _run_cover(row.id, row.family_id)
            done += 1
        print(f"已触发 {done} 条封面生成；结果以 meta.cover_key 是否落库为准。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
