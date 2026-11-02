"""OutputGuard：移植客户端 src/domain/diary.js §8.4（禁词/事实白名单/引用完整性/提示词）。"""
import json
import re

BANNED = [
    "正常", "异常", "偏矮", "偏高", "偏轻", "偏重", "发育迟缓", "发育过快",
    "建议就医", "需要治疗", "不健康", "疾病", "患病", "诊断",
    "最棒", "第一名", "天才", "赢在起跑线", "落后",
]
# 注：原禁词「第一」会误杀里程碑清单固有名称（「第一次翻身」「第一次微笑」），收窄为「第一名」


def check_citations(paras: list[dict]) -> bool:
    """段落引用完整性：每段至少 1 条引用。"""
    return all(len(p.get("src") or []) >= 1 for p in paras)


def scan_banned(paras: list[dict]) -> list[str]:
    text = "\n".join(str(p.get("text", "")) for p in paras)
    return [w for w in BANNED if w in text]


def check_fact_whitelist(paras: list[dict], facts: list[dict]) -> list[str]:
    """输出中的数字必须能在事实集合序列化文本中找到。"""
    bag = json.dumps(facts, ensure_ascii=False)
    bad: list[str] = []
    for p in paras:
        for v in re.findall(r"\d+(?:\.\d+)?", str(p.get("text", ""))):
            if v not in bag:
                bad.append(v)
    return bad


def build_prompt(facts: list[dict], rng: dict) -> list[dict]:
    """组装发往模型的消息（只含结构化事实，不含姓名/原图/精确健康明细）。"""
    return [
        {
            "role": "system",
            "content": "你是家庭成长记录助手。基于给定事实写 3-6 段温暖克制的周记叙述："
                       "不得给出任何医学结论或评估（如正常/异常/偏矮/建议就医），"
                       "不得使用事实之外的日期与数字，不得营销化表述。"
                       '输出 JSON：{"paras":[{"text":"…","src":["引用事实编号"]}]}。',
        },
        {"role": "user", "content": json.dumps({"range": rng, "facts": facts}, ensure_ascii=False)},
    ]
