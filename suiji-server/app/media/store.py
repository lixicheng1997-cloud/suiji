"""MediaStore 抽象 + 本地磁盘 / MinIO 对象存储两种实现（契约 §7）。

- LocalMediaStore：单机开发默认实现，文件落 media_dir。
- MinioMediaStore：docker-compose 部署实现，文件入 MinIO 桶，下载走预签名 URL 或服务端代理。

两种后端共用同一套对象路径规则：`{family_id}/{YYYY-MM-DD}/{文件名}`（按家庭隔离、按天归档、
文件名可读）；同家庭同内容（sha256）在业务层复用同一对象，同名不同内容自动追加 sha 短码，
保证一个路径只对应一份字节。旧的 sha 寻址 key（`sha[:2]/sha.ext`）仍可正常读删，平滑兼容。
"""
import base64
import hashlib
import hmac
import json
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
from urllib.parse import urlparse

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


def _category_of(content_type: str) -> str:
    """按 MIME 推断一级分类目录：images / videos / audio / docs / files。"""
    ct = (content_type or "").lower()
    if ct.startswith("image/"):
        return "images"
    if ct.startswith("video/"):
        return "videos"
    if ct.startswith("audio/"):
        return "audio"
    if ct.startswith("text/") or ct in ("application/pdf",):
        return "docs"
    return "files"


def object_key(family_id: str, filename: str = "", suffix: str = "", sha256_hex: str = "",
               when: datetime | None = None, content_type: str = "", baby_id: str = "",
               user_id: str = "") -> str:
    """对象路径：{family_id}/{baby_id}/{user_id}/{category}/{YYYY-MM-DD}/{文件名}。

    - family_id：家庭隔离（必须）
    - baby_id：按宝宝分目录，多宝宝家庭下文件天然分开；无 baby_id 落 common/
    - user_id：按上传人分目录，便于后续统计「谁拍的」；无 user_id 落 common/
    - category：images/videos/audio/docs/files，按 MIME 自动分
    - date：归档日期，按天聚合
    """
    family = _FAMILY_RE.sub("_", (family_id or "").strip()) or "unknown"
    baby = _FAMILY_RE.sub("_", (baby_id or "").strip()) or "common"
    user = _FAMILY_RE.sub("_", (user_id or "").strip()) or "common"
    cat = _category_of(content_type)
    return f"{family}/{baby}/{user}/{cat}/{day_dir(when)}/{_safe_filename(filename, suffix, sha256_hex)}"


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
             family_id: str = "", filename: str = "", baby_id: str = "", user_id: str = "") -> str:
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

    def presigned_put(self, storage_key: str, content_type: str = "",
                      expires: int = 0) -> str | None:
        """签发短时 PUT 预签名直传地址；不支持（local 磁盘）返回 None，调用方回退 multipart。"""
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
                    content_type: str = "", family_id: str = "", filename: str = "",
                    baby_id: str = "", user_id: str = "") -> str:
        """流式落存储：src 为可读二进制流（会被 seek(0)）。

        默认实现读全量到内存，子类可覆写成真正的流式写入，避免大文件吃内存。
        """
        src.seek(0)
        return self.save(src.read(), sha256_hex, suffix, content_type, family_id, filename,
                         baby_id, user_id)


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
             family_id: str = "", filename: str = "", baby_id: str = "", user_id: str = "") -> str:
        storage_key = _unique_key(self,
            self._new_key(sha256_hex, suffix, family_id, filename, content_type, baby_id, user_id),
            sha256_hex)
        dest = self._resolve(storage_key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            with open(dest, "wb") as f:
                f.write(data)
        return storage_key

    def save_stream(self, src, size: int, sha256_hex: str, suffix: str = "",
                    content_type: str = "", family_id: str = "", filename: str = "",
                    baby_id: str = "", user_id: str = "") -> str:
        storage_key = _unique_key(self,
            self._new_key(sha256_hex, suffix, family_id, filename, content_type, baby_id, user_id),
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
    def _new_key(sha256_hex: str, suffix: str, family_id: str, filename: str,
                 content_type: str = "", baby_id: str = "", user_id: str = "") -> str:
        if not family_id and not filename:
            return content_key(sha256_hex, suffix)
        return object_key(family_id, filename, suffix, sha256_hex,
                          content_type=content_type, baby_id=baby_id, user_id=user_id)

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
             family_id: str = "", filename: str = "", baby_id: str = "", user_id: str = "") -> str:
        return self.save_stream(BytesIO(data), len(data), sha256_hex, suffix, content_type,
                                family_id, filename, baby_id, user_id)

    def path(self, storage_key: str) -> Path | None:
        return None  # 对象无本地路径，下载走 url() / open_stream()

    def exists(self, storage_key: str) -> bool:
        try:
            self._client.stat_object(self.bucket, storage_key)
            return True
        except Exception:
            return False

    def save_stream(self, src, size: int, sha256_hex: str, suffix: str = "",
                    content_type: str = "", family_id: str = "", filename: str = "",
                    baby_id: str = "", user_id: str = "") -> str:
        """流式直传对象存储：不把整份文件读进内存。"""
        self._ensure_bucket()
        base = object_key(family_id, filename, suffix, sha256_hex,
                          content_type=content_type, baby_id=baby_id, user_id=user_id) \
            if (family_id or filename) else content_key(sha256_hex, suffix)
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

        seconds = max(60, int(expires or settings.media_url_expires or 600))
        try:
            signed = self._presign.presigned_get_object(
                self.bucket, storage_key, expires=timedelta(seconds=seconds))
        except Exception as exc:
            logger.warning("生成预签名 URL 失败 %s：%s", storage_key, exc)
            return None
        return self._public_url(signed)

    def presigned_put(self, storage_key: str, content_type: str = "",
                      expires: int = 0) -> str | None:
        """预签名 PUT 直传地址：客户端直传对象存储，再回调服务端登记台账。

        返回 None 表示当前后端不支持直传（local 磁盘 / 预签名失败），调用方回退 multipart。
        """
        from datetime import timedelta

        seconds = max(60, int(expires or settings.media_url_expires or 600))
        try:
            # minio 7.2.x 的 presigned_put_object 只收 (bucket, key, expires)：
            # 早先多传一个 content_type 会抛 TypeError，被下面的 except 吞掉，
            # 于是所有客户端拿到的都是 direct=false，直传通道整体失效。
            # 类型不在签名里也没关系——登记回源读头嗅探为准（register_direct）。
            signed = self._presign.presigned_put_object(
                self.bucket, storage_key, expires=timedelta(seconds=seconds))
        except Exception as exc:
            logger.warning("生成 PUT 预签名 URL 失败 %s：%s", storage_key, exc)
            return None
        return self._public_url(signed)

    def _public_url(self, signed: str) -> str:
        """把纯 host:port 预签名地址改写成客户端可达的 public_url（含 nginx 路径前缀）。

        presign 客户端用纯 host:port 签名（SigV4 把 Host 纳入签名），生成的路径是
        /bucket/key。若 public_url 带路径前缀（如 /minio，nginx 反代前缀），需把前缀
        拼到路径前面；不带前缀时原样返回。
        """
        from urllib.parse import urlparse, urlunparse

        if self.public_url and self.public_url != self._internal_base:
            pub = urlparse(self.public_url)
            sp = urlparse(signed)
            prefix = pub.path.rstrip('/')
            path = prefix + sp.path if prefix else sp.path
            return urlunparse((pub.scheme, pub.netloc, path,
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


class CosMediaStore(MediaStore):
    """腾讯云 COS（S3 兼容）实现（需要依赖：pip install boto3）。

    与 MinioMediaStore 共用同一套对象路径规则与 ABC 方法集；预签名 GET/PUT 走
    boto3 SigV4，virtual-hosted 桶域名 `{bucket}.cos.{region}.myqcloud.com`。
    """

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str,
                 region: str = "ap-beijing", public_url: str = "") -> None:
        if not access_key or not secret_key:
            raise RuntimeError("MEDIA_BACKEND=cos 需要配置 COS_ACCESS_KEY / COS_SECRET_KEY")
        if not bucket:
            raise RuntimeError("MEDIA_BACKEND=cos 需要配置 COS_BUCKET")
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # 依赖缺失只在切换到 cos 时才报错
            raise RuntimeError("MEDIA_BACKEND=cos 需要安装依赖：pip install boto3") from exc

        self.bucket = bucket
        self.region = region or "ap-beijing"
        self._access_key = access_key
        self._secret_key = secret_key
        endpoint = (endpoint or "https://cos.ap-beijing.myqcloud.com").strip().rstrip("/")
        if not endpoint.startswith(("http://", "https://")):
            endpoint = "https://" + endpoint
        self.endpoint = endpoint
        self.public_url = public_url.rstrip("/") if public_url else ""
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=self.region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(
                signature_version="s3",
                s3={"addressing_style": "virtual"},
                retries={"max_attempts": 2},
            ),
        )
        # 桶在控制台已创建：这里 head_bucket 仅探测可达性，不自动建桶
        self._ensure_bucket(probe=True)

    def _ensure_bucket(self, probe: bool = False) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except Exception as exc:
            msg = f"COS 存储暂不可用（{self.endpoint}:{self.bucket}）：{exc}"
            if probe:
                raise RuntimeError(msg)
            logger.warning("%s，将在下次读写时重试", msg)

    def save(self, data: bytes, sha256_hex: str, suffix: str = "", content_type: str = "",
             family_id: str = "", filename: str = "", baby_id: str = "", user_id: str = "") -> str:
        return self.save_stream(BytesIO(data), len(data), sha256_hex, suffix, content_type,
                                family_id, filename, baby_id, user_id)

    def path(self, storage_key: str) -> Path | None:
        return None  # 对象无本地路径，下载走 url() / open_stream()

    def exists(self, storage_key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except Exception:
            return False

    def save_stream(self, src, size: int, sha256_hex: str, suffix: str = "",
                    content_type: str = "", family_id: str = "", filename: str = "",
                    baby_id: str = "", user_id: str = "") -> str:
        """流式直传 COS：不把整份文件读进内存。"""
        base = object_key(family_id, filename, suffix, sha256_hex,
                          content_type=content_type, baby_id=baby_id, user_id=user_id) \
            if (family_id or filename) else content_key(sha256_hex, suffix)
        storage_key = _unique_key(self, base, sha256_hex)
        ct = content_type or mimetypes.guess_type(storage_key)[0] or "application/octet-stream"
        src.seek(0)
        kwargs: dict = {"Bucket": self.bucket, "Key": storage_key, "Body": src, "ContentType": ct}
        if size and size > 0:
            kwargs["ContentLength"] = size
        self._client.put_object(**kwargs)
        return storage_key

    def delete(self, storage_key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=storage_key)
        except Exception as exc:
            logger.warning("删除对象失败 %s：%s", storage_key, exc)

    def url(self, storage_key: str, expires: int = 0) -> str | None:
        """预签名 GET 地址（临时、带签名，等价于契约要求的媒体鉴权）。"""
        seconds = max(60, int(expires or settings.media_url_expires or 600))
        try:
            signed = self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": storage_key},
                ExpiresIn=seconds,
            )
        except Exception as exc:
            logger.warning("生成预签名 URL 失败 %s：%s", storage_key, exc)
            return None
        return self._public_url(signed)

    def presigned_put(self, storage_key: str, content_type: str = "",
                      expires: int = 0) -> str | None:
        """预签名 PUT 直传地址：客户端直传 COS，再回调服务端登记台账。"""
        seconds = max(60, int(expires or settings.media_url_expires or 600))
        try:
            signed = self._client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": storage_key},
                ExpiresIn=seconds,
            )
        except Exception as exc:
            logger.warning("生成 PUT 预签名 URL 失败 %s：%s", storage_key, exc)
            return None
        return self._public_url(signed)

    def presigned_post(self, storage_key: str, content_type: str = "",
                       max_bytes: int = 0, expires: int = 0) -> dict | None:
        """签发 COS PostObject（POST 表单）直传凭证，供 uni.uploadFile 三端直传。

        返回 `{method:'post', url, fields, storage_key, content_type, expires}`；
        签名走 COS SHA1 policy 流程（与 boto3 SigV4 是两套独立签名）。
        表单字段必须排在 file 之前，由前端 uni.uploadFile 以 name='file' 末尾附加文件。
        """
        seconds = max(60, int(expires or settings.media_url_expires or 600))
        now = int(time.time())
        end = now + seconds
        key_time = f"{now};{end}"
        max_bytes = int(max_bytes or settings.file_max_bytes or MAX_MEDIA_BYTES)

        policy = {
            "expiration": datetime.fromtimestamp(end, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "conditions": [
                {"bucket": self.bucket},
                ["eq", "$key", storage_key],
                ["content-length-range", 0, max_bytes],
                {"q-sign-algorithm": "sha1"},
                {"q-ak": self._access_key},
                {"q-sign-time": key_time},
            ],
        }
        policy_text = json.dumps(policy, separators=(",", ":"), ensure_ascii=False)
        policy_b64 = base64.b64encode(policy_text.encode("utf-8")).decode("utf-8")

        # SignKey = HMAC-SHA1(SecretKey, KeyTime)；StringToSign = SHA1(Policy 文本)；
        # Signature = HMAC-SHA1(SignKey 字符串, StringToSign 字符串)，均取 hex 小写。
        sign_key = hmac.new(self._secret_key.encode("utf-8"), key_time.encode("utf-8"),
                            hashlib.sha1).hexdigest()
        string_to_sign = hashlib.sha1(policy_text.encode("utf-8")).hexdigest()
        signature = hmac.new(sign_key.encode("utf-8"), string_to_sign.encode("utf-8"),
                             hashlib.sha1).hexdigest()

        fields: dict = {
            "key": storage_key,
            "policy": policy_b64,
            "q-sign-algorithm": "sha1",
            "q-ak": self._access_key,
            "q-key-time": key_time,
            "q-signature": signature,
            "success_action_status": "200",
        }
        if content_type:
            fields["Content-Type"] = content_type

        return {
            "method": "post",
            "url": self._post_url(),
            "fields": fields,
            "storage_key": storage_key,
            "content_type": content_type or "application/octet-stream",
            "expires": seconds,
        }

    def _post_url(self) -> str:
        if self.public_url:
            return self.public_url
        return f"https://{self.bucket}.cos.{self.region}.myqcloud.com"

    def open_stream(self, storage_key: str, start: int | None = None,
                    end: int | None = None) -> Iterator[bytes] | None:
        """服务端代理下载：对象不存在返回 None（路由层转 404）；带区间时走 Range 读。"""
        try:
            kwargs: dict = {"Bucket": self.bucket, "Key": storage_key}
            if start is not None:
                kwargs["Range"] = f"bytes={start}-" + (str(end) if end is not None else "")
            resp = self._client.get_object(**kwargs)
        except Exception as exc:
            logger.warning("读取对象失败 %s（%s-%s）：%s", storage_key, start, end, exc)
            return None
        return self._iter_object(resp)

    def size(self, storage_key: str) -> int | None:
        try:
            return int(self._client.head_object(Bucket=self.bucket, Key=storage_key)["ContentLength"])
        except Exception as exc:
            logger.warning("读取对象长度失败 %s：%s", storage_key, exc)
            return None

    def _public_url(self, signed: str) -> str:
        """配置了 public_url（自定义域名/前缀）时改写签名地址，否则原样返回。"""
        from urllib.parse import urlparse, urlunparse

        if not self.public_url:
            return signed
        pub = urlparse(self.public_url)
        sp = urlparse(signed)
        prefix = pub.path.rstrip("/")
        path = prefix + sp.path if prefix else sp.path
        return urlunparse((pub.scheme, pub.netloc, path, sp.params, sp.query, sp.fragment))

    @staticmethod
    def _iter_object(resp) -> Iterator[bytes]:
        body = resp["Body"]
        try:
            for chunk in body.iter_chunks(64 * 1024):
                yield chunk
        finally:
            body.close()


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
        elif settings.media_backend == "cos":
            try:
                _store = CosMediaStore(
                    endpoint=settings.cos_endpoint,
                    access_key=settings.cos_access_key,
                    secret_key=settings.cos_secret_key,
                    bucket=settings.cos_bucket,
                    region=settings.cos_region,
                    public_url=settings.cos_public_url,
                )
            except Exception as exc:
                if not settings.allow_fallback:
                    raise
                logger.warning("COS 不可用（%s），降级到本地磁盘：%s", exc, settings.media_dir)
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
