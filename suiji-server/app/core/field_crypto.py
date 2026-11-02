"""敏感字段静态加密（TDD §十 P0）：服务端落库前加密，读出时透明解密。

选型与边界：
- 算法：AES-256-GCM（认证加密，篡改即解密失败）。
- 密钥：优先读环境变量 FIELD_ENC_KEY（base64, 32 字节）；未配置时从
  settings.crypto_key_file 同级目录 field_key.bin 加载，首次启动自动生成。
  该文件随 data/ 一起备份，泄露即等同于库内密文全部可解——绝不随导出下发。
- 密文落库形状：`enc:v1:` + base64(nonce[12] || ciphertext || tag[16])。
- 兼容：读出时无前缀的旧明文原样返回，实现「上线即加密新数据、老数据无感」的
  平滑迁移；老数据无需跑一次性 backfill 脚本（按需可在后续版本补）。

为什么只加密 Baby.name 与 Entry.note：
- birth_date / gestational_weeks / measurement.value / payload 等字段参与月龄计算、
  百分位插值、统计聚合与排序，整字段加密会让这些查询退化为「全表拉到内存再解密」，
  破坏 P95 ≤ 800ms 的目标。这些字段的隐私敞口由「越权防护 + TLS + 私有桶」兜住。
- Baby.name（宝宝姓名）与 Entry.note（自由文本备注）是纯展示字段，不参与任何
  查询条件或聚合，加密对业务零影响。

实现方式用 SQLAlchemy TypeDecorator：模型层声明列类型即自动加解密，业务 service
代码完全无感知；导出/导入拿到的也是明文，不需要对称改写出入参。
"""
from __future__ import annotations

import base64
import logging
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.types import String, TypeDecorator

logger = logging.getLogger("suiji.field_crypto")

PREFIX = "enc:v1:"
_NONCE_LEN = 12  # AES-GCM 推荐 12 字节
_KEY_LEN = 32    # AES-256


class _FieldCrypto:
    """进程内单例：持有对称密钥，提供 encrypt/decrypt。未初始化时 encrypt 抛错、
    decrypt 原样返回（保证服务以「明文模式」也能启动，便于排障）。"""

    def __init__(self) -> None:
        self._aesgcm: AESGCM | None = None
        self.enabled = False

    def init(self, key_b64: str = "", key_file: str | os.PathLike = "") -> None:
        """加载或生成密钥。幂等：重复调用不会轮换密钥。"""
        if self.enabled:
            return
        key: bytes | None = None
        if key_b64:
            try:
                raw = base64.b64decode(key_b64)
                if len(raw) == _KEY_LEN:
                    key = raw
                else:
                    logger.warning("FIELD_ENC_KEY 长度不是 32 字节（实际 %d），忽略并落盘生成新 key", len(raw))
            except Exception:
                logger.warning("FIELD_ENC_KEY 不是合法 base64，忽略并落盘生成新 key")
        if key is None and key_file:
            p = Path(key_file)
            if p.exists():
                try:
                    raw = p.read_bytes()
                    if len(raw) == _KEY_LEN:
                        key = raw
                    else:
                        logger.warning("field_key.bin 长度异常（%d 字节），忽略", len(raw))
                except Exception as exc:
                    logger.warning("读取 field_key.bin 失败：%s", exc)
        if key is None:
            key = secrets.token_bytes(_KEY_LEN)
            if key_file:
                p = Path(key_file)
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(key)
                    try:
                        os.chmod(p, 0o600)
                    except OSError:
                        pass  # Windows 无 chmod 位语义
                    logger.info("已生成静态加密密钥：%s（请随 data/ 一起备份）", p)
                except Exception as exc:
                    logger.warning("写 field_key.bin 失败：%s（密钥仅存内存，重启后旧密文无法解密）", exc)
        self._aesgcm = AESGCM(key)
        self.enabled = True

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return plaintext
        if not self.enabled:
            # 未初始化：不加密，直接落明文（与历史行为一致）
            return plaintext
        nonce = secrets.token_bytes(_NONCE_LEN)
        ct = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return PREFIX + base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, stored: str) -> str:
        if not stored or not stored.startswith(PREFIX):
            return stored or ""
        if not self.enabled or self._aesgcm is None:
            # 密钥不可用：返回占位而不是抛错，避免 bootstrap 整个挂掉
            logger.error("字段已加密但静态加密未初始化，返回占位文本")
            return ""
        try:
            raw = base64.b64decode(stored[len(PREFIX):])
            nonce, ct = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
            return self._aesgcm.decrypt(nonce, ct, None).decode("utf-8")
        except Exception as exc:
            logger.error("字段解密失败（密钥轮换或数据损坏）：%s", exc)
            return ""


field_crypto = _FieldCrypto()


class EncryptedString(TypeDecorator):
    """SQLAlchemy 列类型：写入时加密，读出时解密，对业务代码透明。

    列宽：密文比明文长约 64 字节（nonce+tag+base64 膨胀），建列时给足余量。
    业务侧给的长度参数仍按「明文字符数」理解，本实现内部按 *1.5+64 扩容落库。
    """

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        # 落库列宽：明文长度 * 4/3 + 64 字节余量，向上对齐到 16 的倍数
        widened = max(int((self.length or 255) * 1.4) + 64, 256)
        return dialect.type_descriptor(String(widened))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return field_crypto.encrypt(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return field_crypto.decrypt(str(value))
