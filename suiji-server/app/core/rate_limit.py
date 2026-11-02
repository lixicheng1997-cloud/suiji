"""接口限流（固定窗口计数）：优先 Redis，Redis 不可用时降级进程内存并定期重试恢复。

保护的都是「无鉴权即可调用」的高价值端点：注册、登录、刷新令牌、邀请码加入。
没有限流时这些端点可被无限爆破：撞库、批量注册、枚举邀请码。

设计取舍：
  1. 固定窗口而非滑动窗口——实现简单、单次 Redis INCR，精度足够挡爆破；
     窗口边界最多放行 2 倍配额，对「拦住自动化爆破」这个目标无实质影响。
  2. Redis 不可用时降级内存（可用性优先：不让存储故障变成全站不可用），
     但**不是永久降级**：到点重新探测 Redis，恢复后自动切回，避免一次抖动
     就让限流永久退化成单进程计数（多副本部署下等于没限流）。
  3. 计数键含客户端 IP。IP 取自 X-Real-IP / X-Forwarded-For 只在显式开启
     TRUST_PROXY 时才信任——否则任何人伪造该头即可绕过限流。
"""
import logging
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request

from .config import settings

logger = logging.getLogger(__name__)

_REDIS_RETRY_INTERVAL = 30.0  # Redis 故障后重新探测的间隔（秒）


def _normalize(window: int) -> int:
    return max(1, int(window))


class RateLimiter:
    """固定窗口计数器：hit() 返回 True 表示放行，False 表示已超配额。"""

    def __init__(self) -> None:
        self._redis = None
        self._redis_retry_at = 0.0
        self._mem: dict[str, tuple[int, float]] = {}
        self._last_gc = 0.0
        self._connect()

    # ---------- 后端选择 ----------
    def _connect(self) -> None:
        """建立 Redis 连接；失败时安排下一次重试时间，不永久降级。"""
        self._redis_retry_at = time.time() + _REDIS_RETRY_INTERVAL
        if not settings.redis_url:
            return
        try:
            import redis  # 局部导入：未装依赖时静默降级

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
            logger.warning("限流降级为进程内存：Redis 不可用（%s）", exc)

    def _ensure_backend(self) -> None:
        """Redis 掉线后定期重试；恢复则自动切回（避免一次抖动导致永久降级）。"""
        if self._redis is not None:
            return
        if time.time() < self._redis_retry_at:
            return
        self._connect()

    @property
    def backend(self) -> str:
        return "redis" if self._redis is not None else "memory"

    # ---------- 计数 ----------
    def _mem_hit(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        if now - self._last_gc > 60:  # 每分钟清一次过期项，防止长跑进程内存膨胀
            self._last_gc = now
            for k in [k for k, (_, exp) in self._mem.items() if exp <= now]:
                self._mem.pop(k, None)
        count, expire_at = self._mem.get(key, (0, 0.0))
        if now >= expire_at:
            count, expire_at = 0, now + window
        count += 1
        self._mem[key] = (count, expire_at)
        return count <= limit

    def hit(self, key: str, limit: int, window: int) -> bool:
        """记一次访问；返回 False 表示本次应被拒绝（429）。"""
        window = _normalize(window)
        self._ensure_backend()
        if self._redis is not None:
            try:
                pipe = self._redis.pipeline()
                pipe.incr(key)
                pipe.ttl(key)
                count, ttl = pipe.execute()
                if ttl is None or ttl < 0:
                    self._redis.expire(key, window)
                return int(count) <= limit
            except Exception as exc:
                logger.warning("限流读 Redis 失败，本次走内存（%s）", exc)
                self._redis = None
                self._redis_retry_at = time.time() + _REDIS_RETRY_INTERVAL
        return self._mem_hit(key, limit, window)


rate_limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """限流用的客户端 IP。

    只有在 TRUST_PROXY=1（部署在可信反代之后）时才信任 X-Real-IP /
    X-Forwarded-For：直接暴露时任何人都能伪造这两个头绕过限流。
    """
    if settings.trust_proxy:
        real = (request.headers.get("X-Real-IP") or "").strip()
        if real:
            return real
        forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return (request.client.host if request.client else "") or "unknown"


def limit(scope: str, limit_count: int, window: int):
    """生成限流依赖：同一 IP 在 window 秒内超过 limit_count 次即 429。

    用法：@router.post("/login", dependencies=[Depends(limit("login", 10, 60))])
    """

    def _dep(request: Request) -> None:
        ip = client_ip(request)
        if not rate_limiter.hit(f"rl:{scope}:{ip}", limit_count, window):
            raise HTTPException(
                status_code=429,
                detail=f"操作太频繁，请 {window} 秒后再试",
                headers={"Retry-After": str(window)},
            )

    return Depends(_dep)


def reset(scope: str, ip: str) -> None:
    """清掉某个 IP 的计数（仅测试用）。"""
    if rate_limiter._redis is not None:  # noqa: SLF001 - 测试夹具专用
        try:
            rate_limiter._redis.delete(f"rl:{scope}:{ip}")  # noqa: SLF001
        except Exception:
            pass
    rate_limiter._mem.pop(f"rl:{scope}:{ip}", None)


def _optional_ip(request: Optional[Request]) -> str:
    return client_ip(request) if request is not None else "unknown"
