from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from .issue_style_polish import STYLE_FIELDS
from .reader_writing_contract import item_writing_contract_errors
from .tasks import brief_item_validation_errors
from .utils import read_json, write_json


TASK_TYPE = "fact_check_batch"
PATCH_PROMPT = "fact-check-patch-batch.md"
PATCH_SCHEMA = "fact-check-patch-batch.schema.json"
ALLOWED_FIELDS = frozenset(STYLE_FIELDS)


def apply_minimal_corrections(
    item: dict[str, Any],
    corrections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply guarded field patches without giving Fact Check whole-item authority."""

    patched = dict(item)
    seen: set[str] = set()
    for correction in corrections:
        field = str(correction.get("field") or "")
        if field not in ALLOWED_FIELDS:
            raise ValueError(f"Fact Check cannot patch field {field}")
        if field in seen:
            raise ValueError(f"Fact Check returned multiple patches for field {field}")
        seen.add(field)
        before = str(correction.get("before") or "")
        current = str(patched.get(field) or "")
        if current != before:
            raise ValueError(
                f"Fact Check patch for {field} is stale: before text does not match current item"
            )
        patched[field] = str(correction.get("after") or "")
    return patched


def _reader_item(item: dict[str, Any]) -> dict[str, Any]:
    """Drop internal sidecars before validating the reader-facing item schema."""

    return {key: value for key, value in item.items() if key != "_provenance"}


def _patch_contract_errors(
    root,
    result: dict[str, Any],
    check_input: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    corrections = list(result.get("corrections") or [])
    if result.get("pass") is False and corrections:
        errors.append("failed fact check must not apply corrections")
        return errors

    original = dict(check_input.get("brief_item") or {})
    try:
        patched = apply_minimal_corrections(original, corrections)
    except ValueError as exc:
        return [str(exc)]

    validated = _reader_item(patched)
    item_schema = read_json(root / "schemas" / "brief-item.schema.json")
    validator = Draft202012Validator(item_schema)
    schema_errors = sorted(validator.iter_errors(validated), key=lambda error: list(error.path))
    errors.extend(f"patched item: {error.message}" for error in schema_errors[:5])

    length = check_input.get("length") or {}
    errors.extend(
        f"patched item: {message}"
        for message in brief_item_validation_errors(
            validated,
            min_chars=int(length.get("min_chars", 180)),
            max_chars=int(length.get("max_chars", 260)),
        )
    )
    errors.extend(f"patched item: {message}" for message in item_writing_contract_errors(validated))
    return errors


def install_minimal_fact_check_patches() -> None:
    """Make style output final except for explicit, guarded factual field patches."""

    from . import demo as demo_module
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_minimal_fact_check_patches_installed", False):
        return

    original_create = TaskService.create
    original_apply = Pipeline._apply_task
    original_semantic_errors = TaskService._semantic_errors
    original_demo_output = demo_module._demo_output

    def create(
        self,
        run_id: str,
        task_type: str,
        entity_id: str,
        input_data: dict[str, Any],
        **kwargs,
    ):
        if task_type == TASK_TYPE:
            kwargs["prompt"] = PATCH_PROMPT
            kwargs["schema"] = PATCH_SCHEMA
            metadata = dict(kwargs.get("metadata") or {})
            metadata.update(
                {
                    "correction_mode": "minimal_field_patch",
                    "whole_item_rewrite_allowed": False,
                }
            )
            kwargs["metadata"] = metadata
        return original_create(self, run_id, task_type, entity_id, input_data, **kwargs)

    TaskService.create = create

    def apply_task(self, task: dict[str, Any]) -> None:
        if task.get("task_type") != TASK_TYPE:
            return original_apply(self, task)

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
            corrections = list(result.get("corrections") or [])
            patched = apply_minimal_corrections(current, corrections)
            if patched != current:
                write_json(self.root / row["json_path"], patched)
            self.db.execute(
                "UPDATE brief_items SET fact_check_status=? WHERE id=?",
                ("PASS" if result.get("pass") else "FAIL", brief_item_id),
            )

    Pipeline._apply_task = apply_task

    def semantic_errors(
        self,
        task: dict[str, Any],
        input_data: dict[str, Any],
        data: dict[str, Any],
    ) -> list[str]:
        errors = list(original_semantic_errors(self, task, input_data, data))

        if task.get("task_type") == "item_style_polish":
            inputs = {
                str(row.get("brief_item_id") or ""): row
                for row in input_data.get("items") or []
            }
            for result in data.get("results") or []:
                brief_item_id = str(result.get("brief_item_id") or "")
                source = inputs.get(brief_item_id)
                if not source:
                    continue
                reconstructed = dict(source.get("item") or {})
                for field in STYLE_FIELDS:
                    reconstructed[field] = result.get(field)
                errors.extend(
                    f"item_style_polish {brief_item_id}: {message}"
                    for message in item_writing_contract_errors(_reader_item(reconstructed))
                )

        elif task.get("task_type") == TASK_TYPE:
            checks = {
                str(row.get("brief_item_id") or ""): row
                for row in input_data.get("checks") or []
            }
            for result in data.get("results") or []:
                brief_item_id = str(result.get("brief_item_id") or "")
                check_input = checks.get(brief_item_id)
                if not check_input:
                    continue
                errors.extend(
                    f"fact_check_batch {brief_item_id}: {message}"
                    for message in _patch_contract_errors(self.root, result, check_input)
                )
        return list(dict.fromkeys(errors))

    TaskService._semantic_errors = semantic_errors

    def demo_output(task_type: str, data: dict[str, Any]):
        if task_type == TASK_TYPE:
            return {
                "results": [
                    {
                        "brief_item_id": row["brief_item_id"],
                        "pass": True,
                        "issues": [],
                        "corrections": [],
                    }
                    for row in data.get("checks") or []
                ]
            }
        return original_demo_output(task_type, data)

    demo_module._demo_output = demo_output
    Pipeline._minimal_fact_check_patches_installed = True
    TaskService._minimal_fact_check_patches_installed = True
