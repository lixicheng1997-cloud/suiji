"""事实提取移植校验（diary.js extractFacts / stats.js feedingAgg）。"""
from datetime import datetime, timedelta, timezone

from app.domain.fact_extractor import extract_facts, feeding_agg


def _recent(days_ago: int, hm: str) -> str:
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return d.strftime("%Y-%m-%d") + " " + hm


def test_feeding_agg_count_avg():
    entries = [
        {"type": "feeding", "occurred_at": _recent(1, "08:00"), "payload": {"amount": 120}},
        {"type": "feeding", "occurred_at": _recent(2, "09:00"), "payload": {"amount": 90}},
        {"type": "feeding", "occurred_at": _recent(3, "09:00"), "payload": {"method": "母乳亲喂"}},
        {"type": "sleep", "occurred_at": _recent(1, "13:00"), "payload": {}},
    ]
    agg = feeding_agg(entries, 90)
    assert agg == {"count": 2, "avg": 105}


def test_feeding_agg_window():
    old = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%d 08:00")
    entries = [
        {"type": "feeding", "occurred_at": old, "payload": {"amount": 120}},
        {"type": "feeding", "occurred_at": _recent(0, "08:00"), "payload": {"amount": 60}},
    ]
    assert feeding_agg(entries, 90) == {"count": 1, "avg": 60}


def test_extract_facts_all_types():
    rng = {"start": _recent(7, "00:00")[:10], "end": _recent(0, "00:00")[:10]}
    entries = [
        {"type": "feeding", "occurred_at": _recent(1, "07:12"), "payload": {"amount": 120}},
        {"type": "sleep", "occurred_at": _recent(1, "13:05"), "payload": {}},
        {"type": "poop", "occurred_at": _recent(2, "19:25"), "payload": {}},
        {"type": "photo", "occurred_at": _recent(2, "15:30"), "payload": {"photos": ["a", "b"]}},
        {"type": "feeding", "occurred_at": _recent(30, "06:00"), "payload": {"amount": 90}},  # 区间外
    ]
    milestones = [{"name": "第一次翻身", "done": True, "achieved_at": _recent(2, "16:40"),
                   "source_entry_id": "e_1", "baby_id": "b1"}]
    measurements = [{"metric": "weight", "value": 7.8, "occurred_at": _recent(1, "10:00"),
                     "percentile": 51.2, "entry_id": "e_2", "baby_id": "b1"}]
    facts = extract_facts(entries, milestones, measurements, rng)

    ms = next(f for f in facts if f["type"] == "MILESTONE")
    assert ms["name"] == "第一次翻身" and ms["entry_id"] == "e_1"

    meas = next(f for f in facts if f["type"] == "MEASUREMENT")
    assert meas["percentile"] == 51  # 四舍五入

    media = next(f for f in facts if f["type"] == "MEDIA")
    assert media["count"] == 2

    care = next(f for f in facts if f["type"] == "CARE_STAT")
    assert care["total"] == 4 and care["sleep_count"] == 1 and care["poop_count"] == 1
    assert care["feeding"]["count"] >= 1  # 近 90 天窗口含区间外那条

    routine = next(f for f in facts if f["type"] == "ROUTINE")
    assert routine["morning"] == 1 and routine["noon"] == 1 and routine["night"] == 0
