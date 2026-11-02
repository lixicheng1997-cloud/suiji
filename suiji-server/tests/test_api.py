"""API 冒烟：注册→建档→记录→回收站→媒体→设置→日记→导出/导入→家庭只读/越权。"""
from datetime import datetime, timedelta, timezone

from conftest import API, register, unique_name

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _now_str(days_ago: int = 0, hm: str = "10:00") -> str:
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return d.strftime("%Y-%m-%d") + " " + hm


def _auth(client, prefix="u"):
    headers, body = register(client, prefix=prefix)
    return headers, body


def _create_baby(client, headers, name="小满", birth_days_ago=120):
    birth = (datetime.now(timezone.utc) - timedelta(days=birth_days_ago)).strftime("%Y-%m-%d")
    r = client.post(API + "/babies", headers=headers, json={
        "name": name, "birth_date": birth, "gestational_weeks": 40, "gender": "boy",
        "birth_length": 50, "birth_weight": 3.3,
    })
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 认证与引导 ----------

def test_register_family_gate_then_login_me(client):
    """注册不再代建家庭：need_family=true 且业务接口 409，直到创建/加入家庭。"""
    username = unique_name("auth")
    r = client.post(API + "/auth/register", json={"username": username, "password": "pw123456", "name": "妈妈"})
    assert r.status_code == 200
    body = r.json()
    assert body["access"] and body["refresh"]
    assert body["family"] is None and body["need_family"] is True
    # 用户名已被占用：409 且 detail 是能直接弹给用户的文案
    dup = client.post(API + "/auth/register", json={"username": username, "password": "pw654321"})
    assert dup.status_code == 409, dup.text
    assert "已被注册" in dup.json()["detail"]
    # 用户名太短仍走 422 校验
    assert client.post(API + "/auth/register", json={"username": "ab", "password": "x"}).status_code == 422
    # 登录失败 401
    assert client.post(API + "/auth/login", json={"username": username, "password": "bad"}).status_code == 401

    headers = {"Authorization": "Bearer " + body["access"]}
    # 未关联家庭：业务接口一律 409 need_family，但 /bootstrap 与 /family 放行
    r = client.get(API + "/bootstrap", headers=headers)
    assert r.status_code == 200 and r.json()["family"]["id"] == ""
    for method, path in (("post", "/babies"), ("get", "/entries"), ("get", "/settings"),
                         ("get", "/vaccines"), ("get", "/export/data"), ("get", "/files")):
        r = client.request(method, API + path, headers=headers)
        assert r.status_code == 409 and r.json()["detail"] == "need_family", path
    assert client.get(API + "/family", headers=headers).json()["family"]["need_family"] is True
    # 重复创建无需走到这里已由上面保证；直接创建家庭即完成关联
    r = client.post(API + "/family", headers=headers, json={"name": "小岁的家"})
    assert r.status_code == 200 and r.json()["family"]["role"] == "creator"
    # 关联后业务接口放开
    assert client.get(API + "/entries", headers=headers).status_code == 200

    r = client.post(API + "/auth/login", json={"username": username, "password": "pw123456"})
    assert r.status_code == 200 and r.json()["need_family"] is False
    headers = {"Authorization": "Bearer " + r.json()["access"]}
    me = client.get(API + "/auth/me", headers=headers).json()
    assert me["user"]["username"] == username and me["family"]["name"] == "小岁的家"
    assert me["need_family"] is False
    # refresh
    r = client.post(API + "/auth/refresh", json={"refresh": body["refresh"]})
    assert r.status_code == 200 and r.json()["access"] and r.json()["need_family"] is False
    # 无 token 401
    assert client.get(API + "/bootstrap").status_code == 401


def test_join_family_by_invite_code_clears_gate(client):
    """第二条关联路径：凭邀请码加入后同样解除门控。"""
    h_owner, b_owner = _auth(client, "joinA")
    code = client.post(API + "/family/invite", headers=h_owner).json()["code"]
    fam_id = b_owner["family"]["id"]

    username = unique_name("joinB")
    pending = client.post(API + "/auth/register", json={"username": username, "password": "pw123456"}).json()
    assert pending["need_family"] is True
    h_joiner = {"Authorization": "Bearer " + pending["access"]}
    assert client.get(API + "/entries", headers=h_joiner).status_code == 409

    r = client.post(API + "/family/join", headers=h_joiner, json={"code": code})
    assert r.status_code == 200
    assert r.json()["family"]["id"] == fam_id and r.json()["family"]["role"] == "member"
    assert client.get(API + "/auth/me", headers=h_joiner).json()["need_family"] is False
    assert client.get(API + "/entries", headers=h_joiner).status_code == 200


def test_one_user_one_family_join_unbinds_previous(client):
    """归属唯一（§4.0）：凭邀请码加入其他家庭 = 与当前家庭解绑，个人资料不变、旧家庭数据不再可见。"""
    h_a, b_a = _auth(client, "oneA")
    fam_a = b_a["family"]["id"]
    h_b, b_b = _auth(client, "oneB")
    fam_b = b_b["family"]["id"]
    b_user, b_name = b_b["user"]["id"], b_b["user"]["name"]

    # 旧家庭里的建档与记录，加入新家庭后应随之不可见
    baby = _create_baby(client, h_b, name="旧家庭宝宝")
    entry = client.post(API + "/entries", headers=h_b, json={
        "type": "note", "title": "旧家庭记录", "occurred_at": _now_str(),
    })
    assert entry.status_code == 200, entry.text
    old_entry = entry.json()["id"]

    code = client.post(API + "/family/invite", headers=h_a).json()["code"]
    r = client.post(API + "/family/join", headers=h_b, json={"code": code})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["family"]["id"] == fam_a and body["family"]["role"] == "member"
    assert body["left_family"]["id"] == fam_b  # 明确回传被解绑的旧家庭

    # 唯一归属：B 只在 A 的家庭里，个人资料保持不变
    me = client.get(API + "/auth/me", headers=h_b).json()
    assert me["family"]["id"] == fam_a and me["need_family"] is False
    assert me["user"]["id"] == b_user and me["user"]["name"] == b_name
    # 旧家庭的宝宝/记录对新家庭不可见（越权即 403/404）
    assert client.get(API + f"/entries/{old_entry}", headers=h_b).status_code in (403, 404)
    assert client.put(API + f"/babies/{baby['id']}", headers=h_b, json={"name": "改名"}).status_code in (403, 404)
    assert client.get(API + "/bootstrap", headers=h_b).json()["babies"] == []
    # 归属唯一：已关联家庭不能再自建家庭，重复加入同一家庭 422
    assert client.post(API + "/family", headers=h_b, json={"name": "再建一个"}).status_code == 422
    assert client.post(API + "/family/join", headers=h_b, json={"code": code}).status_code == 422
    # 新家庭视角：B 已在成员列表内
    assert b_user in [m["id"] for m in client.get(API + "/family", headers=h_a).json()["members"]]


def test_creator_joining_other_family_hands_over_creator(client):
    """创建者加入其他家庭：与原家庭解绑，并把创建者身份交给最早加入的成员。"""
    h_a, b_a = _auth(client, "handA")
    fam_a = b_a["family"]["id"]
    h_b, _ = _auth(client, "handB")
    code_a = client.post(API + "/family/invite", headers=h_a).json()["code"]
    assert client.post(API + "/family/join", headers=h_b, json={"code": code_a}).status_code == 200

    h_c, b_c = _auth(client, "handC")
    fam_c = b_c["family"]["id"]
    code_c = client.post(API + "/family/invite", headers=h_c).json()["code"]

    r = client.post(API + "/family/join", headers=h_a, json={"code": code_c})
    assert r.status_code == 200, r.text
    assert r.json()["family"]["id"] == fam_c
    assert r.json()["left_family"]["id"] == fam_a
    # A 在新家庭是普通成员，旧家庭由 B 接管
    assert client.get(API + "/auth/me", headers=h_a).json()["family"]["role"] == "member"
    assert client.post(API + "/family/invite", headers=h_b).status_code == 200
    assert client.post(API + "/family/invite", headers=h_a).status_code == 403
    # 旧家庭留痕里同时记录「A 离开」与「B 接管」
    acts = [i["action"] for i in client.get(API + "/family/audit", headers=h_b).json()["items"]]
    assert "leave" in acts and "role" in acts


def test_removed_member_falls_back_and_creator_cannot_remove_self(client):
    """移除成员 = 与原家庭解绑：无自建家庭者回落 need_family；创建者不能移除自己。"""
    h_a, b_a = _auth(client, "rmA")
    # B 直接凭码加入（没有自建过家庭）
    username = unique_name("rmB")
    pending = client.post(API + "/auth/register", json={"username": username, "password": "pw123456"}).json()
    h_b = {"Authorization": "Bearer " + pending["access"]}
    code = client.post(API + "/family/invite", headers=h_a).json()["code"]
    assert client.post(API + "/family/join", headers=h_b, json={"code": code}).status_code == 200

    a_user = client.get(API + "/auth/me", headers=h_a).json()["user"]["id"]
    assert client.delete(API + f"/family/members/{a_user}", headers=h_a).status_code == 422

    b_user = client.get(API + "/auth/me", headers=h_b).json()["user"]["id"]
    assert client.delete(API + f"/family/members/{b_user}", headers=h_a).status_code == 200
    me = client.get(API + "/auth/me", headers=h_b).json()
    assert me["family"] is None and me["need_family"] is True
    assert client.get(API + "/entries", headers=h_b).status_code == 409
    # 重新关联只能走创建/凭码加入两条路径
    assert client.get(API + "/bootstrap", headers=h_b).json()["family"]["id"] == ""


def test_bootstrap_shape(client):
    headers, _ = _auth(client, "boot")
    r = client.get(API + "/bootstrap", headers=headers)
    assert r.status_code == 200
    s = r.json()
    for key in ("user", "family", "active_baby_id", "babies", "entries", "measurements",
                "media", "milestone_records", "vaccines", "journals", "settings", "trash"):
        assert key in s, key
    assert "members" in s["family"]


# ---------- 建档排期 ----------

def test_baby_creation_initializes_schedules(client):
    headers, _ = _auth(client, "baby")
    baby = _create_baby(client, headers)
    assert baby["is_active"] == 1  # 首个宝宝自动 active
    r = client.get(API + "/vaccines?baby_id=" + baby["id"], headers=headers)
    assert r.status_code == 200
    vaccines = r.json()
    assert len(vaccines) == 22
    bcg = next(v for v in vaccines if v["code"] == "bcg")
    assert bcg["plan_date"] == baby["birth_date"] and bcg["done"] is False and bcg["remind"] is True
    r = client.get(API + "/milestones?baby_id=" + baby["id"], headers=headers)
    ms = r.json()
    assert len(ms) == 13
    assert all(m["done"] is False and m["achieved_at"] == "" for m in ms)
    # 第二个宝宝不自动 active
    baby2 = _create_baby(client, headers, name="二宝")
    assert baby2["is_active"] == 0
    r = client.post(API + f"/babies/{baby2['id']}/activate", headers=headers)
    assert r.json()["is_active"] == 1
    babies = client.get(API + "/babies", headers=headers).json()
    assert sum(b["is_active"] for b in babies) == 1


def test_baby_update_birth_date_replans(client):
    headers, _ = _auth(client, "replan")
    baby = _create_baby(client, headers)
    # 先标记一剂已接种
    v = client.get(API + "/vaccines?baby_id=" + baby["id"], headers=headers).json()[0]
    client.put(API + f"/vaccines/{v['id']}", headers=headers, json={"done": True, "done_date": "2026-01-01"})
    new_birth = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%d")
    r = client.put(API + "/babies/" + baby["id"], headers=headers,
                   json={"name": baby["name"], "birth_date": new_birth})
    assert r.json()["birth_date"] == new_birth
    vaccines = client.get(API + "/vaccines?baby_id=" + baby["id"], headers=headers).json()
    assert vaccines[0]["plan_date"] == new_birth          # 重排
    assert vaccines[0]["done"] is True                    # 保留接种状态
    assert len(vaccines) == 22


# ---------- 记录 ----------

def test_measure_entry_generates_measurement_and_percentile(client):
    headers, _ = _auth(client, "meas")
    baby = _create_baby(client, headers)
    r = client.post(API + "/entries", headers=headers, json={
        "id": "e_meas_1", "type": "measure", "occurred_at": _now_str(1),
        "payload": {"height": 67.5, "weight": 7.8, "head": 43.2, "source": "儿保医院"},
        "title": "身高 67.5cm · 体重 7.8kg",
    })
    assert r.status_code == 200
    row = r.json()
    assert row["id"] == "e_meas_1" and row["baby_id"] == baby["id"]
    snap = client.get(API + "/bootstrap", headers=headers).json()
    mrows = [m for m in snap["measurements"] if m["entry_id"] == "e_meas_1"]
    assert {m["metric"] for m in mrows} == {"height", "weight", "head"}
    assert all(m["baby_id"] == baby["id"] for m in mrows)
    curve = client.get(API + "/growth/curve?metric=weight&baby_id=" + baby["id"], headers=headers).json()
    assert len(curve["points"]) == 1
    assert 0 < curve["points"][0]["percentile"] < 100
    assert curve["standard_version"] == "who-2006-anchor-v1"


def test_milestone_entry_marks_record(client):
    headers, _ = _auth(client, "ms")
    baby = _create_baby(client, headers)
    r = client.post(API + "/entries", headers=headers, json={
        "type": "milestone", "occurred_at": _now_str(0, "16:40"),
        "payload": {"name": "第一次翻身"}, "title": "第一次翻身", "badge": "milestone",
    })
    assert r.status_code == 200
    eid = r.json()["id"]
    ms = client.get(API + "/milestones?baby_id=" + baby["id"], headers=headers).json()
    done = next(m for m in ms if m["name"] == "第一次翻身")
    assert done["done"] is True and done["source_entry_id"] == eid
    assert done["achieved_at"] == _now_str(0, "16:40")


def test_idempotency_key(client):
    headers, _ = _auth(client, "idem")
    _create_baby(client, headers)
    body = {"id": "e_idem_1", "type": "feeding", "occurred_at": _now_str(0, "07:12"),
            "payload": {"method": "瓶喂", "amount": 120}, "title": "瓶喂 120ml"}
    h = dict(headers, **{"Idempotency-Key": "key-abc"})
    r1 = client.post(API + "/entries", headers=h, json=body)
    r2 = client.post(API + "/entries", headers=h, json=body)
    assert r1.json()["id"] == r2.json()["id"] == "e_idem_1"
    snap = client.get(API + "/bootstrap", headers=headers).json()
    assert sum(1 for e in snap["entries"] if e["id"] == "e_idem_1") == 1


def test_unknown_type_422(client):
    headers, _ = _auth(client, "badtype")
    _create_baby(client, headers)
    r = client.post(API + "/entries", headers=headers, json={"type": "spaceship", "occurred_at": _now_str()})
    assert r.status_code == 422


def test_trash_restore_purge(client):
    headers, _ = _auth(client, "trash")
    _create_baby(client, headers)
    r = client.post(API + "/entries", headers=headers,
                    json={"id": "e_trash_1", "type": "note", "occurred_at": _now_str(), "note": "随手记"})
    assert r.status_code == 200
    # 软删
    r = client.delete(API + "/entries/e_trash_1", headers=headers)
    assert r.status_code == 200
    row = r.json()
    assert row["deleted_at"] and row["deleted_by"]
    snap = client.get(API + "/bootstrap", headers=headers).json()
    assert not any(e["id"] == "e_trash_1" for e in snap["entries"])
    assert any(t["id"] == "e_trash_1" and "deleted_by" in t for t in snap["trash"])
    # 恢复
    r = client.post(API + "/entries/e_trash_1/restore", headers=headers)
    assert r.json()["deleted_at"] is None
    assert "deleted_by" not in r.json()
    # 彻底删除
    client.delete(API + "/entries/e_trash_1", headers=headers)
    r = client.delete(API + "/entries/trash/e_trash_1", headers=headers)
    assert r.status_code == 200
    snap = client.get(API + "/bootstrap", headers=headers).json()
    assert not any(t["id"] == "e_trash_1" for t in snap["trash"])
    # 清空回收站
    client.post(API + "/entries", headers=headers,
                json={"id": "e_trash_2", "type": "note", "occurred_at": _now_str()})
    client.delete(API + "/entries/e_trash_2", headers=headers)
    r = client.delete(API + "/entries/trash", headers=headers)
    assert r.json()["count"] >= 1
    assert client.get(API + "/bootstrap", headers=headers).json()["trash"] == []


def test_entries_cursor_pagination(client):
    headers, _ = _auth(client, "page")
    _create_baby(client, headers)
    for i in range(5):
        client.post(API + "/entries", headers=headers,
                    json={"type": "note", "occurred_at": _now_str(i + 1, "09:00"), "note": f"n{i}"})
    r = client.get(API + "/entries?limit=2", headers=headers).json()
    assert len(r["items"]) == 2 and r["next_cursor"]
    r2 = client.get(API + "/entries?limit=2&cursor=" + r["next_cursor"], headers=headers).json()
    assert len(r2["items"]) == 2
    ids = {x["id"] for x in r["items"]} & {x["id"] for x in r2["items"]}
    assert ids == set()


# ---------- 媒体 ----------

def test_media_upload_download(client):
    headers, _ = _auth(client, "media")
    _create_baby(client, headers)
    r = client.post(API + "/media", headers=headers, files={"file": ("p.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["url"] == f"/api/v1/media/{m['id']}" and m["size"] == len(PNG) and m["sha256"]
    # 鉴权下载
    r = client.get(m["url"], headers=headers)
    assert r.status_code == 200 and r.content == PNG
    # 无 token → 403（契约 §7）
    assert client.get(m["url"]).status_code == 403
    # 非法 token → 403
    assert client.get(m["url"], headers={"Authorization": "Bearer not.a.jwt"}).status_code == 403
    # 跨家庭 403
    headers2, _ = _auth(client, "media2")
    assert client.get(m["url"], headers=headers2).status_code == 403


# ---------- 记录人身份 ----------

def test_entry_creator_id_resolves_member_across_family(client):
    """跨成员看记录时，creator_id 必须能定位到成员行；名字串（昵称）与展示名不同源，
    只靠它解析会让主页把「妈妈」显示成「家人」。"""
    h_mom, b_mom = _auth(client, "cid_mom")
    mom_uid = b_mom["user"]["id"]
    _create_baby(client, h_mom)
    # 家长信息（妈妈）：成员展示名走 parent.name，与注册昵称无关
    client.put(API + "/settings", headers=h_mom,
               json={"key": "parent", "value": {"name": "李芳", "relation": "妈妈"}})
    code = client.post(API + "/family/invite", headers=h_mom).json()["code"]
    h_dad = {"Authorization": "Bearer " + client.post(API + "/auth/register", json={
        "username": unique_name("cid_dad"), "password": "pw123456", "name": "爸爸昵称"}).json()["access"]}
    assert client.post(API + "/family/join", headers=h_dad, json={"code": code}).status_code == 200

    r = client.post(API + "/entries", headers=h_mom, json={
        "id": "e_cid_1", "type": "milestone", "title": "第一颗牙", "occurred_at": _now_str(),
        "creator": "冒名的别人"})
    assert r.status_code == 200, r.text
    assert r.json()["creator_id"] == mom_uid
    assert r.json()["creator"] != "冒名的别人"  # 记录人只认令牌

    snap = client.get(API + "/bootstrap", headers=h_dad).json()
    dad_uid = snap["user"]["id"]
    row = next(e for e in snap["entries"] if e["id"] == "e_cid_1")
    assert row["creator_id"] == mom_uid
    mom = next(m for m in snap["family"]["members"] if m["id"] == mom_uid)
    assert mom["relation"] == "妈妈" and mom["name"] == "李芳"

    # 软删行同样带删除人 ID，回收站才能显示「妈妈 删除」
    assert client.delete(API + "/entries/e_cid_1", headers=h_dad).json()["deleted_by_id"] == dad_uid
    restored = client.post(API + "/entries/e_cid_1/restore", headers=h_dad).json()
    assert restored["deleted_at"] is None and "deleted_by_id" not in restored


def test_parent_nickname_equal_username_not_leaked(client):
    """家长信息填的是「昵称」：若昵称与登录账号同名，展示名不得透出账号，退回关系。"""
    headers, body = _auth(client, "nick")
    uid = body["user"]["id"]
    username = body["user"]["username"]
    _create_baby(client, headers)
    client.put(API + "/settings", headers=headers,
               json={"key": "parent", "value": {"name": username, "relation": "奶奶"}})
    member = next(m for m in client.get(API + "/bootstrap", headers=headers).json()["family"]["members"]
                  if m["id"] == uid)
    assert member["name"] != username
    assert member["name"] == "奶奶" and member["relation"] == "奶奶"


# ---------- 设置 ----------

def test_settings_single_key(client):
    headers, _ = _auth(client, "set")
    assert client.get(API + "/settings", headers=headers).json() == {}
    r = client.put(API + "/settings", headers=headers, json={"key": "account", "value": {"name": "妈妈"}})
    assert r.json() == {"account": {"name": "妈妈"}}
    client.put(API + "/settings", headers=headers, json={"key": "consent", "value": {"privacy": True}})
    assert client.get(API + "/settings", headers=headers).json()["consent"] == {"privacy": True}


# ---------- AI 日记（模板兜底） ----------

def test_journal_generate_template_fallback(client):
    headers, _ = _auth(client, "jr")
    _create_baby(client, headers)
    client.post(API + "/entries", headers=headers,
                json={"type": "feeding", "occurred_at": _now_str(1, "07:12"), "payload": {"amount": 120}})
    r = client.post(API + "/journals/generate", headers=headers, json={})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "draft" and j["model_version"] == "template" and j["prompt_version"] == "v1"
    assert j["paras"] and all("text" in p and "cites" in p for p in j["paras"])
    assert "周记草稿" in j["range"]
    # 归档
    r = client.put(API + f"/journals/{j['id']}", headers=headers, json={"status": "archived"})
    assert r.json()["status"] == "archived"
    rows = client.get(API + "/journals", headers=headers).json()
    assert rows[0]["id"] == j["id"]


# ---------- 家庭：邀请/加入/只读/越权 ----------

def test_family_join_and_readonly(client):
    h_a, b_a = _auth(client, "famA")
    fam_id = b_a["family"]["id"]
    r = client.post(API + "/family/invite", headers=h_a)
    assert r.status_code == 200 and r.json()["code"]
    code = r.json()["code"]

    h_b, _ = _auth(client, "famB")
    r = client.post(API + "/family/join", headers=h_b, json={"code": code})
    assert r.status_code == 200, r.text
    assert r.json()["family"]["id"] == fam_id
    # 重复加入 422
    assert client.post(API + "/family/join", headers=h_b, json={"code": code}).status_code == 422
    # 成员不可生成邀请/设只读
    assert client.post(API + "/family/invite", headers=h_b).status_code == 403
    assert client.patch(API + "/family/readonly", headers=h_b, json={"readonly": True}).status_code == 403

    baby = _create_baby(client, h_a)
    # 只读开启：非创建者写 403，创建者可写
    assert client.patch(API + "/family/readonly", headers=h_a, json={"readonly": True}).status_code == 200
    r = client.post(API + "/entries", headers=h_b, json={"type": "note", "occurred_at": _now_str()})
    assert r.status_code == 403 and r.json()["detail"] == "只读模式"
    r = client.post(API + "/entries", headers=h_a, json={"type": "note", "occurred_at": _now_str()})
    assert r.status_code == 200
    # 只读下成员仍可记录者视角读
    assert client.get(API + "/bootstrap", headers=h_b).status_code == 200

    # 跨家庭越权：无关用户 C 改 A 的宝宝 → 403
    h_c, _ = _auth(client, "famC")
    r = client.put(API + "/babies/" + baby["id"], headers=h_c, json={"name": "劫持"})
    assert r.status_code == 403

    # 关闭只读 → B 可写
    client.patch(API + "/family/readonly", headers=h_a, json={"readonly": False})
    assert client.post(API + "/entries", headers=h_b, json={"type": "note", "occurred_at": _now_str()}).status_code == 200

    # 移除成员：B 家庭归属回落（B 自己创建过个人家庭 → 回落）
    b_user = client.get(API + "/auth/me", headers=h_b).json()["user"]["id"]
    r = client.delete(API + f"/family/members/{b_user}", headers=h_a)
    assert r.status_code == 200
    me = client.get(API + "/auth/me", headers=h_b).json()
    assert me["family"]["id"] != fam_id


def test_family_audit_logs_real_operations(client):
    """FR-22：加入/只读/角色变更/删除/导出等写真实留痕，全员可读且不提供写接口。"""
    h_a, b_a = _auth(client, "auditA")
    code = client.post(API + "/family/invite", headers=h_a).json()["code"]

    h_b, _ = _auth(client, "auditB")
    assert client.post(API + "/family/join", headers=h_b, json={"code": code}).status_code == 200
    assert client.patch(API + "/family/readonly", headers=h_a, json={"readonly": True}).status_code == 200

    entry = client.post(API + "/entries", headers=h_a, json={
        "type": "note", "title": "留痕用例", "occurred_at": _now_str(), "note": "x",
    }).json()
    assert client.delete(API + "/entries/" + entry["id"], headers=h_a).status_code == 200

    items = client.get(API + "/family/audit", headers=h_a).json()["items"]
    acts = [i["action"] for i in items]
    # 倒序：最近的删除在最前；join/readonly/create 均真实落库
    assert acts[0] == "delete" and "留痕用例" in items[0]["text"]
    assert "join" in acts and "readonly" in acts and "create" in acts and "invite" in acts

    # 成员可读同一份留痕，且服务端不提供任何增改删接口
    assert client.get(API + "/family/audit", headers=h_b).json()["items"][0]["id"] == items[0]["id"]
    # 只读语义：POST/DELETE 均不可达（无写/删路由）
    assert client.post(API + "/family/audit", headers=h_a, json={}).status_code in (404, 405)
    assert client.delete(API + f"/family/audit/{items[0]['id']}", headers=h_a).status_code in (404, 405)

    # 保留期：超过 180 天的行不再返回
    from app.core.db import SessionLocal
    from app.models import AuditLog

    db = SessionLocal()
    old = db.get(AuditLog, items[-1]["id"])
    old.created_at = (datetime.now(timezone.utc) - timedelta(days=181)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.commit()
    db.close()
    ids = [i["id"] for i in client.get(API + "/family/audit", headers=h_a).json()["items"]]
    assert items[-1]["id"] not in ids


def test_invite_expired(client):
    h_a, _ = _auth(client, "invexp")
    r = client.post(API + "/family/invite", headers=h_a)
    code = r.json()["code"]
    h_b, _ = _auth(client, "invexpb")
    # 直接改库造过期
    from app.core.db import SessionLocal
    from app.models import InviteCode

    db = SessionLocal()
    ic = db.query(InviteCode).filter(InviteCode.code == code).first()
    ic.expires_at = "2000-01-01T00:00:00Z"
    db.commit()
    db.close()
    assert client.post(API + "/family/join", headers=h_b, json={"code": code}).status_code == 422


# ---------- 导出 / 导入 / 清空 ----------

def test_export_import(client):
    h_a, _ = _auth(client, "expA")
    baby = _create_baby(client, h_a)
    client.post(API + "/entries", headers=h_a,
                json={"id": "e_exp_1", "type": "feeding", "occurred_at": _now_str(1, "07:12"),
                      "payload": {"amount": 120}, "title": "瓶喂 120ml"})
    snap = client.get(API + "/export/data", headers=h_a).json()
    assert any(e["id"] == "e_exp_1" for e in snap["entries"])
    # A 先清空自己的业务数据，释放行 id（恢复备份的真实场景）
    assert client.delete(API + "/account/data", headers=h_a).status_code == 200

    h_b, _ = _auth(client, "expB")
    payload = {
        "baby": snap["babies"],
        "entry": snap["entries"],
        "measurement": snap["measurements"],
        "milestone_record": snap["milestone_records"],
        "vaccine": snap["vaccines"],
    }
    r = client.post(API + "/import", headers=h_b, json={"snapshot": payload})
    assert r.status_code == 200, r.text
    imported = r.json()["imported"]
    assert imported["entry"] == 1 and imported["baby"] == 1
    snap_b = client.get(API + "/bootstrap", headers=h_b).json()
    assert any(e["id"] == "e_exp_1" for e in snap_b["entries"])
    # 导入行强制归属当前家庭：B 的家庭获得完整一份数据
    assert len(snap_b["babies"]) == 1 and len(snap_b["vaccines"]) == 22


def test_wipe_account_data(client):
    headers, _ = _auth(client, "wipe")
    _create_baby(client, headers)
    client.post(API + "/entries", headers=headers,
                json={"type": "feeding", "occurred_at": _now_str(), "payload": {"amount": 90}})
    client.put(API + "/settings", headers=headers, json={"key": "account", "value": {"name": "x"}})
    r = client.delete(API + "/account/data", headers=headers)
    assert r.status_code == 200
    snap = client.get(API + "/bootstrap", headers=headers).json()
    assert snap["babies"] == [] and snap["entries"] == [] and snap["vaccines"] == []
    assert snap["measurements"] == [] and snap["milestone_records"] == []
    # 账号/家庭/设置保留
    assert snap["user"] and snap["family"]["id"]
    assert snap["settings"] == {"account": {"name": "x"}}


# ---------- 入参守卫（脏数据不得变成 500） ----------

def test_mood_entry_is_accepted(client):
    """快速记录面板的「心情」tile 走 type=mood：服务端曾只认 note，导致心情永远存不下来。"""
    headers, _ = _auth(client, "mood")
    _create_baby(client, headers)
    r = client.post(API + "/entries", headers=headers,
                    json={"type": "mood", "occurred_at": _now_str(), "payload": {"mood": "开心"}})
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "mood"
def test_dirty_payloads_degrade_instead_of_500(client):
    """ids/snapshot 传错类型：按「没传」处理，不能在推导式里 TypeError。"""
    headers, _ = _auth(client, "guard")
    for bad in ("abc", {"a": 1}, 123, None):
        r = client.post(API + "/notifications/read", headers=headers, json={"ids": bad})
        assert r.status_code == 200, f"ids={bad!r} → {r.status_code} {r.text}"
    r = client.post(API + "/import", headers=headers, json={"snapshot": {"entry": "坏行", "baby": 3}})
    assert r.status_code == 200, r.text
    assert r.json()["imported"]["entry"] == 0 and r.json()["imported"]["baby"] == 0


def test_entry_note_length_and_type_limits(client):
    headers, _ = _auth(client, "limit")
    _create_baby(client, headers)
    r = client.post(API + "/entries", headers=headers,
                    json={"type": "note", "occurred_at": _now_str(), "note": "字" * 701})
    assert r.status_code == 422, r.text
    e = client.post(API + "/entries", headers=headers,
                    json={"id": "e_guard_1", "type": "feeding", "occurred_at": _now_str(), "payload": {}}).json()
    assert client.put(API + "/entries/e_guard_1", headers=headers, json={"type": "giggle"}).status_code == 422
    assert client.put(API + "/entries/e_guard_1", headers=headers, json={"note": "字" * 701}).status_code == 422
    assert e["type"] == "feeding"


def test_baby_field_limits_and_allergy_roundtrip(client):
    """过敏史此前无落库列：客户端提交后被静默丢弃。"""
    headers, _ = _auth(client, "babyguard")
    b = _create_baby(client, headers)
    assert client.put(API + f"/babies/{b['id']}", headers=headers, json={"name": "名" * 21}).status_code == 422
    assert client.put(API + f"/babies/{b['id']}", headers=headers,
                      json={"birth_date": "2026/10/01"}).status_code == 422
    assert client.put(API + f"/babies/{b['id']}", headers=headers,
                      json={"birth_date": "2099-01-01"}).status_code == 422
    assert client.put(API + f"/babies/{b['id']}", headers=headers,
                      json={"gestational_weeks": 90}).status_code == 422
    assert client.put(API + f"/babies/{b['id']}", headers=headers,
                      json={"birth_weight": 300}).status_code == 422
    r = client.put(API + f"/babies/{b['id']}", headers=headers, json={"allergy": "奶粉蛋白过敏"})
    assert r.status_code == 200, r.text
    assert r.json()["allergy"] == "奶粉蛋白过敏"
    assert client.get(API + "/babies", headers=headers).json()[0]["allergy"] == "奶粉蛋白过敏"
    # 上限边界：700 字要能真写进 Postgres 的 varchar(2931)——密文比明文长，SQLite 测不出
    assert client.put(API + f"/babies/{b['id']}", headers=headers,
                      json={"allergy": "蛋" * 701}).status_code == 422
    assert client.put(API + f"/babies/{b['id']}", headers=headers,
                      json={"allergy": "蛋" * 700}).json()["allergy"] == "蛋" * 700
    # 显式清空要生效（PUT 传整行，""就是用户删掉了）
    assert client.put(API + f"/babies/{b['id']}", headers=headers, json={"allergy": ""}).json()["allergy"] == ""


def test_vaccine_long_text_clipped(client):
    headers, _ = _auth(client, "vclip")
    _create_baby(client, headers)
    v = client.get(API + "/vaccines", headers=headers).json()[0]
    r = client.put(API + f"/vaccines/{v['id']}", headers=headers, json={"org": "机构" * 30, "lot": "L" * 90})
    assert r.status_code == 200, r.text
    assert len(r.json()["org"]) == 20 and len(r.json()["lot"]) == 20
