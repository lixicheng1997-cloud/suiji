"""家庭内通知：新增/删除/恢复记录、里程碑勾选达成、疫苗打卡、AI 日记生成 → 投递给其他成员。

覆盖两件事：
  1. 投递面——凡"家里有人做了件事"都逐人落库，且永不包含操作者本人；
  2. 感知面——投递同时推进 family.events_version，让 /events/count 的 ver 维度
     能报出 changed（删除/恢复/打卡不产生新 entry id，只靠 since 维度会漏）。
"""
from datetime import datetime, timedelta, timezone

from conftest import API, register

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _now_str(days_ago: int = 0, hm: str = "10:00") -> str:
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return d.strftime("%Y-%m-%d") + " " + hm


def _family(client, prefix):
    """两人家庭：返回 (创建者 headers, 加入者 headers, 宝宝)。"""
    h_a, b_a = register(client, prefix=prefix + "A")
    h_b, _ = register(client, prefix=prefix + "B")
    code = client.post(API + "/family/invite", headers=h_a).json()["code"]
    assert client.post(API + "/family/join", headers=h_b, json={"code": code}).status_code == 200
    baby = client.post(API + "/babies", headers=h_a, json={
        "name": "小满", "birth_date": (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d"),
        "gestational_weeks": 40, "gender": "boy", "birth_length": 50, "birth_weight": 3.3,
    }).json()
    client.get(API + "/bootstrap", headers=h_b)  # 让加入者拿到 active 宝宝
    return h_a, h_b, baby


def _notices(client, headers):
    return client.get(API + "/notifications", headers=headers).json()["items"]


def _mark_ids(items):
    return {i["id"] for i in items}


def test_create_entry_notifies_other_members_only(client):
    h_a, h_b, _ = _family(client, "nf")
    r = client.post(API + "/entries", headers=h_a, json={
        "type": "feeding", "occurred_at": _now_str(), "title": "瓶喂 120ml",
        "payload": {"method": "瓶喂", "amount": 120},
    })
    assert r.status_code == 200, r.text
    items = _notices(client, h_b)
    assert len(items) == 1
    assert items[0]["type"] == "feed" and items[0]["entry_id"] == r.json()["id"]
    assert "记录了" in items[0]["content"]
    # 操作者本人不收
    assert _notices(client, h_a) == []


def test_voice_and_note_have_copy(client):
    h_a, h_b, _ = _family(client, "nfcopy")
    client.post(API + "/entries", headers=h_a, json={"type": "voice", "occurred_at": _now_str()})
    client.post(API + "/entries", headers=h_a, json={"type": "note", "occurred_at": _now_str()})
    contents = [i["content"] for i in _notices(client, h_b)]
    assert len(contents) == 2
    assert any("声音" in c for c in contents) and any("随手记" in c for c in contents)


def test_backfill_does_not_notify(client):
    h_a, h_b, _ = _family(client, "nfback")
    client.post(API + "/entries", headers=h_a, json={
        "type": "note", "occurred_at": _now_str(30), "is_backfilled": 1,
    })
    assert _notices(client, h_b) == []


def test_delete_and_restore_notify_and_bump_version(client):
    """删除/恢复不改 entry id：只有 version 维度能让客户端感知到这类通知。"""
    h_a, h_b, _ = _family(client, "nfdel")
    eid = client.post(API + "/entries", headers=h_a, json={
        "type": "note", "occurred_at": _now_str(), "note": "一条随手记",
    }).json()["id"]
    seen = _mark_ids(_notices(client, h_b))

    probe = client.get(API + "/events/count?since=&ver=0", headers=h_b).json()
    client.delete(API + f"/entries/{eid}", headers=h_a)
    items = [i for i in _notices(client, h_b) if i["id"] not in seen]
    assert len(items) == 1 and items[0]["type"] == "delete" and "删除了" in items[0]["content"]
    # 记录数没变（软删只是少一条），changed 必须由 ver 维度给出
    after = client.get(API + f"/events/count?since={probe['cursor']}&ver={probe['version']}", headers=h_b).json()
    assert after["count"] == 0 and after["changed"] is True
    # 节流关键：没有新增记录就不该让客户端重拉全家快照
    assert after["new_entries"] is False
    client.post(API + "/notifications/read", headers=h_b, json={"ids": [items[0]["id"]]})

    seen = _mark_ids(_notices(client, h_b))
    client.post(API + f"/entries/{eid}/restore", headers=h_a)
    items = [i for i in _notices(client, h_b) if i["id"] not in seen]
    assert len(items) == 1 and items[0]["type"] == "restore" and "恢复了" in items[0]["content"]


def test_probe_carries_unread_notices(client):
    """一个周期一个请求：/events/count 顺带把本人未读通知带回（合并掉 GET /notifications）。"""
    h_a, h_b, _ = _family(client, "nfprobe")
    client.post(API + "/entries", headers=h_a, json={"type": "photo", "occurred_at": _now_str(), "title": "翻身纪念照"})
    body = client.get(API + "/events/count?since=0&ver=0", headers=h_b).json()
    assert body["changed"] is True and body["new_entries"] is True
    assert len(body["notices"]) == 1
    assert body["notices"][0]["content"].find("翻身纪念照") >= 0
    # 读过后同一次探测不再带回（读后即删）
    client.post(API + "/notifications/read", headers=h_b, json={"ids": [body["notices"][0]["id"]]})
    assert client.get(API + "/events/count?since=0&ver=0", headers=h_b).json()["notices"] == []


def test_first_probe_with_empty_params(client):
    """客户端首轮本地还没有水位，发出的是 `since=&ver=`（空串）：不能 422。

    ver 曾经声明成 int，空串直接被 FastAPI 判成参数校验失败，首探整条链路断掉。
    """
    _, h_b, _ = _family(client, "nfempty")
    r = client.get(API + "/events/count?since=&ver=", headers=h_b)
    assert r.status_code == 200
    body = r.json()
    assert body["changed"] is False and body["new_entries"] is False
    assert body["version"] >= 0


def test_update_entry_does_not_notify(client):
    """改记录不该打扰家人（误触编辑会刷屏），只推进水位。"""
    h_a, h_b, _ = _family(client, "nfupd")
    eid = client.post(API + "/entries", headers=h_a, json={"type": "note", "occurred_at": _now_str()}).json()["id"]
    seen = _mark_ids(_notices(client, h_b))
    client.put(API + f"/entries/{eid}", headers=h_a, json={"note": "改了又改"})
    assert [i for i in _notices(client, h_b) if i["id"] not in seen] == []


def test_milestone_check_notifies_once_per_achievement(client):
    h_a, h_b, baby = _family(client, "nfms")
    ms = client.get(API + "/milestones?baby_id=" + baby["id"], headers=h_a).json()
    target = next(m for m in ms if not m["done"])
    seen = _mark_ids(_notices(client, h_b))
    r = client.put(API + f"/milestones/{target['id']}", headers=h_a,
                   json={"done": True, "achieved_at": _now_str()})
    assert r.status_code == 200, r.text
    items = [i for i in _notices(client, h_b) if i["id"] not in seen]
    assert len(items) == 1 and items[0]["type"] == "milestone"
    assert "达成了里程碑" in items[0]["content"]

    # 反复改达成日期不重复通知
    seen = _mark_ids(_notices(client, h_b))
    client.put(API + f"/milestones/{target['id']}", headers=h_a, json={"done": True, "achieved_at": _now_str(1)})
    assert [i for i in _notices(client, h_b) if i["id"] not in seen] == []

    # 取消达成也不通知
    seen = _mark_ids(_notices(client, h_b))
    client.put(API + f"/milestones/{target['id']}", headers=h_a, json={"done": False})
    assert [i for i in _notices(client, h_b) if i["id"] not in seen] == []


def test_vaccine_checkin_notifies(client):
    h_a, h_b, baby = _family(client, "nfvac")
    v = client.get(API + "/vaccines?baby_id=" + baby["id"], headers=h_a).json()[0]
    seen = _mark_ids(_notices(client, h_b))
    r = client.put(API + f"/vaccines/{v['id']}", headers=h_a, json={"done": True, "done_date": "2026-10-01"})
    assert r.status_code == 200, r.text
    items = [i for i in _notices(client, h_b) if i["id"] not in seen]
    assert len(items) == 1 and items[0]["type"] == "vaccine"
    assert "完成了疫苗接种" in items[0]["content"]

    # 取消完成 / 改机构都不通知
    seen = _mark_ids(_notices(client, h_b))
    client.put(API + f"/vaccines/{v['id']}", headers=h_a, json={"done": False, "done_date": ""})
    client.put(API + f"/vaccines/{v['id']}", headers=h_a, json={"org": "社区医院"})
    assert [i for i in _notices(client, h_b) if i["id"] not in seen] == []


def test_vaccine_sync_batch_merges_into_one_notice(client):
    h_a, h_b, baby = _family(client, "nfvacsync")
    rows = client.get(API + "/vaccines?baby_id=" + baby["id"], headers=h_a).json()[:3]
    seen = _mark_ids(_notices(client, h_b))
    r = client.post(API + "/vaccines/sync", headers=h_a, json={
        "rows": [{"code": x["code"], "baby_id": baby["id"], "done": True} for x in rows]
    })
    assert r.status_code == 200 and r.json()["count"] == 3
    items = [i for i in _notices(client, h_b) if i["id"] not in seen]
    assert len(items) == 1 and "等 3 剂" in items[0]["content"]


def test_journal_generate_notifies(client):
    h_a, h_b, baby = _family(client, "nfjr")
    seen = _mark_ids(_notices(client, h_b))
    r = client.post(API + "/journals/generate", headers=h_a, json={"baby_id": baby["id"]})
    assert r.status_code == 200, r.text
    items = [i for i in _notices(client, h_b) if i["id"] not in seen]
    assert len(items) == 1 and items[0]["type"] == "journal"
    assert "生成了成长日记" in items[0]["content"] and baby["name"] not in items[0]["content"]


def test_read_notifications_deletes_rows(client):
    """读后即删：单条已读只删该条，全部已读清空；不会误删他人行。"""
    h_a, h_b, _ = _family(client, "nfrd")
    for t in ("note", "photo"):
        client.post(API + "/entries", headers=h_a, json={"type": t, "occurred_at": _now_str()})
    client.post(API + "/entries", headers=h_b, json={"type": "note", "occurred_at": _now_str()})
    items = _notices(client, h_b)
    assert len(items) == 2
    r = client.post(API + "/notifications/read", headers=h_b, json={"ids": [items[0]["id"]]})
    assert r.json()["count"] == 1
    assert len(_notices(client, h_b)) == 1
    assert len(_notices(client, h_a)) == 1  # 本人收到的那条不受影响
    assert client.post(API + "/notifications/read", headers=h_b, json={}).json()["count"] == 1
    assert _notices(client, h_b) == []


def test_bootstrap_carries_events_version(client):
    h_a, _, baby = _family(client, "nfver")
    v0 = client.get(API + "/bootstrap", headers=h_a).json()["family"]["events_version"]
    client.post(API + "/entries", headers=h_a, json={"type": "note", "occurred_at": _now_str()})
    v1 = client.get(API + "/bootstrap", headers=h_a).json()["family"]["events_version"]
    assert v1 > v0


def test_notice_actor_puts_relation_before_nickname(client):
    """动态文案的记录人：与宝宝关系在前、昵称在后（「妈妈 · 李芳 记录了…」）。"""
    h_a, h_b, _ = _family(client, "nfrel")
    client.put(API + "/settings", headers=h_a,
               json={"key": "parent", "value": {"name": "李芳", "relation": "妈妈"}})
    assert client.post(API + "/entries", headers=h_a, json={
        "type": "note", "occurred_at": _now_str(), "note": "一条随手记"}).status_code == 200
    items = _notices(client, h_b)
    assert items[0]["actor"] == "妈妈 · 李芳"
    assert items[0]["content"].startswith("妈妈 · 李芳 ")
    # 成员行仍走「昵称优先 + 关系另列」：家庭卡两列分开显示，不能被关系挤掉
    members = client.get(API + "/bootstrap", headers=h_b).json()["family"]["members"]
    assert next(m for m in members if m["relation"] == "妈妈")["name"] == "李芳"
