"""应用配置：.env（python-dotenv）与环境变量，默认值面向本机开发（SQLite）。"""
import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]  # suiji-server 根目录
load_dotenv(BASE_DIR / ".env")

# 已知会被直接照抄进配置的占位密钥：生产环境出现即拒绝启动
_WEAK_SECRETS = {"change-me-in-prod", "changeme", "secret", "test", "your-secret-key"}


def _abs(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (BASE_DIR / path)


def _resolve_sqlite_url(url: str) -> str:
    """相对路径的 sqlite 库文件锚定到项目根，避免受启动 cwd 影响。"""
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///./data"):
        return url
    if url.startswith("sqlite:///./"):
        return "sqlite:///" + str(_abs(url[len("sqlite:///"):])).replace("\\", "/")
    return url


class Settings:
    def __init__(self) -> None:
        # 降级开关先于密钥校验解析：生产（关闭降级）必须显式配置密钥
        self.allow_fallback = os.getenv("SUIJI_ALLOW_FALLBACK", "1").strip().lower() not in (
            "0", "false", "no", "off")
        self.jwt_secret = self._resolve_jwt_secret()
        self.database_url = _resolve_sqlite_url(os.getenv("DATABASE_URL", "sqlite:///./data/suiji.db"))
        # 启动时是否自动执行 Alembic 迁移（alembic upgrade head）。默认 false：
        # 结构变更由启动建表（create_all）兜底，缺列的老库需手动跑迁移；
        # 置 1 后每次启动自动迁移到最新版本（迁移均为判存幂等，可安全重复执行）。
        self.run_migrations = os.getenv("RUN_MIGRATIONS", "0").strip().lower() in ("1", "true", "yes", "on")
        self.redis_url = os.getenv("REDIS_URL", "")
        self.media_dir = _abs(os.getenv("MEDIA_DIR", "./data/media"))
        # 非结构化文件存储后端：local（本地磁盘）/ minio（MinIO/S3 对象存储）
        self.media_backend = os.getenv("MEDIA_BACKEND", "local").strip().lower()
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000").strip()
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY", "").strip()
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY", "").strip()
        self.minio_bucket = os.getenv("MINIO_BUCKET", "suiji").strip() or "suiji"
        self.minio_secure = os.getenv("MINIO_SECURE", "false").strip().lower() in ("1", "true", "yes", "on")
        self.minio_region = os.getenv("MINIO_REGION", "").strip() or None
        # 客户端实际能访问到的 MinIO 地址（容器内 minio:9000 外网不可达时需配置）
        self.minio_public_url = os.getenv("MINIO_PUBLIC_URL", "").strip().rstrip("/")
        # 预签名 URL 有效期（秒）与其硬上限：客户端传多大都不能突破上限，
        # 否则 /files/{id}/url?expires= 会变成「自己签发一年有效的免鉴权直链」
        self.media_url_expires = int(os.getenv("MEDIA_URL_EXPIRES", "600") or 600)
        self.media_url_max_expires = int(os.getenv("MEDIA_URL_MAX_EXPIRES", "3600") or 3600)
        # 对象路径 {family}/{日期}/{文件} 中的日期取 UTC（默认取服务器本地日期）
        self.file_path_date_utc = os.getenv("MEDIA_PATH_DATE_UTC", "0").strip().lower() in (
            "1", "true", "yes", "on")
        # 下载方式：auto（有对外地址走 302 预签名，否则服务端代理）/ redirect / proxy
        self.media_download_mode = os.getenv("MEDIA_DOWNLOAD_MODE", "auto").strip().lower()
        # 单文件最大字节（/files 通用非结构化文件接口）
        self.file_max_bytes = int(os.getenv("FILE_MAX_BYTES", str(200 * 1024 * 1024)) or 200 * 1024 * 1024)
        self.llm_api_base = os.getenv("LLM_API_BASE", "").strip()
        self.llm_api_key = os.getenv("LLM_API_KEY", "").strip()
        self.llm_model = os.getenv("LLM_MODEL", "").strip()
        self.static_config_dir = BASE_DIR / "static" / "config"
        # 降级用的 SQLite 库文件（锚定项目根，避免受启动 cwd 影响）
        self.sqlite_fallback_url = "sqlite:///" + str(BASE_DIR / "data" / "suiji.db").replace("\\", "/")
        # 是否信任反向代理的 X-Real-IP / X-Forwarded-For（限流键用）。
        # 仅在服务确实部署在可信反代（本项目 nginx）之后才开启：
        # 直接暴露时任何人伪造该头即可绕过限流。
        self.trust_proxy = os.getenv("TRUST_PROXY", "0").strip().lower() in ("1", "true", "yes", "on")
        # 启动探测 nginx 网关的地址（GET /healthz）。留空时自动尝试：
        # compose 内 http://nginx/healthz，本机直连 http://127.0.0.1:30080/healthz
        self.nginx_probe_url = os.getenv("NGINX_PROBE_URL", "").strip()
        # CORS 白名单（逗号分隔）。传输加密中间件在 CORS 之外层直出的明文错误
        # 也要按这份名单补跨域头，否则浏览器读不到 409「密钥已更新」（见 payload_crypto.py）。
        self.cors_origins = [o.strip() for o in (os.getenv("CORS_ORIGINS", "") or "").split(",") if o.strip()]
        # ---- 无鉴权端点的限流配额（次 / 窗口秒）----
        self.rl_register = int(os.getenv("RL_REGISTER", "5") or 5)
        self.rl_register_window = int(os.getenv("RL_REGISTER_WINDOW", "3600") or 3600)
        self.rl_login = int(os.getenv("RL_LOGIN", "10") or 10)
        self.rl_login_window = int(os.getenv("RL_LOGIN_WINDOW", "300") or 300)
        self.rl_refresh = int(os.getenv("RL_REFRESH", "60") or 60)
        self.rl_refresh_window = int(os.getenv("RL_REFRESH_WINDOW", "300") or 300)
        self.rl_join = int(os.getenv("RL_JOIN", "10") or 10)
        self.rl_join_window = int(os.getenv("RL_JOIN_WINDOW", "300") or 300)
        self.rl_upload = int(os.getenv("RL_UPLOAD", "60") or 60)
        self.rl_upload_window = int(os.getenv("RL_UPLOAD_WINDOW", "300") or 300)
        # 密码最小长度（注册/改密共用）
        self.password_min_length = int(os.getenv("PASSWORD_MIN_LENGTH", "8") or 8)
        # ---- 应用层传输加密（见 core/crypto.py 的长注释）----
        # off      ：完全关闭，敏感接口只接受明文（cryptography 未安装时的降级态）
        # optional ：接受加密请求，也放行明文（默认：老客户端 / 冒烟脚本仍可跑）
        # required ：清单内接口必须加密，明文一律 400（客户端全部升级后请设为它，
        #            否则中间人可以直接剥掉 X-Sj-Enc 头做降级攻击）
        self.crypto_mode = os.getenv("CRYPTO_MODE", "optional").strip().lower()
        if self.crypto_mode not in ("off", "optional", "required"):
            logger.warning("CRYPTO_MODE=%s 非法，按 optional 处理", self.crypto_mode)
            self.crypto_mode = "optional"
        # RSA 私钥落盘位置（自动生成后要纳入 data/ 备份）
        self.crypto_key_file = _abs(os.getenv("CRYPTO_KEY_FILE", "./data/crypto/app_rsa_private.pem"))
        self.crypto_key_bits = int(os.getenv("CRYPTO_KEY_BITS", "2048") or 2048)
        # 请求时间戳允许偏移（秒）：同时挡重放与客户端时钟严重偏移
        self.crypto_ts_window = int(os.getenv("CRYPTO_TS_WINDOW", "300") or 300)
        # 单条加密报文上限（字节）：加密接口都是小报文，超限直接拒绝，防内存被打爆
        self.crypto_max_bytes = int(os.getenv("CRYPTO_MAX_BYTES", str(1024 * 1024)) or 1024 * 1024)
        # ---- 静态字段加密（TDD §十 P0：宝宝姓名/记录备注落库前加密）----
        # 密钥优先读环境变量（base64, 32 字节）；未配置则从 field_key_file 加载，
        # 首次启动自动生成。密钥与 RSA 私钥同目录，随 data/ 一起备份。
        self.field_enc_key = os.getenv("FIELD_ENC_KEY", "").strip()
        self.field_key_file = _abs(os.getenv("FIELD_KEY_FILE", "./data/crypto/field_key.bin"))

    def _resolve_jwt_secret(self) -> str:
        """JWT 签名密钥：HS256 是对称算法，密钥泄露等于可以伪造任意用户令牌。

        生产（SUIJI_ALLOW_FALLBACK=0，即关闭降级）必须显式配置，留空或用占位密钥直接拒绝启动；
        本机开发允许留空，此时生成一次性随机密钥（重启后旧令牌失效，不会用弱密钥签令牌）。
        """
        raw = (os.getenv("JWT_SECRET") or "").strip()
        if raw and raw not in _WEAK_SECRETS and len(raw) >= 16:
            return raw
        reason = "未配置" if not raw else ("仍是占位值" if raw in _WEAK_SECRETS else "长度不足 16 位")
        if not self.allow_fallback:
            raise RuntimeError(
                f"JWT_SECRET {reason}：生产部署请先在 .env 中设置随机长密钥"
                f"（python -c \"import secrets;print(secrets.token_urlsafe(48))\"）"
            )
        ephemeral = secrets.token_urlsafe(48)
        logger.warning("JWT_SECRET %s，开发模式已启用一次性随机密钥（重启后需重新登录）", reason)
        return ephemeral

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_base and self.llm_api_key and self.llm_model)


settings = Settings()
