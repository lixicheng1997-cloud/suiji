"""到期数据自动清理：回收站 30 天 · AI 日记草稿 30 天 · 操作留痕 180 天。"""
from datetime import datetime, timedelta, timezone

from conftest import API, register

from app.core.db import SessionLocal
from app.models import AiJournal, AuditLog, Entry


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _create_baby(client, headers):
    birth = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y-%m-%d")
    r = client.post(API + "/babies", headers=headers, json={
        "name": "小满", "birth_date": birth, "gestational_weeks": 40, "gender": "boy",
        "birth_length": 50, "birth_weight": 3.3,
    })
    assert r.status_code == 200, r.text


def test_purge_expired(client):
    headers, body = register(client, prefix="clean")
    _create_baby(client, headers)

    # 软删两条记录：一条 31 天前（应被物理清除），一条刚删（应保留）
    for eid, days in (("e_clean_old", 31), ("e_clean_new", 0)):
        r = client.post(API + "/entries", headers=headers,
                        json={"id": eid, "type": "note", "occurred_at": "2026-01-01 10:00", "note": "随手记"})
        assert r.status_code == 200, r.text
        client.delete(API + "/entries/" + eid, headers=headers)
    with SessionLocal() as db:
        db.get(Entry, "e_clean_old").deleted_at = _iso(31)
        db.commit()

    # AI 日记草稿：一条 31 天前暂存（应被清除），一条归档的 40 天前（永久保留）
    r = client.post(API + "/journals/generate", headers=headers, json={})
    assert r.status_code == 200, r.text
    draft_id = r.json()["id"]
    client.put(API + "/journals/" + draft_id, headers=headers, json={"status": "archived"})
    r = client.post(API + "/journals/generate", headers=headers, json={})
    assert r.status_code == 200, r.text
    draft2_id = r.json()["id"]
    with SessionLocal() as db:
        j1 = db.get(AiJournal, draft_id)
        j1.updated_at = _iso(40)
        db.get(AiJournal, draft2_id).updated_at = _iso(31)
        db.commit()

    # 操作留痕（软删时写入）：全部回拨 181 天，应滚动清除
    fam_id = body["family"]["id"]
    with SessionLocal() as db:
        for a in db.query(AuditLog).filter(AuditLog.family_id == fam_id).all():
            a.created_at = _iso(181)
        db.commit()
        before = db.query(AuditLog).filter(AuditLog.family_id == fam_id).count()
        assert before > 0

    # GET /entries/trash 惰性触发全量清理
    r = client.get(API + "/entries/trash", headers=headers)
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()["items"]]
    assert "e_clean_old" not in ids and "e_clean_new" in ids
    assert client.get(API + "/entries/e_clean_old", headers=headers).status_code == 404

    # 草稿被清、归档保留
    journals = client.get(API + "/journals", headers=headers).json()
    j_ids = [j["id"] for j in journals]
    assert draft2_id not in j_ids and draft_id in j_ids

    # 留痕已滚动清除
    with SessionLocal() as db:
        assert db.query(AuditLog).filter(AuditLog.family_id == fam_id).count() == 0


def test_keep_recent_rows(client):
    """未超期的行一律不动：刚删的回收站记录、刚生成的草稿原样保留。"""
    headers, _ = register(client, prefix="keep")
    _create_baby(client, headers)
    client.post(API + "/entries", headers=headers,
                json={"id": "e_keep_1", "type": "note", "occurred_at": "2026-01-01 10:00", "note": "随手记"})
    client.delete(API + "/entries/e_keep_1", headers=headers)
    r = client.post(API + "/journals/generate", headers=headers, json={})
    assert r.status_code == 200, r.text
    draft_id = r.json()["id"]

    r = client.get(API + "/entries/trash", headers=headers)
    assert [t["id"] for t in r.json()["items"]] == ["e_keep_1"]
    journals = client.get(API + "/journals", headers=headers).json()
    assert [j["id"] for j in journals] == [draft_id]
