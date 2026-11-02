"""服务器地址配置（server_endpoint 表）。

暂无配置界面：配置以 static/config/servers.json 为源，播种/同步进表，
客户端只通过 GET /servers 读取（页面只读不写）。
"""
import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models import ServerEndpoint
from .ids import gen_id

logger = logging.getLogger("suiji.servers")

# servers.json 缺失或不可读时的兜底种子（保证服务空库启动也能被客户端选中）
# 端口约定：客户端一律走 30080（nginx 统一入口），不再下发已退役的本机 8000 直连地址
DEFAULT_SEED = [
    {"name": "云服务", "url": "http://49.233.77.155:30080/api/v1", "env": "prod",
     "remark": "内置兜底种子", "enabled": 1, "is_default": 1, "sort": 1},
    {"name": "本地调试", "url": "http://localhost:30080/api/v1", "env": "dev",
     "remark": "内置兜底种子", "enabled": 1, "is_default": 0, "sort": 2},
]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm_url(url: str) -> str:
    """去空白与结尾斜杠：http://host/api/v1/ 与 http://host/api/v1 视为同一条。"""
    return str(url or "").strip().rstrip("/")


def seed_rows() -> list[dict]:
    """读取播种源：static/config/servers.json，缺失/异常时回退内置种子。"""
    path = settings.static_config_dir / "servers.json"
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
    except FileNotFoundError:
        rows = DEFAULT_SEED
    except Exception as exc:  # JSON 损坏等：回退内置，避免启动即失败
        logger.warning("读取 %s 失败，回退内置服务器种子：%s", path, exc)
        rows = DEFAULT_SEED
    if not isinstance(rows, list) or not rows:
        rows = DEFAULT_SEED
    return [r for r in rows if isinstance(r, dict) and _norm_url(r.get("url", ""))]


def to_dict(row: ServerEndpoint) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "url": row.url,
        "env": row.env,
        "remark": row.remark,
        "enabled": int(row.enabled or 0),
        "is_default": int(row.is_default or 0),
        "sort": row.sort,
    }


def _upsert(db: Session, item: dict, now: str) -> bool:
    url = _norm_url(item.get("url", ""))
    row = db.query(ServerEndpoint).filter(ServerEndpoint.url == url).first()
    if row is None:
        row = ServerEndpoint(id=gen_id("srv"), url=url, created_at=now)
        db.add(row)
    row.name = str(item.get("name", "") or url)
    row.env = str(item.get("env", "dev") or "dev")
    row.remark = str(item.get("remark", "") or "")
    row.enabled = 1 if int(item.get("enabled", 1) or 0) else 0
    row.is_default = 1 if int(item.get("is_default", 0) or 0) else 0
    row.sort = int(item.get("sort", 0) or 0)
    row.updated_at = now
    return True


def ensure_seed(db: Session) -> int:
    """表为空时按 servers.json 播种；已配置过则不动（避免覆盖人工改库的结果）。"""
    if db.query(ServerEndpoint).count():
        return 0
    now = _now()
    n = 0
    for item in seed_rows():
        if _upsert(db, item, now):
            n += 1
    db.commit()
    if n:
        logger.info("已播种 %d 条服务器地址配置", n)
    return n


def sync_seed(db: Session, replace: bool = False) -> int:
    """脚本入口：把 servers.json 全量同步进表（按 url upsert）。

    replace=True 时额外删除表中不在配置文件里的行。
    @returns 写入行数
    """
    now = _now()
    keep = set()
    n = 0
    for item in seed_rows():
        url = _norm_url(item.get("url", ""))
        keep.add(url)
        if _upsert(db, item, now):
            n += 1
    removed = 0
    if replace:
        for row in db.query(ServerEndpoint).all():
            if row.url not in keep:
                db.delete(row)
                removed += 1
    db.commit()
    logger.info("同步服务器地址配置：写入/更新 %d 条%s", n, f"，删除 {removed} 条" if removed else "")
    return n


def list_endpoints(db: Session, only_enabled: bool = True) -> list[ServerEndpoint]:
    """客户端可选项：启用优先，sort 升序、同 sort 按名称。"""
    q = db.query(ServerEndpoint)
    if only_enabled:
        q = q.filter(ServerEndpoint.enabled == 1)
    return q.order_by(ServerEndpoint.sort.asc(), ServerEndpoint.name.asc()).all()
