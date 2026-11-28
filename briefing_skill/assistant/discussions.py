"""Simulated group discussions and the checks on what the assistant says about them.

Each scenario is a short discussion colleagues might have, what a good
assistant does with it, and the terms a good reply must or must not carry.
The same scenarios run offline against the index and live against the group,
so a change in behaviour can be read off the same cases.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pathlib import Path

from ..utils import read_json
from .constants import ASSESS_CANDIDATES
from .replies import URL

SCENARIO_FILE = "eval/assistant-discussions.json"
ACTS = ("none", "answer", "add", "review", "gap")
# What the corpus holds for a discussion: a matching item among the first
# lexical hits, one the corpus holds but the hits miss, or none at all.
COVERAGES = ("reached", "missed", "absent")
COVERAGE_LABELS = {"reached": "库里有，也检得到", "missed": "库里有，但前十名里检不到", "absent": "库里没有"}
# A group reply with its cited items: more than this is a wall of text in a chat.
REPLY_CHAR_LIMIT = 600


def load(root: Path, only: list[str] | None = None) -> list[dict[str, Any]]:
    """Every scenario, or the ones named by ``only``."""

    scenarios = read_json(root / SCENARIO_FILE, {}).get("scenarios", [])
    if only:
        unknown = sorted(set(only) - {scenario["id"] for scenario in scenarios})
        if unknown:
            raise ValueError(f"Unknown scenarios: {', '.join(unknown)}")
        scenarios = [scenario for scenario in scenarios if scenario["id"] in only]
    return scenarios


def shape_problems(scenarios: list[dict[str, Any]]) -> list[str]:
    """What is wrong with a scenario file, in plain words; empty when it is sound."""

    problems = []
    ids = [scenario.get("id") for scenario in scenarios]
    problems += [f"duplicate id: {idea_id}" for idea_id in sorted({i for i in ids if ids.count(i) > 1})]
    for scenario in scenarios:
        name = scenario.get("id", "?")
        missing = [key for key in ("id", "title", "target", "speak", "messages", "expect_any", "avoid") if key not in scenario]
        if missing:
            problems.append(f"{name}: missing {', '.join(missing)}")
            continue
        if scenario["target"] not in ACTS:
            problems.append(f"{name}: unknown target {scenario['target']}")
        if scenario["speak"] not in (True, False, "either"):
            problems.append(f"{name}: speak must be true, false or \"either\"")
        if scenario["speak"] is True and not scenario["expect_any"]:
            problems.append(f"{name}: a speaking scenario needs expect_any")
        if "coverage" in scenario and (scenario["coverage"] not in COVERAGES or not scenario["expect_any"]):
            problems.append(f"{name}: coverage must be one of {', '.join(COVERAGES)} and needs expect_any")
        if not scenario["messages"]:
            problems.append(f"{name}: no messages")
    return problems


def discussion_text(scenario: dict[str, Any]) -> str:
    """What the assistant reads of a discussion: its latest messages, as the engine queries them."""

    return " ".join(line["text"] for line in scenario["messages"][-6:])


def cites_expected(titles: list[str], scenario: dict[str, Any]) -> bool:
    return any(term in title for title in titles for term in scenario["expect_any"])


def coverage_of(index: Any, scenario: dict[str, Any]) -> str:
    """Measure what the corpus holds for a discussion, the way the engine queries it."""

    if not cites_expected([doc["title"] for doc in index.docs], scenario):
        return "absent"
    hits = index.search(discussion_text(scenario), ASSESS_CANDIDATES)
    return "reached" if cites_expected([hit["doc"]["title"] for hit in hits], scenario) else "missed"


def evaluate(scenario: dict[str, Any], replies: list[str], *, site_base_url: str) -> dict[str, Any]:
    """Judge what the assistant said about a scenario, by checks that need no model."""

    text = "\n".join(replies)
    spoke = bool(replies)
    wanted = scenario["speak"]
    if spoke and wanted is False:
        timing = False
    elif not spoke and wanted is True:
        timing = False
    else:
        timing = True
    checks = {
        "speaks-when-it-should": timing,
        "links-come-from-the-site": all(link.startswith(site_base_url) for link in URL.findall(text)),
        "cites-something-expected": cites_expected([text], scenario) if spoke else True,
        "avoids-the-wrong-things": not any(term in text for term in scenario["avoid"]),
        "short-enough": len(text) <= REPLY_CHAR_LIMIT,
    }
    return {"ok": all(checks.values()), "checks": checks, "spoke": spoke}


CHECK_LABELS = {
    "speaks-when-it-should": "该说话时说了，不该说时没说",
    "links-come-from-the-site": "链接都指向日报站点",
    "cites-something-expected": "引用了预期的内容",
    "avoids-the-wrong-things": "没有不该出现的内容",
    "short-enough": "长度合适",
}


def report(results: list[dict[str, Any]], *, session: str, generated_at: float) -> str:
    """A page a person can read and score: every discussion, what was said, and the checks."""

    passed = sum(1 for item in results if item["evaluation"]["ok"])
    how = "替身会话按规则取第一条候选，不判断质量" if session == "stand-in" else "由真实会话执行"
    lines = [
        "# 群助手讨论模拟报告", "",
        f"生成于 {datetime.fromtimestamp(generated_at):%Y-%m-%d %H:%M}。共 {len(results)} 个场景，"
        f"{passed} 个通过自动检查。语义判断{how}。自动检查只能查引用和禁忌，接话是否中肯请人工评分。", "",
    ]
    for item in results:
        verdict = "通过" if item["evaluation"]["ok"] else "未通过"
        where = "，" + COVERAGE_LABELS[item["coverage"]] if item.get("coverage") else ""
        lines += [f"## {item['title']}（{verdict}）", "", f"场景编号：`{item['id']}`，目标形态：`{item['target']}`{where}", "", "讨论：", ""]
        lines += [f"- 同事 {line['from'].upper()}：{line['text']}" for line in item["messages"]]
        lines.append("")
        if item["replies"]:
            when = f"，{item['seconds']} 秒后" if item.get("seconds") is not None else ""
            for index, reply in enumerate(item["replies"], 1):
                lines += [f"助手的回复{when}：" if index == 1 else "助手的回复：", "", *["> " + part for part in reply.split("\n")], ""]
        else:
            lines += ["助手没有回复。", ""]
            if item.get("why_silent"):
                lines += [f"去向记录：{'；'.join(item['why_silent'])}", ""]
        marks = [("✓" if item["evaluation"]["checks"][key] else "✗") + " " + label for key, label in CHECK_LABELS.items()]
        lines += ["检查：" + "　".join(marks), "", "人工评分：____ / 5　　备注：", ""]
    return "\n".join(lines)
