"""事实提取：移植客户端 src/domain/diary.js extractFacts + stats.js feedingAgg。"""
from datetime import datetime, timedelta, timezone

from .dates import day_key, hour_of, parse_dt


def feeding_agg(entries: list[dict], days: int = 7) -> dict:
    """近 n 天瓶喂量聚合（只输出 count/avg，健康明细不出域）。"""
    from_dt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    total = 0.0
    n = 0
    for e in entries:
        if e.get("type") != "feeding":
            continue
        t = parse_dt(e.get("occurred_at", ""))
        if not t or t < from_dt:
            continue
        ml = (e.get("payload") or {}).get("amount")
        if ml:
            total += float(ml)
            n += 1
    return {"count": n, "avg": round(total / n) if n else 0}


def extract_facts(entries: list[dict], milestones: list[dict], measurements: list[dict], rng: dict) -> list[dict]:
    """@param rng {'start':'YYYY-MM-DD','end':'YYYY-MM-DD'}"""
    start, end = rng["start"], rng["end"]

    def in_range(s: str) -> bool:
        dk = day_key(s)
        return bool(dk) and start <= dk <= end

    facts: list[dict] = []

    for m in milestones:
        if m.get("done") and in_range(m.get("achieved_at", "")):
            facts.append({
                "type": "MILESTONE", "name": m.get("name", ""),
                "date": day_key(m.get("achieved_at", "")), "entry_id": m.get("source_entry_id", ""),
            })

    for m in measurements:
        if in_range(m.get("occurred_at", "")):
            p = m.get("percentile")
            facts.append({
                "type": "MEASUREMENT", "metric": m.get("metric", ""), "value": m.get("value"),
                "percentile": round(p) if p is not None else None,
                "date": day_key(m.get("occurred_at", "")), "entry_id": m.get("entry_id", ""),
            })

    photos = [e for e in entries if e.get("type") == "photo" and in_range(e.get("occurred_at", ""))]
    if photos:
        media_count = sum(len((e.get("payload") or {}).get("photos") or []) for e in photos)
        facts.append({"type": "MEDIA", "count": media_count, "days": [day_key(p.get("occurred_at", "")) for p in photos]})

    care = [e for e in entries if in_range(e.get("occurred_at", ""))]

    def n(t: str) -> int:
        return sum(1 for e in care if e.get("type") == t)

    facts.append({
        "type": "CARE_STAT",
        "feeding": feeding_agg(care, 90),
        "sleep_count": n("sleep"),
        "poop_count": n("poop"),
        "temp_count": n("temp"),
        "med_count": n("med"),
        "total": len(care),
    })

    hours = []
    for e in care:
        if e.get("type") in ("feeding", "sleep"):
            h = hour_of(e.get("occurred_at", ""))
            if h.isdigit():
                hours.append(int(h))
    if hours:
        facts.append({
            "type": "ROUTINE",
            "morning": sum(1 for h in hours if h < 10),
            "noon": sum(1 for h in hours if 10 <= h < 16),
            "night": sum(1 for h in hours if h >= 16),
        })
    return facts
