from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .tasks import COMPLETE_ENDING_RE
from .utils import read_json, stable_hash, write_json


TASK_TYPE = "reader_projection"
PROMPT = "reader-item-writing.md"
SCHEMA = "reader-item-writing.schema.json"
CONTRACT_VERSION = 1
MACHINE_FIELDS = (
    "title",
    "core_conclusion",
    "mechanism",
    "result",
    "boundary",
    "project_relevance",
)
READER_USED_FIELDS = frozenset(MACHINE_FIELDS)
INTERNAL_TAXONOMY_TERMS = ("TPN卡", "芯片卡", "介质卡", "项目卡")
# These fields are added while rebuilding the publishable issue. They describe
# placement/rendering metadata, not the fact-checked machine item itself. A
# reader sidecar may be generated before the issue wrapper exists, so including
# them in the source hash makes otherwise valid sidecars look stale.
ISSUE_WRAPPER_FIELDS = frozenset(
    {
        "brief_item_id",
        "item_role",
        "topic_id",
        "direction_id",
        "fact_check_status",
        "anchor_id",
        "visual_plan",
        "illustration",
        "brief_upgrade",
        "brief_upgrade_origin",
    }
)
SLOT_LABEL_RE = re.compile(r"(?:^|[。！？!?\n])\s*(?:机制|证据|边界|启发|项目相关性)\s*[：:]")
FORMULAIC_TITLE_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9+._-]{1,24}(?:用|让|把|靠|按|以)[^：:]{4,}$"
)
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])\d+(?:\.\d+)?")


def reader_item_path(root: Path, run_id: str, brief_item_id: str) -> Path:
    """Reader prose is run-scoped output, never a cross-run SQLite cache object."""

    return root / "workspace" / "runs" / run_id / "reader_items" / f"{brief_item_id}.json"


def machine_item_hash(item: dict[str, Any]) -> str:
    """Bind reader prose to the exact fact-checked machine item it paraphrases."""

    payload = {
        key: value
        for key, value in item.items()
        if key != "_provenance" and key not in ISSUE_WRAPPER_FIELDS
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return stable_hash("reader-source-v1", encoded, length=32)


def legacy_machine_item_hash(item: dict[str, Any]) -> str:
    """Hash used by archives written before issue-wrapper fields were normalized."""

    payload = {key: value for key, value in item.items() if key != "_provenance"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return stable_hash("reader-source-v1", encoded, length=32)


def _reader_projection_payload(pipeline, selected: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the current-run reader task from final fact-checked selected items.

    Selection happens after Fact Check. A Fact Cache hit may have supplied the facts
    that produced an item, but cache provenance is deliberately irrelevant here:
    every selected item receives a fresh current-run reader projection.
    """

    items: list[dict[str, Any]] = []
    for row in selected:
        item = read_json(pipeline.root / row["json_path"], {})
        machine = {key: value for key, value in item.items() if key != "_provenance"}
        items.append(
            {
                "brief_item_id": str(row["id"]),
                "item_role": str(row.get("item_role") or "core"),
                "source_item_hash": machine_item_hash(item),
                "machine_item": machine,
            }
        )
    return {
        "reader_contract_version": CONTRACT_VERSION,
        "items": items,
        "constraints": {
            "reader_copy_is_selective_not_lossless": True,
            "machine_fact_fields_remain_immutable": True,
            "takeaway_is_optional": True,
            "do_not_render_machine_slot_labels": True,
            "facts_may_come_from_local_sqlite_cache_but_reader_copy_must_be_current_run": True,
        },
    }


def _projection_entity_id(run_id: str, payload: dict[str, Any]) -> str:
    hashes = [str(row.get("source_item_hash") or "") for row in payload.get("items") or []]
    return stable_hash(run_id, TASK_TYPE, f"v{CONTRACT_VERSION}", *hashes)


def _all_reader_text(result: dict[str, Any]) -> str:
    parts = [str(result.get("title") or ""), str(result.get("lead") or "")]
    parts.extend(str(value or "") for value in result.get("body") or [])
    takeaway = result.get("takeaway")
    if takeaway:
        parts.append(str(takeaway))
    return "\n".join(parts)


def _reader_contract_errors(result: dict[str, Any], machine_item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    title = str(result.get("title") or "").strip()
    lead = str(result.get("lead") or "").strip()
    body = [str(value or "").strip() for value in result.get("body") or []]
    takeaway = result.get("takeaway")
    takeaway_text = str(takeaway or "").strip()

    if not re.search(r"[\u3400-\u9fff]", title):
        errors.append("reader title must contain Chinese reader-facing wording")
    if FORMULAIC_TITLE_RE.match(title):
        errors.append("reader title must not use the repetitive Project+用/让/把/靠/按/以 formula")
    for label, text in (("lead", lead), *[(f"body[{i}]", value) for i, value in enumerate(body)]):
        if text and not COMPLETE_ENDING_RE.search(text):
            errors.append(f"reader {label} must end with a complete sentence")
    if takeaway_text and not COMPLETE_ENDING_RE.search(takeaway_text):
        errors.append("reader takeaway must end with a complete sentence")

    reader_text = _all_reader_text(result)
    if SLOT_LABEL_RE.search(reader_text):
        errors.append("reader copy must not reproduce the machine 机制/证据/边界/启发 slot layout")
    leaked = [term for term in INTERNAL_TAXONOMY_TERMS if term in reader_text]
    if leaked:
        errors.append("reader copy leaks internal topic-card shorthand: " + ", ".join(leaked))

    machine_text = "\n".join(str(machine_item.get(field) or "") for field in MACHINE_FIELDS)
    machine_numbers = set(NUMBER_RE.findall(machine_text))
    invented_numbers = sorted(set(NUMBER_RE.findall(reader_text)) - machine_numbers)
    if invented_numbers:
        errors.append("reader copy introduces numbers absent from the fact-checked item: " + ", ".join(invented_numbers))

    used_fields = [str(value) for value in result.get("used_fields") or []]
    if not used_fields:
        errors.append("reader item must declare at least one supporting machine field")
    unknown = sorted(set(used_fields) - READER_USED_FIELDS)
    if unknown:
        errors.append("reader item references unknown supporting fields: " + ", ".join(unknown))
    if not set(used_fields) & {"core_conclusion", "mechanism", "result"}:
        errors.append("reader item must be grounded in at least one substantive fact field")
    return errors


def _reader_sidecar_current(root: Path, run_id: str, row: dict[str, Any]) -> bool:
    path = reader_item_path(root, run_id, str(row["id"]))
    data = read_json(path, {})
    if not data:
        return False
    item = read_json(root / row["json_path"], {})
    provenance = data.get("_provenance") or {}
    return (
        int(data.get("reader_version") or 0) == CONTRACT_VERSION
        and str(provenance.get("source_item_hash") or "") == machine_item_hash(item)
        and str(provenance.get("run_id") or "") == run_id
    )


def _install_fact_check_first(pipeline_cls) -> None:
    """Bypass the old pre-Fact-Check style pass for new batched runs.

    Existing item_style_polish tasks still resume through the legacy wrapper. New
    runs go Item Draft -> Fact Check -> Reader Projection, so the machine fact model
    is final before any lossy reader-oriented rewriting happens.
    """

    from .editorial_batch import _pack_batches, _policy, plan_fact_check_entries

    legacy_style_prepare_checks = pipeline_cls._maybe_prepare_checks

    def maybe_prepare_checks(self) -> None:
        # Already-started runs keep the exact historical contract.
        if self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type='item_style_polish' LIMIT 1",
            (self.run_id,),
        ):
            return legacy_style_prepare_checks(self)
        standalone = self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type='item_writing' LIMIT 1",
            (self.run_id,),
        )
        batched = self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type='item_writing_batch' LIMIT 1",
            (self.run_id,),
        )
        if standalone and not batched:
            return legacy_style_prepare_checks(self)

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
        if self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type IN ('fact_check','fact_check_batch') LIMIT 1",
            (self.run_id,),
        ):
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

    pipeline_cls._maybe_prepare_checks = maybe_prepare_checks


def install_reader_projection() -> None:
    """Generate flexible reader prose after Fact Check and render it from run sidecars."""

    from . import demo as demo_module
    from .emailer import EmailService
    from .issue_stage import _selected_issue_rows
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_reader_projection_installed", False):
        return

    _install_fact_check_first(Pipeline)

    original_prepare_issue = Pipeline._maybe_prepare_issue
    original_apply_task = Pipeline._apply_task
    original_semantic_errors = TaskService._semantic_errors
    original_demo_output = demo_module._demo_output
    original_topic_groups = EmailService._topic_groups

    def maybe_prepare_issue(self) -> None:
        # Legacy/interrupted runs that already own an issue stay untouched.
        if self.db.fetchone("SELECT 1 FROM issues WHERE run_id=?", (self.run_id,)):
            return original_prepare_issue(self)
        pending_checks = self.db.fetchone(
            """
            SELECT COUNT(*) AS n FROM tasks
            WHERE run_id=? AND task_type IN ('fact_check','fact_check_batch')
              AND status IN ('PENDING','INVALID','COMPLETED')
            """,
            (self.run_id,),
        )["n"]
        if pending_checks:
            return

        selected = _selected_issue_rows(self)
        if not selected:
            return original_prepare_issue(self)
        payload = _reader_projection_payload(self, selected)
        entity_id = _projection_entity_id(self.run_id, payload)
        task = self.db.fetchone(
            "SELECT * FROM tasks WHERE run_id=? AND task_type=? AND entity_id=? LIMIT 1",
            (self.run_id, TASK_TYPE, entity_id),
        )
        if not task:
            self.tasks.create(
                self.run_id,
                TASK_TYPE,
                entity_id,
                payload,
                prompt=PROMPT,
                schema=SCHEMA,
                priority=96,
                metadata={
                    "required_skills": ["human-writing"],
                    "skill_mode": "current_run_reader_projection",
                    "reader_contract_version": CONTRACT_VERSION,
                    "cache_policy": "facts-may-hit-reader-prose-never-cross-run",
                },
            )
            self.db.update_run(self.run_id, stage="AWAITING_READER_PROJECTION")
            return
        if task["status"] != "APPLIED":
            return
        stale = [row["id"] for row in selected if not _reader_sidecar_current(self.root, self.run_id, row)]
        if stale:
            raise RuntimeError(
                "Reader projection sidecar is missing or stale for current fact-checked items: "
                + ", ".join(str(value) for value in stale)
            )
        return original_prepare_issue(self)

    def apply_task(self, task: dict[str, Any]) -> None:
        if task.get("task_type") != TASK_TYPE:
            return original_apply_task(self, task)
        output = self.tasks.read_result(task)
        input_data = read_json(self.root / task["input_path"], {})
        inputs = {
            str(row.get("brief_item_id") or ""): row
            for row in input_data.get("items") or []
        }
        for result in output.get("results") or []:
            brief_item_id = str(result.get("brief_item_id") or "")
            source = inputs.get(brief_item_id)
            if not source:
                raise KeyError(brief_item_id)
            sidecar = {
                "brief_item_id": brief_item_id,
                "reader_version": CONTRACT_VERSION,
                "title": str(result.get("title") or "").strip(),
                "lead": str(result.get("lead") or "").strip(),
                "body": [str(value or "").strip() for value in result.get("body") or []],
                "takeaway": (str(result.get("takeaway") or "").strip() or None),
                "used_fields": [str(value) for value in result.get("used_fields") or []],
                "_provenance": {
                    "task_id": task["id"],
                    "run_id": self.run_id,
                    "source_item_hash": source["source_item_hash"],
                    "reader_contract_version": CONTRACT_VERSION,
                    "cache_scope": "current_run_only",
                },
            }
            write_json(reader_item_path(self.root, self.run_id, brief_item_id), sidecar)

    def semantic_errors(self, task, input_data, data):
        errors = list(original_semantic_errors(self, task, input_data, data))
        if task.get("task_type") != TASK_TYPE:
            return errors
        inputs = {
            str(row.get("brief_item_id") or ""): row
            for row in input_data.get("items") or []
        }
        actual = [str(row.get("brief_item_id") or "") for row in data.get("results") or []]
        if len(actual) != len(set(actual)):
            errors.append("reader_projection contains duplicate brief_item_id values")
        missing = sorted(set(inputs) - set(actual))
        unknown = sorted(set(actual) - set(inputs))
        if missing:
            errors.append("reader_projection omits IDs: " + ", ".join(missing))
        if unknown:
            errors.append("reader_projection references unknown IDs: " + ", ".join(unknown))
        if len(actual) != len(inputs):
            errors.append("reader_projection must return exactly one result per selected item")
        for result in data.get("results") or []:
            brief_item_id = str(result.get("brief_item_id") or "")
            source = inputs.get(brief_item_id)
            if not source:
                continue
            errors.extend(
                f"reader_projection {brief_item_id}: {message}"
                for message in _reader_contract_errors(result, source.get("machine_item") or {})
            )
        return list(dict.fromkeys(errors))

    def topic_groups(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        groups = original_topic_groups(self, data)
        run_id = str(data.get("run_id") or "")
        if not run_id:
            return groups
        for group in groups:
            for item in [*(group.get("items") or []), *(group.get("observations") or [])]:
                brief_item_id = str(item.get("brief_item_id") or "")
                reader = read_json(reader_item_path(self.root, run_id, brief_item_id), {})
                if int(reader.get("reader_version") or 0) != CONTRACT_VERSION:
                    continue
                # This mutation is render-local only. issue.json and the machine item
                # remain the authoritative fact model for synthesis/Roadmap/Idea work.
                item["reader"] = reader
                item["title"] = str(reader.get("title") or item.get("title") or "")
        return groups

    def demo_output(task_type: str, data: dict[str, Any]):
        if task_type == TASK_TYPE:
            results = []
            for row in data.get("items") or []:
                item = row.get("machine_item") or {}
                lead = str(item.get("core_conclusion") or "离线样例用于验证读者层能够从事实层独立生成展示文案。")
                body_text = str(item.get("mechanism") or item.get("result") or lead)
                if not COMPLETE_ENDING_RE.search(lead):
                    lead = lead.rstrip("，,：:；;") + "。"
                if not COMPLETE_ENDING_RE.search(body_text):
                    body_text = body_text.rstrip("，,：:；;") + "。"
                result = {
                    "brief_item_id": row["brief_item_id"],
                    "title": str(item.get("title") or "技术进展：离线读者层验证"),
                    "lead": lead,
                    "body": [body_text],
                    "used_fields": ["core_conclusion", "mechanism"],
                }
                takeaway = str(item.get("project_relevance") or "").strip()
                if takeaway:
                    if not COMPLETE_ENDING_RE.search(takeaway):
                        takeaway = takeaway.rstrip("，,：:；;") + "。"
                    result["takeaway"] = takeaway
                results.append(result)
            return {"results": results}
        return original_demo_output(task_type, data)

    Pipeline._maybe_prepare_issue = maybe_prepare_issue
    Pipeline._apply_task = apply_task
    TaskService._semantic_errors = semantic_errors
    EmailService._topic_groups = topic_groups
    demo_module._demo_output = demo_output
    Pipeline._reader_projection_installed = True
    TaskService._reader_projection_installed = True
