from __future__ import annotations

import html
import re
from typing import Any


def _appendix_row(topic_name: str, items: list[dict[str, Any]]) -> str:
    entries = []
    for item in items:
        summary = str(item.get("summary") or "").strip()
        url = html.escape(str(item.get("url") or "#"), quote=True)
        title = html.escape(str(item.get("title") or ""))
        source = html.escape(str(item.get("source_name") or "原始来源"))
        published = html.escape(str(item.get("published_at") or ""))
        score = float(item.get("score") or 0)
        entries.append(
            "<div style='padding:7px 0;border-top:1px solid #deded8'>"
            f"<a href='{url}' style='font-size:13px;line-height:1.35;font-weight:700;color:#222;text-decoration:none'>{title}</a>"
            + (f"<div style='font-size:11px;line-height:1.45;color:#666;margin-top:3px'>{html.escape(summary)}</div>" if summary else "")
            + f"<div style='font-size:10px;color:#888;margin-top:3px'>{published} · {score:.0f}分 · 阅读原文：<a href='{url}' style='color:#002fa7'>{source}</a></div>"
            "</div>"
        )
    return (
        "<tr data-topic-appendix='1'><td class='pad-x' style='padding:0 28px 12px'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f3f4f1;border-left:3px solid #8a8a82'><tr><td style='padding:10px 12px'>"
        f"<div style='font:700 11px Microsoft YaHei,Arial,sans-serif;color:#555;margin-bottom:2px'>{html.escape(topic_name)} · 更多相关进展</div>"
        "<div style='font-size:10px;line-height:1.4;color:#888;margin-bottom:3px'>Top4之外已判定相关的A级原始内容，仅作速览，不参与本期综合判断。</div>"
        + "".join(entries)
        + "</td></tr></table></td></tr>"
    )


def insert_inline_topic_appendices(
    html_text: str,
    topic_list: list[dict[str, Any]],
    appendix: dict[str, list[dict[str, Any]]],
) -> str:
    """Insert each topic's short remainder before the next topic header or Radar."""

    if not appendix:
        return html_text
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_text, "html.parser")
    topics_by_id = {str(topic.get("id")): topic for topic in topic_list}
    topic_anchor_re = re.compile(r"^topic-")

    for topic_id, items in appendix.items():
        if not items:
            continue
        anchor = soup.find("a", id=f"topic-{topic_id}")
        if anchor is None:
            continue
        header_row = anchor.find_parent("tr")
        if header_row is None:
            continue
        target = header_row.find_next_sibling("tr")
        while target is not None:
            if target.find("a", id=topic_anchor_re):
                break
            if "热点雷达" in target.get_text(" ", strip=True):
                break
            target = target.find_next_sibling("tr")
        if target is None:
            continue
        topic_name = str((topics_by_id.get(topic_id) or {}).get("name") or topic_id)
        fragment = BeautifulSoup(_appendix_row(topic_name, items), "html.parser")
        row = fragment.find("tr")
        if row is not None:
            target.insert_before(row)
    return str(soup)


def install_topic_appendix_rendering() -> None:
    """Attach Top4 remainder summaries to their owning topic section."""

    from . import coverage_policy
    from .emailer import EmailService

    if getattr(EmailService, "_topic_appendix_rendering_installed", False):
        return

    original_topic_groups = EmailService._topic_groups
    original_build = EmailService.build

    def topic_groups(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        groups = original_topic_groups(self, data)
        appendix = getattr(self, "_topic_appendix_cache", {}) or {}
        by_id = {str(group.get("id")): group for group in groups}

        for topic in self.config.topic_list():
            topic_id = str(topic.get("id") or "")
            extra = list(appendix.get(topic_id) or [])
            if not extra:
                continue
            group = by_id.get(topic_id)
            if group is None:
                group = {
                    "id": topic_id,
                    "name": topic.get("name") or topic_id,
                    "description": topic.get("description", ""),
                    "items": [],
                    "observations": [],
                    "total_count": 0,
                }
                groups.append(group)
                by_id[topic_id] = group
            group["appendix"] = extra
            group["appendix_count"] = len(extra)
            group["total_count"] = int(group.get("total_count") or 0) + len(extra)

        for group in groups:
            group.setdefault("appendix", [])
            group.setdefault("appendix_count", len(group["appendix"]))

        order = {str(topic.get("id")): index for index, topic in enumerate(self.config.topic_list())}
        groups.sort(key=lambda group: order.get(str(group.get("id")), len(order)))
        return groups

    def build(self, run_id: str, *, status_after: str = "AWAITING_APPROVAL"):
        path = original_build(self, run_id, status_after=status_after)
        appendix = getattr(self, "_topic_appendix_cache", {}) or {}
        if appendix:
            rendered = insert_inline_topic_appendices(
                path.read_text(encoding="utf-8"),
                self.config.topic_list(),
                appendix,
            )
            path.write_text(rendered, encoding="utf-8")
        return path

    # coverage_policy originally injected one combined appendix before the
    # global Radar. Inline topic rendering supersedes that fallback.
    coverage_policy._appendix_html = lambda service, appendix: ""
    EmailService._topic_groups = topic_groups
    EmailService.build = build
    EmailService._topic_appendix_rendering_installed = True
