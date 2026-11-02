"""密码哈希（bcrypt）与 JWT（HS256）签发 / 校验（契约 §2）。

令牌按用途分成三类，互不通用（服务端逐类校验 type，拿错一律 401/403）：
  access   业务接口      2 小时  —— Authorization: Bearer
  refresh  换取新令牌    30 天   —— 一次性：用后即焚，重放即判定泄露并整体失效
  media    仅媒体下载    7 天    —— 供 <img src>/<video src> 直连（无法带 Header），
                                  不能调用任何业务接口，泄露也读不到结构化数据

每个令牌都带两个撤销锚点：
  jti  唯一 ID   → 单个令牌精确撤销（登出、refresh 轮换），见 core/session_store.py
  iat  签发时刻  → 与用户级 epoch 水位线比对，实现「改密 / 被移出家庭」后全量失效
"""
import time
import uuid

import jwt
from passlib.context import CryptContext

from .config import settings

ACCESS_SECONDS = 2 * 3600      # 业务令牌：短命，靠 refresh 续期
REFRESH_SECONDS = 30 * 86400   # 刷新令牌：长命，但只能换一次
# 媒体令牌：只用于下载、泄露也读不到结构化数据，但它会出现在 URL 里
# （nginx 日志、浏览器历史、Referer），7 天太长——泄露后有整整一周可下载全部照片。
# 定为 24 小时：access 2 小时到期时 refresh 会一并把 media 换新，正常使用不受影响。
MEDIA_SECONDS = 24 * 3600

ACCESS = "access"
REFRESH = "refresh"
MEDIA = "media"

_TTL = {ACCESS: ACCESS_SECONDS, REFRESH: REFRESH_SECONDS, MEDIA: MEDIA_SECONDS}

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _clamp(plain: str) -> str:
    """bcrypt 上限 72 字节：超长口令截断，避免注册 500。"""
    raw = plain.encode("utf-8")[:72]
    return raw.decode("utf-8", errors="ignore")


def hash_password(plain: str) -> str:
    return _pwd.hash(_clamp(plain))


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd.verify(_clamp(plain), hashed)
    except ValueError:
        return False


def ttl_seconds(token_type: str) -> int:
    """令牌寿命（秒）；未知类型按 access 处理（最短，最保守）。"""
    return _TTL.get(token_type, ACCESS_SECONDS)


def create_token(user_id: str, family_id: str, role: str, token_type: str) -> str:
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "family_id": family_id,
        "role": role,
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "iat": now,
        # 毫秒级签发时刻：与用户水位线比对时，秒级精度会让「同一秒内签发的令牌」
        # 躲过撤销（例如 refresh 重放触发全量失效时）。标准 iat 只有秒，故另存一份。
        "iat_ms": int(time.time() * 1000),
        "exp": now + ttl_seconds(token_type),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def issued_ms(payload: dict) -> int:
    """令牌签发时刻（毫秒）；兼容没有 iat_ms 的旧令牌。"""
    if payload.get("iat_ms"):
        return int(payload["iat_ms"])
    return int(payload.get("iat") or 0) * 1000


def decode_token(token: str) -> dict:
    """解码 JWT；过期/非法抛 jwt.PyJWTError。"""
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
