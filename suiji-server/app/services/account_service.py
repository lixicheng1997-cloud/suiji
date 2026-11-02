"""账号注销（TDD §十）：二次验证 → 30 天冷静期可撤销 → 期满彻底删除。

状态机：
- user.deletion_scheduled_at == ""       正常账号
- user.deletion_scheduled_at > now       冷静期内，登录/业务正常，但客户端可拉到 banner 提示
- user.deletion_scheduled_at <= now       已到期，等 purge_due_accounts 物理删除

彻底删除范围：
- 创建者：整个家庭的业务数据（entry/measurement/growth_point/media/baby/vaccine/milestone/journal/audit）
  + MinIO 对象 + family + family_member + invite_code + setting + notification
- 普通成员：只删自己的 family_member/setting/notification，不动家庭数据
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..domain.dates import utc_now_iso
from ..media.store import get_store
from ..models import (
    AiJournal,
    AuditLog,
    Baby,
    Entry,
    EntryMedia,
    Family,
    FamilyMember,
    FileObject,
    GrowthPoint,
    InviteCode,
    Measurement,
    MilestoneRecord,
    Notification,
    Setting,
    User,
    Vaccine,
)
from . import entry_service

logger = logging.getLogger("suiji.account")

DELETION_GRACE_DAYS = 30


def _iso_in(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def request_deletion(db: Session, user: User) -> str:
    """标记用户进入冷静期，返回计划删除时刻（ISO 串）。"""
    when = _iso_in(DELETION_GRACE_DAYS)
    user.deletion_scheduled_at = when
    db.commit()
    logger.info("用户 %s 已申请注销，计划于 %s 彻底删除", user.id, when)
    return when


def cancel_deletion(db: Session, user: User) -> None:
    user.deletion_scheduled_at = ""
    db.commit()
    logger.info("用户 %s 已撤销注销申请", user.id)


def status_of(user: User) -> dict:
    """供 /auth/deactivate 查询与 bootstrap 注入 banner。"""
    if not user.deletion_scheduled_at:
        return {"scheduled": False, "execute_at": ""}
    return {"scheduled": True, "execute_at": user.deletion_scheduled_at}


def _purge_family_business(db: Session, family_id: str) -> None:
    """清空一个家庭的全部业务数据（含 MinIO 对象）。与 data.py wipe_data 对齐。"""
    for e in db.query(Entry).filter(Entry.family_id == family_id).all():
        entry_service.purge_entry(db, e)
    m_ids = [m.id for m in db.query(Measurement).filter(Measurement.family_id == family_id).all()]
    if m_ids:
        db.query(GrowthPoint).filter(GrowthPoint.measurement_id.in_(m_ids)).delete(synchronize_session=False)
        db.query(Measurement).filter(Measurement.id.in_(m_ids)).delete(synchronize_session=False)
    for md in db.query(EntryMedia).filter(EntryMedia.family_id == family_id).all():
        if md.storage_key:
            try:
                get_store().delete(md.storage_key)
            except Exception as exc:
                logger.warning("删除 MinIO 对象失败 %s：%s", md.storage_key, exc)
        db.delete(md)
    for fo in db.query(FileObject).filter(FileObject.family_id == family_id).all():
        if fo.storage_key:
            try:
                get_store().delete(fo.storage_key)
            except Exception as exc:
                logger.warning("删除 MinIO 对象失败 %s：%s", fo.storage_key, exc)
        db.delete(fo)
    db.query(Baby).filter(Baby.family_id == family_id).delete(synchronize_session=False)
    db.query(MilestoneRecord).filter(MilestoneRecord.family_id == family_id).delete(synchronize_session=False)
    db.query(Vaccine).filter(Vaccine.family_id == family_id).delete(synchronize_session=False)
    db.query(AiJournal).filter(AiJournal.family_id == family_id).delete(synchronize_session=False)
    db.query(AuditLog).filter(AuditLog.family_id == family_id).delete(synchronize_session=False)
    db.query(Notification).filter(Notification.family_id == family_id).delete(synchronize_session=False)


def purge_due_accounts(db: Session) -> int:
    """扫描已到期的注销申请，彻底删除用户及其关联数据。返回删除用户数。"""
    now = utc_now_iso()
    due = (
        db.query(User)
        .filter(User.deletion_scheduled_at != "", User.deletion_scheduled_at <= now)
        .all()
    )
    purged = 0
    for u in due:
        try:
            fid = u.family_id or ""
            family = db.get(Family, fid) if fid else None
            if family and family.creator_id == u.id:
                # 创建者：整个家庭随账号一起删
                _purge_family_business(db, fid)
                db.query(FamilyMember).filter(FamilyMember.family_id == fid).delete(synchronize_session=False)
                db.query(InviteCode).filter(InviteCode.family_id == fid).delete(synchronize_session=False)
                db.delete(family)
            else:
                # 普通成员：只退出家庭，家庭数据保留
                db.query(FamilyMember).filter(
                    FamilyMember.family_id == fid, FamilyMember.user_id == u.id
                ).delete(synchronize_session=False)
                db.query(Notification).filter(Notification.user_id == u.id).delete(synchronize_session=False)
            db.query(Setting).filter(Setting.user_id == u.id).delete(synchronize_session=False)
            db.delete(u)
            db.commit()
            purged += 1
            logger.info("已彻底删除到期注销用户 %s（family=%s）", u.id, fid)
        except Exception as exc:
            db.rollback()
            logger.error("删除用户 %s 失败：%s", u.id, exc)
    return purged
