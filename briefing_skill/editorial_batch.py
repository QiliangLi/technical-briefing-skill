from __future__ import annotations

import json
import logging
from typing import Any

from jsonschema import Draft202012Validator

from .dedup import EventClusterer
from .safe_efficiency import _annotate_event, _editorial_score_floor
from .tasks import brief_item_validation_errors
from .utils import now_iso, read_json, source_url_is_resolved, stable_hash, write_json


LOGGER = logging.getLogger(__name__)


def _policy(config) -> dict[str, Any]:
    return dict(config.settings.get("efficiency") or {})


def _pack_batches(
    entries: list[dict[str, Any]],
    *,
    max_items: int,
    max_chars: int,
) -> list[list[dict[str, Any]]]:
    """Pack deterministic editorial work without creating oversized prompts."""

    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for entry in entries:
        size = len(json.dumps(entry["payload"], ensure_ascii=False, sort_keys=True))
        if current and (len(current) >= max_items or current_chars + size > max_chars):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(entry)
        current_chars += size
    if current:
        batches.append(current)
    return batches


def _id_set_errors(expected: list[str], actual: list[str], label: str) -> list[str]:
    errors: list[str] = []
    if len(actual) != len(set(actual)):
        errors.append(f"{label} contains duplicate IDs")
    missing = sorted(set(expected) - set(actual))
    unknown = sorted(set(actual) - set(expected))
    if missing:
        errors.append(f"{label} omits IDs: {', '.join(missing)}")
    if unknown:
        errors.append(f"{label} references unknown IDs: {', '.join(unknown)}")
    if len(actual) != len(expected):
        errors.append(f"{label} must return exactly one result per input")
    return errors


def plan_item_writing_entries(pipeline) -> list[dict[str, Any]]:
    """Build item-writing inputs directly from finalized Facts and persisted events.

    This is the authoritative editorial planner for new runs. It deliberately does not
    create temporary standalone `item_writing` tasks and then intercept TaskService.
    """

    unfinished = pipeline.db.fetchone(
        """
        SELECT COUNT(*) AS n FROM tasks
        WHERE run_id=? AND task_type IN ('fact_extraction','fact_evidence_repair')
          AND status IN ('PENDING','INVALID','COMPLETED')
        """,
        (pipeline.run_id,),
    )["n"]
    fact_count = pipeline.db.fetchone(
        "SELECT COUNT(*) AS n FROM facts WHERE run_id=?",
        (pipeline.run_id,),
    )["n"]
    if unfinished or not fact_count:
        return []

    clusters = EventClusterer(pipeline.db).persist(
        pipeline.run_id,
        EventClusterer(pipeline.db).cluster_run(pipeline.run_id),
    )
    floor = _editorial_score_floor(pipeline.config)
    entries: list[dict[str, Any]] = []
    for cluster in clusters:
        members = cluster["members"]
        facts = [read_json(pipeline.root / member["json_path"]) for member in members]
        candidates = [
            pipeline.db.fetchone("SELECT * FROM candidates WHERE id=?", (member["candidate_id"],))
            for member in members
        ]
        raws = [
            pipeline.db.fetchone(
                "SELECT r.* FROM raw_items r JOIN candidates c ON c.raw_item_id=r.id WHERE c.id=?",
                (member["candidate_id"],),
            )
            for member in members
        ]
        has_resolved_primary = any(
            raw
            and raw.get("source_level") == "A"
            and source_url_is_resolved(raw.get("original_url") or raw.get("aihot_url"))
            and bool(fact.get("primary_source_resolved"))
            for fact, raw in zip(facts, raws)
        )
        if not has_resolved_primary:
            LOGGER.info(
                "Skipping editorial draft for event %s without a resolved primary A-level source",
                cluster["event_id"],
            )
            continue

        score = pipeline.scorer.event_score(facts, candidates, raws)
        pipeline.db.execute("UPDATE events SET score=? WHERE id=?", (score, cluster["event_id"]))
        if float(score) < floor:
            _annotate_event(
                pipeline.db,
                str(cluster["event_id"]),
                editorial_deferred=True,
                editorial_deferred_reason="deterministic score below minimum selectable issue role",
                editorial_score=float(score),
                editorial_score_floor=float(floor),
            )
            continue

        payload = {
            "event_id": cluster["event_id"],
            "topic": pipeline.config.topic(cluster["topic_id"]),
            "direction": pipeline.config.direction(cluster["topic_id"], cluster["direction_id"]),
            "score": score,
            "facts": facts,
            "sources": [
                {
                    "title": raw["title"],
                    "url": raw["original_url"] or raw["aihot_url"],
                    "source_level": raw["source_level"],
                    "discovery_source": raw["discovery_source"],
                    "published_at": raw["published_at"],
                }
                for raw in raws
                if raw
            ],
            "length": {
                "min_chars": pipeline.config.settings.get("brief_item_min_chars", 300),
                "max_chars": pipeline.config.settings.get("brief_item_max_chars", 450),
            },
        }
        entries.append({"payload": payload, "priority": float(score)})

    entries.sort(key=lambda row: (-row["priority"], str(row["payload"]["event_id"])))
    return entries


def plan_fact_check_entries(pipeline) -> list[dict[str, Any]]:
    """Build Fact Check inputs directly from persisted polished brief items."""

    entries: list[dict[str, Any]] = []
    items = pipeline.db.fetchall(
        "SELECT * FROM brief_items WHERE run_id=? AND fact_check_status='PENDING'",
        (pipeline.run_id,),
    )
    for item in items:
        event_members = pipeline.db.fetchall(
            """
            SELECT f.json_path FROM event_members em
            JOIN facts f ON f.candidate_id=em.candidate_id AND f.run_id=em.run_id
            WHERE em.event_id=? AND em.run_id=?
            """,
            (item["event_id"], pipeline.run_id),
        )
        payload = {
            "brief_item_id": item["id"],
            "brief_item": read_json(pipeline.root / item["json_path"]),
            "facts": [read_json(pipeline.root / row["json_path"]) for row in event_members],
            "length": {
                "min_chars": pipeline.config.settings.get("brief_item_min_chars", 300),
                "max_chars": pipeline.config.settings.get("brief_item_max_chars", 450),
            },
            "rules": [
                "All numbers must be supported by facts.",
                "Baseline and experimental conditions must not be omitted when material.",
                "Project inference must be labelled as project judgement, not source fact.",
                "AI HOT summaries cannot be the sole evidence.",
                "Every field must be a complete sentence without ellipsis or dangling punctuation.",
            ],
        }
        entries.append({"payload": payload, "priority": float(item["score"]) + 5})
    entries.sort(key=lambda row: (-row["priority"], str(row["payload"]["brief_item_id"])))
    return entries


def install_editorial_batching() -> None:
    """Install an explicit batch planner for drafting and independent Fact Checks."""

    from . import demo as demo_module
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_editorial_batching_installed", False):
        return

    original_prepare_items = Pipeline._maybe_prepare_items
    original_prepare_checks = Pipeline._maybe_prepare_checks
    original_prepare_issue = Pipeline._maybe_prepare_issue
    original_apply_task = Pipeline._apply_task
    original_semantic_errors = TaskService._semantic_errors
    original_demo_output = demo_module._demo_output

    def maybe_prepare_items(self) -> None:
        # Resume old runs with their already-created standalone tasks unchanged.
        if self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type='item_writing' LIMIT 1",
            (self.run_id,),
        ):
            return original_prepare_items(self)
        if self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type='item_writing_batch' LIMIT 1",
            (self.run_id,),
        ):
            return

        entries = plan_item_writing_entries(self)
        if not entries:
            return
        policy = _policy(self.config)
        batch_size = max(1, int(policy.get("item_writing_batch_size", 4)))
        char_limit = max(12000, int(policy.get("editorial_batch_max_input_chars", 65000)))
        for index, batch in enumerate(
            _pack_batches(entries, max_items=batch_size, max_chars=char_limit),
            1,
        ):
            event_ids = [str(row["payload"]["event_id"]) for row in batch]
            entity_id = stable_hash(self.run_id, "item-writing-batch", *event_ids)
            self.tasks.create(
                self.run_id,
                "item_writing_batch",
                entity_id,
                {
                    "batch_id": f"writing-{index}",
                    "items": [row["payload"] for row in batch],
                    "constraints": {
                        "independent_items": True,
                        "no_cross_item_fact_transfer": True,
                    },
                },
                prompt="item-writing-batch.md",
                schema="item-writing-batch.schema.json",
                priority=max(row["priority"] for row in batch),
            )
        self.db.update_run(self.run_id, stage="AWAITING_ITEMS")

    def maybe_prepare_checks(self) -> None:
        writing_unfinished = self.db.fetchone(
            """
            SELECT COUNT(*) AS n FROM tasks
            WHERE run_id=? AND task_type='item_writing_batch'
              AND status IN ('PENDING','INVALID','COMPLETED')
            """,
            (self.run_id,),
        )["n"]
        if writing_unfinished:
            return
        if self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type='fact_check' LIMIT 1",
            (self.run_id,),
        ):
            return original_prepare_checks(self)
        if self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type='fact_check_batch' LIMIT 1",
            (self.run_id,),
        ):
            return

        item_count = self.db.fetchone(
            "SELECT COUNT(*) AS n FROM brief_items WHERE run_id=?",
            (self.run_id,),
        )["n"]
        if not item_count:
            return
        entries = plan_fact_check_entries(self)
        if not entries:
            return

        policy = _policy(self.config)
        batch_size = max(1, int(policy.get("fact_check_batch_size", 4)))
        char_limit = max(12000, int(policy.get("editorial_batch_max_input_chars", 65000)))
        for index, batch in enumerate(
            _pack_batches(entries, max_items=batch_size, max_chars=char_limit),
            1,
        ):
            item_ids = [str(row["payload"]["brief_item_id"]) for row in batch]
            entity_id = stable_hash(self.run_id, "fact-check-batch", *item_ids)
            self.tasks.create(
                self.run_id,
                "fact_check_batch",
                entity_id,
                {
                    "batch_id": f"fact-check-{index}",
                    "checks": [row["payload"] for row in batch],
                    "constraints": {
                        "independent_items": True,
                        "no_cross_item_evidence": True,
                    },
                },
                prompt="fact-check-batch.md",
                schema="fact-check-batch.schema.json",
                priority=max(row["priority"] for row in batch),
            )
        self.db.update_run(self.run_id, stage="AWAITING_FACT_CHECK")

    def maybe_prepare_issue(self) -> None:
        pending = self.db.fetchone(
            """
            SELECT COUNT(*) AS n FROM tasks
            WHERE run_id=? AND task_type='fact_check_batch'
              AND status IN ('PENDING','INVALID','COMPLETED')
            """,
            (self.run_id,),
        )["n"]
        if pending:
            return
        return original_prepare_issue(self)

    def apply_task(self, task: dict[str, Any]) -> None:
        if task["task_type"] == "item_writing_batch":
            output = self.tasks.read_result(task)
            task_input = read_json(self.root / task["input_path"], {})
            inputs = {str(row["event_id"]): row for row in task_input.get("items", [])}
            for result in output.get("results", []):
                event_id = str(result.get("event_id") or "")
                source_input = inputs[event_id]
                item = dict(result["item"])
                item_path = self.run_dir / "items" / f"{event_id}.json"
                write_json(
                    item_path,
                    {
                        **item,
                        "_provenance": {
                            "task_id": task["id"],
                            "event_id": event_id,
                            "batch_id": task_input.get("batch_id"),
                            "source_urls": [source.get("url") for source in source_input.get("sources", [])],
                        },
                    },
                )
                self.db.execute(
                    """
                    INSERT OR REPLACE INTO brief_items(
                        id, run_id, event_id, json_path, score,
                        fact_check_status, approved, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stable_hash(self.run_id, "item", event_id),
                        self.run_id,
                        event_id,
                        str(item_path.relative_to(self.root)),
                        item.get("score", 0),
                        "PENDING",
                        0,
                        now_iso(),
                    ),
                )
            return

        if task["task_type"] == "fact_check_batch":
            # Legacy batch results are kept for resumability. New runs are intercepted
            # by fact_check_minimal_patch and never grant whole-item rewrite authority.
            output = self.tasks.read_result(task)
            for result in output.get("results", []):
                brief_item_id = str(result.get("brief_item_id") or "")
                item = self.db.fetchone("SELECT * FROM brief_items WHERE id=?", (brief_item_id,))
                if not item:
                    raise KeyError(brief_item_id)
                if result.get("corrected_item"):
                    current_item = read_json(self.root / item["json_path"], {})
                    corrected = dict(result["corrected_item"])
                    if current_item.get("_provenance"):
                        corrected["_provenance"] = current_item["_provenance"]
                    write_json(self.root / item["json_path"], corrected)
                self.db.execute(
                    "UPDATE brief_items SET fact_check_status=? WHERE id=?",
                    ("PASS" if result["pass"] else "FAIL", brief_item_id),
                )
            return

        return original_apply_task(self, task)

    def semantic_errors(
        self,
        task: dict[str, Any],
        input_data: dict[str, Any],
        data: dict[str, Any],
    ) -> list[str]:
        errors = list(original_semantic_errors(self, task, input_data, data))

        if task["task_type"] == "item_writing_batch":
            expected = [str(row.get("event_id") or "") for row in input_data.get("items", [])]
            actual = [str(row.get("event_id") or "") for row in data.get("results", [])]
            errors.extend(_id_set_errors(expected, actual, "item_writing_batch"))
            inputs = {str(row.get("event_id") or ""): row for row in input_data.get("items", [])}
            item_schema = read_json(self.root / "schemas" / "brief-item.schema.json")
            validator = Draft202012Validator(item_schema)
            for index, result in enumerate(data.get("results", [])):
                event_id = str(result.get("event_id") or "")
                if event_id not in inputs or not isinstance(result.get("item"), dict):
                    continue
                item = result["item"]
                schema_errors = sorted(validator.iter_errors(item), key=lambda error: list(error.path))
                errors.extend(
                    f"item_writing_batch result {index}: {error.message}"
                    for error in schema_errors[:5]
                )
                pseudo_task = {**task, "task_type": "item_writing", "entity_id": event_id}
                errors.extend(
                    f"item_writing_batch {event_id}: {message}"
                    for message in original_semantic_errors(self, pseudo_task, inputs[event_id], item)
                )
                length = inputs[event_id].get("length") or {}
                errors.extend(
                    f"item_writing_batch {event_id}: {message}"
                    for message in brief_item_validation_errors(
                        item,
                        min_chars=int(length.get("min_chars", 300)),
                        max_chars=int(length.get("max_chars", 450)),
                    )
                )

        elif task["task_type"] == "fact_check_batch":
            expected = [str(row.get("brief_item_id") or "") for row in input_data.get("checks", [])]
            actual = [str(row.get("brief_item_id") or "") for row in data.get("results", [])]
            errors.extend(_id_set_errors(expected, actual, "fact_check_batch"))
            inputs = {str(row.get("brief_item_id") or ""): row for row in input_data.get("checks", [])}
            item_schema = read_json(self.root / "schemas" / "brief-item.schema.json")
            validator = Draft202012Validator(item_schema)
            for index, result in enumerate(data.get("results", [])):
                brief_item_id = str(result.get("brief_item_id") or "")
                if brief_item_id not in inputs:
                    continue
                check_input = inputs[brief_item_id]
                pseudo_task = {**task, "task_type": "fact_check", "entity_id": brief_item_id}
                pseudo_output = {
                    "pass": result.get("pass"),
                    "issues": result.get("issues") or [],
                    "corrected_item": result.get("corrected_item"),
                }
                errors.extend(
                    f"fact_check_batch {brief_item_id}: {message}"
                    for message in original_semantic_errors(self, pseudo_task, check_input, pseudo_output)
                )
                corrected = result.get("corrected_item")
                if isinstance(corrected, dict):
                    schema_errors = sorted(validator.iter_errors(corrected), key=lambda error: list(error.path))
                    errors.extend(
                        f"fact_check_batch result {index} corrected_item: {error.message}"
                        for error in schema_errors[:5]
                    )
                    length = check_input.get("length") or {}
                    errors.extend(
                        f"fact_check_batch {brief_item_id}: corrected_item: {message}"
                        for message in brief_item_validation_errors(
                            corrected,
                            min_chars=int(length.get("min_chars", 300)),
                            max_chars=int(length.get("max_chars", 450)),
                        )
                    )
        return errors

    def demo_output(task_type: str, data: dict[str, Any]):
        if task_type == "item_writing_batch":
            return {
                "results": [
                    {"event_id": row["event_id"], "item": original_demo_output("item_writing", row)}
                    for row in data.get("items", [])
                ]
            }
        if task_type == "fact_check_batch":
            return {
                "results": [
                    {"brief_item_id": row["brief_item_id"], **original_demo_output("fact_check", row)}
                    for row in data.get("checks", [])
                ]
            }
        return original_demo_output(task_type, data)

    Pipeline._maybe_prepare_items = maybe_prepare_items
    Pipeline._maybe_prepare_checks = maybe_prepare_checks
    Pipeline._maybe_prepare_issue = maybe_prepare_issue
    Pipeline._apply_task = apply_task
    Pipeline._editorial_batching_installed = True
    TaskService._semantic_errors = semantic_errors
    TaskService._editorial_batching_installed = True
    demo_module._demo_output = demo_output
