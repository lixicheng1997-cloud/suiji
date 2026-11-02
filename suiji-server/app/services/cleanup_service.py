"""到期数据自动清理：回收站 30 天 · AI 日记草稿 30 天 · 操作留痕 180 天 · 通知 30 天/200 条 · 注销冷静期到期账号。

触发方式：
  1. 启动时（lifespan）全量跑一遍；
  2. main.py 起的后台 asyncio 循环每 6 小时跑一遍（定时任务，不再只靠惰性触发）；
  3. GET /entries/trash 与 GET /notifications 时惰性触发（兜底，防定时任务挂掉）。
失败只告警不中断。
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..domain.dates import day_key, days_between, today_utc
from ..models import AiJournal, AuditLog, Entry, Notification

from . import account_service, entry_service

logger = logging.getLogger("suiji.cleanup")

TRASH_KEEP_DAYS = 30   # 回收站保留期（与客户端 trash.vue / api.js 文案一致）
DRAFT_KEEP_DAYS = 30   # 未归档 AI 日记草稿保留期（与 diary/edit.vue 文案一致）
AUDIT_KEEP_DAYS = 180  # 操作留痕保留期（AuditLog 模型注释约定）
NOTIF_KEEP_DAYS = 30   # 未读通知保留期（读后即删；长期不打开消息中心的旧通知滚动清理）
NOTIF_MAX_PER_USER = 200  # 单用户未读通知上限，超出删最老（list_notifications limit 100，留余量）
SWEEP_INTERVAL_SECONDS = 6 * 3600  # 后台定时清理间隔：6 小时


def _expired(s: str, keep_days: int) -> bool:
    """按日期粒度判断是否超期；解析失败视为未超期（宁可多留，不误删）。"""
    return days_between(day_key(s), today_utc()) >= keep_days


def purge_expired(db: Session) -> dict:
    """清掉全部家庭中过期的回收站记录、未归档日记草稿、操作留痕与到期注销账号，返回各计数。"""
    counts = {"trash": 0, "drafts": 0, "audit": 0, "accounts": 0}

    # 回收站：软删超 30 天 → 连同 measurement/growth_point/media 与文件字节物理清除
    for e in db.query(Entry).filter(Entry.deleted_at.isnot(None)).all():
        if _expired(e.deleted_at or "", TRASH_KEEP_DAYS):
            entry_service.purge_entry(db, e)
            counts["trash"] += 1

    # AI 日记草稿：未归档超 30 天（按 updated_at 计，暂存会续期；归档的永久保留）
    for j in db.query(AiJournal).filter(AiJournal.status == "draft").all():
        if _expired(j.updated_at or j.created_at or "", DRAFT_KEEP_DAYS):
            db.delete(j)
            counts["drafts"] += 1

    # 操作留痕：超 180 天滚动清除（ISO 串字典序即时间序，服务端统一 Z 后缀生成）
    cutoff = (datetime.now(timezone.utc) - timedelta(days=AUDIT_KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts["audit"] = db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete(synchronize_session=False)

    # 注销冷静期到期账号：连同家庭数据彻底删除
    counts["accounts"] = account_service.purge_due_accounts(db)

    if any(counts.values()):
        db.commit()
        logger.info("到期数据清理：回收站 %s 条 · 日记草稿 %s 条 · 操作留痕 %s 条 · 注销账号 %s 个",
                    counts["trash"], counts["drafts"], counts["audit"], counts["accounts"])
    return counts


def purge_old_notifications(db: Session) -> int:
    """清理通知表：超 30 天的未读通知滚动删除；单用户未读超过上限时删最老的。

    通知是「读后即删」模型，长期不打开消息中心的用户会无限堆积；
    list_notifications limit 100，超过 200 条的老通知永远拉不到，不如主动清掉。
    惰性触发：list_notifications / create entry 前各调一次，失败静默。
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=NOTIF_KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    deleted = db.query(Notification).filter(Notification.created_at < cutoff).delete(synchronize_session=False)

    # 单用户未读超上限：每个用户保留最新 NOTIF_MAX_PER_USER 条
    overloaded = (
        db.query(Notification.user_id)
        .group_by(Notification.user_id)
        .having(func.count(Notification.id) > NOTIF_MAX_PER_USER)
        .all()
    )
    for (uid,) in overloaded:
        keep_ids = [
            r[0] for r in db.query(Notification.id)
            .filter(Notification.user_id == uid)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(NOTIF_MAX_PER_USER)
            .all()
        ]
        if keep_ids:
            deleted += db.query(Notification).filter(Notification.id.in_(keep_ids)).delete(synchronize_session=False)

    if deleted:
        db.commit()
        logger.info("通知表清理：删除 %s 条过期/超量通知", deleted)
    return int(deleted)
