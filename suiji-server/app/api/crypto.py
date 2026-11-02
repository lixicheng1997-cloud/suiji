"""公开端点：下发传输加密用的 RSA 公钥（契约 §2.0 传输加密）。

公钥本身不含秘密，无需鉴权、也无需家庭上下文——客户端在登录前就要拿到它，
否则第一个请求（登录）就发不出去。
"""
from fastapi import APIRouter, HTTPException

from ..core.crypto import crypto

router = APIRouter(prefix="/crypto", tags=["crypto"])


@router.get("/public-key")
def public_key():
    """客户端据此加密会话密钥；kid 用于标识密钥版本（轮换后旧缓存失效）。

    返回内容只含公钥材料，泄露无风险——真正的秘密是服务端私钥，永不下发。
    """
    info = crypto.info()
    if not info:
        raise HTTPException(status_code=404, detail="服务端未启用传输加密")
    return info
