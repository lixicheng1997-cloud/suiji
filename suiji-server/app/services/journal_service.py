"""AI 成长日记管线（契约 §11）：事实提取→LLM+OutputGuard→模板兜底。"""
import json
import logging
import re

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.deps import AuthContext
from ..domain.dates import date_minus_days, day_key, month_day, today_utc, utc_now_iso
from ..domain.fact_extractor import extract_facts
from ..domain.output_guard import build_prompt, check_citations, check_fact_whitelist, scan_banned
from ..models import AiJournal, Baby, Entry, GrowthPoint, Measurement, MilestoneRecord
from ..domain import growth_lms
from . import notify_service
from .ids import gen_id
from .rows import entry_row, journal_row, measurement_row, milestone_row

logger = logging.getLogger("suiji.journal")

PROMPT_VERSION = "v1"


def _fmt_date(dk: str) -> str:
    return month_day(dk)


def template_diary(facts: list[dict], rng: dict, baby_name: str) -> dict:
    """模板化生成（§8.5 兜底，零成本离线可用；姓名仅本地模板可用）。"""
    paras = []
    name = baby_name or "宝宝"
    ms = [f for f in facts if f["type"] == "MILESTONE"]
    if ms:
        paras.append({
            "text": "这段时间最闪亮的事，是" + name + "完成了"
                    + "、".join("「" + m["name"] + "」" for m in ms)
                    + "——每一个瞬间都值得被记住（"
                    + "、".join(_fmt_date(m["date"]) for m in ms) + "）。",
            "src": [_fmt_date(m["date"]) + " 里程碑 · " + m["name"] for m in ms],
            "entryIds": [m["entry_id"] for m in ms if m.get("entry_id")],
        })
    feed = next((f for f in facts if f["type"] == "CARE_STAT"), None)
    if feed:
        seg = ["这段时间共记录 " + str(feed["total"]) + " 条成长瞬间"]
        if feed["feeding"]["count"]:
            seg.append("喂养 " + str(feed["feeding"]["count"]) + " 次、平均约 " + str(feed["feeding"]["avg"]) + "ml")
        if feed["sleep_count"]:
            seg.append("睡眠 " + str(feed["sleep_count"]) + " 段")
        if feed["poop_count"]:
            seg.append("便便 " + str(feed["poop_count"]) + " 次")
        paras.append({
            "text": "，".join(seg) + "。吃睡节奏由家人一笔笔记下，平稳而踏实。",
            "src": ["区间照护统计 · " + _fmt_date(rng["start"]) + "–" + _fmt_date(rng["end"])],
            "entryIds": [],
        })
    meas = [f for f in facts if f["type"] == "MEASUREMENT"]
    if meas:
        latest = meas[-1]
        metric_label = {"height": "身高", "weight": "体重"}.get(latest["metric"], "头围")
        unit = "kg" if latest["metric"] == "weight" else "cm"
        paras.append({
            "text": "生长曲线上又落了一个点：" + _fmt_date(latest["date"]) + " "
                    + metric_label + " " + str(latest["value"]) + unit
                    + ("，处于 P" + str(latest["percentile"]) + " 参考位" if latest.get("percentile") is not None else "")
                    + "。",
            "src": [_fmt_date(m["date"]) + " 测量 · " + m["metric"] + " " + str(m["value"]) for m in meas],
            "entryIds": [m["entry_id"] for m in meas if m.get("entry_id")],
        })
    media = next((f for f in facts if f["type"] == "MEDIA"), None)
    if media:
        paras.append({
            "text": "镜头也记录下了 " + str(media["count"]) + " 张照片，分布在 " + str(len(media["days"])) + " 个日子里。",
            "src": [_fmt_date(d) + " 照片" for d in media["days"]],
            "entryIds": [],
        })
    if not paras:
        paras.append({
            "text": "这段时间还没有足够的记录。点开右下角的 + ，随手记一句，下次回顾就会更丰富一些。",
            "src": [],
            "entryIds": [],
        })
    return {
        "range": _fmt_date(rng["start"]) + " – " + _fmt_date(rng["end"]) + " · 周记草稿",
        "paras": paras,
        "fact_count": len(facts),
    }


def _parse_llm_paras(content: str) -> list[dict] | None:
    """解析模型输出（容忍 ```json 围栏）。"""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    paras = obj.get("paras") if isinstance(obj, dict) else None
    if not isinstance(paras, list) or not paras:
        return None
    for p in paras:
        if not isinstance(p, dict) or not isinstance(p.get("text"), str) or not p["text"]:
            return None
        if not isinstance(p.get("src"), list):
            p["src"] = []
    return paras


def _call_llm(facts: list[dict], rng: dict) -> list[dict] | None:
    url = settings.llm_api_base.rstrip("/") + "/chat/completions"
    # enable_thinking=false：关闭 qwen3 系列推理模式，长提示下延迟从 30s+ 降到秒级
    payload = {"model": settings.llm_model, "messages": build_prompt(facts, rng), "enable_thinking": False}
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json=payload, headers={"Authorization": "Bearer " + settings.llm_api_key})
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        return _parse_llm_paras(content)
    except Exception as e:  # 网络/格式异常均视为失败，由调用方重生成或兜底
        logger.warning("LLM 调用失败：%s", type(e).__name__)
        return None


def _collect(db: Session, family_id: str, baby: Baby, rng: dict):
    entries = [
        entry_row(e)
        for e in db.query(Entry)
        .filter(Entry.family_id == family_id, Entry.deleted_at.is_(None))
        .all()
        if not e.baby_id or e.baby_id == baby.id
    ]
    milestones = [
        milestone_row(m)
        for m in db.query(MilestoneRecord)
        .filter(MilestoneRecord.family_id == family_id, MilestoneRecord.done.is_(True))
        .all()
        if not m.baby_id or m.baby_id == baby.id
    ]
    measurements = []
    for m in db.query(Measurement).filter(Measurement.family_id == family_id).all():
        if m.baby_id and m.baby_id != baby.id:
            continue
        row = measurement_row(m)
        gp = db.get(GrowthPoint, m.id)
        if gp is not None:
            row["percentile"] = gp.percentile_p
        elif baby.birth_date:
            from ..domain.dates import age_months

            age_m = age_months(baby.birth_date, m.occurred_at, baby.gestational_weeks)
            row["percentile"] = growth_lms.percentile_of(m.metric, baby.gender, age_m, m.value)
        measurements.append(row)
    return extract_facts(entries, milestones, measurements, rng)


def generate(db: Session, auth: AuthContext, body: dict) -> dict:
    baby_id = body.get("baby_id") or ""
    baby = db.get(Baby, baby_id) if baby_id else None
    if baby is None:
        baby = db.query(Baby).filter(Baby.family_id == auth.family_id, Baby.is_active == 1).first()
    if baby is None:
        baby = db.query(Baby).filter(Baby.family_id == auth.family_id).order_by(Baby.created_at).first()
    if baby is None:
        raise HTTPException(status_code=422, detail="请先创建宝宝档案")
    if baby.family_id != auth.family_id:
        raise HTTPException(status_code=403, detail="无权访问该记录")

    end = day_key(body.get("range_end") or "") or today_utc()
    start = day_key(body.get("range_start") or "") or date_minus_days(end, 6)
    rng = {"start": start, "end": end}

    facts = _collect(db, auth.family_id, baby, rng)

    model_version = "template"
    paras = None
    if settings.llm_configured:
        for attempt in range(2):  # 失败重生成 1 次
            candidate = _call_llm(facts, rng)
            if candidate is None:
                logger.warning("日记生成：LLM 输出解析失败（第 %s 次尝试）", attempt + 1)
                continue
            banned = scan_banned(candidate)
            bad = check_fact_whitelist(candidate, facts)
            cite_ok = check_citations(candidate)
            if banned or bad or not cite_ok:
                logger.warning("日记生成：守卫拦截（第 %s 次）banned=%s bad_numbers=%s citations_ok=%s",
                               attempt + 1, banned, bad, cite_ok)
                continue
            # src/entryIds 供客户端「来源溯源」折叠展示；cites 保持契约字段
            paras = [{"text": p["text"], "src": p.get("src", []), "entryIds": [], "cites": []} for p in candidate]
            model_version = settings.llm_model
            break

    if paras is None:
        tpl = template_diary(facts, rng, baby.name)
        paras = [{"text": p["text"], "src": p.get("src", []), "entryIds": p["entryIds"], "cites": p["entryIds"]} for p in tpl["paras"]]

    now = utc_now_iso()
    journal = AiJournal(
        id=gen_id("j"), family_id=auth.family_id, baby_id=baby.id,
        range=f"{_fmt_date(start)} – {_fmt_date(end)} · 周记草稿",
        range_start=start, range_end=end,
        paras=paras, status="draft",
        model_version=model_version, prompt_version=PROMPT_VERSION,
        fact_count=len(facts), created_at=now, updated_at=now,
    )
    db.add(journal)
    db.commit()
    db.refresh(journal)
    notify_service.notify_family(
        db, auth, ntype="journal",
        content=f"{notify_service.actor_name(db, auth)} 生成了成长日记（{journal.range}）")
    db.commit()
    return journal_row(journal)
