"""Reply text for the group assistant and the program-side gates on it.

Only two kinds of replies exist, answers and recommendations. The model never
writes reply prose about a paper: each line quotes the document's own published
conclusion, and every link is generated from the index.
"""

from __future__ import annotations

import math
import re
from typing import Any, Callable

from .constants import ANSWER_MAX_ITEMS, IM_WORD_LIMIT, ROADMAP_PER_ANSWER

URL = re.compile(r"https?://\S+")
CJK_CHAR = re.compile(r"[\u3400-\u9fff]")
ASCII_WORD = re.compile(r"[A-Za-z0-9]+")
SENTENCE_END = re.compile(r"(?<=[。！？!?；;])\s*|\n+")

MARKERS = {"item": "📄", "radar": "📡", "idea": "💡", "roadmap": "🗺"}

NO_MATCH_TEXT = "日报库里没有直接相关的。"
NO_MATCH_UNREFINED_TEXT = "日报库里没有直接相关的，这次没能细查。"
ANSWER_HEADER = "日报库里相关的："
LOW_CONFIDENCE_HEADER = "日报库里相关度较低的有："
FOOTER = "觉得有用点 👍，不相关点 👎"
UNREFINED_NOTE = "（没能细查）"

# Intl.Segmenter counts a Chinese word as roughly 1.6 characters; URLs are not
# part of what a person reads, so they are left out of the budget.
CJK_CHARS_PER_WORD = 1.6


def first_sentence(text: str, limit: int = 60) -> str:
    for sentence in SENTENCE_END.split(text or ""):
        cleaned = sentence.strip()
        if cleaned:
            return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"
    return ""


def count_words(text: str) -> int:
    visible = URL.sub("", text)
    return math.ceil(len(CJK_CHAR.findall(visible)) / CJK_CHARS_PER_WORD) + len(ASCII_WORD.findall(visible))


def within_limit(text: str, limit: int = IM_WORD_LIMIT) -> bool:
    return count_words(text) <= limit


def select_documents(hits: list[dict[str, Any]], limit: int = ANSWER_MAX_ITEMS) -> list[dict[str, Any]]:
    """Keep the best hits, with at most one roadmap pointer."""

    selected: list[dict[str, Any]] = []
    roadmaps = 0
    for hit in hits:
        doc = hit["doc"] if "doc" in hit else hit
        if doc["kind"] == "roadmap":
            if roadmaps >= ROADMAP_PER_ANSWER:
                continue
            roadmaps += 1
        selected.append(doc)
        if len(selected) >= limit:
            break
    return selected


def _date_label(doc: dict[str, Any]) -> str:
    date = doc.get("issue_date") or ""
    if doc["kind"] == "idea":
        return f"{doc.get('status') or 'seed'}" + (f"，{date} 起" if date else "")
    return date


def _line(doc: dict[str, Any], sentence_limit: int = 60) -> str:
    marker = MARKERS.get(doc["kind"], "📄")
    date = _date_label(doc)
    date_part = f"（{date}）：" if date else ("：" if doc.get("summary") else "")
    title = doc["title"]
    sentence = first_sentence(doc.get("summary") or "", sentence_limit) if doc["kind"] != "roadmap" else ""
    if doc["kind"] == "roadmap":
        return f"• {marker} 专题脉络：**{title}** [查看详情]({doc['url']})"
    if doc["kind"] == "radar":
        return f"• {marker} 雷达题录（日报未展开）：**{title}**{date_part} [查看详情]({doc['url']})"
    return f"• {marker} **{title}**{date_part}{sentence} [查看详情]({doc['url']})"


def _answer_text(docs: list[dict[str, Any]], header: str, sentence_limit: int = 60, note: str = "") -> str:
    lines = [header + note] + [_line(doc, sentence_limit) for doc in docs] + [FOOTER]
    return "\n".join(lines)


def _fit(build: Callable[[int], str]) -> str | None:
    """Shrink a reply until it fits the IM word limit; give up only if nothing fits."""

    for sentence_limit in (60, 40, 24, 12, 0):
        text = build(sentence_limit)
        if within_limit(text):
            return text
    return None


def compose_answer(
    hits: list[dict[str, Any]],
    *,
    refined: bool = False,
    unrefined: bool = False,
) -> str | None:
    """Draft an answer from retrieval hits.

    ``unrefined`` marks the fallback sent when a refinement task never came back.
    """

    docs = select_documents(hits)
    if not docs:
        return NO_MATCH_UNREFINED_TEXT if unrefined else NO_MATCH_TEXT
    header = ANSWER_HEADER if refined else LOW_CONFIDENCE_HEADER
    note = UNREFINED_NOTE if unrefined else ""
    while docs:
        text = _fit(lambda limit: _answer_text(docs, header, limit, note))
        if text is not None:
            return text
        docs = docs[:-1]
    return NO_MATCH_UNREFINED_TEXT if unrefined else NO_MATCH_TEXT


def compose_recommendation(doc: dict[str, Any]) -> str:
    source = "idea 库里有一条相关的" if doc["kind"] == "idea" else "日报里有一篇相关的"
    date = doc.get("issue_date") or ""
    date_part = f"（{date}）" if date else ""

    def build(limit: int) -> str:
        sentence = first_sentence(doc.get("summary") or "", limit)
        detail = f"：{sentence}" if sentence else ""
        return f"这个方向{source}：**{doc['title']}**{date_part}{detail} [查看详情]({doc['url']})"

    return _fit(build) or f"这个方向{source} [查看详情]({doc['url']})"
