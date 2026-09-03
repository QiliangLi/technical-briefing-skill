from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .business_time import briefing_date
from .utils import read_json, source_url_is_resolved, write_json


def primary_row_matches_direction(
    row: dict[str, Any],
    topic_id: str,
    direction: dict[str, Any],
) -> bool:
    """Return True only when a usable primary source row proves coverage for
    one direction of the topic its ``topic_hint`` names.

    Evidence boundary: a row whose ``topic_hint`` belongs to another topic can
    never prove coverage here, even when its title or summary matches the
    direction vocabulary. Keyword fallback applies only within the same topic.
    """

    if str(row.get("source_level") or "").upper() != "A":
        return False
    if bool(row.get("discovery_only")):
        return False
    if not source_url_is_resolved(row.get("original_url") or row.get("aihot_url")):
        return False
    if str(row.get("topic_hint") or "") != str(topic_id):
        return False
    direction_id = str(direction.get("id") or "")
    if str(row.get("direction_hint") or "") == direction_id:
        return True
    terms = [
        str(term).strip().lower()
        for term in direction.get("include_terms") or []
        if str(term).strip()
    ]
    if not terms:
        return False
    text = f"{row.get('title') or ''} {row.get('summary') or ''}".lower()
    matches = sum(term in text for term in terms)
    return matches >= (1 if len(terms) <= 2 else 2)


def primary_direction_is_covered(
    raw_rows: Iterable[dict[str, Any]],
    topic_id: str,
    direction: dict[str, Any],
) -> bool:
    """Count a direction as covered only when a usable primary source exists."""

    for row in raw_rows:
        if primary_row_matches_direction(row, topic_id, direction):
            return True
    return False


def relevance_batch_validation_errors(
    output: dict[str, Any],
    input_data: dict[str, Any],
) -> list[str]:
    expected = [
        str(row.get("candidate_id") or "")
        for row in input_data.get("candidates") or []
    ]
    actual = [
        str(row.get("candidate_id") or "")
        for row in output.get("results") or []
    ]
    errors: list[str] = []
    if len(actual) != len(set(actual)):
        errors.append("relevance_batch contains duplicate candidate_id values")
    unknown = sorted(set(actual) - set(expected))
    missing = sorted(set(expected) - set(actual))
    if unknown:
        errors.append(f"relevance_batch references unknown candidate IDs: {', '.join(unknown)}")
    if missing:
        errors.append(f"relevance_batch omits candidate IDs: {', '.join(missing)}")
    if len(actual) != len(expected):
        errors.append("relevance_batch must return exactly one result per input candidate")
    return errors


def _install_renderer_length_guard() -> None:
    """Make the legacy short-item warning follow the configured item budget."""

    from .rendering import Renderer

    if getattr(Renderer, "_configured_length_guard_installed", False):
        return
    original_validate = Renderer.validate

    def validate(self, run_id: str) -> dict[str, Any]:
        report = original_validate(self, run_id)
        minimum = int(self.config.settings.get("brief_item_min_chars", 300))
        from .expanded import historical_brief_upgrade_min_chars

        historical_minimum = historical_brief_upgrade_min_chars(self.config)
        prefix = "Item may be too short: "
        warnings = list(report.get("warnings") or [])
        if any(str(warning).startswith(prefix) for warning in warnings):
            issue = self.db.fetchone("SELECT issue_json_path FROM issues WHERE run_id=?", (run_id,))
            data = read_json(self.root / issue["issue_json_path"], {}) if issue and issue.get("issue_json_path") else {}
            fields = ("core_conclusion", "mechanism", "result", "boundary", "project_relevance")
            lengths = {
                str(item.get("title") or ""): (
                    len("".join(str(item.get(field) or "") for field in fields)),
                    historical_minimum
                    if item.get("brief_upgrade")
                    and item.get("brief_upgrade_origin") == "historical"
                    else minimum,
                )
                for item in data.get("items") or []
            }
            report["warnings"] = [
                warning
                for warning in warnings
                if not (
                    str(warning).startswith(prefix)
                    and lengths.get(str(warning)[len(prefix):], (0, minimum))[0]
                    >= lengths.get(str(warning)[len(prefix):], (0, minimum))[1]
                )
            ]
            write_json(self.root / "workspace" / "runs" / run_id / "validation.json", report)
        return report

    Renderer.validate = validate
    Renderer._configured_length_guard_installed = True


def install_quality_guards() -> None:
    """Tighten gap search, batch validation, and configured length handling."""

    from . import pipeline as pipeline_module
    from .discovery_stage import _preferred_domains
    from .efficiency import DEFAULT_DEEP_TOPICS
    from .tasks import TaskService

    _install_renderer_length_guard()

    Pipeline = pipeline_module.Pipeline
    if getattr(Pipeline, "_quality_guards_installed", False):
        return

    original_semantic_errors = TaskService._semantic_errors

    def prepare_agent_search(self, max_queries: int = 4) -> int:
        policy = dict(self.config.settings.get("efficiency") or {})
        limit = min(
            max(0, int(max_queries)),
            int(self.config.settings.get("agent_web_search_max_queries", 4)),
        )
        if not limit:
            return 0
        deep_topics = set(
            policy.get("deep_topics")
            or DEFAULT_DEEP_TOPICS
        )
        raw_rows = self.db.fetchall(
            """
            SELECT title, summary, topic_hint, direction_hint, source_level,
                   discovery_only, original_url, aihot_url
            FROM raw_items WHERE run_id=?
            """,
            (self.run_id,),
        )
        priority_map = {"highest": 100, "high": 80, "medium": 55, "low": 30}
        gaps = [
            (topic, direction)
            for topic, direction in self.config.iter_directions()
            if topic.get("id") in deep_topics
            and not primary_direction_is_covered(raw_rows, topic["id"], direction)
        ]
        gaps.sort(
            key=lambda pair: (
                -priority_map.get(pair[0].get("aihot_priority", "low"), 30),
                pair[0]["id"],
                pair[1]["id"],
            )
        )
        max_age_days = pipeline_module.freshness_limits(self.config)["absolute"]
        date_to = briefing_date(self.config)
        date_from = date_to - timedelta(days=max_age_days)
        created = 0
        for topic, direction in gaps:
            if created >= limit:
                break
            queries = direction.get("queries") or []
            if not queries:
                continue
            self.tasks.create(
                self.run_id,
                "agent_web_search",
                f"{topic['id']}:{direction['id']}",
                {
                    "topic_id": topic["id"],
                    "topic_name": topic["name"],
                    "direction_id": direction["id"],
                    "direction_name": direction["name"],
                    "query": queries[0],
                    "preferred_domains": _preferred_domains(str(topic["id"])),
                    "freshness_days": max_age_days,
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                    "max_results": 10,
                    "search_reason": "no resolved A-level fixed-source coverage",
                },
                prompt="agent-web-search.md",
                schema="web-search-results.schema.json",
                priority=priority_map.get(topic.get("aihot_priority", "low"), 30),
            )
            created += 1
        if created:
            self.db.update_run(self.run_id, stage="AWAITING_AGENT_SEARCH")
        return created

    def semantic_errors(
        self,
        task: dict[str, Any],
        input_data: dict[str, Any],
        data: dict[str, Any],
    ) -> list[str]:
        errors = original_semantic_errors(self, task, input_data, data)
        if task["task_type"] == "relevance_batch":
            errors.extend(relevance_batch_validation_errors(data, input_data))
        return errors

    Pipeline.prepare_agent_search = prepare_agent_search
    Pipeline._quality_guards_installed = True
    TaskService._semantic_errors = semantic_errors
