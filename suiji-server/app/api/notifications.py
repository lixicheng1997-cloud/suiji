"""家人动态通知（落库版）：服务端逐人投递，客户端读过即删。

GET  /notifications        → 本人的未读通知（已读行已被删，所以列表即全部）
POST /notifications/read   → {ids: [...]} 逐条删除；ids 省略/为空 = 全部已读（全删）

「读后即删」省掉了已读状态列：未读的换设备/重装仍在，读过的不再出现，
客户端无需再维护 sj_msg_read 之类的本地已读账本来对抗跨天 id 漂移。

轮询链路只走一个请求：GET /events/count 顺带返回本人的未读通知（§6.5），
本端点留给消息中心手动刷新与后续其他调用方。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import AuthContext, require_family
from ..domain.dates import utc_now_iso
from ..models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _notification_row(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "content": n.content,
        "actor": n.actor,
        "entry_id": n.entry_id,
        "created_at": n.created_at,
    }


@router.get("")
def list_notifications(db: Session = Depends(get_db), auth: AuthContext = Depends(require_family)):
    """本人通知，按创建时间倒序，上限 200 条（正常不会积压：读过即删；超量由定时清理滚动收敛）。

    这里**不再**惰性跑 purge_old_notifications：轮询端每 15~30 秒就会拉一次通知，
    而清理是「全表过期扫描 + 按用户 GROUP BY 计数」，跟着轮询频率跑等于把维护成本
    摊到每一次读上。清理归 main.py 的 6 小时后台任务（SWEEP_INTERVAL_SECONDS）负责。
    """
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == auth.user_id, Notification.family_id == auth.family_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(200)
        .all()
    )
    return {"items": [_notification_row(n) for n in rows]}


@router.post("/read")
def read_notifications(body: dict, db: Session = Depends(get_db),
                       auth: AuthContext = Depends(require_family)):
    """已读即删：ids 为空/缺省时删除本人全部通知。"""
    raw = body.get("ids")
    # 客户端异常（或老版本）可能传字符串/对象进来：非列表一律当作「全部已读」，
    # 否则 dict/int 会在下面推导式里 TypeError 变成 500
    ids = [i for i in raw if i] if isinstance(raw, list) else []
    q = db.query(Notification).filter(
        Notification.user_id == auth.user_id,
        Notification.family_id == auth.family_id,
    )
    if ids:
        q = q.filter(Notification.id.in_([str(i) for i in ids]))
    count = q.delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "count": int(count), "read_at": utc_now_iso()}
