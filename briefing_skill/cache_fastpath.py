from __future__ import annotations

from pathlib import Path

from .cost_schema import ensure_cost_schema
from .utils import now_iso, read_json


def _file_chars(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return 0


def install_fact_cache_fastpath() -> None:
    """Apply fact-cache hits synchronously so they never reach an Agent queue."""

    from .pipeline import Pipeline

    if getattr(Pipeline, "_fact_cache_fastpath_installed", False):
        return
    original_prepare = Pipeline._maybe_prepare_facts

    def maybe_prepare_facts(self) -> None:
        original_prepare(self)
        ensure_cost_schema(self.db)
        rows = self.db.fetchall(
            """
            SELECT * FROM tasks
            WHERE run_id=? AND task_type='fact_extraction' AND status='PENDING'
            ORDER BY priority DESC, created_at
            """,
            (self.run_id,),
        )
        for task in rows:
            task_input = read_json(self.root / task["input_path"], {})
            document = task_input.get("document") or {}
            if not document.get("fact_cache_hit"):
                continue
            output_path = self.root / task["output_path"]
            if not output_path.is_file():
                continue
            # Cached facts were persisted only after a previously validated
            # fact_extraction result. The current output also carries the new
            # deterministic task binding written by TaskService.create.
            self._apply_task(task)
            finished = now_iso()
            self.db.execute(
                "UPDATE tasks SET status='APPLIED',updated_at=?,error=NULL WHERE id=?",
                (finished, task["id"]),
            )
            self.db.execute(
                """
                UPDATE task_metrics
                SET output_chars=?,completed_at=?,cache_hit=1,last_error=NULL
                WHERE task_id=?
                """,
                (_file_chars(output_path), finished, task["id"]),
            )

    Pipeline._maybe_prepare_facts = maybe_prepare_facts
    Pipeline._fact_cache_fastpath_installed = True
