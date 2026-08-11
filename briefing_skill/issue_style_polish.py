from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator

from .tasks import BRIEF_FIELDS, brief_item_validation_errors
from .utils import read_json, stable_hash, write_json

STYLE_FIELDS = ("title", *BRIEF_FIELDS)
TASK_TYPE = "item_style_polish"


def _style_input(pipeline) -> dict[str, Any]:
    rows = pipeline.db.fetchall(
        "SELECT * FROM brief_items WHERE run_id=? ORDER BY score DESC, id",
        (pipeline.run_id,),
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        item = read_json(pipeline.root / row["json_path"], {})
        items.append(
            {
                "brief_item_id": row["id"],
                "event_id": row["event_id"],
                "item": {
                    key: value
                    for key, value in item.items()
                    if key != "_provenance"
                },
            }
        )
    return {
        "items": items,
        "constraints": {
            "single_issue_level_pass": True,
            "editable_fields": list(STYLE_FIELDS),
            "preserve_facts_numbers_conditions": True,
            "preserve_all_non_style_fields": True,
            "no_cross_item_fact_transfer": True,
        },
    }


def _strip_redundant_writing_skills(
    task_type: str,
    metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Keep draft/synthesis tasks free of the old two-skill rewrite chain."""

    if task_type not in {"item_writing", "item_writing_batch", "issue_synthesis"}:
        return metadata
    cleaned = dict(metadata or {})
    cleaned.pop("required_skills", None)
    cleaned.pop("skill_mode", None)
    return cleaned or None


def install_issue_style_polish() -> None:
    """Polish all drafted items once, then fact-check the polished reader text."""

    from . import demo as demo_module
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_issue_style_polish_installed", False):
        return

    original_prepare_checks = Pipeline._maybe_prepare_checks
    original_apply_task = Pipeline._apply_task
    original_semantic_errors = TaskService._semantic_errors
    original_create = TaskService.create
    original_demo_output = demo_module._demo_output

    def create(
        self,
        run_id: str,
        task_type: str,
        entity_id: str,
        input_data: dict[str, Any],
        **kwargs,
    ):
        kwargs["metadata"] = _strip_redundant_writing_skills(
            task_type,
            kwargs.get("metadata"),
        )
        return original_create(
            self,
            run_id,
            task_type,
            entity_id,
            input_data,
            **kwargs,
        )

    def maybe_prepare_checks(self) -> None:
        # Existing fact-check tasks belong to an older run contract. Resume them
        # unchanged rather than inserting a new style stage retroactively.
        if self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type IN ('fact_check','fact_check_batch') LIMIT 1",
            (self.run_id,),
        ):
            return original_prepare_checks(self)

        writing_unfinished = self.db.fetchone(
            """
            SELECT COUNT(*) AS n FROM tasks
            WHERE run_id=? AND task_type IN ('item_writing','item_writing_batch')
              AND status IN ('PENDING','INVALID','COMPLETED')
            """,
            (self.run_id,),
        )["n"]
        if writing_unfinished:
            return

        item_count = self.db.fetchone(
            "SELECT COUNT(*) AS n FROM brief_items WHERE run_id=?",
            (self.run_id,),
        )["n"]
        if not item_count:
            return

        existing = self.db.fetchone(
            "SELECT * FROM tasks WHERE run_id=? AND task_type=? LIMIT 1",
            (self.run_id, TASK_TYPE),
        )
        if existing:
            if existing["status"] != "APPLIED":
                return
            return original_prepare_checks(self)

        payload = _style_input(self)
        entity_id = stable_hash(self.run_id, TASK_TYPE)
        self.tasks.create(
            self.run_id,
            TASK_TYPE,
            entity_id,
            payload,
            prompt="item-style-polish.md",
            schema="item-style-polish.schema.json",
            priority=95,
            metadata={
                "required_skills": ["human-writing"],
                "skill_mode": "single_issue_level_chinese_technical_polish",
            },
        )
        self.db.update_run(self.run_id, stage="AWAITING_STYLE_POLISH")

    def apply_task(self, task: dict[str, Any]) -> None:
        if task["task_type"] != TASK_TYPE:
            return original_apply_task(self, task)

        output = self.tasks.read_result(task)
        for result in output.get("results", []):
            brief_item_id = str(result.get("brief_item_id") or "")
            row = self.db.fetchone(
                "SELECT * FROM brief_items WHERE id=? AND run_id=?",
                (brief_item_id, self.run_id),
            )
            if not row:
                raise KeyError(brief_item_id)
            current = read_json(self.root / row["json_path"], {})
            polished = dict(current)
            for field in STYLE_FIELDS:
                polished[field] = result[field]
            write_json(self.root / row["json_path"], polished)
        return

    def semantic_errors(
        self,
        task: dict[str, Any],
        input_data: dict[str, Any],
        data: dict[str, Any],
    ) -> list[str]:
        errors = list(original_semantic_errors(self, task, input_data, data))
        if task["task_type"] != TASK_TYPE:
            return errors

        expected_rows = input_data.get("items") or []
        expected = [str(row.get("brief_item_id") or "") for row in expected_rows]
        actual = [str(row.get("brief_item_id") or "") for row in data.get("results", [])]
        if len(actual) != len(set(actual)):
            errors.append("item_style_polish contains duplicate brief_item_id values")
        missing = sorted(set(expected) - set(actual))
        unknown = sorted(set(actual) - set(expected))
        if missing:
            errors.append(f"item_style_polish omits IDs: {', '.join(missing)}")
        if unknown:
            errors.append(f"item_style_polish references unknown IDs: {', '.join(unknown)}")
        if len(actual) != len(expected):
            errors.append("item_style_polish must return exactly one result per input")

        inputs = {
            str(row.get("brief_item_id") or ""): row.get("item") or {}
            for row in expected_rows
        }
        item_schema = read_json(self.root / "schemas" / "brief-item.schema.json")
        validator = Draft202012Validator(item_schema)
        for index, result in enumerate(data.get("results", [])):
            brief_item_id = str(result.get("brief_item_id") or "")
            original = inputs.get(brief_item_id)
            if not original:
                continue
            reconstructed = dict(original)
            for field in STYLE_FIELDS:
                reconstructed[field] = result.get(field)
            schema_errors = sorted(
                validator.iter_errors(reconstructed),
                key=lambda error: list(error.path),
            )
            errors.extend(
                f"item_style_polish result {index}: {error.message}"
                for error in schema_errors[:5]
            )
            length = self.db.fetchone(
                "SELECT json_path FROM brief_items WHERE id=? AND run_id=?",
                (brief_item_id, task["run_id"]),
            )
            if length:
                settings = getattr(self, "config", None)
            min_chars = 180
            max_chars = 260
            errors.extend(
                f"item_style_polish {brief_item_id}: {message}"
                for message in brief_item_validation_errors(
                    reconstructed,
                    min_chars=min_chars,
                    max_chars=max_chars,
                )
            )
        return errors

    def demo_output(task_type: str, data: dict[str, Any]):
        if task_type == TASK_TYPE:
            return {
                "results": [
                    {
                        "brief_item_id": row["brief_item_id"],
                        **{
                            field: row["item"].get(field, "")
                            for field in STYLE_FIELDS
                        },
                    }
                    for row in data.get("items", [])
                ]
            }
        return original_demo_output(task_type, data)

    TaskService.create = create
    TaskService._semantic_errors = semantic_errors
    Pipeline._maybe_prepare_checks = maybe_prepare_checks
    Pipeline._apply_task = apply_task
    Pipeline._issue_style_polish_installed = True
    TaskService._issue_style_polish_installed = True
    demo_module._demo_output = demo_output
