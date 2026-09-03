import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

from tests.util_run_cleanup import isolated_demo_root, purge_run


def test_clean_issue_is_ready_to_send_without_human_approval(tmp_path):
    source_root = Path(__file__).resolve().parents[1]
    root = isolated_demo_root(tmp_path, source_root)
    run_id = f"pytest-release-{uuid.uuid4().hex[:8]}"
    env = {**os.environ, "BRIEFING_SKIP_DOTENV": "1"}
    try:
        demo = subprocess.run(
            [sys.executable, "briefing.py", "--root", str(root), "demo", "--run", run_id],
            cwd=root,
            text=True,
            capture_output=True,
            env=env,
        )
        assert demo.returncode == 0, demo.stderr + demo.stdout

        with sqlite3.connect(root / "workspace" / "briefing.sqlite") as conn:
            issue_status = conn.execute(
                "SELECT status FROM issues WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            run_stage = conn.execute(
                "SELECT stage FROM runs WHERE id=?", (run_id,)
            ).fetchone()[0]
            minimum_score = conn.execute(
                "SELECT MIN(score) FROM brief_items WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        assert issue_status == "READY_TO_SEND"
        assert run_stage == "READY_TO_SEND"
        assert minimum_score >= 80

        for removed_command in ("review", "approve"):
            removed = subprocess.run(
                [sys.executable, "briefing.py", "--root", str(root), removed_command, "--run", run_id],
                cwd=root,
                text=True,
                capture_output=True,
                env=env,
            )
            assert removed.returncode != 0
            assert "invalid choice" in removed.stderr

        unconfirmed_send = subprocess.run(
            [sys.executable, "briefing.py", "--root", str(root), "send", "--run", run_id],
            cwd=root,
            text=True,
            capture_output=True,
            env=env,
        )
        assert unconfirmed_send.returncode == 1
        assert "Refusing to send without --confirm-send" in unconfirmed_send.stderr
    finally:
        purge_run(root, run_id)
