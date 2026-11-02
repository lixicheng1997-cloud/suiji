"""OutputGuard 校验（diary.js §8.4 移植）。"""
import json

from app.domain.output_guard import (
    BANNED,
    build_prompt,
    check_citations,
    check_fact_whitelist,
    scan_banned,
)


def test_scan_banned():
    paras = [{"text": "宝宝发育一切正常，非常棒"}, {"text": "今天吃了 120ml"}]
    hits = scan_banned(paras)
    assert "正常" in hits


def test_scan_clean():
    paras = [{"text": "这段时间共记录 4 条成长瞬间"}]
    assert scan_banned(paras) == []


def test_fact_whitelist():
    facts = [{"type": "CARE_STAT", "total": 4, "feeding": {"count": 2, "avg": 105}}]
    ok = [{"text": "共记录 4 条，喂养 2 次、平均约 105ml"}]
    assert check_fact_whitelist(ok, facts) == []
    bad = [{"text": "体重达到 8.8kg"}]
    assert check_fact_whitelist(bad, facts) == ["8.8"]


def test_citations():
    assert check_citations([{"text": "a", "src": ["x"]}]) is True
    assert check_citations([{"text": "a", "src": []}]) is False


def test_banned_contains_medical_terms():
    for w in ("发育迟缓", "建议就医", "赢在起跑线"):
        assert w in BANNED


def test_build_prompt_shape():
    msgs = build_prompt([{"type": "CARE_STAT"}], {"start": "2026-01-01", "end": "2026-01-07"})
    assert len(msgs) == 2 and msgs[0]["role"] == "system"
    payload = json.loads(msgs[1]["content"])
    assert payload["range"]["start"] == "2026-01-01"
