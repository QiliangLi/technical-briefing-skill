from __future__ import annotations

from datetime import timedelta
from typing import Any

from .adapters.base import CollectedItem
from .business_time import briefing_date
from .collection import CollectionService
from .utils import read_json, stable_hash


DEFAULT_MAX_GAP_LANES = 4


def _preferred_domains(topic_id: str) -> list[str]:
    if topic_id == "agent_acceleration":
        return [
            "arxiv.org",
            "openreview.net",
            "github.com",
            "simonwillison.net",
            "latent.space",
        ]
    if topic_id == "optical_network":
        return [
            "ofcconference.org",
            "dl.acm.org",
            "arxiv.org",
            "research.google",
        ]
    if topic_id == "ai_chip_accelerator":
        return [
            "arxiv.org",
            "dl.acm.org",
            "ieeexplore.ieee.org",
            "nvidia.com",
            "amd.com",
            "cloud.google.com",
        ]
    return []


def plan_coverage_gap_searches(pipeline, *, max_queries: int = DEFAULT_MAX_GAP_LANES) -> list[dict[str, Any]]:
    """Plan the same uncovered lanes as before, without creating one task per lane."""

    from . import coverage_policy, quality_guard
    from .freshness import freshness_limits

    coverage_policy.materialize_deep_backlog(pipeline.config, pipeline.db, pipeline.run_id)
    limit = min(
        max(0, int(max_queries)),
        int(pipeline.config.settings.get("agent_web_search_max_queries", DEFAULT_MAX_GAP_LANES)),
    )
    if not limit:
        return []
    raw_rows = pipeline.db.fetchall(
        """
        SELECT title,summary,topic_hint,direction_hint,source_level,discovery_only,
               original_url,aihot_url,canonical_url,identity_key,payload_json
        FROM raw_items WHERE run_id=?
        """,
        (pipeline.run_id,),
    )
    priority_map = {"highest": 100, "high": 80, "medium": 55, "low": 30}
    gaps = [
        (topic, direction)
        for topic, direction in pipeline.config.iter_directions()
        if not quality_guard.primary_direction_is_covered(
            raw_rows,
            topic["id"],
            direction,
        )
    ]
    gaps.sort(
        key=lambda pair: (
            -priority_map.get(pair[0].get("aihot_priority", "low"), 30),
            pair[0]["id"],
            pair[1]["id"],
        )
    )
    max_age_days = freshness_limits(pipeline.config)["absolute"]
    date_to = briefing_date(pipeline.config)
    date_from = date_to - timedelta(days=max_age_days)
    searches: list[dict[str, Any]] = []
    for topic, direction in gaps:
        if len(searches) >= limit:
            break
        queries = direction.get("queries") or []
        if not queries:
            continue
        search_id = f"{topic['id']}:{direction['id']}"
        searches.append(
            {
                "search_id": search_id,
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
                "priority": priority_map.get(topic.get("aihot_priority", "low"), 30),
            }
        )
    return searches


def discovery_batch_semantic_errors(
    input_data: dict[str, Any],
    output: dict[str, Any],
) -> list[str]:
    searches = {
        str(row.get("search_id") or ""): row
        for row in input_data.get("searches") or []
    }
    results = output.get("results") or []
    actual = [str(row.get("search_id") or "") for row in results if isinstance(row, dict)]
    errors: list[str] = []
    if len(actual) != len(set(actual)):
        errors.append("agent_web_search batch contains duplicate search_id values")
    missing = sorted(set(searches) - set(actual))
    unknown = sorted(set(actual) - set(searches))
    if missing:
        errors.append("agent_web_search batch omits search IDs: " + ", ".join(missing))
    if unknown:
        errors.append("agent_web_search batch references unknown search IDs: " + ", ".join(unknown))
    if len(actual) != len(searches):
        errors.append("agent_web_search batch must return exactly one group per search lane")
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            continue
        search_id = str(result.get("search_id") or "")
        expected = searches.get(search_id)
        if not expected:
            continue
        if str(result.get("topic_id") or "") != str(expected.get("topic_id") or ""):
            errors.append(f"agent_web_search result {index} changed topic_id for {search_id}")
        if str(result.get("direction_id") or "") != str(expected.get("direction_id") or ""):
            errors.append(f"agent_web_search result {index} changed direction_id for {search_id}")
    return errors


def install_discovery_stage() -> None:
    """Make coverage-gap web discovery one issue-level Agent invocation."""

    from . import demo as demo_module
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_discovery_stage_installed", False):
        return

    original_apply = Pipeline._apply_task
    original_semantic_errors = TaskService._semantic_errors
    original_demo_output = demo_module._demo_output

    def prepare_agent_search(self, max_queries: int = DEFAULT_MAX_GAP_LANES) -> int:
        if self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type='agent_web_search' LIMIT 1",
            (self.run_id,),
        ):
            return 0
        searches = plan_coverage_gap_searches(self, max_queries=max_queries)
        if not searches:
            return 0
        search_ids = [str(row["search_id"]) for row in searches]
        self.tasks.create(
            self.run_id,
            "agent_web_search",
            stable_hash(self.run_id, "agent-web-search-batch", *search_ids),
            {
                "batch_id": "coverage-gap-search",
                "searches": [
                    {key: value for key, value in row.items() if key != "priority"}
                    for row in searches
                ],
                "constraints": {
                    "independent_search_lanes": True,
                    "no_cross_lane_result_transfer": True,
                    "return_one_group_per_search_id": True,
                },
            },
            prompt="agent-web-search-batch.md",
            schema="web-search-batch.schema.json",
            priority=max(float(row["priority"]) for row in searches),
            metadata={
                "discovery_batch": True,
                "search_lane_count": len(searches),
            },
        )
        self.db.update_run(self.run_id, stage="AWAITING_AGENT_SEARCH")
        return 1

    Pipeline.prepare_agent_search = prepare_agent_search

    def apply_task(self, task: dict[str, Any]) -> None:
        if task.get("task_type") != "agent_web_search":
            return original_apply(self, task)
        input_data = read_json(self.root / task["input_path"], {})
        if not input_data.get("searches"):
            return original_apply(self, task)

        output = self.tasks.read_result(task)
        searches = {
            str(row.get("search_id") or ""): row
            for row in input_data.get("searches") or []
        }
        collected: list[CollectedItem] = []
        for group in output.get("results") or []:
            search_id = str(group.get("search_id") or "")
            lane = searches[search_id]
            for result in group.get("items") or []:
                collected.append(
                    CollectedItem(
                        source_id="agent_web_search",
                        discovery_source="Agent Web Search",
                        source_level=result.get("source_level", "B"),
                        discovery_only=not bool(result.get("primary")),
                        title=result.get("title", "Untitled"),
                        summary=result.get("summary", ""),
                        original_url=result.get("url", ""),
                        published_at=result.get("published_at"),
                        topic_hint=lane["topic_id"],
                        direction_hint=lane["direction_id"],
                        priority=18.0 if result.get("primary") else 10.0,
                        payload={
                            "publisher": result.get("publisher"),
                            "agent_search_query": lane.get("query"),
                            "agent_search_id": search_id,
                        },
                    )
                )
        service = CollectionService(self.config, self.db, self.run_dir)
        try:
            service.persist(self.run_id, collected)
        finally:
            service.close()

    Pipeline._apply_task = apply_task

    def semantic_errors(self, task, input_data, data):
        errors = list(original_semantic_errors(self, task, input_data, data))
        if task.get("task_type") == "agent_web_search" and input_data.get("searches"):
            errors.extend(discovery_batch_semantic_errors(input_data, data))
        return list(dict.fromkeys(errors))

    TaskService._semantic_errors = semantic_errors

    def demo_output(task_type: str, data: dict[str, Any]):
        if task_type == "agent_web_search" and data.get("searches"):
            return {
                "results": [
                    {
                        "search_id": row["search_id"],
                        "topic_id": row["topic_id"],
                        "direction_id": row["direction_id"],
                        "items": [],
                    }
                    for row in data.get("searches") or []
                ]
            }
        return original_demo_output(task_type, data)

    demo_module._demo_output = demo_output
    Pipeline._discovery_stage_installed = True
