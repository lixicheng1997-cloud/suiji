"""令牌生命周期：登出即时撤销 / refresh 一次性轮换 / media 令牌权限边界 / 踢人失效。

这些用例锁定「无状态 JWT 也要能主动失效」的三个锚点：
  jti 黑名单（登出）、refresh 占位（重放检测）、用户水位线（移出家庭）。
"""
from conftest import API, register, unique_name

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _register_only(client, prefix="sess"):
    username = unique_name(prefix)
    r = client.post(API + "/auth/register",
                    json={"username": username, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return username, r.json()


def test_logout_revokes_access_immediately(client):
    headers, _ = register(client, prefix="logout")
    assert client.get(API + "/auth/me", headers=headers).status_code == 200
    assert client.post(API + "/auth/logout", headers=headers, json={}).status_code == 200
    # 撤销发生在服务端：同一 access 立刻失效，而不是等自然过期
    assert client.get(API + "/auth/me", headers=headers).status_code == 401


def test_logout_revokes_refresh(client):
    headers, body = register(client, prefix="logoutRT")
    client.post(API + "/auth/logout", headers=headers, json={"refresh": body["refresh"]})
    # 登出后旧 refresh 不能再换新令牌
    assert client.post(API + "/auth/refresh", json={"refresh": body["refresh"]}).status_code == 401


def test_refresh_rotates_and_replay_kills_session(client):
    _, body = _register_only(client, "replay")
    first = body["refresh"]
    r = client.post(API + "/auth/refresh", json={"refresh": first})
    assert r.status_code == 200, r.text
    rotated = r.json()
    assert rotated["refresh"] and rotated["refresh"] != first
    assert rotated["media"]
    # 旧 refresh 二次提交 = 重放，直接 401
    assert client.post(API + "/auth/refresh", json={"refresh": first}).status_code == 401
    # 且抬高水位线：轮换刚拿到的新 access 也一并作废（毫秒级比对）
    h = {"Authorization": "Bearer " + rotated["access"]}
    assert client.get(API + "/auth/me", headers=h).status_code == 401


def test_media_token_downloads_but_cannot_call_api(client):
    headers, body = register(client, prefix="media")
    media = body["media"]
    # media 令牌只能下载，业务接口一律类型不匹配
    assert client.get(API + "/bootstrap",
                      headers={"Authorization": "Bearer " + media}).status_code == 401
    r = client.post(API + "/files", headers=headers,
                    files={"file": ("头像.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    # <img src> 场景：query 传 media 令牌可下载
    assert client.get(url, params={"token": media, "inline": 1}).status_code == 200
    # access 令牌不允许出现在 URL 里：会落进 nginx 日志 / 浏览器历史 / Referer，
    # 下载 URL 只认受限的 media 令牌（access 仍可走 Authorization 头）
    assert client.get(url, params={"token": body["access"], "inline": 1}).status_code == 403
    assert client.get(url, headers={"Authorization": "Bearer " + body["access"]}).status_code == 200
    # 无令牌 → 403（不是 401，与契约 §7 一致）
    assert client.get(url).status_code == 403


def test_removed_member_loses_original_family_data(client):
    """被移出后：family_id 每次实时查库，旧令牌立刻失去原家庭数据访问权。

    这里不强制下线（该用户可能回落到自己创建的家庭，继续沿用现有会话），
    所以断言的是「身份还在、家庭已换」，而不是 401。
    """
    h_owner, b_owner = register(client, prefix="kickA")
    owner_family = b_owner["family"]["id"]
    code = client.post(API + "/family/invite", headers=h_owner).json()["code"]

    _, pending = _register_only(client, "kickB")
    h_member = {"Authorization": "Bearer " + pending["access"]}
    assert client.post(API + "/family/join", headers=h_member,
                       json={"code": code}).status_code == 200
    me = client.get(API + "/auth/me", headers=h_member).json()
    assert me["family"]["id"] == owner_family

    assert client.delete(API + "/family/members/" + me["user"]["id"],
                         headers=h_owner).status_code == 200
    after = client.get(API + "/auth/me", headers=h_member)
    assert after.status_code == 200
    # 令牌仍能识别身份，但已不带原家庭 context
    assert (after.json()["family"] or {}).get("id") != owner_family
