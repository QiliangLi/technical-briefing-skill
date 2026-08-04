from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .db import Database
from .utils import now_iso, read_json, stable_hash, write_json

LOGGER = logging.getLogger(__name__)

BRIEF_FIELDS = ("core_conclusion", "mechanism", "result", "boundary", "project_relevance")
INCOMPLETE_ENDING_RE = re.compile(r"(?:…|\.\.\.|[，,:：;；、])(?:[”’\"）)\]]*)$")
COMPLETE_ENDING_RE = re.compile(r"[。！？.!?](?:[”’\"）)\]]*)$")


def brief_item_validation_errors(
    item: dict[str, Any],
    *,
    min_chars: int = 300,
    max_chars: int = 450,
) -> list[str]:
    errors: list[str] = []
    substantive = []
    for field in BRIEF_FIELDS:
        value = " ".join(str(item.get(field) or "").split())
        substantive.append(value)
        if not value:
            errors.append(f"{field} is empty")
            continue
        if INCOMPLETE_ENDING_RE.search(value) or not COMPLETE_ENDING_RE.search(value):
            errors.append(f"{field} must end with a complete sentence")
    total = len("".join(substantive))
    if total < min_chars or total > max_chars:
        errors.append(f"substantive text length {total} is outside {min_chars}-{max_chars}")
    return errors


class TaskService:
    def __init__(self, db: Database, root: Path, run_dir: Path):
        self.db = db
        self.root = root
        self.run_dir = run_dir

    def create(
        self,
        run_id: str,
        task_type: str,
        entity_id: str,
        input_data: dict[str, Any],
        *,
        prompt: str,
        schema: str,
        priority: float = 0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task_id = stable_hash(run_id, task_type, entity_id)
        task_dir = self.run_dir / "tasks" / task_type
        input_path = task_dir / f"{task_id}.input.json"
        output_path = task_dir / f"{task_id}.output.json"
        write_json(input_path, input_data)
        row = {
            "id": task_id,
            "run_id": run_id,
            "task_type": task_type,
            "entity_id": entity_id,
            "input_path": str(input_path.relative_to(self.root)),
            "output_path": str(output_path.relative_to(self.root)),
            "prompt_path": f"prompts/{prompt}",
            "schema_path": f"schemas/{schema}",
            "status": "PENDING",
            "priority": priority,
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO tasks(
                    id, run_id, task_type, entity_id, input_path, output_path,
                    prompt_path, schema_path, status, priority, metadata_json,
                    created_at, updated_at
                ) VALUES (
                    :id, :run_id, :task_type, :entity_id, :input_path, :output_path,
                    :prompt_path, :schema_path, :status, :priority, :metadata_json,
                    :created_at, :updated_at
                )
                """,
                row,
            )
        return row

    def list(self, run_id: str, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            return self.db.fetchall(
                "SELECT * FROM tasks WHERE run_id=? AND status=? ORDER BY priority DESC, created_at",
                (run_id, status),
            )
        return self.db.fetchall("SELECT * FROM tasks WHERE run_id=? ORDER BY status, priority DESC", (run_id,))

    def next(self, run_id: str) -> dict[str, Any] | None:
        return self.db.fetchone(
            "SELECT * FROM tasks WHERE run_id=? AND status='PENDING' ORDER BY priority DESC, created_at LIMIT 1",
            (run_id,),
        )

    def sync(self, run_id: str) -> tuple[int, int]:
        completed = failed = 0
        for task in self.list(run_id, "PENDING"):
            output_path = self.root / task["output_path"]
            if not output_path.exists():
                continue
            try:
                data = read_json(output_path)
                schema = read_json(self.root / task["schema_path"])
                errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
                if errors:
                    message = "; ".join(error.message for error in errors[:5])
                    raise ValueError(message)
                if task["task_type"] == "item_writing":
                    input_data = read_json(self.root / task["input_path"], {})
                    length = input_data.get("length") or {}
                    semantic_errors = brief_item_validation_errors(
                        data,
                        min_chars=int(length.get("min_chars", 300)),
                        max_chars=int(length.get("max_chars", 450)),
                    )
                    if semantic_errors:
                        raise ValueError("; ".join(semantic_errors))
                elif task["task_type"] == "fact_check" and data.get("corrected_item"):
                    input_data = read_json(self.root / task["input_path"], {})
                    length = input_data.get("length") or {}
                    semantic_errors = brief_item_validation_errors(
                        data["corrected_item"],
                        min_chars=int(length.get("min_chars", 300)),
                        max_chars=int(length.get("max_chars", 450)),
                    )
                    if semantic_errors:
                        raise ValueError("corrected_item: " + "; ".join(semantic_errors))
                self.db.execute(
                    "UPDATE tasks SET status='COMPLETED', updated_at=?, error=NULL WHERE id=?",
                    (now_iso(), task["id"]),
                )
                completed += 1
            except Exception as exc:
                LOGGER.warning("Task output invalid %s: %s", task["id"], exc)
                self.db.execute(
                    "UPDATE tasks SET status='INVALID', updated_at=?, error=? WHERE id=?",
                    (now_iso(), str(exc), task["id"]),
                )
                failed += 1
        return completed, failed

    def reopen_invalid(self, run_id: str) -> int:
        rows = self.db.fetchall("SELECT id FROM tasks WHERE run_id=? AND status='INVALID'", (run_id,))
        for row in rows:
            self.db.execute("UPDATE tasks SET status='PENDING', error=NULL, updated_at=? WHERE id=?", (now_iso(), row["id"]))
        return len(rows)

    def instructions(self, task: dict[str, Any]) -> str:
        return (
            f"Task {task['id']} ({task['task_type']})\n"
            f"1. Read {task['prompt_path']}\n"
            f"2. Read {task['input_path']}\n"
            f"3. Produce JSON matching {task['schema_path']}\n"
            f"4. Write it to {task['output_path']}\n"
            f"5. Run: python briefing.py advance --run {task['run_id']}"
        )
