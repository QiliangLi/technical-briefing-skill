"""Reports the assistant sends its owner privately.

Two kinds leave for the owner: a coverage gap, when the group discusses
something valuable that neither the briefing nor its configured topics cover,
and a notice when the assistant stops speaking on its own. The owner decides
what to do; a report changes nothing by itself.
"""

from __future__ import annotations

from typing import Any


def scope_label(nearest: str, topics: list[dict[str, Any]]) -> str:
    """A topic or direction id as the owner knows it."""

    for topic in topics:
        if topic["id"] == nearest:
            return f"专题「{topic['name']}」"
        for direction in topic["directions"]:
            if direction["id"] == nearest:
                return f"专题「{topic['name']}」下的方向「{direction['name']}」"
    return nearest


def gap_text(report_id: str, body: dict[str, Any], *, created_at: str) -> str:
    """A coverage gap in the terms the owner can act on: nearest scope and terms to add."""

    people = "、".join(body["names"]) or "几位同事"
    when = created_at[:16].replace("T", " ")
    nearest = f"最接近的现有范围：{body['nearest_label']}" if body.get("nearest_label") else "现有专题里没有相近的范围"
    return "\n".join(
        [
            f"群里在讨论一个日报没覆盖的方向（{when}，{len(body['texts'])} 条消息，{people}）",
            f"讨论的要点：「{body['summary']}」",
            nearest,
            f"建议加的检索词：{'、'.join(body['terms'])}" if body["terms"] else "建议加的检索词：（没给出）",
            f"建议归入：{body['placement']}",
            f"原文：python briefing.py assistant report show {report_id}",
        ]
    )


def notice_text(text: str) -> str:
    return f"群助手：{text}"
