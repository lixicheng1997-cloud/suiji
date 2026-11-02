"""把 static/config/servers.json 同步进 server_endpoint 表。

暂无服务器地址配置界面：改完 servers.json 后跑一次本脚本即可生效。

用法（在 suiji-server 目录下）：
    python scripts/seed_servers.py            # 按 url 增量 upsert（保留库里多余的行）
    python scripts/seed_servers.py --replace  # 全量对齐（删除库里不在配置文件中的行）
    python scripts/seed_servers.py --list     # 只打印当前库里的配置
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.db import SessionLocal  # noqa: E402
from app.models import ServerEndpoint  # noqa: E402
from app.services import server_service  # noqa: E402


def _list(db):
    rows = db.query(ServerEndpoint).order_by(ServerEndpoint.sort, ServerEndpoint.name).all()
    if not rows:
        print("（server_endpoint 表为空）")
        return
    for r in rows:
        flag = "启用" if r.enabled else "停用"
        dflt = " · 默认" if r.is_default else ""
        print(f"[{flag}{dflt}] {r.name}  {r.url}  ({r.env}) {r.remark}")


def main() -> int:
    args = set(sys.argv[1:])
    with SessionLocal() as db:
        if "--list" in args:
            _list(db)
            return 0
        n = server_service.sync_seed(db, replace="--replace" in args)
        print(f"已写入/更新 {n} 条；当前库内配置：")
        _list(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
