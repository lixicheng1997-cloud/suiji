"""首页天气（公开端点）：按请求 IP 粗判城市返回当日天气，无需登录与设备定位权限。

失败一律返回空对象（{text:'',temp:null,city:''}），不抛错、不阻断首页；
同一 IP 限流防止外部接口被刷量。
"""
from fastapi import APIRouter, Depends, Request

from ..core.rate_limit import client_ip, limit as rate_limit
from ..core.config import settings
from ..services import weather_service

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("")
def current_weather(request: Request,
                   _rl=rate_limit("weather", settings.rl_weather, settings.rl_weather_window)):
    """GET /weather → {text:'晴', temp:26, city:'济南'}；拿不到天气时字段为空。"""
    ip = client_ip(request)
    return weather_service.get_weather(ip)
