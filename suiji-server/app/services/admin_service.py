"""内置系统管理员账号：服务启动时自动写入数据库（幂等）。

管理员（is_admin=1）在「我的」页可见普通成员看不到的演示/运维入口
（首次引导流程、重置首次安装标记、启动加载动画、服务器地址、控件样式演示）。

账号自带一个「系统管理」家庭：客户端有「已登录但未关联家庭」的强制门控
（见 suiji-uniapp src/utils/first-run.js），无家庭会被拦在引导页，
因此播种时一并建好家庭并置为 creator，保证管理员能直接进入业务页。

已存在则只补齐管理员标记与家庭关联，绝不覆盖用户改过的密码。
"""
import logging
import os

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from ..core.security import hash_password
from ..domain.dates import utc_now_iso
from ..models import Family, FamilyMember, User
from .ids import gen_id

logger = logging.getLogger("suiji.admin")

# 内置管理员凭据：可用环境变量覆盖（生产请在 .env 里改掉默认口令）
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_NAME = os.getenv("ADMIN_NAME", "系统管理员")
ADMIN_INIT_PASSWORD = os.getenv("ADMIN_INIT_PASSWORD", "admin888")
ADMIN_FAMILY_NAME = "系统管理"


def _ensure_column(db: Session) -> None:
    """老库补列：create_all 不会给已存在的表加新列，这里按需 ALTER TABLE 补 is_admin。

    SQLite / PostgreSQL 的「ADD COLUMN ... DEFAULT 0」语法一致，直接执行即可。
    """
    bind = db.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("user")}
    if "is_admin" in cols:
        return
    db.execute(text('ALTER TABLE "user" ADD COLUMN is_admin INTEGER DEFAULT 0'))
    db.commit()
    logger.info("user 表已补 is_admin 列")


def _attach_family(db: Session, admin: User) -> None:
    """管理员无家庭时补建「系统管理」家庭并置为 creator。"""
    now = utc_now_iso()
    fam = db.query(Family).filter(Family.creator_id == admin.id).first()
    if fam is None:
        fam = Family(id=gen_id("fam"), name=ADMIN_FAMILY_NAME, creator_id=admin.id, readonly=0, created_at=now)
        db.add(fam)
        db.flush()
        db.add(FamilyMember(
            family_id=fam.id, user_id=admin.id, role="creator",
            color="#7A5FB0", joined_at=now,
        ))
    admin.family_id = fam.id


def ensure_admin(db: Session) -> None:
    """启动播种：不存在则创建管理员账号 + 家庭；已存在则补齐标记，不重置密码。"""
    _ensure_column(db)
    admin = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if admin is None:
        now = utc_now_iso()
        fam = Family(id=gen_id("fam"), name=ADMIN_FAMILY_NAME, creator_id="", readonly=0, created_at=now)
        admin = User(
            id=gen_id("usr"), username=ADMIN_USERNAME, name=ADMIN_NAME,
            password_hash=hash_password(ADMIN_INIT_PASSWORD), family_id="",
            created_at=now, is_admin=1,
        )
        db.add(admin)
        db.flush()
        fam.creator_id = admin.id
        db.add(fam)
        db.add(FamilyMember(
            family_id=fam.id, user_id=admin.id, role="creator",
            color="#7A5FB0", joined_at=now,
        ))
        admin.family_id = fam.id
        db.commit()
        logger.info("已写入内置管理员账号：%s", ADMIN_USERNAME)
        return

    changed = False
    if not int(admin.is_admin or 0):
        admin.is_admin = 1
        changed = True
    if not admin.family_id:
        _attach_family(db, admin)
        changed = True
    if changed:
        db.commit()
