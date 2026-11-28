"""Reply text for the group assistant and the program-side gates on it.

The model never writes about a paper. It writes the framing, one or two
sentences saying what in the discussion the reply answers. Every title,
number and link below that is the document's own published text, taken from
the index: the reader card's headline and lead, a result, a boundary.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from .constants import ANSWER_MAX_ITEMS, ROADMAP_PER_ANSWER

URL = re.compile(r"https?://\S+")
CJK_CHAR = re.compile(r"[\u3400-\u9fff]")
ASCII_WORD = re.compile(r"[A-Za-z0-9]+")
SENTENCE_END = re.compile(r"(?<=[。！？!?；;])\s*|\n+")

MARKERS = {"item": "📄", "radar": "📡", "idea": "💡", "roadmap": "🗺", "judgement": "🧭"}

NO_MATCH_TEXT = "日报库里没有直接相关的。"
NO_MATCH_UNREFINED_TEXT = "日报库里没有直接相关的，这次没能细查。"
ANSWER_HEADER = "日报库里相关的："
LOW_CONFIDENCE_HEADER = "日报库里相关度较低的有："
FOOTER = "觉得有用点 👍，不相关点 👎"
UNREFINED_NOTE = "（没能细查）"

# What a reply of each kind may take on screen, in characters; links do not
# count. A chat message that runs past this is a wall nobody reads.
CHAR_LIMITS = {"answer": 700, "recommendation": 600, "alert": 900, "report": 1500}
# A reader lead is shown whole up to this many characters, then shortened.
LEAD_LENGTHS = (160, 100, 60, 0)


def first_sentence(text: str, limit: int = 60) -> str:
    for sentence in SENTENCE_END.split(text or ""):
        cleaned = sentence.strip()
        if cleaned:
            return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"
    return ""


def visible_length(text: str) -> int:
    return len(URL.sub("", text))


def within_limit(text: str, kind: str = "answer") -> bool:
    return visible_length(text) <= CHAR_LIMITS[kind]


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


def _headline(doc: dict[str, Any]) -> str:
    return doc.get("headline") or doc["title"]


def _lead(doc: dict[str, Any], limit: int) -> str:
    """The document's published lead, whole or cut at a sentence end."""

    lead = doc.get("lead") or doc.get("summary") or ""
    if doc["kind"] == "judgement":
        lead = first_sentence(lead, 120)
    if len(lead) <= limit:
        return lead
    cut = lead[:limit].rfind("。")
    return lead[: cut + 1] if cut >= limit // 3 else lead[: limit - 1] + "…"


def _line(doc: dict[str, Any], lead_limit: int) -> str:
    """One cited document: headline, date, its own published lead, and a link from the index."""

    marker = MARKERS.get(doc["kind"], "📄")
    date = _date_label(doc)
    date_part = f"（{date}）" if date else ""
    lead = _lead(doc, lead_limit)
    if doc["kind"] == "roadmap":
        return f"• {marker} 专题脉络：**{doc['title']}** [查看详情]({doc['url']})"
    label = "本期判断：" if doc["kind"] == "judgement" else ""
    spoken = f"：{lead}" if lead else ""
    return f"• {marker} {label}**{_headline(doc)}**{date_part}{spoken} [查看详情]({doc['url']})"


def _fit(build: Callable[[int], str], kind: str) -> str | None:
    """Shorten the cited leads until the reply fits; give up only if nothing fits."""

    for lead_limit in LEAD_LENGTHS:
        text = build(lead_limit)
        if within_limit(text, kind):
            return text
    return None


def compose_answer(
    hits: list[dict[str, Any]], *, framing: str = "", refined: bool = False, unrefined: bool = False
) -> str | None:
    """Draft an answer from retrieval hits.

    ``unrefined`` marks the fallback sent when a refinement task never came back.
    """

    docs = select_documents(hits)
    if not docs:
        return NO_MATCH_UNREFINED_TEXT if unrefined else NO_MATCH_TEXT
    header = ANSWER_HEADER if refined else LOW_CONFIDENCE_HEADER
    note = UNREFINED_NOTE if unrefined else ""
    opening = [framing] if framing else []
    while docs:
        text = _fit(lambda limit: "\n".join(opening + [header + note] + [_line(doc, limit) for doc in docs] + [FOOTER]), "answer")
        if text is not None:
            return text
        docs = docs[:-1]
    return NO_MATCH_UNREFINED_TEXT if unrefined else NO_MATCH_TEXT


def compose_add(framing: str, docs: list[dict[str, Any]]) -> str | None:
    """A contribution to a discussion: the framing, then one or two cited documents."""

    kept = list(docs)
    while kept:
        text = _fit(lambda limit: "\n".join([framing] + [_line(doc, limit) for doc in kept]), "recommendation")
        if text is not None:
            return text
        kept = kept[:-1]
    return None


def compose_review(
    framing: str,
    *,
    closest: dict[str, Any] | None,
    supporting: list[dict[str, Any]],
    counter: list[dict[str, Any]],
    missing: str,
) -> str | None:
    """A review of a colleague's idea, line by line: closest idea, support, limits, what is missing.

    Every fact is a cited document's own text; only ``framing`` and ``missing``
    are the session's words.
    """

    def build(limit: int) -> str:
        lines = [framing]
        if closest is not None:
            date = _date_label(closest)
            lines.append(f"最接近的 idea：💡 **{_headline(closest)}**（{date}） [查看详情]({closest['url']})")
        if supporting:
            lines.append("支持它的证据：" + _line(supporting[0], limit)[2:])
        if counter:
            lines.append("要注意的：" + _line(counter[0], limit)[2:])
        elif supporting and supporting[0].get("boundary"):
            lines.append(f"要注意的边界：{first_sentence(supporting[0]['boundary'], 80)}")
        if missing:
            lines.append(f"库里还没找到的：{missing}")
        return "\n".join(lines)

    return _fit(build, "recommendation")


def compose_alert(issue_date: str, picks: list[dict[str, Any]]) -> str | None:
    """A notice that a new issue holds something for this group.

    ``picks`` are ``{"why": str, "doc": document}``; the ``why`` is the
    session's sentence tying the item to the group's own discussion.
    """

    kept = list(picks)
    while kept:
        text = _fit(
            lambda limit: "\n".join(
                [f"新一期日报（{issue_date}）里有 {len(kept)} 条和你们最近的讨论相关："]
                + [f"• {pick['why']}\n  {_line(pick['doc'], limit)[2:]}" for pick in kept]
            ),
            "alert",
        )
        if text is not None:
            return text
        kept = kept[:-1]
    return None
