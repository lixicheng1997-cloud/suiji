"""pytest 环境：内存 SQLite + TestClient（必须在导入 app 前设置环境变量）。"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="suiji-test-")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
# 置空 Redis：会话撤销账本自动降级进程内存，测试不依赖中间件
os.environ["REDIS_URL"] = ""
# 测试密钥需满足生产强度校验（≥16 位且非占位值），同时关闭生产级的严格模式
os.environ["JWT_SECRET"] = "pytest-only-secret-0123456789abcdef"
os.environ["SUIJI_ALLOW_FALLBACK"] = "1"
os.environ["MEDIA_DIR"] = os.path.join(_TMP, "media")
# 置空而非 pop：load_dotenv 不覆盖已存在的环境变量，防止 .env 的真实 LLM/MinIO 配置渗入测试
os.environ["LLM_API_BASE"] = ""
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_MODEL"] = ""
os.environ["MEDIA_BACKEND"] = "local"
os.environ["MINIO_PUBLIC_URL"] = ""
# 放宽限流配额：功能测试会在同一个 client IP（testclient）上反复注册/上传，
# 生产配额（注册 5 次/小时）会误伤。限流本身由 tests/test_rate_limit.py 单独验证。
for _k in ("RL_REGISTER", "RL_LOGIN", "RL_REFRESH", "RL_JOIN", "RL_UPLOAD"):
    os.environ[_k] = "100000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api/v1"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


_counter = {"n": 0}


def unique_name(prefix: str = "user") -> str:
    _counter["n"] += 1
    return f"{prefix}_{_counter['n']}"


def register(client, prefix="user", name=""):
    """注册并返回 (token_header, body)。

    注册本身不再代建家庭（返回 family=null / need_family=true），
    这里替客户端完成强制引导那一步：POST /family 建立个人家庭，保持 creator 角色。
    """
    username = unique_name(prefix)
    r = client.post(API + "/auth/register",
                    json={"username": username, "password": "pw123456", "name": name or username})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["family"] is None and body["need_family"] is True
    headers = {"Authorization": "Bearer " + body["access"]}
    fam = client.post(API + "/family", headers=headers, json={"name": (name or username) + "的家庭"})
    assert fam.status_code == 200, fam.text
    return headers, dict(body, family=fam.json()["family"], need_family=False)
