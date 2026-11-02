"""日期与月龄口径：移植客户端 src/domain/shared/date.js（含矫正月龄）。"""
import calendar
import math
from datetime import date, datetime, timedelta, timezone


def utc_now_iso() -> str:
    """服务端生成时间统一 UTC ISO8601：'YYYY-MM-DDTHH:MM:SSZ'。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_key(s: str) -> str:
    return str(s or "")[:10]


def hour_of(s: str) -> str:
    """'YYYY-MM-DD HH:mm' 或 ISO 串 → 小时 'HH'。"""
    return str(s or "")[11:13]


def parse_dt(s: str) -> datetime | None:
    """兼容 'YYYY-MM-DD HH:mm[:ss]' 与 'YYYY-MM-DDTHH:MM:SS[Z]'。"""
    if not s:
        return None
    t = str(s).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    return None


def _to_date(s: str) -> date | None:
    dt = parse_dt(s)
    return dt.date() if dt else None


def add_months(d: date, n: int) -> date:
    """Date + n 个月（月末夹紧，如 1-31 +1 → 2-28/29）。"""
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def add_months_str(date_str: str, n: int) -> str:
    d = _to_date(date_str)
    if not d:
        return date_str
    return add_months(d, n).isoformat()


def age_months(birth_date: str, at: str, gest_weeks: int = 0) -> float:
    """月龄（小数，用于曲线横轴）；胎龄 <37 按矫正月龄回拨（同 date.js 公式）。"""
    b = _to_date(birth_date)
    t = _to_date(at)
    if not b or not t:
        return 0.0
    months = (t.year - b.year) * 12 + (t.month - b.month)
    months += (t.day - b.day) / 30.4375
    gw = int(gest_weeks or 0)
    if gw and gw < 37:
        months -= (37 - gw) / 4.345
    return months


def age_text(birth_date: str, at: str, gest_weeks: int = 0) -> str:
    """'X 个月 Y 天' / 'Y 天' / '未出生'。"""
    months = age_months(birth_date, at, gest_weeks)
    if months < 0:
        return "未出生"
    m = math.floor(months)
    b = _to_date(birth_date)
    t = _to_date(at)
    if not b or not t:
        return "未出生"
    base = add_months(b, m)
    days = max(0, (t - base).days)
    if m == 0:
        return f"{days} 天"
    return f"{m} 个月" + (f" {days} 天" if days > 0 else "")


def month_day(dk: str) -> str:
    """'YYYY-MM-DD' → 'M 月 D 日'。"""
    parts = str(dk or "")[:10].split("-")
    if len(parts) != 3:
        return str(dk or "")
    return f"{int(parts[1])} 月 {int(parts[2])} 日"


def days_between(a: str, b: str) -> int:
    da, db = _to_date(a), _to_date(b)
    if not da or not db:
        return 0
    return (db - da).days


def today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def date_minus_days(dk: str, n: int) -> str:
    d = _to_date(dk) or datetime.now(timezone.utc).date()
    return (d - timedelta(days=n)).isoformat()
