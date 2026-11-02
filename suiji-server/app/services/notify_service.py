"""家庭通知投递：按收件人 user_id 逐人落 notification 行（排除操作者本人）。

站内通知的唯一写入口。触发面覆盖：记录新增/软删/恢复、里程碑清单勾选达成、
疫苗剂次标记完成、AI 成长日记生成——凡是"家庭里有人做了一件值得让别人知道的
事"，都从这里出线。

配套的读端是 /notifications（读后即删），增量感知走 /events/count 的
events_version 水位，因此每次投递都必须同时 bump 版本：投递与水位推进绑在
一个函数里，避免调用方漏掉一半（通知落了库但客户端不会去拉）。
"""
from sqlalchemy.orm import Session

from ..core.deps import AuthContext
from ..domain.dates import utc_now_iso
from ..models import Family, FamilyMember, Notification, Setting, User
from .ids import gen_id
from .rows import actor_label

# 家人动态通知文案（与客户端 FEED_TEXT 口径一致，不含健康数值）
FEED_TEXT = {
    "milestone": "记录了里程碑",
    "sleep": "记录了一次睡眠",
    "photo": "上传了照片",
    "feeding": "记录了一次喂养",
    "measure": "记录了一次测量",
    "poop": "记录了一次照护情况",
    "temp": "记录了一次照护情况",
    "med": "记录了一次照护情况",
    "voice": "录了一段声音",
    "note": "记了一条随手记",
    "mood": "记了一条心情",
}

# 通知标题按类型区分（消息中心据此出图标与文案分组）
TITLES = {
    "feed": "家人动态",
    "delete": "家人动态",
    "restore": "家人动态",
    "milestone": "里程碑达成",
    "vaccine": "疫苗接种",
    "journal": "成长日记",
}


def actor_name(db: Session, auth_or_user_id) -> str:
    """操作人展示名：与宝宝关系在前、昵称在后（「妈妈 · 李芳」），不含登录账号。"""
    uid = auth_or_user_id.user_id if isinstance(auth_or_user_id, AuthContext) else str(auth_or_user_id)
    u = db.get(User, uid)
    st = db.get(Setting, uid)
    parent = ((st.data or {}).get("parent") or {}) if st else {}
    return actor_label(u, parent)


def bump_family_version(db: Session, family_id: str) -> None:
    """家庭事件版本号 +1：客户端水位线据此感知删除/修改（id 不变但有事情发生）。"""
    if not family_id:
        return
    db.query(Family).filter(Family.id == family_id).update(
        {"events_version": Family.events_version + 1}, synchronize_session=False)


def family_recipients(db: Session, family_id: str, actor_user_id: str) -> list[str]:
    """同家庭其他成员（排除操作者本人）。"""
    if not family_id:
        return []
    return [
        m.user_id for m in db.query(FamilyMember.user_id)
        .filter(FamilyMember.family_id == family_id, FamilyMember.user_id != actor_user_id)
    ]


def notify_family(db: Session, auth: AuthContext, *, ntype: str, content: str,
                  entry_id: str = "", actor: str = "") -> int:
    """给家庭其他成员逐人投递一条通知，并推进 events_version 水位。

    只 add/update，不 commit——由调用方与业务写操作同事务提交，保证
    "记录落了库" 与 "通知落了库" 要么都成、要么都不成。
    返回收件人数（0 表示家里只有操作者一人，无需投递）。
    """
    actor = actor or actor_name(db, auth)
    recipients = family_recipients(db, auth.family_id, auth.user_id)
    if not recipients:
        bump_family_version(db, auth.family_id)
        return 0
    now = utc_now_iso()
    # content/title 直接来自 entry.title（长度客户端可控），列宽 varchar(255)/64：
    # 截断兜底，否则一条超长标题的记录会让其他成员的通知投递整笔回滚
    content = (content or "")[:200]
    title = TITLES.get(ntype, "家人动态")[:32]
    for uid in recipients:
        db.add(Notification(
            id=gen_id("nt"), family_id=auth.family_id, user_id=uid,
            type=ntype, title=title, content=content,
            actor=actor[:32], entry_id=entry_id, created_at=now,
        ))
    bump_family_version(db, auth.family_id)
    return len(recipients)
