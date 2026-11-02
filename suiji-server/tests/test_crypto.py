"""传输加密测试：密钥盒往返 + 中间件端到端（解密请求 / 加密响应 / 拒绝篡改）。

不依赖数据库：自己搭一个最小 FastAPI app 挂上中间件，路由直接回显收到的 body，
这样既能验证「路由拿到的确实是明文」，也能验证响应加密。
"""
import base64
import json
import os
import sys
import time

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import crypto as crypto_mod  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.payload_crypto import ENCRYPTED_PATHS, PayloadCryptoMiddleware  # noqa: E402

crypto = crypto_mod.crypto


# ---------------- 客户端侧（模拟前端 crypto.js 的行为） ----------------
def client_seal(cek: bytes, iv: bytes, plaintext: bytes, ctx: bytes) -> tuple[str, str]:
    """与前端一致的加密：AES-256-CBC(PKCS7) + HMAC-SHA256(Encrypt-then-MAC)。"""
    from cryptography.hazmat.primitives import hashes, hmac
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    enc_key, mac_key = crypto._derive(cek)
    n = 16 - (len(plaintext) % 16)
    enc = Cipher(algorithms.AES(enc_key), modes.CBC(iv)).encryptor()
    data = enc.update(plaintext + bytes([n]) * n) + enc.finalize()
    tag = hmac.HMAC(mac_key, hashes.SHA256())
    tag.update(ctx + iv + data)
    return base64.b64encode(data).decode(), base64.b64encode(tag.finalize()).decode()


def client_wrap(cek: bytes) -> str:
    """用服务端公钥做 RSA-OAEP-256 封装（前端 crypto.js 的 rsaEncrypt）。"""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    pub = load_pem_public_key(crypto.public_pem.encode())
    return base64.b64encode(pub.encrypt(
        cek,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                     algorithm=hashes.SHA256(), label=None),
    )).decode()


def client_open(cek: bytes, envelope: dict, ctx: bytes) -> bytes:
    """解密服务端响应（前端 crypto.js 的 openResponse）。"""
    from cryptography.hazmat.primitives import hashes, hmac
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    enc_key, mac_key = crypto._derive(cek)
    iv = base64.b64decode(envelope["iv"])
    data = base64.b64decode(envelope["data"])
    tag = base64.b64decode(envelope["tag"])
    h = hmac.HMAC(mac_key, hashes.SHA256())
    h.update(ctx + iv + data)
    h.verify(tag)
    dec = Cipher(algorithms.AES(enc_key), modes.CBC(iv)).decryptor()
    padded = dec.update(data) + dec.finalize()
    return padded[:-padded[-1]]


def build_app() -> FastAPI:
    app = FastAPI()

    @app.post("/api/v1/auth/login")
    async def login(request: Request):
        raw = await request.body()
        return {"echo": json.loads(raw.decode("utf-8")), "access": "tok"}

    @app.get("/api/v1/export/data")
    async def export_data():
        return {"babies": [{"id": "b1", "name": "小满"}]}

    app.add_middleware(PayloadCryptoMiddleware)
    return app


@pytest.fixture(scope="module")
def client():
    assert crypto.enabled, f"传输加密未启用：{crypto.reason}"
    with TestClient(build_app()) as c:
        yield c


def enc_headers(cek: bytes, iv: bytes, path: str, ts_ms: int, direction: str):
    wrapped = client_wrap(cek)
    header = f"1|{crypto.kid}|{ts_ms}|{base64.b64encode(iv).decode()}|{wrapped}"
    ctx = crypto.context(crypto.kid, ts_ms, direction, path)
    return {"X-Sj-Enc": header}, ctx


# ---------------- 密钥盒 ----------------
def test_box_roundtrip():
    cek = os.urandom(32)
    ctx = crypto.context(crypto.kid, 1, "req", "/api/v1/auth/login")
    iv_b64, data_b64, tag_b64 = crypto.seal_payload(cek, b'{"a":1}', ctx)
    out = crypto.open_payload(cek, base64.b64decode(iv_b64), base64.b64decode(data_b64),
                              base64.b64decode(tag_b64), ctx)
    assert out == b'{"a":1}'
    # 解封：RSA 包回去能还原同一个 cek
    assert crypto.unwrap_cek(client_wrap(cek)) == cek
    assert crypto.unwrap_cek(base64.b64encode(b"garbage").decode()) is None


def test_tamper_rejected():
    cek = os.urandom(32)
    ctx = crypto.context(crypto.kid, 1, "req", "/p")
    iv_b64, data_b64, tag_b64 = crypto.seal_payload(cek, b'{"a":1}', ctx)
    bad = bytes([base64.b64decode(data_b64)[0] ^ 0x01]) + base64.b64decode(data_b64)[1:]
    assert crypto.open_payload(cek, base64.b64decode(iv_b64), bad,
                               base64.b64decode(tag_b64), ctx) is None
    # 换个上下文（换接口）同样失败：AAD 绑定了路径
    other = crypto.context(crypto.kid, 1, "req", "/api/v1/auth/password")
    assert crypto.open_payload(cek, base64.b64decode(iv_b64), base64.b64decode(data_b64),
                               base64.b64decode(tag_b64), other) is None


def test_ts_window():
    assert crypto.ts_valid(int(time.time() * 1000))
    assert not crypto.ts_valid(int(time.time() * 1000) - 10 * 60 * 1000)


# ---------------- 中间件端到端 ----------------
def test_plain_request_still_works_in_optional_mode(client):
    r = client.post("/api/v1/auth/login", json={"username": "u", "password": "p@ss1234"})
    assert r.status_code == 200, r.text
    assert r.json()["echo"] == {"username": "u", "password": "p@ss1234"}


def test_encrypted_request_and_response(client):
    path = "/api/v1/auth/login"
    cek = os.urandom(32)
    iv = os.urandom(16)
    ts = int(time.time() * 1000)
    headers, ctx_req = enc_headers(cek, iv, path, ts, "req")
    data, tag = client_seal(cek, iv, b'{"username":"u","password":"p@ss1234"}', ctx_req)

    r = client.post(path, json={"v": 1, "enc": "A256CBC-HS256", "data": data, "tag": tag},
                    headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enc"] == "A256CBC-HS256"          # 响应被加密，不是明文回显
    assert "access" not in body
    plain = json.loads(client_open(cek, body, crypto.context(crypto.kid, ts, "resp", path)))
    assert plain["echo"] == {"username": "u", "password": "p@ss1234"}
    assert plain["access"] == "tok"


def test_encrypted_get_response(client):
    """GET 无请求体时，只借会话密钥加密响应（/export/data 场景）。"""
    path = "/api/v1/export/data"
    cek = os.urandom(32)
    ts = int(time.time() * 1000)
    headers, _ = enc_headers(cek, os.urandom(16), path, ts, "req")
    r = client.get(path, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enc"] == "A256CBC-HS256"
    plain = json.loads(client_open(cek, body, crypto.context(crypto.kid, ts, "resp", path)))
    assert plain["babies"][0]["name"] == "小满"


def test_tampered_ciphertext_rejected(client):
    path = "/api/v1/auth/login"
    cek = os.urandom(32)
    iv = os.urandom(16)
    ts = int(time.time() * 1000)
    headers, ctx_req = enc_headers(cek, iv, path, ts, "req")
    data, tag = client_seal(cek, iv, b'{"username":"u"}', ctx_req)
    r = client.post(path, json={"v": 1, "enc": "A256CBC-HS256", "data": data, "tag": tag[:-4] + "AAAA"},
                    headers=headers)
    assert r.status_code == 400


def test_stale_timestamp_rejected(client):
    path = "/api/v1/auth/login"
    cek = os.urandom(32)
    iv = os.urandom(16)
    ts = int(time.time() * 1000) - 20 * 60 * 1000
    headers, ctx_req = enc_headers(cek, iv, path, ts, "req")
    data, tag = client_seal(cek, iv, b'{"username":"u"}', ctx_req)
    r = client.post(path, json={"v": 1, "enc": "A256CBC-HS256", "data": data, "tag": tag},
                    headers=headers)
    assert r.status_code == 400


def test_unknown_kid_rejected(client):
    path = "/api/v1/auth/login"
    cek = os.urandom(32)
    iv = os.urandom(16)
    ts = int(time.time() * 1000)
    headers, ctx_req = enc_headers(cek, iv, path, ts, "req")
    headers["X-Sj-Enc"] = headers["X-Sj-Enc"].replace(crypto.kid, "0" * 16)
    data, tag = client_seal(cek, iv, b'{"username":"u"}', ctx_req)
    r = client.post(path, json={"v": 1, "enc": "A256CBC-HS256", "data": data, "tag": tag},
                    headers=headers)
    assert r.status_code == 409


def test_required_mode_rejects_plaintext(client, monkeypatch):
    monkeypatch.setattr(settings, "crypto_mode", "required")
    try:
        r = client.post("/api/v1/auth/login", json={"username": "u", "password": "p"})
        assert r.status_code == 400
    finally:
        monkeypatch.setattr(settings, "crypto_mode", "optional")


def test_non_listed_path_untouched(client):
    """清单外的接口不做任何处理（大文件上传等不受影响）。"""
    assert "/api/v1/entries" not in ENCRYPTED_PATHS
