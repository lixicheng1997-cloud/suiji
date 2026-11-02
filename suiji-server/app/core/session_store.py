"""会话撤销账本（Redis 优先，不可用时降级进程内存）。

无状态 JWT 的固有短板是「签发后无法收回」，这里用三份账本补齐撤销能力：

  1. jti 黑名单   sess:jti:<jti>       登出 / refresh 轮换时写入，TTL = 令牌剩余寿命
  2. refresh 占位 sess:rt:<jti>        换取新令牌时 SETNX 占位；第二次出现即判定重放
  3. 用户 epoch   sess:epoch:<user_id> 用户级失效水位线；令牌 iat 早于该值即失效
                                      （改密、被移出家庭、注销账号）

降级语义与既有 IdempotencyStore 一致：Redis 不可用时退到进程内存，
单进程内语义完全成立，多副本部署下撤销会退化为「最终一致」，不会误放行新风险。
"""
import logging
import time
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

# epoch 水位线保留期：必须长于 refresh 寿命，否则旧 refresh 会绕过水位线重新生效
EPOCH_TTL_SECONDS = 60 * 86400
# Redis 故障后重新探测的间隔（秒）：降級是临时的，到点必须重试
_REDIS_RETRY_INTERVAL = 30.0


class _MemoryBackend:
    """进程内存实现：Redis 不可用时的降级后端（key -> (value, 过期时间戳)）。"""

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float]] = {}

    def _purge(self) -> None:
        now = time.time()
        for k in [k for k, (_, exp) in self._data.items() if exp <= now]:
            self._data.pop(k, None)

    def get(self, key: str) -> Optional[str]:
        item = self._data.get(key)
        if not item:
            return None
        value, expire_at = item
        if time.time() >= expire_at:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str, ttl: int) -> None:
        self._purge()
        self._data[key] = (value, time.time() + max(1, ttl))

    def setnx(self, key: str, value: str, ttl: int) -> bool:
        """不存在才写入；返回 True 表示本次抢到（未被使用过）。"""
        if self.get(key) is not None:
            return False
        self.set(key, value, ttl)
        return True

    def delete(self, key: str) -> None:
        self._data.pop(key, None)


class SessionStore:
    """撤销账本；所有方法都不抛异常，Redis 故障时静默降级。

    降级是**临时**的：Redis 抖动后到点自动重连，不会一次失败就永久退到内存。
    早先实现在异常分支里直接把 _redis 置 None 且不再重试，结果是：
    一次网络抖动 → 撤销账本永久变成单进程内存 → 多副本部署下登出、refresh
    重放检测、改密失效全部静默失效（已签发的令牌在其寿命内继续可用）。
    """

    def __init__(self) -> None:
        self._redis = None
        self._redis_retry_at = 0.0
        self._mem = _MemoryBackend()
        # 已撤销 jti 的进程内快照：撤销立即在本进程生效，同时避免重复打 Redis
        self._revoked: dict[str, float] = {}
        self._connect()

    # ---------- 后端选择 ----------
    def _connect(self) -> None:
        self._redis_retry_at = time.time() + _REDIS_RETRY_INTERVAL
        if not settings.redis_url:
            return
        try:
            import redis  # 局部导入：未装/不可达时静默降级

            client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            client.ping()
            self._redis = client
        except Exception as exc:
            self._redis = None
            logger.warning("会话账本降级为进程内存：Redis 不可用（%s）", exc)

    def _ensure_backend(self) -> None:
        """Redis 掉线后定期重试；恢复则自动切回共享账本。"""
        if self._redis is not None:
            return
        if time.time() < self._redis_retry_at:
            return
        self._connect()

    @property
    def backend(self) -> str:
        return "redis" if self._redis is not None else "memory"

    # ---------- 内部读写 ----------
    def _get(self, key: str) -> Optional[str]:
        self._ensure_backend()
        if self._redis is not None:
            try:
                return self._redis.get(key)
            except Exception as exc:
                logger.warning("会话账本读失败，本次走内存（%s）", exc)
                self._redis = None
                self._redis_retry_at = time.time() + _REDIS_RETRY_INTERVAL
        return self._mem.get(key)

    def _set(self, key: str, value: str, ttl: int) -> None:
        ttl = max(1, int(ttl))
        self._ensure_backend()
        if self._redis is not None:
            try:
                self._redis.set(key, value, ex=ttl)
                return
            except Exception as exc:
                logger.warning("会话账本写失败，本次走内存（%s）", exc)
                self._redis = None
                self._redis_retry_at = time.time() + _REDIS_RETRY_INTERVAL
        self._mem.set(key, value, ttl)

    def _setnx(self, key: str, value: str, ttl: int) -> bool:
        self._ensure_backend()
        if self._redis is not None:
            try:
                return bool(self._redis.set(key, value, ex=max(1, int(ttl)), nx=True))
            except Exception as exc:
                logger.warning("会话账本占位失败，本次走内存（%s）", exc)
                self._redis = None
                self._redis_retry_at = time.time() + _REDIS_RETRY_INTERVAL
        return self._mem.setnx(key, value, ttl)

    def _delete(self, key: str) -> None:
        self._ensure_backend()
        if self._redis is not None:
            try:
                self._redis.delete(key)
                return
            except Exception:
                self._redis = None
                self._redis_retry_at = time.time() + _REDIS_RETRY_INTERVAL
        self._mem.delete(key)

    # ---------- 1. jti 黑名单 ----------
    def revoke(self, jti: str, exp_ts: int) -> None:
        """撤销单个令牌；残留寿命即为黑名单 TTL，过期后自动回收。"""
        if not jti:
            return
        ttl = int(exp_ts) - int(time.time())
        if ttl <= 0:
            return  # 已过期，无需占用账本
        self._revoked[jti] = time.time() + ttl
        self._set(f"sess:jti:{jti}", "1", ttl)

    def is_revoked(self, jti: str) -> bool:
        if not jti:
            return False
        expire_at = self._revoked.get(jti)
        if expire_at is not None:
            if time.time() < expire_at:
                return True
            self._revoked.pop(jti, None)
        return self._get(f"sess:jti:{jti}") is not None

    # ---------- 2. refresh 一次性 ----------
    def consume_refresh(self, jti: str, exp_ts: int) -> bool:
        """占位式消费：True=首次使用；False=已被用过（重放）。"""
        if not jti:
            return True
        ttl = int(exp_ts) - int(time.time())
        if ttl <= 0:
            return False
        return self._setnx(f"sess:rt:{jti}", "1", ttl)

    def revoke_refresh(self, jti: str, exp_ts: int) -> None:
        """显式作废 refresh（登出时同时带上它，避免登出后仍能续期）。"""
        if not jti:
            return
        ttl = int(exp_ts) - int(time.time())
        if ttl <= 0:
            return
        self._set(f"sess:rt:{jti}", "1", ttl)

    # ---------- 3. 用户 epoch ----------
    def bump_epoch(self, user_id: str) -> int:
        """抬高水位线：此前签发的所有令牌（含 refresh/media）立即失效。

        用毫秒时间戳：秒级精度会让「同一秒内签发」的令牌（如 refresh 轮换刚下发的新
        access）比对新水位线时不满足 iat < epoch，从而躲过撤销。
        """
        if not user_id:
            return 0
        now_ms = int(time.time() * 1000)
        self._set(f"sess:epoch:{user_id}", str(now_ms), EPOCH_TTL_SECONDS)
        return now_ms

    def epoch_of(self, user_id: str) -> int:
        """返回水位线（毫秒）；无记录为 0。"""
        if not user_id:
            return 0
        raw = self._get(f"sess:epoch:{user_id}")
        try:
            return int(raw) if raw else 0
        except ValueError:
            return 0


session_store = SessionStore()
