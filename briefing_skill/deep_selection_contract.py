from __future__ import annotations

import html
from typing import Any

from .utils import canonicalize_url


APPENDIX_PREFIX = "TOPIC_APPENDIX:"


def appendix_candidate_is_deferred(row: dict[str, Any] | None) -> bool:
    """Return true only for a genuine topic-local Top4 remainder candidate."""

    if not row:
        return False
    return (
        int(row.get("relevant") or 0) == 1
        and int(row.get("fulltext_required") or 0) == 1
        and str(row.get("status") or "") == "DEFERRED_BUDGET"
        and str(row.get("source_level") or "").upper() == "A"
        and not bool(row.get("discovery_only"))
    )


def _candidate_for_url(service, run_id: str, url: str) -> dict[str, Any] | None:
    canonical = canonicalize_url(url)
    if not canonical:
        return None
    return service.db.fetchone(
        """
        SELECT c.relevant,c.fulltext_required,c.status,c.topic_id,
               r.source_level,r.discovery_only,r.canonical_url,r.original_url
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
        WHERE c.run_id=? AND (r.canonical_url=? OR r.original_url=?)
        ORDER BY CASE WHEN c.status='DEFERRED_BUDGET' THEN 0 ELSE 1 END,
                 c.relevance_score DESC
        LIMIT 1
        """,
        (run_id, canonical, canonical),
    )


def _filter_deferred_appendix(service, run_id: str, appendix: dict[str, list[dict[str, Any]]]):
    """Drop relevant-only candidates; an appendix is the tail of the Deep pool only."""

    cleaned: dict[str, list[dict[str, Any]]] = {}
    for topic_id, items in appendix.items():
        kept: list[dict[str, Any]] = []
        for item in items:
            row = _candidate_for_url(service, run_id, str(item.get("url") or ""))
            if not appendix_candidate_is_deferred(row):
                continue
            if str(row.get("topic_id") or "") != str(topic_id):
                continue

            # Release-family aggregation may attach several source links. Keep only
            # members that are independently proven to be deferred Deep candidates.
            links = []
            for link in item.get("links") or []:
                linked = _candidate_for_url(service, run_id, str(link.get("url") or ""))
                if appendix_candidate_is_deferred(linked) and str(linked.get("topic_id") or "") == str(topic_id):
                    links.append(link)
            updated = {**item, "selection_role": "DEFERRED_TOP4"}
            if item.get("links") is not None:
                updated["links"] = links
                updated["family_size"] = max(1, len(links)) if links else 1
            kept.append(updated)
        if kept:
            cleaned[str(topic_id)] = kept
    return cleaned


def render_deferred_appendix_row(topic_name: str, items: list[dict[str, Any]]) -> str:
    """Render a reader-facing Top4 tail without exposing internal relevance scores."""

    entries = []
    for item in items:
        summary = str(item.get("summary") or "").strip()
        url = html.escape(str(item.get("url") or "#"), quote=True)
        title = html.escape(str(item.get("title") or ""))
        source = html.escape(str(item.get("source_name") or "原始来源"))
        published = html.escape(str(item.get("published_at") or ""))
        links = item.get("links") or []
        rendered_links = []
        for index, link in enumerate(links, 1):
            link_url = html.escape(str(link.get("url") or ""), quote=True)
            if not link_url:
                continue
            label = html.escape(str(link.get("label") or f"更新{index}"))
            rendered_links.append(f"<a href='{link_url}' style='color:#002fa7'>{label}</a>")
        source_links = " · ".join(rendered_links) if rendered_links else f"<a href='{url}' style='color:#002fa7'>{source}</a>"
        family_label = (
            f" · {int(item.get('family_size') or 0)}项合并"
            if int(item.get("family_size") or 0) > 1
            else ""
        )
        entries.append(
            "<div style='padding:7px 0;border-top:1px solid #deded8'>"
            f"<a href='{url}' style='font-size:13px;line-height:1.35;font-weight:700;color:#222;text-decoration:none'>{title}</a>"
            + (f"<div style='font-size:11px;line-height:1.45;color:#666;margin-top:3px'>{html.escape(summary)}</div>" if summary else "")
            + f"<div style='font-size:10px;color:#888;margin-top:3px'>{published}{family_label} · 阅读原文：{source_links}</div>"
            "</div>"
        )
    return (
        "<tr data-topic-appendix='1'><td class='pad-x' style='padding:0 28px 12px'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f3f4f1;border-left:3px solid #8a8a82'><tr><td style='padding:10px 12px'>"
        f"<div style='font:700 11px Microsoft YaHei,Arial,sans-serif;color:#555;margin-bottom:2px'>{html.escape(topic_name)} · 其他相关进展</div>"
        "<div style='font-size:10px;line-height:1.4;color:#888;margin-bottom:3px'>以下内容已达到深度候选门槛，但位于本专题前4名之后，仅作速览；不包含仅相关但未达到深度门槛的候选。</div>"
        + "".join(entries)
        + "</td></tr></table></td></tr>"
    )


def _selection_validation(service, run_id: str) -> list[str]:
    """Validate the DB-side invariant used by the reader-facing appendix."""

    policy = dict(service.config.settings.get("efficiency") or {})
    deep_topics = set(policy.get("deep_topics") or [])
    per_topic_max = max(1, int(policy.get("max_fact_candidates_per_topic", 4)))
    failures: list[str] = []

    for topic_id in sorted(deep_topics):
        row = service.db.fetchone(
            """
            SELECT
              SUM(CASE WHEN c.relevant=1 AND c.fulltext_required=1
                        AND r.source_level='A' AND r.discovery_only=0 THEN 1 ELSE 0 END) AS eligible,
              SUM(CASE WHEN c.status='DEFERRED_BUDGET' THEN 1 ELSE 0 END) AS deferred
            FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
            WHERE c.run_id=? AND c.topic_id=?
            """,
            (run_id, topic_id),
        ) or {}
        eligible = int(row.get("eligible") or 0)
        deferred = int(row.get("deferred") or 0)
        if eligible <= per_topic_max and deferred:
            failures.append(
                f"{topic_id}: {deferred} DEFERRED_BUDGET candidates exist although only {eligible} Deep-eligible candidates exist"
            )

    issue = service.db.fetchone("SELECT id FROM issues WHERE run_id=?", (run_id,))
    if not issue:
        return failures
    appendix_rows = service.db.fetchall(
        "SELECT canonical_url,category FROM issue_radar_items WHERE issue_id=? AND category LIKE ?",
        (issue["id"], f"{APPENDIX_PREFIX}%"),
    )
    for item in appendix_rows:
        topic_id = str(item.get("category") or "")[len(APPENDIX_PREFIX):]
        candidate = _candidate_for_url(service, run_id, str(item.get("canonical_url") or ""))
        if not appendix_candidate_is_deferred(candidate):
            failures.append(
                f"{topic_id}: topic appendix contains a candidate that is not DEFERRED_BUDGET Deep tail"
            )
    return failures


def install_deep_selection_contract() -> None:
    """Make topic-local Top4 / appendix semantics a fail-closed product contract."""

    from . import coverage_policy, topic_appendix_render
    from .pipeline import Pipeline
    from .rendering import Renderer

    if getattr(Pipeline, "_deep_selection_contract_installed", False):
        return

    original_collect = coverage_policy.collect_topic_appendix

    def collect_topic_appendix(service, run_id: str, issue_data: dict[str, Any]):
        appendix = original_collect(service, run_id, issue_data)
        return _filter_deferred_appendix(service, run_id, appendix)

    coverage_policy.collect_topic_appendix = collect_topic_appendix
    topic_appendix_render._appendix_row = render_deferred_appendix_row

    original_validate = Renderer.validate

    def validate(self, run_id: str):
        report = original_validate(self, run_id)
        failures = _selection_validation(self, run_id)
        if failures:
            report.setdefault("failures", []).extend(failures)
        else:
            report.setdefault("passes", []).append(
                "Topic appendices contain only genuine DEFERRED_BUDGET Deep-tail candidates"
            )
        return report

    Renderer.validate = validate
    Pipeline._deep_selection_contract_installed = True
