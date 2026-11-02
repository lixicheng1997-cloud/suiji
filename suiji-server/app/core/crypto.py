"""应用层传输加密：RSA-OAEP-256 封装会话密钥 + AES-256-CBC/HMAC-SHA256 加密报文。

为什么需要它
------------
客户端与服务端之间跑的是明文 HTTP（nginx 30080 未启用 TLS 时），链路上任意一跳
都能直接看到请求/响应原文：账号口令、JWT 三件套、邀请码、导出数据全部裸奔。
TLS 当然是最彻底的解法，但「自用 + 自签证书 + 多端（小程序 / App / H5）」的组合里
证书分发成本高，所以在应用层再补一层端到端加密：链路被看穿也拿不到明文。

为什么是混合加密而不是「RSA 直接加密报文」
------------------------------------------
RSA-2048（OAEP-SHA256）单次最多装 190 字节，装不下请求体，且大块数据用 RSA 极慢。
标准做法是混合加密（TLS / JWE 同理）：
    1. 客户端生成随机会话密钥 CEK（32 字节）；
    2. 用服务端 RSA 公钥加密 CEK（非对称：客户端只需公钥，私钥永不出服务端）；
    3. 用 CEK 派生的对称密钥加密报文（快，无长度限制）。
这样既拿到非对称的「无需预共享密钥」好处，又不受 RSA 长度限制。

为什么选 CBC + HMAC 而不是 GCM
------------------------------
客户端只有 crypto-js（无 GCM 实现），而 Encrypt-then-MAC 的
AES-256-CBC + HMAC-SHA256 是 TLS 1.2 的同款构造，两端都能用现成库原生实现——
自己手写 GCM 的 GHASH 反而更容易出错。两个子密钥由 CEK 单向派生，互不复用。

报文格式（统一走 header 携带密钥材料，GET 无 body 也能加密响应）
--------------------------------------------------------------
请求头 X-Sj-Enc: <v>|<kid>|<ts_ms>|<iv_b64>|<rsa(cek)_b64>
请求体（有 body 时）: {"v":1,"data":"<b64>","tag":"<b64>"}
响应体（请求加密过时）: {"v":1,"enc":"A256CBC-HS256","iv":"<b64>","data":"<b64>","tag":"<b64>"}
AAD 上下文把 kid / ts / 方向 / path 一起绑进 HMAC，防止把 A 接口的密文搬到 B 接口重放。
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)

ALG = "RSA-OAEP-256"     # 密钥封装算法
ENC = "A256CBC-HS256"    # 内容加密算法
HEADER = "x-sj-enc"      # 请求头（小写：ASGI scope 里的 header 名一律小写）
CEK_BYTES = 32
IV_BYTES = 16
TAG_BYTES = 32
SCHEMA_V = 1

# 参与 HMAC 的上下文分隔符：保证「加密用密钥」与「验签用密钥」不同，
# 也保证同一 CEK 在请求/响应两个方向上产生的密文不可互换。
_DERIVE_ENC = b"suiji:enc:v1"
_DERIVE_MAC = b"suiji:mac:v1"

try:  # cryptography 是可选依赖：没装就整体降级为「不加密」，不影响服务启动
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    _HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover - 取决于运行环境
    _HAS_CRYPTOGRAPHY = False


def b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64url(value: int) -> str:
    """大整数 → JWK 用的无符号大端 base64url（去 padding）。"""
    raw = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


class CryptoBox:
    """服务端密钥盒：持有 RSA 私钥，负责解封 CEK 与报文加解密。"""

    def __init__(self) -> None:
        self.enabled = False
        self.kid = ""
        self.public_pem = ""
        self.reason = ""
        self._private = None
        self._setup()

    # ---------- 初始化 ----------
    def _setup(self) -> None:
        if not _HAS_CRYPTOGRAPHY:
            self.reason = "未安装 cryptography（pip install cryptography）"
            logger.warning("传输加密未启用：%s，敏感接口将只接受明文请求", self.reason)
            return
        if settings.crypto_mode == "off":
            self.reason = "CRYPTO_MODE=off"
            logger.info("传输加密已按配置关闭（CRYPTO_MODE=off）")
            return
        try:
            self._private = self._load_or_create()
        except Exception as exc:  # 密钥读不到/写不下不能拖垮启动
            self.reason = f"RSA 密钥加载失败：{exc}"
            logger.warning("传输加密未启用：%s", self.reason)
            return
        self.public_pem = self._private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        self.kid = hashlib.sha256(self._private.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )).hexdigest()[:16]
        self.enabled = True
        logger.info("传输加密已启用：alg=%s enc=%s kid=%s", ALG, ENC, self.kid)

    def _load_or_create(self):
        """读取私钥 PEM；不存在则生成并落盘（权限 600）。

        自动生成是刻意的：单人自用部署不该因为「忘了生成密钥」就整个用不了加密。
        密钥文件与媒体数据同级，备份 data/ 目录时一并带走——丢了它，
        客户端缓存的旧公钥就再也解不开（换密钥等于让所有客户端重新取公钥，不致命）。
        """
        path: Path = settings.crypto_key_file
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return serialization.load_pem_private_key(path.read_bytes(), password=None)
        key = rsa.generate_private_key(public_exponent=65537, key_size=settings.crypto_key_bits)
        path.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        try:
            os.chmod(path, 0o600)  # 私钥只对自己可读
        except OSError:  # Windows 上 chmod 语义不同，忽略
            pass
        logger.warning("已生成新的 RSA-%d 密钥对：%s（请纳入 data/ 备份）",
                       settings.crypto_key_bits, path)
        return key

    # ---------- 对外接口 ----------
    def info(self) -> dict | None:
        """下发给客户端的公钥信息（不含任何私密内容）。

        同时给 PEM 与 JWK 两种形式：PEM 是通用形态（服务端之间 / 排查用），
        JWK 直接把模数 n 与公钥指数 e 摊平——客户端（小程序 / App）没有 DER 解析器，
        有了 n/e 就能直接用 BigInt 做 RSA 模幂，不必引入额外的 ASN.1 依赖。
        """
        if not self.enabled:
            return None
        nums = self._private.public_key().public_numbers()
        return {
            "alg": ALG,
            "enc": ENC,
            "kid": self.kid,
            "pem": self.public_pem,
            "n": _b64url(nums.n),
            "e": _b64url(nums.e),
            "max_bytes": settings.crypto_max_bytes,
        }

    def unwrap_cek(self, wrapped_b64: str) -> bytes | None:
        """RSA-OAEP-256 解出会话密钥；任何失败都返回 None（不向调用方泄露原因）。"""
        if not self.enabled:
            return None
        try:
            raw = self._private.decrypt(
                b64d(wrapped_b64),
                padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                             algorithm=hashes.SHA256(), label=None),
            )
        except Exception:
            return None
        return raw if len(raw) == CEK_BYTES else None

    @staticmethod
    def _derive(cek: bytes) -> tuple[bytes, bytes]:
        return (hashlib.sha256(cek + _DERIVE_ENC).digest(),
                hashlib.sha256(cek + _DERIVE_MAC).digest())

    @staticmethod
    def context(kid: str, ts: int, direction: str, path: str) -> bytes:
        """AAD：把密钥版本、时间戳、方向、路径绑进 HMAC。

        路径进 AAD 之后，「把改密请求的密文原样重放到登录接口」会直接验签失败；
        时间戳进 AAD 之后，抓到的密文包只能在时间窗内重放。
        """
        return f"suiji:v1|{kid}|{ts}|{direction}|{path}".encode("utf-8")

    def open_payload(self, cek: bytes, iv: bytes, data: bytes, tag: bytes,
                     ctx: bytes) -> bytes | None:
        """解密并验签（先验证 MAC 再解密：Encrypt-then-MAC 的正确顺序）。

        返回 None 表示拒绝；绝不抛出具体原因——区分「MAC 错」与「padding 错」
        就是给攻击者一个 padding oracle。
        """
        enc_key, mac_key = self._derive(cek)
        if not hmac.compare_digest(hmac.new(mac_key, ctx + iv + data, hashlib.sha256).digest(), tag):
            return None
        try:
            dec = Cipher(algorithms.AES(enc_key), modes.CBC(iv)).decryptor()
            padded = dec.update(data) + dec.finalize()
        except Exception:
            return None
        n = padded[-1] if padded else 0
        if n < 1 or n > 16 or len(padded) < n:
            return None
        body = padded[:-n]
        # 逐字节校验 PKCS#7 填充：不一致立即失败，且不透露是哪一步失败
        if not hmac.compare_digest(padded[-n:], bytes([n]) * n):
            return None
        return body

    def seal_payload(self, cek: bytes, plaintext: bytes, ctx: bytes) -> tuple[str, str, str]:
        """加密并签名，返回 (iv_b64, data_b64, tag_b64)。"""
        enc_key, mac_key = self._derive(cek)
        iv = os.urandom(IV_BYTES)
        n = 16 - (len(plaintext) % 16)
        enc = Cipher(algorithms.AES(enc_key), modes.CBC(iv)).encryptor()
        data = enc.update(plaintext + bytes([n]) * n) + enc.finalize()
        tag = hmac.new(mac_key, ctx + iv + data, hashlib.sha256).digest()
        return b64e(iv), b64e(data), b64e(tag)

    def ts_valid(self, ts: int) -> bool:
        """时间戳窗口校验（毫秒）：同时挡掉过期重放与客户端时钟严重偏移。"""
        try:
            ts = int(ts)
        except (TypeError, ValueError):
            return False
        return abs(time.time() * 1000 - ts) <= settings.crypto_ts_window * 1000


crypto = CryptoBox()


def parse_header(value: str) -> tuple[str, int, bytes, str] | None:
    """解析 X-Sj-Enc：v|kid|ts|iv_b64|wrapped_b64。"""
    try:
        parts = (value or "").split("|")
        if len(parts) != 5:
            return None
        v, kid, ts, iv_b64, wrapped = parts
        if int(v) != SCHEMA_V:
            return None
        return kid, int(ts), b64d(iv_b64), wrapped
    except Exception:
        return None


def envelope(iv_b64: str, data_b64: str, tag_b64: str) -> bytes:
    """响应密文封装（JSON 字节）。"""
    return json.dumps(
        {"v": SCHEMA_V, "enc": ENC, "iv": iv_b64, "data": data_b64, "tag": tag_b64},
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
