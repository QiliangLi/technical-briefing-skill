from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .db import Database
from .utils import canonicalize_url, normalize_text, now_iso, read_json, source_url_is_resolved, stable_hash, write_json

LOGGER = logging.getLogger(__name__)

BRIEF_FIELDS = ("core_conclusion", "mechanism", "result", "boundary", "project_relevance")
INCOMPLETE_ENDING_RE = re.compile(r"(?:…|\.\.\.|[，,:：;；、])(?:[”’\"）)\]]*)$")
COMPLETE_ENDING_RE = re.compile(r"[。！？.!?](?:[”’\"）)\]]*)$")
TASK_BINDING_KEY = "_task"


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


def synthesis_item_payload(row: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """Expose only the selected core-item fields needed for synthesis."""
    return {
        "brief_item_id": row["id"],
        "title": item.get("title"),
        "topic_id": row.get("topic_id"),
        "topic_name": item.get("topic_name"),
        "direction_id": row.get("direction_id"),
        "core_conclusion": item.get("core_conclusion"),
        "mechanism": item.get("mechanism"),
        "result": item.get("result"),
        "boundary": item.get("boundary"),
        "project_relevance": item.get("project_relevance"),
        "score": float(row.get("score") or item.get("score") or 0),
        "item_role": row.get("item_role", "core"),
    }


def issue_synthesis_validation_errors(
    output: dict[str, Any],
    input_data: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    input_items = input_data.get("items") or []
    items_by_id = {
        str(item.get("brief_item_id")): item
        for item in input_items
        if item.get("brief_item_id")
    }
    judgements = output.get("judgements") or []
    single_evidence_count = 0
    for index, judgement in enumerate(judgements):
        if not isinstance(judgement, dict):
            continue
        evidence_ids = [str(value) for value in judgement.get("evidence_item_ids") or []]
        if len(evidence_ids) != len(set(evidence_ids)):
            errors.append(f"judgement {index} contains duplicate evidence_item_ids")
        unknown = sorted(set(evidence_ids) - set(items_by_id))
        if unknown:
            errors.append(f"judgement {index} references unknown evidence_item_ids: {', '.join(unknown)}")
        if len(evidence_ids) <= 1:
            single_evidence_count += 1
        title = " ".join(str(judgement.get("title") or "").split())
        body = " ".join(str(judgement.get("body") or "").split())
        if "对应：" in body or "对应:" in body:
            errors.append(f"judgement {index} body must not contain 对应：")
        if INCOMPLETE_ENDING_RE.search(title):
            errors.append(f"judgement {index} title has an incomplete ending")
        if INCOMPLETE_ENDING_RE.search(body):
            errors.append(f"judgement {index} body has an incomplete ending")
        if not COMPLETE_ENDING_RE.search(body):
            errors.append(f"judgement {index} body must contain a complete sentence")
        for item in input_items:
            if normalize_text(body) in {
                normalize_text(item.get("title")),
                normalize_text(item.get("core_conclusion")),
            }:
                errors.append(f"judgement {index} body must synthesize rather than copy one item")
                break
            if normalize_text(title) == normalize_text(item.get("title")):
                errors.append(f"judgement {index} title must not copy an item title")
                break
    if len(input_items) >= 2 and judgements and single_evidence_count == len(judgements):
        errors.append("multi-item synthesis cannot make every judgement depend on only one item")
    headline = " ".join(str(output.get("headline") or "").split())
    if re.search(r"本期(?:共)?筛选出\s*\d+\s*条", headline):
        errors.append("headline must describe the technical issue, not the selection process")
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
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        task_id = stable_hash(run_id, task_type, entity_id)
        task_dir = self.run_dir / "tasks" / task_type
        input_path = task_dir / f"{task_id}.input.json"
        output_path = task_dir / f"{task_id}.output.json"
        if TASK_BINDING_KEY in input_data:
            raise ValueError(f"{TASK_BINDING_KEY} is reserved for deterministic task binding")
        input_digest = stable_hash(
            json.dumps(input_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            length=32,
        )
        binding = {
            "id": task_id,
            "type": task_type,
            "entity_id": entity_id,
            "input_digest": input_digest,
        }
        write_json(input_path, {TASK_BINDING_KEY: binding, **input_data})
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
        if replace_existing:
            output_path.unlink(missing_ok=True)
        with self.db.connect() as conn:
            sql = (
                """
                INSERT INTO tasks(
                    id, run_id, task_type, entity_id, input_path, output_path,
                    prompt_path, schema_path, status, priority, metadata_json,
                    created_at, updated_at
                ) VALUES (
                    :id, :run_id, :task_type, :entity_id, :input_path, :output_path,
                    :prompt_path, :schema_path, :status, :priority, :metadata_json,
                    :created_at, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    input_path=excluded.input_path,
                    output_path=excluded.output_path,
                    prompt_path=excluded.prompt_path,
                    schema_path=excluded.schema_path,
                    status='PENDING',
                    priority=excluded.priority,
                    metadata_json=excluded.metadata_json,
                    error=NULL,
                    updated_at=excluded.updated_at
                """
                if replace_existing
                else """
                INSERT OR IGNORE INTO tasks(
                    id, run_id, task_type, entity_id, input_path, output_path,
                    prompt_path, schema_path, status, priority, metadata_json,
                    created_at, updated_at
                ) VALUES (
                    :id, :run_id, :task_type, :entity_id, :input_path, :output_path,
                    :prompt_path, :schema_path, :status, :priority, :metadata_json,
                    :created_at, :updated_at
                )
                """
            )
            conn.execute(sql, row)
        return row

    def read_result(self, task: dict[str, Any], raw: dict[str, Any] | None = None) -> dict[str, Any]:
        """Read a task result and fail closed when it is bound to another task."""
        data = dict(raw if raw is not None else read_json(self.root / task["output_path"]))
        input_data = read_json(self.root / task["input_path"], {})
        expected = input_data.get(TASK_BINDING_KEY)
        if expected is not None:
            actual = data.pop(TASK_BINDING_KEY, None)
            if actual != expected:
                raise ValueError(
                    "task binding mismatch: output must echo the exact _task object from its input"
                )
        else:
            data.pop(TASK_BINDING_KEY, None)
        return data

    @staticmethod
    def _source_urls(sources: list[dict[str, Any]] | None) -> set[str]:
        return {
            canonicalize_url(str(source.get("url") or ""))
            for source in (sources or [])
            if source.get("url")
        }

    def _semantic_errors(
        self,
        task: dict[str, Any],
        input_data: dict[str, Any],
        data: dict[str, Any],
    ) -> list[str]:
        errors: list[str] = []
        entity_field = {
            "relevance_review": "candidate_id",
            "fact_extraction": "candidate_id",
            "item_writing": "event_id",
            "issue_synthesis": "issue_id",
        }.get(task["task_type"])
        if entity_field and str(input_data.get(entity_field) or "") != str(task["entity_id"]):
            errors.append(f"input {entity_field} does not match task entity_id")

        if task["task_type"] == "fact_extraction":
            source = input_data.get("source") or {}
            document = input_data.get("document") or {}
            if normalize_text(data.get("title")) != normalize_text(source.get("title")):
                errors.append("fact title must exactly identify the tasked source title")
            if data.get("primary_source_resolved"):
                if source.get("discovery_only"):
                    errors.append("primary_source_resolved cannot be true for a discovery-only source")
                if not source_url_is_resolved(source.get("url")):
                    errors.append("primary_source_resolved requires a specific, resolved source URL")
                if document.get("fetch_status") != "FETCHED":
                    errors.append("primary_source_resolved requires a fetched source document")

        if task["task_type"] == "agent_web_search":
            for index, result in enumerate(data.get("results", [])):
                if result.get("primary") and not source_url_is_resolved(result.get("url")):
                    errors.append(f"primary web-search result {index} requires a specific source URL")
                if result.get("primary") and result.get("source_level") != "A":
                    errors.append(f"primary web-search result {index} must be A-level")

        if task["task_type"] == "item_writing":
            topic = input_data.get("topic") or {}
            direction = input_data.get("direction") or {}
            if data.get("topic_name") != topic.get("name"):
                errors.append("item topic_name must exactly match the tasked topic")
            if data.get("direction_name") != direction.get("name"):
                errors.append("item direction_name must exactly match the tasked direction")
            try:
                if float(data.get("score")) != float(input_data.get("score")):
                    errors.append("item score must exactly match the deterministic input score")
            except (TypeError, ValueError):
                errors.append("item score is not comparable to the deterministic input score")
            allowed_urls = self._source_urls(input_data.get("sources"))
            output_urls = self._source_urls(data.get("sources"))
            if not output_urls or not output_urls.issubset(allowed_urls):
                errors.append("item sources must be a non-empty subset of the tasked source URLs")
            if not any(
                source.get("source_level") == "A"
                and source.get("primary") is True
                and source_url_is_resolved(source.get("url"))
                for source in data.get("sources", [])
            ):
                errors.append("item requires at least one resolved primary A-level source")

        if task["task_type"] == "fact_check":
            item = input_data.get("brief_item") or {}
            checked_item = data.get("corrected_item") or item
            if data.get("corrected_item"):
                for field in ("topic_name", "direction_name", "published_at", "score"):
                    if checked_item.get(field) != item.get(field):
                        errors.append(f"fact check cannot change immutable field {field}")
                if self._source_urls(checked_item.get("sources")) != self._source_urls(item.get("sources")):
                    errors.append("fact check cannot replace or invent source URLs")
            if data.get("pass"):
                if not any(bool(fact.get("primary_source_resolved")) for fact in input_data.get("facts", [])):
                    errors.append("fact check cannot pass without resolved primary facts")
                if not any(
                    source.get("source_level") == "A"
                    and source.get("primary") is True
                    and source_url_is_resolved(source.get("url"))
                    for source in checked_item.get("sources", [])
                ):
                    errors.append("fact check cannot pass without a resolved primary A-level source URL")

        if task["task_type"] == "issue_synthesis":
            expected_topics = {
                str(item.get("topic_name"))
                for item in input_data.get("items", [])
                if item.get("topic_name")
            }
            if set(map(str, data.get("topic_names", []))) != expected_topics:
                errors.append("issue synthesis topic_names must exactly match the tasked core items")
            errors.extend(issue_synthesis_validation_errors(data, input_data))
        return errors

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
                raw = read_json(output_path)
                data = self.read_result(task, raw)
                input_data = read_json(self.root / task["input_path"], {})
                schema = read_json(self.root / task["schema_path"])
                errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
                if errors:
                    message = "; ".join(error.message for error in errors[:5])
                    raise ValueError(message)
                if task["task_type"] == "item_writing":
                    length = input_data.get("length") or {}
                    semantic_errors = brief_item_validation_errors(
                        data,
                        min_chars=int(length.get("min_chars", 300)),
                        max_chars=int(length.get("max_chars", 450)),
                    )
                    if semantic_errors:
                        raise ValueError("; ".join(semantic_errors))
                elif task["task_type"] == "fact_check" and data.get("corrected_item"):
                    item_schema = read_json(self.root / "schemas" / "brief-item.schema.json")
                    item_errors = sorted(
                        Draft202012Validator(item_schema).iter_errors(data["corrected_item"]),
                        key=lambda error: list(error.path),
                    )
                    if item_errors:
                        raise ValueError(
                            "corrected_item: " + "; ".join(error.message for error in item_errors[:5])
                        )
                    length = input_data.get("length") or {}
                    semantic_errors = brief_item_validation_errors(
                        data["corrected_item"],
                        min_chars=int(length.get("min_chars", 300)),
                        max_chars=int(length.get("max_chars", 450)),
                    )
                    if semantic_errors:
                        raise ValueError("corrected_item: " + "; ".join(semantic_errors))
                cross_stage_errors = self._semantic_errors(task, input_data, data)
                if cross_stage_errors:
                    raise ValueError("; ".join(cross_stage_errors))
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
        try:
            metadata = json.loads(task.get("metadata_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            metadata = {}
        required_skills = [str(skill) for skill in metadata.get("required_skills") or [] if skill]
        skill_lines = ""
        if required_skills:
            skill_names = ", ".join(f"${skill}" for skill in required_skills)
            skill_lines = (
                f"4. Required skills: {skill_names}\n"
                "5. Build the factual draft first, then use the required skills in the listed order before producing final JSON; do not let them add or change facts\n"
            )
            transport_step = 6
        else:
            transport_step = 4
        return (
            f"Task {task['id']} ({task['task_type']})\n"
            f"1. Read {task['prompt_path']}\n"
            f"2. Read {task['input_path']}\n"
            f"3. Produce result fields matching {task['schema_path']}\n"
            f"{skill_lines}"
            f"{transport_step}. Also copy the input's exact `_task` object into the top level of the output JSON; it is transport metadata validated separately from the result schema\n"
            f"{transport_step + 1}. Write only this task's result to {task['output_path']}\n"
            f"{transport_step + 2}. Run: python3 briefing.py advance --run {task['run_id']}"
        )
