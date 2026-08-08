from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .tasks import TASK_BINDING_KEY
from .utils import now_iso, read_json, write_json


REPAIRABLE_ERROR_MARKERS = (
    "task binding mismatch",
    "must end with a complete sentence",
    "has an incomplete ending",
    "substantive text length",
    "topic_name must exactly match",
    "direction_name must exactly match",
    "score must exactly match",
    "sources must be a non-empty subset",
    "cannot change immutable field",
    "cannot replace or invent source urls",
    "contains duplicate ids",
    "contains duplicate evidence_item_ids",
    "omits ids",
    "references unknown ids",
    "references unknown evidence_item_ids",
    "must return exactly one result per input",
    "topic_names must exactly match",
    "body must not contain 对应",
    "title must not copy an item title",
    "body must synthesize rather than copy one item",
)


def is_targeted_repairable(error: str | None) -> bool:
    value = str(error or "").lower()
    return bool(value) and any(marker.lower() in value for marker in REPAIRABLE_ERROR_MARKERS)


def _source_urls(value: list[dict[str, Any]] | None) -> list[str]:
    return [str(row.get("url") or "") for row in (value or []) if row.get("url")]


def deterministic_constraints(task: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
    task_type = str(task.get("task_type") or "")
    result: dict[str, Any] = {
        "task_id": task.get("id"),
        "task_type": task_type,
        "entity_id": task.get("entity_id"),
        "required_task_binding": input_data.get(TASK_BINDING_KEY),
    }
    if task_type == "fact_extraction":
        source = input_data.get("source") or {}
        document = input_data.get("document") or {}
        result.update(
            {
                "candidate_id": input_data.get("candidate_id"),
                "source_title": source.get("title"),
                "source_url": source.get("url"),
                "source_level": source.get("source_level"),
                "source_discovery_only": bool(source.get("discovery_only")),
                "document_fetch_status": document.get("fetch_status"),
            }
        )
    elif task_type == "item_writing":
        result.update(
            {
                "event_id": input_data.get("event_id"),
                "topic_name": (input_data.get("topic") or {}).get("name"),
                "direction_name": (input_data.get("direction") or {}).get("name"),
                "score": input_data.get("score"),
                "allowed_source_urls": _source_urls(input_data.get("sources")),
                "length": input_data.get("length") or {},
            }
        )
    elif task_type == "item_writing_batch":
        result["items"] = [
            {
                "event_id": row.get("event_id"),
                "topic_name": (row.get("topic") or {}).get("name"),
                "direction_name": (row.get("direction") or {}).get("name"),
                "score": row.get("score"),
                "allowed_source_urls": _source_urls(row.get("sources")),
                "length": row.get("length") or {},
            }
            for row in input_data.get("items") or []
        ]
    elif task_type == "fact_check":
        item = input_data.get("brief_item") or {}
        result["immutable_item"] = {
            key: item.get(key)
            for key in ("topic_name", "direction_name", "published_at", "score")
        }
        result["allowed_source_urls"] = _source_urls(item.get("sources"))
        result["length"] = input_data.get("length") or {}
    elif task_type == "fact_check_batch":
        result["checks"] = [
            {
                "brief_item_id": row.get("brief_item_id"),
                "immutable_item": {
                    key: (row.get("brief_item") or {}).get(key)
                    for key in ("topic_name", "direction_name", "published_at", "score")
                },
                "allowed_source_urls": _source_urls((row.get("brief_item") or {}).get("sources")),
                "length": row.get("length") or {},
            }
            for row in input_data.get("checks") or []
        ]
    elif task_type == "issue_synthesis":
        result.update(
            {
                "allowed_evidence_item_ids": [
                    row.get("brief_item_id") for row in input_data.get("items") or []
                    if row.get("brief_item_id")
                ],
                "required_topic_names": sorted(
                    {
                        str(row.get("topic_name"))
                        for row in input_data.get("items") or []
                        if row.get("topic_name")
                    }
                ),
                "max_judgements": input_data.get("max_judgements"),
            }
        )
    elif task_type == "relevance_batch":
        result["candidate_ids"] = [
            row.get("candidate_id") for row in input_data.get("candidates") or []
            if row.get("candidate_id")
        ]
    return result


def prepare_targeted_repair(service, task: dict[str, Any]) -> str | None:
    """Write a small sidecar containing only the invalid result and fixed constraints."""

    error = str(task.get("error") or "")
    if not is_targeted_repairable(error):
        return None
    try:
        input_data = read_json(service.root / task["input_path"], {})
        invalid_output = read_json(service.root / task["output_path"], {})
    except Exception:
        return None
    if not isinstance(input_data, dict) or not isinstance(invalid_output, dict):
        return None

    try:
        metadata = json.loads(task.get("metadata_json") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        metadata = {}
    attempts = int(metadata.get("targeted_repair_attempts") or 0)
    if attempts >= 1:
        return None

    path = service.run_dir / "tasks" / "repair" / f"{task['id']}.repair.json"
    payload = {
        "task_id": task["id"],
        "task_type": task["task_type"],
        "validation_error": error,
        "invalid_output": invalid_output,
        "deterministic_constraints": deterministic_constraints(task, input_data),
        "repair_rules": [
            "Do not read the original task input, Evidence Pack, full text, or any external source.",
            "Do not add new factual claims, numbers, sources, mechanisms, or conclusions.",
            "Repair only the validator-reported structural/formatting/immutable-field issue using the existing output.",
            "If shortening is needed, delete redundancy; if wording must change, preserve the existing factual meaning.",
            "Return a complete replacement JSON object that matches the original task schema.",
            "Echo the exact required_task_binding as the top-level _task object.",
        ],
        "prepared_at": now_iso(),
    }
    write_json(path, payload)
    metadata.update(
        {
            "targeted_repair": True,
            "targeted_repair_attempts": attempts + 1,
            "repair_input_path": str(path.relative_to(service.root)),
            "repair_input_chars": len(json.dumps(payload, ensure_ascii=False)),
            "original_input_chars": len(json.dumps(input_data, ensure_ascii=False)),
        }
    )
    service.db.execute(
        "UPDATE tasks SET metadata_json=?, status='PENDING', error=NULL, updated_at=? WHERE id=?",
        (json.dumps(metadata, ensure_ascii=False), now_iso(), task["id"]),
    )
    return str(path.relative_to(service.root))


def install_invalid_targeted_repair() -> None:
    """Retry simple INVALID outputs without re-reading expensive source evidence."""

    from .tasks import TaskService

    if getattr(TaskService, "_invalid_targeted_repair_installed", False):
        return

    original_instructions = TaskService.instructions
    original_peek_group = getattr(TaskService, "peek_group", None)

    def reopen_invalid(self, run_id: str) -> int:
        rows = self.db.fetchall(
            "SELECT * FROM tasks WHERE run_id=? AND status='INVALID' ORDER BY priority DESC, created_at",
            (run_id,),
        )
        for task in rows:
            if prepare_targeted_repair(self, task):
                continue
            try:
                metadata = json.loads(task.get("metadata_json") or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                metadata = {}
            metadata.pop("targeted_repair", None)
            metadata.pop("repair_input_path", None)
            self.db.execute(
                "UPDATE tasks SET status='PENDING', error=NULL, metadata_json=?, updated_at=? WHERE id=?",
                (json.dumps(metadata, ensure_ascii=False), now_iso(), task["id"]),
            )
        return len(rows)

    def instructions(self, task: dict[str, Any]) -> str:
        try:
            metadata = json.loads(task.get("metadata_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            metadata = {}
        repair_path = str(metadata.get("repair_input_path") or "")
        if not metadata.get("targeted_repair") or not repair_path:
            return original_instructions(self, task)
        return (
            f"Task {task['id']} ({task['task_type']}) targeted validation repair\n"
            "1. Read prompts/task-output-repair.md\n"
            f"2. Read ONLY {repair_path}\n"
            f"3. Match the original result schema: {task['schema_path']}\n"
            "4. Do NOT read the original task input, Evidence Pack, full text, project context, or external sources\n"
            "5. Preserve all existing factual meaning; add no new facts or numbers\n"
            "6. Copy deterministic_constraints.required_task_binding exactly into the top-level `_task` field\n"
            f"7. Write the complete repaired JSON to {task['output_path']}\n"
            f"8. Run: python3 briefing.py advance --run {task['run_id']}"
        )

    def peek_group(self, run_id: str, **kwargs):
        group = original_peek_group(self, run_id, **kwargs) if original_peek_group else []
        if not group:
            return group
        first = group[0]
        try:
            metadata = json.loads(first.get("metadata_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            metadata = {}
        if metadata.get("targeted_repair"):
            return [first]
        return group

    TaskService.reopen_invalid = reopen_invalid
    TaskService.instructions = instructions
    if original_peek_group:
        TaskService.peek_group = peek_group
    TaskService._invalid_targeted_repair_installed = True
