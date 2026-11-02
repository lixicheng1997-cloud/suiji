"""增量探测 /events/count（方案 A：客户端前台纯轮询）。

用途：App 在前台时每 15~30 秒问一次「本家庭有没有新动态」——有则客户端重拉
bootstrap，通知弹窗与去重全部走既有本地账本（sj_notices），本端点只回答
"有没有新增/变更"，不区分操作人（宁多勿漏，客户端 othersFeeds 会过滤自己）。

水位线两个维度：
  - since (entry.id)：字典序即时间序，新建记录能感知；
  - ver  (family.events_version)：entry 的修改/软删/恢复不改 id，但会 bump 版本号。
    注意：版本变化**不再**触发整包重拉（客户端按 new_entries 判定），因为多数
    变更只是打卡/勾选/删除，为一个勾就重下全家快照是卡顿的主因；数据对齐交给
    冷启动与下拉刷新。

为了把「探测 + 取通知」压成一次往返（弱网下两个串行请求就是秒级卡顿），
本端点顺带返回本人未读通知。清理类维护工作不放这儿，交给 6 小时后台任务。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import require_family
from ..models import Entry, Family, Notification
from .notifications import _notification_row

router = APIRouter(prefix="/events", tags=["events"])

# 单次响应携带的通知上限：正常积压个位数，留足余量同时给响应体设个硬边界
NOTICES_LIMIT = 50


@router.get("/count")
def events_count(since: str = Query(""), ver: str = Query(""),
                 db: Session = Depends(get_db), auth=Depends(require_family)):
    """GET /events/count?since=<entry水位>&ver=<版本水位>
    → {count, cursor, version, changed, new_entries, notices}。

    count = 本家庭未软删且 id > since 的记录数；
    version = family.events_version 当前值；
    changed = count>0 或 version>ver（客户端据此决定要不要取通知/刷新红点）；
    new_entries = count>0（只有真的多了记录才值得重拉 bootstrap）；
    cursor = 新 entry 水位（无新增时原样回传 since）；
    notices = 本人未读通知（形状同 GET /notifications）。
    首次调用 since/ver 都空：只初始化水位，不触发重拉（存量记录不该被当成新动态）。

    ver 声明成 str 而不是 int：客户端首次轮询时本地还没有版本水位，会原样发出
    `ver=`（空串）。类型注解写 int 会让这一发直接 422，整个首探链路断掉。
    """
    ver_num = int(ver) if ver.isdigit() else 0
    q = db.query(func.count(Entry.id), func.max(Entry.id)).filter(
        Entry.family_id == auth.family_id,
        Entry.deleted_at.is_(None),
    )
    if since:
        q = q.filter(Entry.id > since)
    count, max_id = q.first()
    count = int(count or 0)
    fam = db.get(Family, auth.family_id)
    family_ver = int(fam.events_version or 0) if fam else 0

    first_seen = (not since) and (not ver_num)
    version_changed = family_ver > ver_num
    changed = (count > 0 or version_changed) and not first_seen

    notices = (
        db.query(Notification)
        .filter(Notification.user_id == auth.user_id, Notification.family_id == auth.family_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(NOTICES_LIMIT)
        .all()
    )
    return {
        "count": count,
        "cursor": (max_id if count else since) or "",
        "version": family_ver,
        "changed": changed,
        "new_entries": count > 0,
        "notices": [_notification_row(n) for n in notices],
    }
