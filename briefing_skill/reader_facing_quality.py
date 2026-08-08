from __future__ import annotations

import html
from typing import Any

from .utils import canonicalize_url, read_json


FORBIDDEN_READER_PHRASES = (
    "high-confidence A-level rule match",
    "A-level rule match",
    "B-level rule match",
    "rule_score",
    "selection reason",
)


def _contains_internal_reason(text: str) -> bool:
    lower = str(text or "").lower()
    return any(phrase.lower() in lower for phrase in FORBIDDEN_READER_PHRASES)


def _clean_topic_appendix(service, original_collect, run_id: str, issue_data: dict[str, Any]):
    appendix = original_collect(service, run_id, issue_data)
    cleaned: dict[str, list[dict[str, Any]]] = {}
    for topic_id, items in appendix.items():
        kept: list[dict[str, Any]] = []
        for item in items:
            summary = str(item.get("summary") or "").strip()
            if not summary or _contains_internal_reason(summary):
                url = canonicalize_url(item.get("url"))
                raw = service.db.fetchone(
                    """
                    SELECT summary FROM raw_items
                    WHERE canonical_url=? OR original_url=?
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (url, url),
                )
                summary = service.__class__._clean_text((raw or {}).get("summary")) if raw else ""
                if summary:
                    from .coverage_policy import _clean_summary

                    summary = _clean_summary(summary)
            if not summary or _contains_internal_reason(summary):
                # A title-only appendix item is not useful enough to occupy reader space.
                continue
            kept.append({**item, "summary": summary})
        if kept:
            cleaned[topic_id] = kept
    return cleaned


def _source_title(service, item: dict[str, Any]) -> str:
    for source in item.get("sources") or []:
        url = canonicalize_url(source.get("url"))
        if not url:
            continue
        row = service.db.fetchone(
            """
            SELECT title FROM raw_items
            WHERE canonical_url=? OR original_url=?
            ORDER BY created_at DESC LIMIT 1
            """,
            (url, url),
        )
        title = str((row or {}).get("title") or "").strip()
        if title:
            return title
    return ""


def _inject_source_titles(service, run_id: str, path):
    issue_row = service.db.fetchone("SELECT issue_json_path FROM issues WHERE run_id=?", (run_id,))
    if not issue_row or not issue_row.get("issue_json_path"):
        return path
    issue = read_json(service.root / issue_row["issue_json_path"], {})
    text = path.read_text(encoding="utf-8")
    for item in issue.get("items") or []:
        if item.get("item_role", "core") != "core":
            continue
        source_title = _source_title(service, item)
        if not source_title:
            continue
        anchor = html.escape(str(item.get("anchor_id") or f"item-{item.get('brief_item_id', '')}"), quote=True)
        marker = f'id="{anchor}"'
        start = text.find(marker)
        if start < 0:
            continue
        h2_end = text.find("</h2>", start)
        if h2_end < 0:
            continue
        insert_at = h2_end + len("</h2>")
        block = (
            "<div data-source-title=\"1\" style=\"font-size:10px;line-height:1.35;color:#777;"
            "margin:-2px 0 7px\">论文/来源："
            + html.escape(source_title)
            + "</div>"
        )
        text = text[:insert_at] + block + text[insert_at:]
    path.write_text(text, encoding="utf-8")
    return path


def install_reader_facing_quality() -> None:
    """Keep internal scoring metadata out of the briefing and collapse project impact."""

    from . import coverage_policy, project_insight
    from .emailer import EmailService
    from .pipeline import Pipeline
    from .rendering import Renderer

    if getattr(Pipeline, "_reader_facing_quality_installed", False):
        return

    original_collect = coverage_policy.collect_topic_appendix

    def collect_topic_appendix(service, run_id: str, issue_data: dict[str, Any]):
        return _clean_topic_appendix(service, original_collect, run_id, issue_data)

    coverage_policy.collect_topic_appendix = collect_topic_appendix

    # Project Insight remains a structured internal synthesis signal, but the reader sees
    # one unified “本期判断” section. The synthesis prompt is responsible for folding any
    # material project implication into normal judgements.
    project_insight.render_project_insight_email_block = lambda issue: ""

    original_build = EmailService.build

    def build(self, run_id: str, *args, **kwargs):
        path = original_build(self, run_id, *args, **kwargs)
        return _inject_source_titles(self, run_id, path)

    EmailService.build = build

    original_validate = Renderer.validate

    def validate(self, run_id: str):
        report = original_validate(self, run_id)
        failures = [
            value
            for value in report.get("failures", [])
            if value != "Project insights are not exposed in the email"
        ]
        report["failures"] = failures
        issue_row = self.db.fetchone("SELECT email_path FROM issues WHERE run_id=?", (run_id,))
        if not issue_row or not issue_row.get("email_path"):
            return report
        text = (self.root / issue_row["email_path"]).read_text(encoding="utf-8")
        if "data-project-insight-count=" in text or ">项目影响<" in text:
            report.setdefault("failures", []).append("Project impact must be merged into 本期判断, not rendered separately")
        else:
            report.setdefault("passes", []).append("Project impact is merged into 本期判断")
        leaked = [phrase for phrase in FORBIDDEN_READER_PHRASES if phrase.lower() in text.lower()]
        if leaked:
            report.setdefault("failures", []).append(
                "Internal selection metadata leaked into reader output: " + ", ".join(sorted(set(leaked)))
            )
        else:
            report.setdefault("passes", []).append("Reader output contains no internal selection metadata")
        core_count = text.count("id=\"item-")
        source_title_count = text.count("data-source-title=\"1\"")
        if core_count and source_title_count < core_count:
            report.setdefault("warnings", []).append(
                f"Only {source_title_count}/{core_count} detailed items expose an original source title"
            )
        return report

    Renderer.validate = validate
    Pipeline._reader_facing_quality_installed = True
