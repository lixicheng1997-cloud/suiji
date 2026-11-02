"""安全回归：锁住本次加固的边界（上传类型、导入注入、越权、限流、改密失效）。

这些用例全部是「曾经能过、现在必须挡住」的口子，删掉任何一条都意味着
对应的防护被撤掉了。
"""
import time

from conftest import API, register

PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
HTML = b"<html><script>alert(1)</script></html>"


def _fam(client, prefix="sec"):
    headers, body = register(client, prefix=prefix)
    return headers, body


# ---------- 上传类型 ----------

def test_html_upload_rejected(client):
    """扩展名白名单：.html 一律拒，避免上传后被同源渲染成存储型 XSS。"""
    headers, _ = _fam(client, "sec_html")
    r = client.post(API + "/files", headers=headers,
                    files={"file": ("x.html", HTML, "text/html")})
    assert r.status_code == 422, r.text


def test_svg_upload_rejected(client):
    headers, _ = _fam(client, "sec_svg")
    r = client.post(API + "/files", headers=headers,
                    files={"file": ("x.svg", b"<svg onload=alert(1)>", "image/svg+xml")})
    assert r.status_code == 422, r.text


def test_disguised_html_rejected(client):
    """改扩展名绕过白名单无效：字节是 HTML 就按 HTML 拒。"""
    headers, _ = _fam(client, "sec_disguise")
    r = client.post(API + "/files", headers=headers,
                    files={"file": ("x.png", HTML, "image/png")})
    assert r.status_code == 422, r.text


def test_content_type_not_taken_from_client(client):
    """库里登记的 Content-Type 必须是嗅探结果，不是客户端传的值。"""
    headers, _ = _fam(client, "sec_ct")
    r = client.post(API + "/files", headers=headers,
                    files={"file": ("x.png", PNG, "text/html")})
    assert r.status_code == 200, r.text
    assert r.json()["content_type"] == "image/png"


def test_unsafe_download_forces_attachment(client):
    """非图片/音视频/PDF 一律 attachment + nosniff，不会被浏览器当页面执行。"""
    headers, _ = _fam(client, "sec_dl")
    r = client.post(API + "/files", headers=headers,
                    files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    resp = client.get(url, headers=headers, params={"inline": 1})
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].startswith("attachment")
    assert resp.headers["x-content-type-options"] == "nosniff"


# ---------- 导入注入 ----------

def test_import_cannot_inject_storage_key(client):
    """/import 不能写入 storage_key：否则可以指向别的家庭的对象去读。"""
    owner, _ = _fam(client, "sec_owner")
    r = client.post(API + "/files", headers=owner,
                    files={"file": ("p.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    victim_key = r.json()["storage_key"]

    attacker, _ = _fam(client, "sec_attacker")
    media_id = "md_attacker_0001"
    r = client.post(API + "/import", headers=attacker, json={"snapshot": {
        "entry_media": [{"id": media_id, "storage_key": victim_key, "sha256": "x" * 64, "size": 1}],
    }})
    assert r.status_code == 200, r.text
    # 该行即使建出来，storage_key 也应被白名单拦掉（读不到别人家的字节）
    got = client.get(f"{API}/media/{media_id}", headers=attacker)
    assert got.status_code in (403, 404), got.status_code


def test_import_foreign_baby_id_blanked(client):
    """导入行的 baby_id/entry_id 必须落在本家庭内，跨家庭引用会被置空。"""
    owner, _ = _fam(client, "sec_fk_owner")
    baby = client.post(API + "/babies", headers=owner,
                       json={"name": "小满", "birth_date": "2025-01-01"}).json()
    attacker, _ = _fam(client, "sec_fk_attacker")
    eid = "e_attacker_0001"
    r = client.post(API + "/import", headers=attacker, json={"snapshot": {
        "entry": [{"id": eid, "type": "note", "baby_id": baby["id"], "note": "x"}],
    }})
    assert r.status_code == 200, r.text
    got = client.get(f"{API}/entries/{eid}", headers=attacker)
    assert got.status_code == 200
    assert got.json()["baby_id"] == ""


# ---------- 越权 ----------

def test_entry_cannot_bind_foreign_baby(client):
    """POST /entries 的 baby_id 必须属于本家庭。"""
    owner, _ = _fam(client, "sec_baby_owner")
    baby = client.post(API + "/babies", headers=owner,
                       json={"name": "小满", "birth_date": "2025-01-01"}).json()
    other, _ = _fam(client, "sec_baby_other")
    r = client.post(API + "/entries", headers=other,
                    json={"type": "note", "baby_id": baby["id"], "note": "x"})
    assert r.status_code == 403, r.text


def test_member_cannot_wipe_family_data(client):
    """清空家庭全部数据是创建者专属动作，普通成员不行。"""
    creator, creator_body = _fam(client, "sec_wipe_creator")
    code = client.post(API + "/family/invite", headers=creator).json()["code"]
    member, _ = _fam(client, "sec_wipe_member")
    assert client.post(API + "/family/join", headers=member, json={"code": code}).status_code == 200

    assert client.delete(API + "/account/data", headers=member).status_code == 403
    assert client.delete(API + "/account/data", headers=creator).status_code == 200


def test_creator_cannot_demote_self(client):
    """创建者不能把自己降级：否则家庭永久失去管理者。"""
    headers, _ = _fam(client, "sec_demote")
    me = client.get(API + "/auth/me", headers=headers).json()
    uid = me["user"]["id"]
    r = client.patch(f"{API}/family/members/{uid}", headers=headers, json={"role": "member"})
    assert r.status_code == 422, r.text


def test_audit_export_requires_creator(client):
    creator, _ = _fam(client, "sec_audit_creator")
    assert client.post(API + "/family/audit/export", headers=creator).status_code == 200
    code = client.post(API + "/family/invite", headers=creator).json()["code"]
    member, _ = _fam(client, "sec_audit_member")
    client.post(API + "/family/join", headers=member, json={"code": code})
    assert client.post(API + "/family/audit/export", headers=member).status_code == 403


# ---------- 认证 ----------

def test_weak_password_rejected(client):
    r = client.post(API + "/auth/register",
                    json={"username": "weak_user_1", "password": "123456"})
    assert r.status_code == 422, r.text


def test_change_password_invalidates_old_tokens(client):
    """改密必须真的收回已签发令牌：抬高水位线，旧 access 立刻失效。"""
    headers, body = _fam(client, "sec_pwd")
    old_access = body["access"]
    r = client.post(API + "/auth/password", headers=headers,
                    json={"old_password": "pw123456", "new_password": "newpass123"})
    assert r.status_code == 200, r.text
    # 旧令牌作废
    assert client.get(API + "/auth/me",
                      headers={"Authorization": "Bearer " + old_access}).status_code == 401
    # 新令牌可用（当前设备不用重新登录）
    assert client.get(API + "/auth/me",
                      headers={"Authorization": "Bearer " + r.json()["access"]}).status_code == 200


def test_change_password_requires_old_password(client):
    headers, _ = _fam(client, "sec_pwd2")
    r = client.post(API + "/auth/password", headers=headers,
                    json={"old_password": "wrong-pass", "new_password": "newpass123"})
    assert r.status_code == 400, r.text


def test_logout_all_devices(client):
    headers, body = _fam(client, "sec_logout_all")
    again = client.post(API + "/auth/login",
                        json={"username": body["user"]["username"],
                              "password": "pw123456"}).json()
    assert client.post(API + "/auth/logout", headers=headers,
                       json={"all": True}).status_code == 200
    # 另一台设备签发的令牌也失效
    assert client.get(API + "/auth/me",
                      headers={"Authorization": "Bearer " + again["access"]}).status_code == 401


# ---------- 限流 ----------

def test_rate_limiter_blocks_after_quota():
    from app.core import rate_limit

    key = "rl:unit-test:ip"
    rate_limit.rate_limiter._mem.pop(key, None)
    assert rate_limit.rate_limiter.hit(key, 2, 60) is True
    assert rate_limit.rate_limiter.hit(key, 2, 60) is True
    assert rate_limit.rate_limiter.hit(key, 2, 60) is False
    rate_limit.rate_limiter._mem.pop(key, None)


def test_login_rate_limited(client):
    """把配额顶满后再登录必须 429（爆破防护真的挂在路由上）。"""
    from app.core import rate_limit
    from app.core.config import settings

    headers, body = register(client, prefix="sec_rl")
    username = body["user"]["username"]
    key = f"rl:login:testclient"
    rate_limit.rate_limiter._mem[key] = (settings.rl_login, time.time() + 60)
    try:
        r = client.post(API + "/auth/login", json={"username": username, "password": "pw123456"})
        assert r.status_code == 429, r.text
    finally:
        rate_limit.rate_limiter._mem.pop(key, None)


def test_presign_expiry_is_capped(client):
    """预签名有效期由服务端封顶，客户端传再大也没用。"""
    from app.core.config import settings

    headers, _ = _fam(client, "sec_presign")
    r = client.post(API + "/files", headers=headers,
                    files={"file": ("p.png", PNG, "image/png")})
    fid = r.json()["id"]
    got = client.get(f"{API}/files/{fid}/url", headers=headers, params={"expires": 99999999})
    assert got.status_code == 200
    assert got.json()["expires"] <= settings.media_url_max_expires
