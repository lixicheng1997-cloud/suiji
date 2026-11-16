"""首页天气：按客户端公网 IP 定位城市，再取当日天气。

隐私口径：本服务**不申请、不采集设备 GPS 定位**，只按请求 IP 粗判到城市级；
IP 不入库、不落业务表，仅在本次请求内用于查询天气。

数据源（均免 key、公开可用，失败即降级为「无天气」，不阻断首页）：
  1. 定位：ip-api.com（IPv4 公网 IP → 城市名 / 经纬度，45 次/分钟匿名限额）；
  2. 天气：wttr.in（城市名或经纬度 → 当前天气中文描述 + 温度，format=j1）。

结果按城市（经纬度四舍五入到 0.1°）在进程内存缓存 30 分钟，IP→城市的定位结果同样缓存 30 分钟——
两道缓存合起来才真正做到「进首页不必每次都打外部接口」：只缓存天气而每次重新定位，
等于把 ip-api 那一跳留在关键路径上。
外部接口不可用/超时/格式不符时返回 None，由端点回空对象，前端静默隐藏天气行。
"""
import logging
import re
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 6.0
_CACHE_TTL = 1800.0  # 30 分钟
_cache: dict[str, tuple[float, dict]] = {}
# IP → 定位结果。_cache 按城市存，可它的 key 要先定位才拿得到，所以定位本身必须单独存：
# 否则下面这道缓存永远命不中，每次进首页都要多付一次 ip-api 往返（实测 0.4~1.4s）。
_loc_cache: dict[str, tuple[float, dict]] = {}
_LOC_CACHE_MAX = 512    # key 是公网 IP，必须设上限，不然表会跟着访客数一直长

# 外部接口返回的天气中文/英文描述词 → 首页展示用的短文案（兼容常见阴晴雨雪）
_COND_MAP = {
    "sunny": "晴", "clear": "晴", "partly cloudy": "多云", "cloudy": "阴",
    "overcast": "阴", "mist": "薄雾", "fog": "雾", "haze": "霾", "smoke": "霾",
    "smoky haze": "霾", "smoky fog": "霾", "dust": "沙尘", "sand": "沙尘",
    "patchy rain possible": "有雨", "patchy light rain": "小雨",
    "light rain": "小雨", "moderate rain": "中雨", "heavy rain": "大雨",
    "rain": "雨", "thundery outbreaks possible": "雷阵雨", "thunderstorm": "雷阵雨",
    "patchy snow possible": "有雪", "light snow": "小雪", "moderate snow": "中雪",
    "heavy snow": "大雪", "snow": "雪", "sleet": "雨夹雪", "freezing rain": "冻雨",
    "blizzard": "暴雪", "ice pellets": "冰粒",
}


def _cache_key(lat: float, lon: float) -> str:
    return f"{round(lat, 1)},{round(lon, 1)}"


def _condition_text(code: str) -> str:
    """wttr.in 天气描述（可能中英混杂）→ 中文短文案；认不出则原样截取前 6 字。"""
    raw = re.sub(r"\s+", " ", str(code or "").strip().lower())
    if not raw:
        return ""
    if raw in _COND_MAP:
        return _COND_MAP[raw]
    # 复合描述（如 "light rain, mist"）：取第一段命中的词
    for part in raw.split(","):
        part = part.strip()
        if part in _COND_MAP:
            return _COND_MAP[part]
    for k, v in _COND_MAP.items():
        if k in raw:
            return v
    # 未收录的罕见词：不把英文原文印到首页，统一落「多云」兜底
    return "多云"


def _is_private_ip(ip: str) -> bool:
    """是否为非公网地址（内网/回环/链路本地）：这类地址 ip-api 无法定位。"""
    if not ip:
        return True
    s = ip.strip()
    if s in ("unknown", "localhost", "::1", "127.0.0.1", "0.0.0.0"):
        return True
    if s.startswith("fc") or s.startswith("fd") or s.startswith("fe80"):  # IPv6 私有/链路本地
        return True
    parts = s.split(".")
    if len(parts) != 4:
        return False
    try:
        a, b = int(parts[0]), int(parts[1])
    except ValueError:
        return True
    return (a == 10 or a == 127 or (a == 172 and 16 <= b <= 31)
            or (a == 192 and b == 168) or (a == 169 and b == 254) or a == 0)


def _ip_locate(ip: str) -> Optional[dict]:
    """公网 IP → {city, lat, lon}；非公网/定位失败返回 None。"""
    if _is_private_ip(ip):
        return None
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.get(
                "http://ip-api.com/json/" + ip,
                params={"fields": "status,city,lat,lon,message"},
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") != "success":
            return None
        lat, lon = data.get("lat"), data.get("lon")
        if lat is None or lon is None:
            return None
        return {"city": str(data.get("city") or "").strip(), "lat": float(lat), "lon": float(lon)}
    except Exception as exc:  # 网络/解析异常：静默降级
        logger.warning("IP 定位失败：%s", type(exc).__name__)
        return None


def _egress_locate() -> Optional[dict]:
    """客户端 IP 为内网（本地 Docker 开发等）时，用服务端出口公网 IP 兜底定位一次。"""
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.get(
                "http://ip-api.com/json/",
                params={"fields": "status,city,lat,lon,message"},
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") != "success":
            return None
        lat, lon = data.get("lat"), data.get("lon")
        if lat is None or lon is None:
            return None
        return {"city": str(data.get("city") or "").strip(), "lat": float(lat), "lon": float(lon)}
    except Exception as exc:
        logger.warning("出口 IP 兜底定位失败：%s", type(exc).__name__)
        return None


def _fetch_weather(loc: dict) -> Optional[dict]:
    """定位结果 → {text, temp, city}；优先城市名，失败回退经纬度。"""
    queries = []
    if loc.get("city"):
        queries.append(loc["city"])
    queries.append(f"{loc['lat']},{loc['lon']}")
    last_err: Optional[Exception] = None
    for q in queries:
        try:
            with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
                # 查询段作为 path 拼在域名后；中文城市名由 httpx 按 URL 规则编码
                resp = client.get(
                    httpx.URL("https://wttr.in/" + q).copy_with(params={"format": "j1", "lang": "zh"}),
                )
                resp.raise_for_status()
                data = resp.json()
            cur = (data.get("current_condition") or [{}])[0]
            temp = cur.get("temp_C")
            # 中文 lang=zh 时取 lang_zh，缺省回退 weatherDesc
            desc = ""
            lang_zh = cur.get("lang_zh")
            if isinstance(lang_zh, list) and lang_zh:
                desc = str(lang_zh[0].get("value") or "")
            if not desc:
                desc = str((cur.get("weatherDesc") or [{}])[0].get("value") or "")
            if temp is None and not desc:
                continue
            return {
                "text": _condition_text(desc),
                "temp": int(temp) if str(temp).lstrip("-").isdigit() else None,
                "city": loc.get("city") or "",
            }
        except Exception as exc:  # noqa: PERF203 单接口失败换下一种查询
            last_err = exc
            continue
    if last_err:
        logger.warning("天气获取失败：%s", type(last_err).__name__)
    return None


def _locate_cached(ip: str) -> Optional[dict]:
    """IP → 定位结果，命中直接复用，未命中才打外部接口（失败回退出口 IP）。

    只缓存成功结果：定位接口偶发失败不该被钉成半小时「无天气」。
    """
    now = time.time()
    hit = _loc_cache.get(ip)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    loc = _ip_locate(ip) or _egress_locate()
    if not loc:
        return None
    _loc_cache[ip] = (now, loc)
    if len(_loc_cache) > _LOC_CACHE_MAX:
        for k in sorted(_loc_cache, key=lambda x: _loc_cache[x][0])[:_LOC_CACHE_MAX // 4]:
            _loc_cache.pop(k, None)
    return loc


def get_weather(ip: str) -> dict:
    """对外主入口：按客户端 IP 取天气；任何一步失败返回空对象（前端隐藏天气）。

    客户端为内网地址（本地 Docker 开发、局域网调试）时，定位回退到服务端出口公网 IP，
    避免开发环境天气恒为空；生产环境客户端均为公网 IP，走正常按请求方定位。
    """
    loc = _locate_cached(ip)
    if not loc:
        return {}
    key = _cache_key(loc["lat"], loc["lon"])
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]
    weather = _fetch_weather(loc)
    if not weather:
        return {}
    _cache[key] = (time.time(), weather)
    return weather
