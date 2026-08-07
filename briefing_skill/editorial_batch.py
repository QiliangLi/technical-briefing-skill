from __future__ import annotations

import json
from typing import Any, Callable

from jsonschema import Draft202012Validator

from .tasks import brief_item_validation_errors
from .utils import now_iso, read_json, stable_hash, write_json


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


def _capture_tasks(
    task_service,
    wanted_type: str,
    producer: Callable[[], None],
) -> list[dict[str, Any]]:
    """Run an existing deterministic planner while capturing one task type."""

    captured: list[dict[str, Any]] = []
    bound_create = task_service.create
    had_instance_override = "create" in task_service.__dict__
    previous_override = task_service.__dict__.get("create")

    def capture_create(
        run_id: str,
        task_type: str,
        entity_id: str,
        input_data: dict[str, Any],
        **kwargs,
    ):
        if task_type == wanted_type:
            captured.append(
                {
                    "run_id": run_id,
                    "task_type": task_type,
                    "entity_id": entity_id,
                    "input_data": input_data,
                    "priority": float(kwargs.get("priority") or 0),
                    "metadata": dict(kwargs.get("metadata") or {}),
                }
            )
            return {
                "id": stable_hash(run_id, "captured", task_type, entity_id),
                "run_id": run_id,
                "task_type": task_type,
                "entity_id": entity_id,
                "status": "CAPTURED",
            }
        return bound_create(run_id, task_type, entity_id, input_data, **kwargs)

    task_service.create = capture_create
    try:
        producer()
    finally:
        if had_instance_override:
            task_service.create = previous_override
        else:
            del task_service.create
    return captured


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


def install_editorial_batching() -> None:
    """Batch writing and independent fact checks while preserving per-item gates."""

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

        captured = _capture_tasks(
            self.tasks,
            "item_writing",
            lambda: original_prepare_items(self),
        )
        if not captured:
            return

        policy = _policy(self.config)
        batch_size = max(1, int(policy.get("item_writing_batch_size", 4)))
        char_limit = max(12000, int(policy.get("editorial_batch_max_input_chars", 65000)))
        entries = [
            {
                "payload": {"event_id": row["entity_id"], **row["input_data"]},
                "priority": row["priority"],
            }
            for row in sorted(captured, key=lambda row: (-row["priority"], row["entity_id"]))
        ]
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
                metadata={
                    "required_skills": ["human-writing", "humanizer"],
                    "skill_mode": "batch_chinese_technical_rewrite_then_ai_pattern_audit",
                },
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

        captured = _capture_tasks(
            self.tasks,
            "fact_check",
            lambda: original_prepare_checks(self),
        )
        if not captured:
            return

        policy = _policy(self.config)
        batch_size = max(1, int(policy.get("fact_check_batch_size", 4)))
        char_limit = max(12000, int(policy.get("editorial_batch_max_input_chars", 65000)))
        entries = [
            {
                "payload": {"brief_item_id": row["entity_id"], **row["input_data"]},
                "priority": row["priority"],
            }
            for row in sorted(captured, key=lambda row: (-row["priority"], row["entity_id"]))
        ]
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
                            "source_urls": [
                                source.get("url") for source in source_input.get("sources", [])
                            ],
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
                    for message in original_semantic_errors(
                        self, pseudo_task, check_input, pseudo_output
                    )
                )
                corrected = result.get("corrected_item")
                if isinstance(corrected, dict):
                    schema_errors = sorted(
                        validator.iter_errors(corrected), key=lambda error: list(error.path)
                    )
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
                    {
                        "event_id": row["event_id"],
                        "item": original_demo_output("item_writing", row),
                    }
                    for row in data.get("items", [])
                ]
            }
        if task_type == "fact_check_batch":
            return {
                "results": [
                    {
                        "brief_item_id": row["brief_item_id"],
                        **original_demo_output("fact_check", row),
                    }
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
