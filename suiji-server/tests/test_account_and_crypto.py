"""新功能测试：敏感字段静态加密 + 账号注销冷静期 + 到期 purge。"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.field_crypto import field_crypto
from app.main import app  # noqa: F401  触发 lifespan
from app.models import Baby, Entry, User
from app.services import account_service

from conftest import API, client, register  # noqa: F401


def _raw_column(db, table: str, column: str, row_id: str) -> str:
    """绕过 ORM 的 TypeDecorator，直接读数据库里存的原始字符串（应为密文）。"""
    sql = text(f"SELECT {column} FROM {table} WHERE id = :id")
    return db.execute(sql, {"id": row_id}).scalar_one()


# ---------- 字段加密 ----------

def test_baby_name_stored_encrypted_readable_plaintext(client):
    headers, body = register(client, "crypto")
    # 创建一个宝宝
    r = client.post(API + "/babies", headers=headers, json={
        "name": "小糯米", "birth_date": "2026-03-01", "gender": "girl",
    })
    assert r.status_code in (200, 201), r.text
    baby = r.json()
    assert baby["name"] == "小糯米"  # API 返回明文

    # 直查数据库（绕过 ORM 解密）：库里落的是密文
    with SessionLocal() as db:
        raw = _raw_column(db, "baby", "name", baby["id"])
        assert raw != "小糯米"
        assert raw.startswith("enc:v1:"), f"期望密文前缀，实际：{raw[:40]}"

    # ORM 读出来应透明解密
    with SessionLocal() as db:
        row = db.get(Baby, baby["id"])
        assert row.name == "小糯米"


def test_entry_note_encrypted(client):
    headers, body = register(client, "note")
    # 先建 baby
    r = client.post(API + "/babies", headers=headers, json={
        "name": "宝宝", "birth_date": "2026-03-01", "gender": "boy",
    })
    baby_id = r.json()["id"]
    # 写一条带备注的记录
    r = client.post(API + "/entries", headers=headers, json={
        "type": "feeding", "baby_id": baby_id, "occurred_at": "2026-10-30T10:00:00Z",
        "note": "今天奶量 120ml，体温 37.2℃，有点低热", "payload": {"amount": 120},
    })
    assert r.status_code in (200, 201), r.text
    e = r.json()
    assert e["note"] == "今天奶量 120ml，体温 37.2℃，有点低热"

    with SessionLocal() as db:
        raw = _raw_column(db, "entry", "note", e["id"])
        assert raw != e["note"]
        assert raw.startswith("enc:v1:"), f"期望密文前缀，实际：{raw[:40]}"


def test_bootstrap_returns_decrypted(client):
    headers, body = register(client, "bootstrap")
    r = client.post(API + "/babies", headers=headers, json={
        "name": "朵朵", "birth_date": "2026-05-01", "gender": "girl",
    })
    baby_id = r.json()["id"]
    client.post(API + "/entries", headers=headers, json={
        "type": "sleep", "baby_id": baby_id, "occurred_at": "2026-10-30T11:00:00Z",
        "note": "小睡 40 分钟", "payload": {"minutes": 40},
    })
    # bootstrap 全量快照
    r = client.get(API + "/bootstrap", headers=headers)
    assert r.status_code == 200, r.text
    snap = r.json()
    assert snap["babies"][0]["name"] == "朵朵"
    assert any(e["note"] == "小睡 40 分钟" for e in snap["entries"])


# ---------- 账号注销 ----------

def test_deactivate_requires_correct_password(client):
    headers, body = register(client, "deact")
    # 错密码
    r = client.post(API + "/auth/deactivate", headers=headers, json={"password": "wrong-password"})
    assert r.status_code == 400
    # 查状态：未申请
    r = client.get(API + "/auth/deactivate", headers=headers)
    assert r.status_code == 200
    assert r.json()["scheduled"] is False


def test_deactivate_request_and_cancel(client):
    headers, body = register(client, "deact2")
    # 申请注销
    r = client.post(API + "/auth/deactivate", headers=headers, json={"password": "pw123456"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["scheduled"] is True
    assert data["execute_at"]

    # 状态应显示在冷静期
    r = client.get(API + "/auth/deactivate", headers=headers)
    assert r.json()["scheduled"] is True
    assert r.json()["execute_at"] == data["execute_at"]

    # 撤销
    r = client.post(API + "/auth/deactivate/cancel", headers=headers)
    assert r.status_code == 200
    assert r.json()["scheduled"] is False

    # 状态清空
    r = client.get(API + "/auth/deactivate", headers=headers)
    assert r.json()["scheduled"] is False


def test_due_account_purged_with_family_data(client):
    headers, body = register(client, "purge")
    # 造一条宝宝记录
    client.post(API + "/babies", headers=headers, json={
        "name": "待删宝宝", "birth_date": "2026-01-01", "gender": "boy",
    })
    me = client.get(API + "/auth/me", headers=headers).json()
    user_id = me["user"]["id"]
    family_id = me["family"]["id"]

    # 直接把 deletion_scheduled_at 改成过去
    with SessionLocal() as db:
        u = db.get(User, user_id)
        u.deletion_scheduled_at = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.commit()
        baby_count_before = db.query(Baby).filter(Baby.family_id == family_id).count()
        assert baby_count_before >= 1

    # 跑 purge
    with SessionLocal() as db:
        n = account_service.purge_due_accounts(db)
        assert n == 1

    # 验证：用户与家庭业务数据都没了
    with SessionLocal() as db:
        assert db.get(User, user_id) is None
        from app.models import Family
        assert db.get(Family, family_id) is None
        assert db.query(Baby).filter(Baby.family_id == family_id).count() == 0

