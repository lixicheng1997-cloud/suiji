"""MediaStore 抽象 + 本地磁盘 / MinIO 对象存储两种实现（契约 §7）。

- LocalMediaStore：单机开发默认实现，文件落 media_dir。
- MinioMediaStore：docker-compose 部署实现，文件入 MinIO 桶，下载走预签名 URL 或服务端代理。

两种后端共用同一套对象路径规则：`{family_id}/{YYYY-MM-DD}/{文件名}`（按家庭隔离、按天归档、
文件名可读）；同家庭同内容（sha256）在业务层复用同一对象，同名不同内容自动追加 sha 短码，
保证一个路径只对应一份字节。旧的 sha 寻址 key（`sha[:2]/sha.ext`）仍可正常读删，平滑兼容。
"""
import logging
import mimetypes
import re
import shutil
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Iterator

from ..core.config import settings

MAX_MEDIA_BYTES = 200 * 1024 * 1024  # 200MB
MAX_NAME_LEN = 96  # 文件名段最大字符数（storage_key 列长有限，超出截断并保留扩展名）

logger = logging.getLogger(__name__)

_ILLEGAL_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_WS_RE = re.compile(r"\s+")
_FAMILY_RE = re.compile(r"[^0-9A-Za-z._-]+")


def content_key(sha256_hex: str, suffix: str = "") -> str:
    """内容寻址 key：sha 前 2 位做一级目录，同 sha 天然去重。

    仅用于旧数据兼容与缺少家庭上下文的兜底，新上传走 object_key()。
    """
    return f"{sha256_hex[:2]}/{sha256_hex}{suffix}"


def _safe_filename(filename: str, suffix: str = "", sha256_hex: str = "") -> str:
    """文件名段：去路径分隔符/控制字符，补齐扩展名，超长截断。"""
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = _WS_RE.sub(" ", _ILLEGAL_RE.sub("_", name)).strip().strip(".")
    if not name:
        name = f"unnamed_{sha256_hex[:12]}" if sha256_hex else "unnamed"
    if suffix and not name.lower().endswith(suffix.lower()):
        name += suffix  # 扩展名决定 mime 推断与客户端预览，缺失时补齐
    if len(name) > MAX_NAME_LEN:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) <= 9:
            name = stem[: max(8, MAX_NAME_LEN - len(ext) - 1)].rstrip(".") + dot + ext
        else:
            name = name[:MAX_NAME_LEN]
    return name


def day_dir(when: datetime | None = None) -> str:
    """归档日期目录 YYYY-MM-DD（默认服务器本地日期，MEDIA_PATH_DATE_UTC=1 时取 UTC）。"""
    if when is None:
        when = datetime.now(timezone.utc) if settings.file_path_date_utc else datetime.now()
    return when.strftime("%Y-%m-%d")


def object_key(family_id: str, filename: str = "", suffix: str = "", sha256_hex: str = "",
               when: datetime | None = None) -> str:
    """对象路径：{family_id}/{YYYY-MM-DD}/{文件名}。"""
    family = _FAMILY_RE.sub("_", (family_id or "").strip()) or "unknown"
    return f"{family}/{day_dir(when)}/{_safe_filename(filename, suffix, sha256_hex)}"


def _conflict_key(key: str, sha256_hex: str, n: int) -> str:
    """同名冲突：在扩展名前追加 sha 短码，保证不同内容不互相覆盖。"""
    head, dot, ext = key.rpartition(".")
    if dot and "/" not in ext:
        return f"{head}_{sha256_hex[:n]}{dot}{ext}"
    return f"{key}_{sha256_hex[:n]}"


def _unique_key(store: "MediaStore", key: str, sha256_hex: str) -> str:
    if not store.exists(key):
        return key
    for n in (8, 16, 32):
        cand = _conflict_key(key, sha256_hex, n)
        if not store.exists(cand):
            return cand
    return _conflict_key(key, sha256_hex, 64)


class MediaStore(ABC):
    @abstractmethod
    def save(self, data: bytes, sha256_hex: str, suffix: str = "", content_type: str = "",
             family_id: str = "", filename: str = "") -> str:
        """落盘（或上传）并返回 storage_key。"""

    @abstractmethod
    def path(self, storage_key: str) -> Path | None:
        """storage_key → 本地可读路径；对象存储无本地路径时返回 None。"""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        ...

    def exists(self, storage_key: str) -> bool:
        """对象是否已存在（用于同名冲突消解）；默认不做探测。"""
        return False

    def url(self, storage_key: str, expires: int = 0) -> str | None:
        """可直接下载的临时 URL；不支持则返回 None（走本地/代理下载）。"""
        return None

    def open_stream(self, storage_key: str, start: int | None = None,
                    end: int | None = None) -> Iterator[bytes] | None:
        """打开对象字节流（对象不存在返回 None）；不支持则返回 None。

        start/end 是闭区间的字节偏移（HTTP Range 语义），用于音频/视频的拖动播放：
        没有分段读取能力时忽略偏移、整份回流，调用方需自己核对返回长度。
        """
        return None

    def size(self, storage_key: str) -> int | None:
        """对象总字节数（Range 响应要写 Content-Range 的总长）；取不到返回 None。"""
        return None

    def save_stream(self, src, size: int, sha256_hex: str, suffix: str = "",
                    content_type: str = "", family_id: str = "", filename: str = "") -> str:
        """流式落存储：src 为可读二进制流（会被 seek(0)）。

        默认实现读全量到内存，子类可覆写成真正的流式写入，避免大文件吃内存。
        """
        src.seek(0)
        return self.save(src.read(), sha256_hex, suffix, content_type, family_id, filename)


class LocalMediaStore(MediaStore):
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_key: str) -> Path:
        # 防目录穿越：key 只允许 base36/斜杠/点/下划线/连字符
        safe = Path(storage_key)
        if ".." in safe.parts or safe.is_absolute():
            raise ValueError("非法 storage_key")
        return self.base_dir / safe

    def save(self, data: bytes, sha256_hex: str, suffix: str = "", content_type: str = "",
             family_id: str = "", filename: str = "") -> str:
        storage_key = _unique_key(self, self._new_key(sha256_hex, suffix, family_id, filename),
                                  sha256_hex)
        dest = self._resolve(storage_key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            with open(dest, "wb") as f:
                f.write(data)
        return storage_key

    def save_stream(self, src, size: int, sha256_hex: str, suffix: str = "",
                    content_type: str = "", family_id: str = "", filename: str = "") -> str:
        storage_key = _unique_key(self, self._new_key(sha256_hex, suffix, family_id, filename),
                                  sha256_hex)
        dest = self._resolve(storage_key)
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.seek(0)
            with open(dest, "wb") as f:
                shutil.copyfileobj(src, f, length=256 * 1024)
        return storage_key

    def exists(self, storage_key: str) -> bool:
        try:
            return self._resolve(storage_key).exists()
        except ValueError:
            return False

    def path(self, storage_key: str) -> Path | None:
        # 空 key 会解析成媒体根目录本身，交给 FileResponse 就是 500——必须是「不存在」
        if not (storage_key or "").strip():
            return None
        try:
            p = self._resolve(storage_key)
        except ValueError:
            return None
        return p if p.is_file() else None

    @staticmethod
    def _new_key(sha256_hex: str, suffix: str, family_id: str, filename: str) -> str:
        if not family_id and not filename:
            return content_key(sha256_hex, suffix)
        return object_key(family_id, filename, suffix, sha256_hex)

    def delete(self, storage_key: str) -> None:
        try:
            p = self._resolve(storage_key)
        except ValueError:
            return
        if p.exists():
            p.unlink()


class MinioMediaStore(MediaStore):
    """MinIO / S3 兼容对象存储实现（需要依赖：pip install minio）。"""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str,
                 secure: bool = False, region: str | None = None, public_url: str = "") -> None:
        if not access_key or not secret_key:
            raise RuntimeError("MEDIA_BACKEND=minio 需要配置 MINIO_ACCESS_KEY / MINIO_SECRET_KEY")
        try:
            from minio import Minio
        except ImportError as exc:  # 依赖缺失只在切换到 minio 时才报错
            raise RuntimeError("MEDIA_BACKEND=minio 需要安装依赖：pip install minio") from exc

        self.bucket = bucket
        endpoint = (endpoint or "localhost:9000").strip().rstrip("/")
        for scheme in ("https://", "http://"):
            if endpoint.startswith(scheme):
                secure = scheme == "https://"  # 显式 scheme 优先于 MINIO_SECURE
                endpoint = endpoint[len(scheme):]
                break
        self.endpoint = endpoint
        self._internal_base = f"{'https' if secure else 'http'}://{endpoint}"
        self.public_url = public_url.rstrip("/") if public_url else self._internal_base
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key,
                             secure=secure, region=region or None)
        # 预签名必须用客户端实际访问的 host 计算（SigV4 把 Host 纳入签名），
        # 否则改写主机名后 MinIO 校验 SignatureDoesNotMatch。presign 为纯本地计算，不发网络请求。
        # public_url 可能带路径（如 http://host:30080/minio，nginx 反代前缀），
        # Minio() 构造函数只接受 host:port，路径部分在 URL 替换时拼接。
        self._presign = self._client
        if public_url and self.public_url != self._internal_base:
            try:
                p_host = self.public_url.split("://", 1)[1].split("/", 1)[0]
                p_secure = self.public_url.startswith("https")
                # 显式指定 region，避免 presign 时发 _get_region 请求到公网 host
                # （公网 nginx 只有 /minio/ 前缀，直接查 bucket 会 404）
                self._presign = Minio(p_host, access_key=access_key, secret_key=secret_key,
                                      secure=p_secure, region=region or "us-east-1")
            except Exception as exc:
                logger.warning("预签名独立客户端创建失败，沿用内部端点：%s", exc)
        self._ready = False
        # 建桶即探测：连不上就抛错，交给 get_store() 降级到本地磁盘
        self._ensure_bucket(probe=True)

    def _ensure_bucket(self, probe: bool = False) -> None:
        if self._ready:
            return
        last_exc: Exception | None = None
        for attempt in range(3):  # 给刚启动的 MinIO 一点时间
            try:
                if not self._client.bucket_exists(self.bucket):
                    self._client.make_bucket(self.bucket)
                self._ready = True
                return
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(1)
        msg = f"MinIO 存储暂不可用（{self.endpoint}:{self.bucket}）：{last_exc}"
        if probe:
            raise RuntimeError(msg)
        logger.warning("%s，将在下次读写时重试", msg)

    def save(self, data: bytes, sha256_hex: str, suffix: str = "", content_type: str = "",
             family_id: str = "", filename: str = "") -> str:
        return self.save_stream(BytesIO(data), len(data), sha256_hex, suffix, content_type,
                                family_id, filename)

    def path(self, storage_key: str) -> Path | None:
        return None  # 对象无本地路径，下载走 url() / open_stream()

    def exists(self, storage_key: str) -> bool:
        try:
            self._client.stat_object(self.bucket, storage_key)
            return True
        except Exception:
            return False

    def save_stream(self, src, size: int, sha256_hex: str, suffix: str = "",
                    content_type: str = "", family_id: str = "", filename: str = "") -> str:
        """流式直传对象存储：不把整份文件读进内存。"""
        self._ensure_bucket()
        base = object_key(family_id, filename, suffix, sha256_hex) if (family_id or filename) \
            else content_key(sha256_hex, suffix)
        storage_key = _unique_key(self, base, sha256_hex)
        ct = content_type or mimetypes.guess_type(storage_key)[0] or "application/octet-stream"
        src.seek(0)
        self._client.put_object(self.bucket, storage_key, src,
                                length=size, content_type=ct)
        return storage_key

    def delete(self, storage_key: str) -> None:
        try:
            self._client.remove_object(self.bucket, storage_key)
        except Exception as exc:
            logger.warning("删除对象失败 %s：%s", storage_key, exc)

    def url(self, storage_key: str, expires: int = 0) -> str | None:
        """预签名 GET 地址（临时、带签名，等价于契约要求的媒体鉴权）。"""
        from datetime import timedelta
        from urllib.parse import urlparse, urlunparse

        seconds = max(60, int(expires or settings.media_url_expires or 600))
        try:
            signed = self._presign.presigned_get_object(
                self.bucket, storage_key, expires=timedelta(seconds=seconds))
        except Exception as exc:
            logger.warning("生成预签名 URL 失败 %s：%s", storage_key, exc)
            return None
        # presign 客户端用纯 host:port 签名（SigV4 把 Host 纳入签名），
        # 生成的路径是 /bucket/key。若 public_url 带路径前缀（如 /minio，
        # nginx 反代前缀），需把前缀拼到路径前面。
        if self.public_url and self.public_url != self._internal_base:
            pub = urlparse(self.public_url)
            sp = urlparse(signed)
            prefix = pub.path.rstrip('/')
            path = prefix + sp.path if prefix else sp.path
            signed = urlunparse((pub.scheme, pub.netloc, path,
                                 sp.params, sp.query, sp.fragment))
        return signed

    def open_stream(self, storage_key: str, start: int | None = None,
                    end: int | None = None) -> Iterator[bytes] | None:
        """服务端代理下载：对象不存在返回 None（路由层转 404）。

        带 start/end 时走 MinIO 的区间读（offset/length），音视频拖动播放要用它；
        区间起点超出对象长度时 MinIO 直接报错，同样归为 None 由上层回 404/416。
        """
        try:
            if start is None:
                resp = self._client.get_object(self.bucket, storage_key)
            else:
                length = None if end is None else max(0, end - start + 1)
                resp = self._client.get_object(self.bucket, storage_key,
                                               offset=int(start), length=length)
        except Exception as exc:
            logger.warning("读取对象失败 %s（%s-%s）：%s", storage_key, start, end, exc)
            return None
        return self._iter_object(resp)

    def size(self, storage_key: str) -> int | None:
        try:
            return int(self._client.stat_object(self.bucket, storage_key).size)
        except Exception as exc:
            logger.warning("读取对象长度失败 %s：%s", storage_key, exc)
            return None

    @staticmethod
    def _iter_object(resp) -> Iterator[bytes]:
        try:
            for chunk in resp.stream(64 * 1024):
                yield chunk
        finally:
            resp.close()
            resp.release_conn()


_store: MediaStore | None = None


def get_store() -> MediaStore:
    global _store
    if _store is None:
        if settings.media_backend == "minio":
            try:
                _store = MinioMediaStore(
                    endpoint=settings.minio_endpoint,
                    access_key=settings.minio_access_key,
                    secret_key=settings.minio_secret_key,
                    bucket=settings.minio_bucket,
                    secure=settings.minio_secure,
                    region=settings.minio_region,
                    public_url=settings.minio_public_url,
                )
            except Exception as exc:
                if not settings.allow_fallback:
                    raise
                # 本地开发常见：没装 minio 依赖 / 没起 MinIO 服务 → 降级本地磁盘
                logger.warning("对象存储不可用（%s），降级到本地磁盘：%s", exc, settings.media_dir)
                _store = LocalMediaStore(settings.media_dir)
        else:
            _store = LocalMediaStore(settings.media_dir)
    return _store


def reset_store_for_tests(base_dir: Path) -> None:
    """测试注入：重建本地存储指向临时目录（也可传 None 让配置在下次调用时重新生效）。"""
    global _store
    _store = LocalMediaStore(base_dir) if base_dir else None
    if base_dir and _store and _store.base_dir.exists():
        shutil.rmtree(_store.base_dir, ignore_errors=True)
        _store.base_dir.mkdir(parents=True, exist_ok=True)
