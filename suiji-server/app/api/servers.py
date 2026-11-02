"""服务器地址 /servers（公开端点）：客户端登录前就要能拉到可选列表。

数据来源为 server_endpoint 表（暂无配置界面，由 static/config/servers.json 播种），
页面只读不写——因此这里不提供 POST/PUT/DELETE。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..services import server_service

router = APIRouter(prefix="/servers", tags=["servers"])


@router.get("")
def list_servers(db: Session = Depends(get_db)):
    """可选服务器地址列表：GET /servers → {rows:[{id,name,url,env,remark,is_default,sort}]}。"""
    rows = server_service.list_endpoints(db)
    if not rows:
        # 表为空（未播种 / 被清空）：即时补种一次，避免客户端拿到空列表
        server_service.ensure_seed(db)
        rows = server_service.list_endpoints(db)
    return {"rows": [server_service.to_dict(r) for r in rows]}
