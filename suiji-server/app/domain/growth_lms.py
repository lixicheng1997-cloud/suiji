"""WHO 0-24 月龄参考表：移植客户端 src/domain/growth.js（锚点插值 + 分段线性百分位）。"""
import json
import math
from functools import lru_cache

from ..core.config import settings


@lru_cache(maxsize=1)
def _load() -> dict:
    path = settings.static_config_dir / "growth_lms.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def standard_version() -> str:
    return _load().get("standard_version", "who-2006-anchor-v1")


def bands_at(metric: str, gender: str, age_m: float) -> list[float]:
    """月龄（可小数）→ 相邻两月锚点线性插值 [P3,P15,P50,P85,P97]。"""
    data = _load()["metrics"]
    rows = (data.get(metric) or data["weight"])["girl" if gender == "girl" else "boy"]
    m = max(0.0, min(24.0, float(age_m)))
    lo = math.floor(m)
    hi = min(24, lo + 1)
    f = m - lo
    a, b = rows[lo], rows[hi]
    return [a[i] + (b[i] - a[i]) * f for i in range(5)]


def percentile_of(metric: str, gender: str, age_m: float, value: float) -> float:
    """实测值 → 百分位（0-100），区间外按相邻锚段斜率外推并夹紧（同 growth.js）。"""
    p3, p15, p50, p85, p97 = bands_at(metric, gender, age_m)
    anchors = [[p3, 3], [p15, 15], [p50, 50], [p85, 85], [p97, 97]]
    if value <= p3:
        slope = (15 - 3) / (p15 - p3)
        return max(0.1, 3 - (p3 - value) * slope)
    if value >= p97:
        slope = (97 - 85) / (p97 - p85)
        return min(99.9, 97 + (value - p97) * slope)
    for i in range(len(anchors) - 1):
        x0, y0 = anchors[i]
        x1, y1 = anchors[i + 1]
        if x0 <= value <= x1:
            return y0 + ((value - x0) / (x1 - x0)) * (y1 - y0)
    return 50.0


# Acklam 逆正态近似（百分位 → z 分数，供 growth_point 留痕）
_A = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
      1.383577518672690e+02, -3.066479806614715e+01, 2.506628277459239e+00]
_B = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989586609057e+02,
      6.680131188771972e+01, -1.328068155043207e+01, 1.0]
_C = [-7.784894002430293e-03, -0.3223964580411365, -2.400758277101886,
      -2.549732539320792, 4.374664141407859, 2.938163982833994]
_D = [7.784695709041462e-03, 0.3224671243101449, 2.445134137142996, 3.754408661907416]
_PL = 0.02425


def z_from_percentile(p: float) -> float:
    q = float(p) / 100.0
    if q <= 0:
        return -4.0
    if q >= 1:
        return 4.0
    if q < _PL:
        r = math.sqrt(-2 * math.log(q))
        return (((((_C[0] * r + _C[1]) * r + _C[2]) * r + _C[3]) * r + _C[4]) * r + _C[5]) / \
               (((((_D[0] * r + _D[1]) * r + _D[2]) * r + _D[3]) * r + 1))
    if q <= 1 - _PL:
        r = q - 0.5
        s = r * r
        return (((((_A[0] * s + _A[1]) * s + _A[2]) * s + _A[3]) * s + _A[4]) * s + _A[5]) * r / \
               (((((_B[0] * s + _B[1]) * s + _B[2]) * s + _B[3]) * s + _B[4]) * s + 1)
    r = math.sqrt(-2 * math.log(1 - q))
    return -(((((  _C[0] * r + _C[1]) * r + _C[2]) * r + _C[3]) * r + _C[4]) * r + _C[5]) / \
           (((((_D[0] * r + _D[1]) * r + _D[2]) * r + _D[3]) * r + 1))
