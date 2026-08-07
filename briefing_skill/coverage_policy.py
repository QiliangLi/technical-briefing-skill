from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .freshness import published_age_days
from .utils import canonicalize_url, now_iso, source_url_is_resolved, stable_hash


APPENDIX_PREFIX = "TOPIC_APPENDIX:"


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _project_key(row: dict[str, Any]) -> str:
    payload = row.get("payload_json")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload or "{}")
        except json.JSONDecodeError:
            payload = {}
    if isinstance(payload, dict) and payload.get("repo"):
        return f"github:{str(payload['repo']).strip().lower()}"

    url = str(row.get("original_url") or row.get("canonical_url") or row.get("url") or "")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    if host in {"github.com", "www.github.com"} and len(parts) >= 2:
        return f"github:{parts[0].lower()}/{parts[1].lower()}"
    return str(row.get("identity_key") or canonicalize_url(url) or row.get("id") or "unknown")


def materialize_deep_backlog(config, db, run_id: str) -> int:
    """Carry unpushed A-level sources from the rolling deep lookback into this run.

    Raw-item history is already stored in SQLite, so this creates lightweight
    current-run references instead of re-fetching old documents. Stable identities
    that were already sent as a deep item, topic appendix, or Radar item are skipped.
    """

    policy = dict(config.settings.get("efficiency") or {})
    lookback_days = max(1, int(policy.get("deep_lookback_days", 60)))
    max_items = max(0, int(policy.get("backlog_materialize_per_run", 120)))
    if not max_items:
        return 0

    current = db.fetchall(
        "SELECT identity_key, canonical_url FROM raw_items WHERE run_id=?",
        (run_id,),
    )
    current_keys = {
        str(row.get("identity_key") or row.get("canonical_url") or "")
        for row in current
        if row.get("identity_key") or row.get("canonical_url")
    }
    pushed_event_keys = {
        str(row["event_key"])
        for row in db.fetchall(
            "SELECT DISTINCT event_key FROM events WHERE last_pushed_at IS NOT NULL AND event_key IS NOT NULL AND event_key!=''"
        )
    }
    pushed_urls = {
        str(row["canonical_url"])
        for row in db.fetchall("SELECT canonical_url FROM radar_history")
        if row.get("canonical_url")
    }

    rows = db.fetchall(
        """
        SELECT * FROM raw_items
        WHERE run_id<>? AND source_level='A' AND discovery_only=0
          AND published_at IS NOT NULL
        ORDER BY priority DESC, published_at DESC, created_at DESC
        """,
        (run_id,),
    )
    copied = 0
    seen: set[str] = set()
    for row in rows:
        age = published_age_days(row.get("published_at"))
        if age is None or age > lookback_days:
            continue
        canonical = canonicalize_url(row.get("original_url") or row.get("aihot_url") or row.get("canonical_url"))
        identity = str(row.get("identity_key") or canonical or stable_hash(row.get("source_id"), row.get("external_id"), row.get("title")))
        if identity in current_keys or identity in seen or identity in pushed_event_keys or canonical in pushed_urls:
            continue
        payload = {}
        try:
            payload = json.loads(row.get("payload_json") or "{}")
        except json.JSONDecodeError:
            pass
        payload["carryover_from_run"] = row.get("run_id")
        new_id = stable_hash(run_id, "carryover", identity, row.get("source_id"))
        db.execute(
            """
            INSERT OR IGNORE INTO raw_items(
                id, run_id, source_id, discovery_source, source_level, discovery_only,
                title, summary, original_url, aihot_url, canonical_url, identity_key,
                published_at, discovered_at, authors_json, external_id, topic_hint,
                direction_hint, priority, content_hash, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                run_id,
                row["source_id"],
                row["discovery_source"],
                row["source_level"],
                row["discovery_only"],
                row["title"],
                row.get("summary"),
                row.get("original_url"),
                row.get("aihot_url"),
                canonical,
                identity,
                row.get("published_at"),
                row.get("discovered_at"),
                row.get("authors_json"),
                row.get("external_id"),
                row.get("topic_hint"),
                row.get("direction_hint"),
                row.get("priority") or 0,
                row.get("content_hash"),
                json.dumps(payload, ensure_ascii=False),
                now_iso(),
            ),
        )
        seen.add(identity)
        current_keys.add(identity)
        copied += 1
        if copied >= max_items:
            break
    return copied


def primary_direction_is_diversely_covered(
    raw_rows: Iterable[dict[str, Any]],
    topic_id: str,
    direction: dict[str, Any],
) -> bool:
    """TPN needs more than one project before a direction is considered covered."""

    direction_id = str(direction.get("id") or "")
    terms = [str(term).strip().lower() for term in direction.get("include_terms") or [] if str(term).strip()]
    required_projects = 2 if topic_id == "tpn" else 1
    projects: set[str] = set()
    for row in raw_rows:
        if str(row.get("source_level") or "").upper() != "A" or bool(row.get("discovery_only")):
            continue
        if not source_url_is_resolved(row.get("original_url") or row.get("aihot_url")):
            continue
        matched = row.get("topic_hint") == topic_id and row.get("direction_hint") == direction_id
        if not matched:
            text = f"{row.get('title') or ''} {row.get('summary') or ''}".lower()
            matches = sum(term in text for term in terms)
            matched = bool(terms and matches >= (1 if len(terms) <= 2 else 2))
        if matched:
            projects.add(_project_key(row))
            if len(projects) >= required_projects:
                return True
    return False


def select_diverse_deep_budget(
    rows: Iterable[dict[str, Any]],
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select deep candidates with topic fairness and hard same-project diversity."""

    policy = dict(settings.get("efficiency") or {})
    total_max = max(1, int(policy.get("max_fact_candidates_total", 16)))
    per_topic_max = max(1, int(policy.get("max_fact_candidates_per_topic", 4)))
    per_direction_max = max(1, int(policy.get("max_fact_candidates_per_direction", 2)))
    per_project_max = max(1, int(policy.get("max_fact_candidates_per_project", 1)))

    ordered = sorted(
        list(rows),
        key=lambda row: (
            -_number(row.get("relevance_score")),
            -_number(row.get("rule_score")),
            -_number(row.get("priority")),
            str(row.get("id") or ""),
        ),
    )
    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ordered:
        by_topic[str(row.get("topic_id") or "unknown")].append(row)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    topic_counts: dict[str, int] = defaultdict(int)
    direction_counts: dict[tuple[str, str], int] = defaultdict(int)
    project_counts: dict[tuple[str, str], int] = defaultdict(int)

    def can_take(row: dict[str, Any], *, relax_direction: bool = False) -> bool:
        topic = str(row.get("topic_id") or "unknown")
        direction = str(row.get("direction_id") or "unknown")
        project = _project_key(row)
        if len(selected) >= total_max or topic_counts[topic] >= per_topic_max:
            return False
        if project_counts[(topic, project)] >= per_project_max:
            return False
        if not relax_direction and direction_counts[(topic, direction)] >= per_direction_max:
            return False
        return True

    def take(row: dict[str, Any]) -> None:
        topic = str(row.get("topic_id") or "unknown")
        direction = str(row.get("direction_id") or "unknown")
        project = _project_key(row)
        selected.append(row)
        selected_ids.add(str(row.get("id") or ""))
        topic_counts[topic] += 1
        direction_counts[(topic, direction)] += 1
        project_counts[(topic, project)] += 1

    # First give each active topic one high-value slot before filling globally.
    topic_order = sorted(by_topic, key=lambda topic: -_number(by_topic[topic][0].get("relevance_score")))
    for topic in topic_order:
        if len(selected) >= total_max:
            break
        for row in by_topic[topic]:
            if can_take(row):
                take(row)
                break

    # Then fill by value while preserving project and direction diversity.
    for row in ordered:
        if len(selected) >= total_max:
            break
        if str(row.get("id") or "") in selected_ids:
            continue
        if can_take(row):
            take(row)

    # Direction diversity is soft: if capacity remains, allow another direction
    # duplicate, but never let one project consume multiple deep slots.
    for row in ordered:
        if len(selected) >= total_max:
            break
        if str(row.get("id") or "") in selected_ids:
            continue
        if can_take(row, relax_direction=True):
            take(row)

    deferred = [row for row in ordered if str(row.get("id") or "") not in selected_ids]
    return selected, deferred


def _clean_summary(value: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    matches = list(re.finditer(r"[。！？.!?](?:[”’\"）)\]]*)", clipped))
    if matches:
        return clipped[: matches[-1].end()].strip()
    return clipped.rstrip("，,：:；;、 ") + "。"


def collect_topic_appendix(service, run_id: str, issue_data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    policy = dict(service.config.settings.get("efficiency") or {})
    deep_topics = set(policy.get("deep_topics") or [])
    per_topic_max = max(0, int(policy.get("topic_appendix_max_per_topic", 8)))
    per_project_max = max(1, int(policy.get("topic_appendix_max_per_project", 2)))
    min_score = _number(policy.get("topic_appendix_min_relevance_score"), 45)
    if not per_topic_max:
        return {}

    selected_urls = {
        canonicalize_url(source.get("url"))
        for item in issue_data.get("items", [])
        for source in item.get("sources", [])
        if source.get("url")
    }
    history_urls = {
        str(row["canonical_url"])
        for row in service.db.fetchall("SELECT canonical_url FROM radar_history")
        if row.get("canonical_url")
    }
    rows = service.db.fetchall(
        """
        SELECT c.*, r.title, r.summary, r.original_url, r.canonical_url, r.published_at,
               r.discovery_source, r.payload_json, r.identity_key, r.source_level, r.discovery_only
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
        WHERE c.run_id=? AND c.relevant=1 AND r.source_level='A' AND r.discovery_only=0
        ORDER BY c.relevance_score DESC, c.rule_score DESC, r.priority DESC, r.published_at DESC
        """,
        (run_id,),
    )
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    project_counts: dict[tuple[str, str], int] = defaultdict(int)
    seen_urls: set[str] = set()
    for row in rows:
        topic_id = str(row.get("topic_id") or "")
        if topic_id not in deep_topics or _number(row.get("relevance_score")) < min_score:
            continue
        url = canonicalize_url(row.get("original_url") or row.get("canonical_url"))
        if not url or url in selected_urls or url in history_urls or url in seen_urls:
            continue
        if len(result[topic_id]) >= per_topic_max:
            continue
        project = _project_key(row)
        if project_counts[(topic_id, project)] >= per_project_max:
            continue
        payload = {}
        try:
            payload = json.loads(row.get("payload_json") or "{}")
        except json.JSONDecodeError:
            pass
        source_name = str(payload.get("publisher") or row.get("discovery_source") or "原始来源")
        summary = _clean_summary(row.get("relevance_reason") or row.get("summary") or "")
        result[topic_id].append(
            {
                "topic_id": topic_id,
                "title": row["title"],
                "summary": summary,
                "url": url,
                "source_name": source_name,
                "published_at": str(row.get("published_at") or "")[:10],
                "score": _number(row.get("relevance_score")),
                "project_key": project,
            }
        )
        project_counts[(topic_id, project)] += 1
        seen_urls.add(url)
    return dict(result)


def _appendix_html(service, appendix: dict[str, list[dict[str, Any]]]) -> str:
    if not appendix:
        return ""
    blocks = []
    for topic in service.config.topic_list():
        items = appendix.get(topic["id"], [])
        if not items:
            continue
        rows = []
        for item in items:
            rows.append(
                "<div style='padding:8px 0;border-top:1px solid #deded8'>"
                f"<a href='{html.escape(item['url'], quote=True)}' style='font-size:13px;line-height:1.35;font-weight:700;color:#222;text-decoration:none'>{html.escape(item['title'])}</a>"
                + (f"<div style='font-size:11px;line-height:1.45;color:#666;margin-top:3px'>{html.escape(item['summary'])}</div>" if item["summary"] else "")
                + f"<div style='font-size:10px;color:#888;margin-top:3px'>{html.escape(item['published_at'])} · {item['score']:.0f}分 · 阅读原文：<a href='{html.escape(item['url'], quote=True)}' style='color:#002fa7'>{html.escape(item['source_name'])}</a></div>"
                "</div>"
            )
        blocks.append(
            "<tr><td class='pad-x' style='padding:4px 28px 10px'>"
            "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f3f4f1;border-left:3px solid #8a8a82'><tr><td style='padding:10px 12px'>"
            f"<div style='font:700 11px Microsoft YaHei,Arial,sans-serif;color:#555;margin-bottom:2px'>{html.escape(topic['name'])} · 更多相关进展</div>"
            + "".join(rows)
            + "</td></tr></table></td></tr>"
        )
    if not blocks:
        return ""
    header = (
        "<tr><td class='pad-x' style='padding:20px 28px 6px'>"
        "<div style='border-top:3px solid #555;padding-top:10px'>"
        "<span style='font-size:19px;font-weight:700'>专题补充</span>"
        "<div style='font-size:11px;line-height:1.45;color:#777;margin-top:3px'>各专题Top4之外、已判定相关且有A级原始来源的内容。仅保留1～2句速览，不参与本期综合判断。</div>"
        "</div></td></tr>"
    )
    return header + "".join(blocks)


def install_coverage_policy() -> None:
    """Install rolling backlog, diversity selection, and topic appendices."""

    from . import efficiency, emailer, pipeline, quality_guard

    Pipeline = pipeline.Pipeline
    EmailService = emailer.EmailService
    if getattr(Pipeline, "_coverage_policy_installed", False):
        return

    original_search = Pipeline.prepare_agent_search
    original_relevance = Pipeline.prepare_relevance
    original_build = EmailService.build
    original_aihot_groups = EmailService._aihot_groups

    def prepare_agent_search(self, max_queries: int = 4) -> int:
        materialize_deep_backlog(self.config, self.db, self.run_id)
        return original_search(self, max_queries=max_queries)

    def prepare_relevance(self) -> int:
        materialize_deep_backlog(self.config, self.db, self.run_id)
        return original_relevance(self)

    def persisted_radar_groups(self, issue_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM issue_radar_items WHERE issue_id=? AND category NOT LIKE ? ORDER BY position",
            (issue_id, f"{APPENDIX_PREFIX}%"),
        )
        categories: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            categories.setdefault(row["category"], []).append(
                {
                    "title": row["title"],
                    "summary": row.get("summary") or "",
                    "url": row["canonical_url"],
                    "source_name": row["source_name"],
                    "published_at": row["published_at"],
                }
            )
        return [{"name": name, "items": items} for name, items in categories.items()]

    def aihot_groups(self, issue_date=None, *, issue_id=None, issue_data=None):
        groups = original_aihot_groups(self, issue_date, issue_id=issue_id, issue_data=issue_data)
        appendix = getattr(self, "_topic_appendix_cache", {})
        appendix_urls = {item["url"] for items in appendix.values() for item in items}
        if not appendix_urls:
            return groups
        filtered = []
        for group in groups:
            items = [item for item in group.get("items", []) if canonicalize_url(item.get("url")) not in appendix_urls]
            if items:
                filtered.append({**group, "items": items})
        return filtered

    def build(self, run_id: str, *, status_after: str = "AWAITING_APPROVAL") -> Path:
        issue_row = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
        issue_data = {}
        if issue_row and issue_row.get("issue_json_path"):
            from .utils import read_json
            issue_data = read_json(self.root / issue_row["issue_json_path"])
        appendix = collect_topic_appendix(self, run_id, issue_data)
        self._topic_appendix_cache = appendix
        path = original_build(self, run_id, status_after=status_after)
        if not issue_row:
            return path

        position = 1000
        for topic_id, items in appendix.items():
            for item in items:
                position += 1
                self.db.execute(
                    """
                    INSERT OR REPLACE INTO issue_radar_items(
                        issue_id, canonical_url, normalized_title, category, title,
                        summary, source_name, published_at, position
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        issue_row["id"],
                        item["url"],
                        self._normalise_reference(item["title"]),
                        f"{APPENDIX_PREFIX}{topic_id}",
                        item["title"],
                        item["summary"],
                        item["source_name"],
                        item["published_at"],
                        position,
                    ),
                )

        section = _appendix_html(self, appendix)
        if section:
            text = path.read_text(encoding="utf-8")
            marker = '<span style="font-size:19px;font-weight:700">热点雷达</span>'
            index = text.find(marker)
            if index >= 0:
                row_start = text.rfind("<tr>", 0, index)
                if row_start >= 0:
                    text = text[:row_start] + section + text[row_start:]
            else:
                text = text.replace("</table></td></tr></table>\n</body>", section + "</table></td></tr></table>\n</body>")
            path.write_text(text, encoding="utf-8")
        return path

    efficiency.select_deep_budget = select_diverse_deep_budget
    quality_guard.primary_direction_is_covered = primary_direction_is_diversely_covered
    Pipeline.prepare_agent_search = prepare_agent_search
    Pipeline.prepare_relevance = prepare_relevance
    EmailService._persisted_radar_groups = persisted_radar_groups
    EmailService._aihot_groups = aihot_groups
    EmailService.build = build
    Pipeline._coverage_policy_installed = True
