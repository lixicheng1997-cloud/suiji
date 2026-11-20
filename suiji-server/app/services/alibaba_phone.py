"""阿里云号码认证服务封装（app/services/alibaba_phone.py）。

能力（用户已购买，控制台开通号码认证）：
  - GetMobile    ：一键登录取号 —— 客户端原生 SDK getToken 返回的令牌，服务端换取
                   本机 SIM 手机号（响应里 PhoneNumber 为 Base64 编码）。
  - VerifyPhone  ：本机号码校验 —— 客户端输入手机号后 SDK getVerifyToken 拿令牌，
                   服务端校验「输入号 == 本机 SIM 号」，PASS 才放行。

实现：手写阿里云 RPC 签名（HMAC-SHA1）直连 dypnsapi，不引官方 SDK——
alibabacloud_dypnsapi20170525 会拖入 tea/credentials 全家桶 10+ 依赖，与项目
轻量自包含风格不符；此处仅 2 个 Action，手写签名约百行更可控。

签名口径（阿里云 RPC 风格 V1.0）：
  1. 公共参数 + 业务参数按 key 升序拼接 k=v&...（值做 RFC3986 百分号编码）；
  2. stringToSign = "GET" + "&" + percentEncode("/") + "&" + percentEncode(query)；
  3. HMAC-SHA1(AccessKeySecret + "&", stringToSign) → Base64 即 Signature。

phone_hash_of：手机号的确定性哈希（HMAC-SHA256，密钥从 JWT_SECRET 派生）。
EncryptedString 密文带随机 nonce 无法建唯一索引，唯一性由 phone_hash 承担；
派生密钥与 JWT 签名密钥隔离（先 sha256 一轮），避免同一密钥双用途。
"""
import base64
import hashlib
import hmac
import logging
import secrets
import urllib.parse
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from ..core.config import settings

logger = logging.getLogger("suiji.alibaba_phone")

_ENDPOINT = "https://dypnsapi.aliyuncs.com"
_API_VERSION = "2017-05-25"
_TIMEOUT = 10.0

# 校验结果判 PASS 的取值（阿里云 VerifyPhone 响应 VerifyResult 字段）
_PASS = "PASS"


def _percent_encode(value: str) -> str:
    """阿里云要求的 RFC3986 百分号编码（+ → %20，* → %2A，%7E → ~）。"""
    return urllib.parse.quote(str(value), safe="-_.~")


def _phone_ready() -> bool:
    """号码认证是否已配置可用（AK 与开关都就位）。"""
    return bool(settings.aliyun_phone_enabled and settings.aliyun_phone_ak_id
                and settings.aliyun_phone_ak_secret)


def _rpc(action: str, biz: dict) -> dict:
    """发起一次阿里云 RPC 调用并解析 JSON 响应；异常统一归一为 503/502 HTTPException。

    服务端异常（阿里云限流/宕机/参数错）一律对外表现成 503 文案，
    不把内部细节暴露给客户端；调用方按 503 引导前端回退账号密码。
    """
    params = {
        "Action": action,
        "Version": _API_VERSION,
        "Format": "JSON",
        "AccessKeyId": settings.aliyun_phone_ak_id,
        "SignatureMethod": "HMAC-SHA1",
        "SignatureVersion": "1.0",
        "SignatureNonce": uuid.uuid4().hex,
        "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **biz,
    }
    sorted_query = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}"
        for k, v in sorted(params.items())
    )
    string_to_sign = "GET&" + _percent_encode("/") + "&" + _percent_encode(sorted_query)
    signature = base64.b64encode(
        hmac.new((settings.aliyun_phone_ak_secret + "&").encode("utf-8"),
                 string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    ).decode("ascii")
    url = f"{_ENDPOINT}/?Signature={_percent_encode(signature)}&{sorted_query}"

    try:
        resp = httpx.get(url, timeout=_TIMEOUT)
        data = resp.json()
    except Exception as exc:
        logger.warning("阿里云号码认证 %s 调用失败：%s", action, exc)
        raise HTTPException(status_code=503, detail="号码认证服务暂时不可用，请稍后再试或使用账号密码登录")
    if resp.status_code != 200 or str(data.get("Code")) != "OK":
        # 业务失败：InvalidToken / 服务未开通 / 限流等，归一 503（避免暴露枚举面）
        logger.warning("阿里云号码认证 %s 返回异常：%s", action, data)
        raise HTTPException(status_code=503, detail="号码认证未通过，请稍后再试或使用账号密码登录")
    return data


def get_mobile(token: str) -> str:
    """一键登录取号：token → 本机手机号（响应 Base64 解码）。"""
    data = _rpc("GetMobile", {"AccessToken": token})
    raw = (data.get("GetMobileResult") or {}).get("PhoneNumber") or ""
    try:
        phone = base64.b64decode(raw).decode("utf-8").strip()
    except Exception:
        phone = raw.strip()  # 兜底：个别形态已直出明文
    if not phone:
        raise HTTPException(status_code=503, detail="号码认证未通过，请稍后再试或使用账号密码登录")
    return phone


def verify_phone(phone: str, token: str) -> bool:
    """本机号码校验：输入号是否为本机 SIM 号（PASS 才算通过）。"""
    data = _rpc("VerifyPhone", {"PhoneNumber": phone, "AccessToken": token})
    result = (data.get("VerifyPhoneResult") or {})
    if str(result.get("VerifyResult") or "").upper() == _PASS:
        return True
    raise HTTPException(status_code=503, detail="手机号与本机不匹配，请确认后重试或使用账号密码登录")


def _phone_hash_of(phone: str) -> str:
    key = hashlib.sha256(("sj-phone-hash:" + settings.jwt_secret).encode("utf-8")).digest()
    return hmac.new(key, phone.encode("utf-8"), hashlib.sha256).digest()[:32].hex()


def phone_hash_of(phone: str) -> str:
    """手机号确定性哈希（唯一查询键）；空号返回空串（未绑定用户）。"""
    phone = (phone or "").strip()
    return _phone_hash_of(phone) if phone else ""


def gen_auto_username() -> str:
    """自动注册账号的用户名：sj + 10 位随机 base36（不对外展示，仅占位防冲突）。"""
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    return "sj" + "".join(secrets.choice(alphabet) for _ in range(10))
