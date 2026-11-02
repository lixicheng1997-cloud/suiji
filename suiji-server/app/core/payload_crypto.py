"""敏感接口的请求解密 / 响应加密中间件（纯 ASGI，挂在路由之前）。

工作位置：命中 ENCRYPTED_PATHS 且带 X-Sj-Enc 头的请求，先还原成明文再交给路由——
业务代码拿到的就是普通 JSON，完全无感知；响应沿同一条会话密钥加密回传。

响应也必须加密：登录 / 刷新接口下发的正是 JWT 三件套，只加密请求不加密响应，
等于把令牌明文送回链路上（攻击者不需要知道密码，抓响应就能接管会话）。

用纯 ASGI 而不是 @app.middleware("http")：后者要把 body 换成明文后塞回 Request，
得依赖 Starlette 内部字段（_CachedRequest 的 receive 可否替换），不同版本行为不一致；
ASGI 层直接换掉 receive 是协议内的正规做法，版本无关。
"""
import json
import logging

from .config import settings
from .crypto import ENC, HEADER, SCHEMA_V, crypto, envelope, parse_header

logger = logging.getLogger(__name__)

# 需要加密传输的敏感接口（完整路径，含 /api/v1 前缀）。
# 选择标准是「泄露即等同于账号被接管 / 隐私整体外泄」：
#   auth/*        口令与令牌三件套
#   family/join   邀请码（拿到就能进家庭）
#   family/invite 生成的邀请码（响应里带回明文 code）
#   export/data   一次性导出全部家庭数据
# 照片/视频等大文件刻意不加密：几百 MB 在 JS 里做对称加密会卡死主线程，
# 它们走的是独立的 media 受限令牌，且本身不是结构化敏感数据。
ENCRYPTED_PATHS = frozenset({
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/password",
    "/api/v1/auth/deactivate",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/family/join",
    "/api/v1/family/invite",
    "/api/v1/export/data",
})


def _get_header(scope, name: bytes) -> str:
    for k, v in scope.get("headers") or []:
        if k.lower() == name:
            try:
                return v.decode("latin-1")
            except UnicodeDecodeError:
                return ""
    return ""


def _find(headers, name: bytes) -> bytes:
    for k, v in headers:
        if k.lower() == name:
            return v
    return b""


async def _read_body(receive, limit: int) -> bytes | None:
    """读完请求体；超过 limit 或客户端提前断开返回 None。"""
    chunks: list[bytes] = []
    total = 0
    more = True
    while more:
        msg = await receive()
        if msg["type"] == "http.disconnect":
            return None
        chunk = msg.get("body", b"") or b""
        total += len(chunk)
        if total > limit:
            return None
        chunks.append(chunk)
        more = bool(msg.get("more_body"))
    return b"".join(chunks)


def _cors_headers(scope) -> list:
    """为本中间件直出的明文响应补 CORS 头。

    中间件注册在 CORSMiddleware 之外层（保证加密响应不被内层改动），因此这里的
    错误响应（尤其 409「密钥已更新」）不经过 CORS 处理。不补跨域头的话，浏览器
    会把响应直接拦成 CORS 错误，H5 前端读不到 409、公钥重取重试永远不会触发。
    仅回显白名单内的 Origin，与 CORSMiddleware 行为一致。
    """
    if not settings.cors_origins:
        return []
    origin = _get_header(scope, b"origin")
    if not origin:
        return []
    if "*" in settings.cors_origins:
        return [(b"access-control-allow-origin", b"*")]
    if origin in settings.cors_origins:
        return [(b"access-control-allow-origin", origin.encode("latin-1")),
                (b"vary", b"Origin")]
    return []


async def _json_response(send, status: int, payload: dict, cors: list | None = None) -> None:
    """直接回一个明文 JSON 响应（解密失败时没有可用的会话密钥，只能明文）。

    这些错误文案刻意统一、不区分「MAC 错 / padding 错 / 时间戳错」的细节：
    给出区分等于送一个解密 oracle。
    """
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if cors:
        headers += cors
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": headers,
    })
    await send({"type": "http.response.body", "body": body, "more_body": False})


class PayloadCryptoMiddleware:
    """命中清单的请求：解密入站报文、加密出站响应。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # OPTIONS 是浏览器的 CORS 预检：它不带业务头也不带 body，
        # 若在 required 模式下把它判成「明文请求」返回 400，跨域直接就断了
        if scope.get("type") != "http" or scope.get("method") == "OPTIONS" \
                or scope.get("path") not in ENCRYPTED_PATHS:
            await self.app(scope, receive, send)
            return

        raw_header = _get_header(scope, HEADER.encode("latin-1"))
        if not raw_header:
            # 未加密：按 CRYPTO_MODE 决定放行还是拒绝
            if settings.crypto_mode == "required" and crypto.enabled:
                await _json_response(send, 400, {"detail": "该接口要求加密传输，请升级客户端"}, _cors_headers(scope))
                return
            await self.app(scope, receive, send)
            return

        if not crypto.enabled:
            await _json_response(send, 400, {"detail": "服务端未启用传输加密"}, _cors_headers(scope))
            return

        parsed = parse_header(raw_header)
        if parsed is None:
            await _json_response(send, 400, {"detail": "加密请求头无效"}, _cors_headers(scope))
            return
        kid, ts, iv, wrapped = parsed
        if kid != crypto.kid:
            # 密钥轮换后旧客户端缓存的公钥不再有效：让它重新拉一次公钥即可恢复
            await _json_response(send, 409, {"detail": "密钥已更新，请重试"}, _cors_headers(scope))
            return
        if not crypto.ts_valid(ts):
            await _json_response(send, 400, {"detail": "请求已过期，请校准本机时间后重试"}, _cors_headers(scope))
            return
        cek = crypto.unwrap_cek(wrapped)
        if cek is None or len(iv) != 16:
            await _json_response(send, 400, {"detail": "加密密钥无效"}, _cors_headers(scope))
            return

        path = scope.get("path", "")
        ctx_req = crypto.context(kid, ts, "req", path)
        method = (scope.get("method") or "GET").upper()
        headers = scope.get("headers") or []

        if method in ("GET", "HEAD", "OPTIONS", "DELETE") and \
                not _find(headers, b"content-length") and not _find(headers, b"transfer-encoding"):
            plaintext = b""      # 无请求体：只借这条会话密钥加密响应（如 /export/data）
        else:
            raw = await _read_body(receive, settings.crypto_max_bytes)
            if raw is None:
                await _json_response(send, 413, {"detail": "请求体过大"}, _cors_headers(scope))
                return
            plaintext = b""
            if raw.strip():
                try:
                    env = json.loads(raw.decode("utf-8"))
                    data = env.get("data", "")
                    tag = env.get("tag", "")
                    if env.get("v") != SCHEMA_V or env.get("enc") != ENC or not data:
                        raise ValueError("bad envelope")
                    from .crypto import b64d
                    opened = crypto.open_payload(cek, iv, b64d(data), b64d(tag), ctx_req)
                except Exception:
                    opened = None
                if opened is None:
                    await _json_response(send, 400, {"detail": "加密载荷无效"}, _cors_headers(scope))
                    return
                plaintext = opened

        # 用明文重建请求：路由 / pydantic 看到的就是一个普通的 JSON 请求
        new_headers = [(k, v) for k, v in headers
                       if k.lower() not in (b"content-length", b"content-type")]
        new_headers.append((b"content-type", b"application/json"))
        new_headers.append((b"content-length", str(len(plaintext)).encode("ascii")))
        new_scope = dict(scope)
        new_scope["headers"] = new_headers

        async def new_receive():
            return {"type": "http.request", "body": plaintext, "more_body": False}

        await self.app(new_scope, new_receive, self._seal_send(send, cek, kid, ts, path))

    # ---------- 响应加密 ----------
    @staticmethod
    def _seal_send(send, cek: bytes, kid: str, ts: int, path: str):
        ctx_resp = crypto.context(kid, ts, "resp", path)
        state: dict = {"start": None, "chunks": None}

        async def wrapped(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers") or []
                ctype = _find(headers, b"content-type")
                raw_len = _find(headers, b"content-length")
                # 只加密「已知长度且不大」的 JSON：流式响应（无 content-length）
                # 与超大响应原样透传——客户端按「是不是 envelope」判断是否解密，不会出错。
                if ctype.startswith(b"application/json") and raw_len:
                    try:
                        length = int(raw_len)
                    except ValueError:
                        length = -1
                    if 0 <= length <= settings.crypto_max_bytes:
                        state["start"] = message
                        state["chunks"] = []
                        return
                await send(message)
                return

            if message["type"] == "http.response.body":
                if state["chunks"] is None:
                    await send(message)
                    return
                state["chunks"].append(message.get("body", b"") or b"")
                if message.get("more_body"):
                    return
                raw = b"".join(state["chunks"])
                iv_b64, data_b64, tag_b64 = crypto.seal_payload(cek, raw, ctx_resp)
                out = envelope(iv_b64, data_b64, tag_b64)
                start = state["start"]
                new_headers = [(k, v) for k, v in (start.get("headers") or [])
                               if k.lower() != b"content-length"]
                new_headers.append((b"content-length", str(len(out)).encode("ascii")))
                await send({"type": "http.response.start",
                            "status": start["status"], "headers": new_headers})
                await send({"type": "http.response.body", "body": out, "more_body": False})
                return

            await send(message)

        return wrapped
