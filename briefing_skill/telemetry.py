from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .cost_schema import ensure_cost_schema
from .utils import now_iso


def _file_chars(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return 0


def run_stats(db, root: Path, run_id: str) -> dict[str, Any]:
    ensure_cost_schema(db)
    run = db.fetchone("SELECT * FROM runs WHERE id=?", (run_id,)) or {}
    rows = db.fetchall(
        """
        SELECT tm.*, t.status, t.priority, t.created_at, t.updated_at
        FROM task_metrics tm JOIN tasks t ON t.id=tm.task_id
        WHERE tm.run_id=?
        ORDER BY tm.task_type, t.created_at
        """,
        (run_id,),
    )
    by_type: dict[str, dict[str, Any]] = {}
    for row in rows:
        group = by_type.setdefault(
            row["task_type"],
            {
                "tasks": 0,
                "completed": 0,
                "invalid": 0,
                "attempts": 0,
                "cache_hits": 0,
                "input_chars": 0,
                "prompt_chars": 0,
                "output_chars": 0,
                "document_chars": 0,
                "evidence_chars": 0,
            },
        )
        group["tasks"] += 1
        group["completed"] += int(row.get("status") in {"COMPLETED", "APPLIED"})
        group["invalid"] += int(row.get("invalid_count") or 0)
        group["attempts"] += int(row.get("attempts") or 0)
        group["cache_hits"] += int(row.get("cache_hit") or 0)
        for key in ("input_chars", "prompt_chars", "output_chars", "document_chars", "evidence_chars"):
            group[key] += int(row.get(key) or 0)
        if group["document_chars"]:
            group["evidence_reduction_ratio"] = round(
                max(0.0, 1.0 - group["evidence_chars"] / group["document_chars"]), 4
            )

    totals = {
        "tasks": sum(value["tasks"] for value in by_type.values()),
        "completed": sum(value["completed"] for value in by_type.values()),
        "invalid": sum(value["invalid"] for value in by_type.values()),
        "attempts": sum(value["attempts"] for value in by_type.values()),
        "cache_hits": sum(value["cache_hits"] for value in by_type.values()),
        "input_chars": sum(value["input_chars"] for value in by_type.values()),
        "prompt_chars": sum(value["prompt_chars"] for value in by_type.values()),
        "output_chars": sum(value["output_chars"] for value in by_type.values()),
        "document_chars": sum(value["document_chars"] for value in by_type.values()),
        "evidence_chars": sum(value["evidence_chars"] for value in by_type.values()),
    }
    totals["agent_read_chars_proxy"] = totals["input_chars"] + totals["prompt_chars"] + totals["evidence_chars"]
    if totals["document_chars"]:
        totals["evidence_reduction_ratio"] = round(
            max(0.0, 1.0 - totals["evidence_chars"] / totals["document_chars"]), 4
        )
    cache = db.fetchone("SELECT COUNT(*) AS n FROM fact_cache") or {"n": 0}
    duration_seconds = None
    if run.get("created_at") and run.get("updated_at"):
        try:
            duration_seconds = round(
                (datetime.fromisoformat(run["updated_at"]) - datetime.fromisoformat(run["created_at"])).total_seconds(),
                3,
            )
        except (TypeError, ValueError):
            pass
    return {
        "run_id": run_id,
        "stage": run.get("stage"),
        "status": run.get("status"),
        "run_wall_seconds": duration_seconds,
        "totals": totals,
        "by_task_type": by_type,
        "fact_cache_entries": int(cache.get("n") or 0),
        "notes": [
            "agent_read_chars_proxy is a deterministic character-volume proxy, not an API or Codex token bill.",
            "attempts are observed when tasks are obtained through `tasks next`; direct external execution may not increment them.",
        ],
    }


def install_task_telemetry() -> None:
    """Record deterministic task-cost proxies and expose `briefing.py stats`."""

    from .tasks import TaskService

    if getattr(TaskService, "_telemetry_installed", False):
        return

    original_create = TaskService.create
    original_next = TaskService.next
    original_sync = TaskService.sync
    original_reopen = TaskService.reopen_invalid

    def create(self, run_id: str, task_type: str, entity_id: str, input_data: dict[str, Any], **kwargs):
        row = original_create(self, run_id, task_type, entity_id, input_data, **kwargs)
        ensure_cost_schema(self.db)
        input_path = self.root / row["input_path"]
        prompt_path = self.root / row["prompt_path"]
        document = input_data.get("document") or {}
        self.db.execute(
            """
            INSERT INTO task_metrics(
                task_id,run_id,task_type,input_chars,prompt_chars,document_chars,evidence_chars,cache_hit
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(task_id) DO UPDATE SET
                input_chars=excluded.input_chars,
                prompt_chars=excluded.prompt_chars,
                document_chars=excluded.document_chars,
                evidence_chars=excluded.evidence_chars,
                cache_hit=excluded.cache_hit
            """,
            (
                row["id"],
                run_id,
                task_type,
                _file_chars(input_path),
                _file_chars(prompt_path),
                int(document.get("raw_char_count") or document.get("char_count") or 0),
                int(document.get("evidence_char_count") or document.get("char_count") or 0),
                int(bool(document.get("fact_cache_hit"))),
            ),
        )
        return row

    def next_task(self, run_id: str):
        task = original_next(self, run_id)
        if not task:
            return None
        ensure_cost_schema(self.db)
        metric = self.db.fetchone("SELECT * FROM task_metrics WHERE task_id=?", (task["id"],))
        if metric:
            last_started = metric.get("last_started_at")
            if not last_started or str(last_started) < str(task.get("updated_at") or ""):
                now = now_iso()
                self.db.execute(
                    """
                    UPDATE task_metrics
                    SET attempts=attempts+1,
                        first_started_at=COALESCE(first_started_at, ?),
                        last_started_at=?
                    WHERE task_id=?
                    """,
                    (now, now, task["id"]),
                )
        return task

    def sync(self, run_id: str):
        ensure_cost_schema(self.db)
        before = {row["id"]: row for row in self.list(run_id)}
        result = original_sync(self, run_id)
        after = {row["id"]: row for row in self.list(run_id)}
        for task_id, task in after.items():
            old_status = (before.get(task_id) or {}).get("status")
            new_status = task.get("status")
            if old_status == new_status or new_status not in {"COMPLETED", "INVALID"}:
                continue
            output_chars = _file_chars(self.root / task["output_path"])
            if new_status == "COMPLETED":
                self.db.execute(
                    "UPDATE task_metrics SET output_chars=?,completed_at=?,last_error=NULL WHERE task_id=?",
                    (output_chars, now_iso(), task_id),
                )
            else:
                self.db.execute(
                    "UPDATE task_metrics SET output_chars=?,invalid_count=invalid_count+1,last_error=? WHERE task_id=?",
                    (output_chars, task.get("error"), task_id),
                )
        return result

    def reopen_invalid(self, run_id: str) -> int:
        count = original_reopen(self, run_id)
        if count:
            ensure_cost_schema(self.db)
            self.db.execute(
                """
                UPDATE task_metrics SET last_started_at=NULL
                WHERE task_id IN (SELECT id FROM tasks WHERE run_id=? AND status='PENDING')
                """,
                (run_id,),
            )
        return count

    TaskService.create = create
    TaskService.next = next_task
    TaskService.sync = sync
    TaskService.reopen_invalid = reopen_invalid
    TaskService._telemetry_installed = True

    # Patch the CLI lazily so the core cli.py stays free of metrics-specific code.
    from . import cli

    if getattr(cli, "_stats_command_installed", False):
        return
    original_build_parser = cli.build_parser

    def cmd_stats(args) -> int:
        root, paths, config, db = cli._context(args)
        run_id = cli._resolve_run(db, args.run)
        print(json.dumps(run_stats(db, root, run_id), ensure_ascii=False, indent=2))
        return 0

    def build_parser():
        parser = original_build_parser()
        subparsers_action = next(
            action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
        )
        p = subparsers_action.add_parser("stats")
        p.add_argument("--run", default="latest")
        p.set_defaults(func=cmd_stats)
        return parser

    cli.build_parser = build_parser
    cli._stats_command_installed = True
