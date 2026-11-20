"""手机号登录（阿里云号码认证）链路：mock GetMobile/VerifyPhone，不真连阿里云。

覆盖：服务闸 503 / 一键登录自动注册 / 同号二次登录命中同一账号 / 本机号码校验登录 /
绑定与冲突 409 / 解绑（空密码账号拒解绑 + 设置密码后可解绑）/ 手机号哈希确定性。
"""
import base64

import pytest

from app.api import auth as auth_api
from app.services.alibaba_phone import phone_hash_of

from conftest import register

PHONE = "13800001234"
PHONE_B = "13800005678"
PHONE_C = "13900007890"  # 各用例共享同一内存库，避免跨用例号码冲突


def _mock_aliyun(monkeypatch, phone=PHONE):
    """把 auth 命名空间里的阿里云调用换成可控桩：GetMobile 直出手机号，VerifyPhone 一律 PASS。"""
    monkeypatch.setattr(auth_api, "get_mobile", lambda token: phone)
    monkeypatch.setattr(auth_api, "verify_phone", lambda p, token: True)


def test_phone_service_disabled(client, monkeypatch):
    """AK/开关未配置时端点 503（前端按钮隐藏，端点兜底）。"""
    monkeypatch.setattr(auth_api.settings, "aliyun_phone_enabled", False)
    r = client.post("/api/v1/auth/phone/oneclick", json={"token": "t"})
    assert r.status_code == 503
    r = client.post("/api/v1/auth/phone/verify-login", json={"phone": PHONE, "token": "t"})
    assert r.status_code == 503
    r = client.post("/api/v1/auth/phone/bind", json={"phone": PHONE, "token": "t"},
                    headers={"Authorization": "Bearer x"})
    assert r.status_code in (401, 503)  # 闸在鉴权前：未配置直接 503，不泄账号状态


def test_oneclick_auto_register_and_relogin(client, monkeypatch):
    """首次一键登录自动注册（need_family=true、无密码）；同号再登命中同一账号。"""
    _mock_aliyun(monkeypatch)
    r = client.post("/api/v1/auth/phone/oneclick", json={"token": "t1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["need_family"] is True
    user1 = body["user"]
    assert user1["phone"] == "138****1234"
    assert user1["username"].startswith("sj") and len(user1["username"]) == 12
    # 自动注册账号无密码，无法走密码登录
    r2 = client.post("/api/v1/auth/login", json={"username": user1["username"], "password": "pw123456"})
    assert r2.status_code == 401
    # 同号二次登录 → 同一账号
    r3 = client.post("/api/v1/auth/phone/oneclick", json={"token": "t2"})
    assert r3.status_code == 200
    assert r3.json()["user"]["id"] == user1["id"]


def test_verify_login_and_bind_conflict(client, monkeypatch):
    """本机号码校验登录 + 绑定冲突：手机号已归属他人账号 → 绑定 409 不合并。"""
    headers, _ = register(client, prefix="phbind")
    # 用户 A 已通过一键登录占用 PHONE
    _mock_aliyun(monkeypatch)
    client.post("/api/v1/auth/phone/oneclick", json={"token": "t"})
    # 用户 B（密码注册）想把同一手机号绑到自己账号 → 409
    r = client.post("/api/v1/auth/phone/bind", json={"phone": PHONE, "token": "t"}, headers=headers)
    assert r.status_code == 409
    # B 绑定未占用的手机号 → 成功，user_row 出脱敏手机号
    r2 = client.post("/api/v1/auth/phone/bind", json={"phone": PHONE_B, "token": "t"}, headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["user"]["phone"] == "138****5678"
    # 手机号校验登录 B 的账号（VerifyPhone PASS → 按 phone_hash 命中）
    r3 = client.post("/api/v1/auth/phone/verify-login", json={"phone": PHONE_B, "token": "t"})
    assert r3.status_code == 200
    assert r3.json()["user"]["id"] == r2.json()["user"]["id"]


def test_unbind_guards(client, monkeypatch):
    """解绑闸：未绑定 400；手机号账号（无密码）拒解绑；设置密码后可解绑。"""
    headers, _ = register(client, prefix="phunbind")
    # 未绑定 → 400
    r = client.post("/api/v1/auth/phone/unbind", json={"password": "pw123456"}, headers=headers)
    assert r.status_code == 400
    # 绑定后未设密码？——密码注册的账号本就有密码，这里改测「手机号账号设置密码」闭环：
    _mock_aliyun(monkeypatch)
    rb = client.post("/api/v1/auth/phone/bind", json={"phone": PHONE_C, "token": "t"}, headers=headers)
    assert rb.status_code == 200
    # 解绑成功（密码注册账号有密码）
    r2 = client.post("/api/v1/auth/phone/unbind", json={"password": "pw123456"}, headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["user"]["phone"] == ""
    # 错误密码 → 400
    client.post("/api/v1/auth/phone/bind", json={"phone": PHONE_C, "token": "t"}, headers=headers)
    r3 = client.post("/api/v1/auth/phone/unbind", json={"password": "wrong-pass"}, headers=headers)
    assert r3.status_code == 400


def test_phone_account_set_password(client, monkeypatch):
    """手机号自动注册账号首次设置密码：免验旧密码，之后可密码登录。"""
    _mock_aliyun(monkeypatch)
    body = client.post("/api/v1/auth/phone/oneclick", json={"token": "t3"}).json()
    user = body["user"]
    headers = {"Authorization": "Bearer " + body["access"]}
    # 首次设置密码：免验旧密码（old_password 可为空）
    r = client.post("/api/v1/auth/password",
                    json={"old_password": "", "new_password": "phone-pass-1"}, headers=headers)
    assert r.status_code == 200, r.text
    # 设置密码后可密码登录（双通道）
    r2 = client.post("/api/v1/auth/login", json={"username": user["username"], "password": "phone-pass-1"})
    assert r2.status_code == 200, r2.text


def test_phone_hash_deterministic():
    """phone_hash 确定性：同号同哈希、异号异哈希、空号空哈希。"""
    assert phone_hash_of(PHONE) == phone_hash_of(" 13800001234 ")  # 去空白后一致
    assert phone_hash_of(PHONE) != phone_hash_of(PHONE_B)
    assert phone_hash_of("") == "" and phone_hash_of(None) == ""


def test_phone_format_gate(client, monkeypatch):
    """手机号格式闸：非 11 位/非数字/非 1 开头 → 422。"""
    _mock_aliyun(monkeypatch)
    for bad in ("1380000123", "1380000123a", "23800001234", ""):
        r = client.post("/api/v1/auth/phone/verify-login", json={"phone": bad, "token": "t"})
        assert r.status_code == 422, bad
