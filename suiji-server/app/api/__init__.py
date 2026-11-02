"""API 路由聚合：全部挂载于 /api/v1（契约基础路径）。"""
from fastapi import APIRouter, Depends

from ..core.deps import require_family
from . import (auth, babies, bootstrap, crypto, data, entries, events, family, files, growth,
               journals, media, milestones, notifications, servers, settings, vaccines)

api_router = APIRouter()

# 家庭门控：除 auth（注册/登录/令牌，无账号上下文）与 family（创建/加入，正是关联入口）
# 之外，其余业务路由统一前置 require_family——未关联家庭的账号一律 409 need_family。
# bootstrap 有意放行：引导页要靠它拿到「当前无家庭」的状态并为建家/加入后的跳转灌缓存。
api_router.include_router(auth.router)
api_router.include_router(bootstrap.router)
api_router.include_router(family.router)
# servers 是登录前就要读的公开配置（客户端选服务器地址用），同样无账号/家庭上下文
api_router.include_router(servers.router)
# crypto 只下发 RSA 公钥（公开材料）：客户端登录前先取它，才能加密第一个请求
api_router.include_router(crypto.router)
# 注意：files 的下载端点支持 ?token=（<img src> 无法带 Header），它的家庭门控在
# app/api/files.py 内部逐个端点施加，不能走 router 级依赖（会先被 Bearer 解析挡成 401）。
api_router.include_router(files.router)
# media 同理：契约要求无/非法 token 一律 403，门控写在 endpoint 内部。
api_router.include_router(media.router)
for router in (babies.router, entries.router, vaccines.router,
               milestones.router, settings.router, journals.router, data.router, growth.router,
               events.router, notifications.router):
    api_router.include_router(router, dependencies=[Depends(require_family)])

__all__ = ["api_router"]
