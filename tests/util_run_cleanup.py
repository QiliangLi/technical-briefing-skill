"""Remove a test-created run from the shared repository database and workspace.

Tests that exercise the real `briefing.py` CLI must not leave `pytest-*` runs in
`workspace/briefing.sqlite`: a leftover run hijacks `--run latest` resolution and
can leak demo judgements into production tables. Call `purge_run` in a `finally`
block after the assertions.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path


def purge_run(root: Path, run_id: str) -> None:
    db_path = root / "workspace" / "briefing.sqlite"
    if db_path.is_file():
        with sqlite3.connect(db_path) as conn:
            issue_ids = [
                row[0]
                for row in conn.execute("SELECT id FROM issues WHERE run_id=?", (run_id,))
            ]
            for issue_id in issue_ids:
                conn.execute("DELETE FROM issue_items WHERE issue_id=?", (issue_id,))
                conn.execute("DELETE FROM issue_radar_items WHERE issue_id=?", (issue_id,))
            conn.execute("DELETE FROM issues WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM brief_items WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM tasks WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM relevance_cache_usage WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM candidate_assessments WHERE run_id=?", (run_id,))
            conn.execute(
                "DELETE FROM candidates WHERE raw_item_id IN (SELECT id FROM raw_items WHERE run_id=?)",
                (run_id,),
            )
            conn.execute("DELETE FROM raw_items WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM run_execution_provenance WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM runs WHERE id=?", (run_id,))
    run_dir = root / "workspace" / "runs" / run_id
    if run_dir.is_dir():
        shutil.rmtree(run_dir)
