import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path


def test_clean_issue_is_ready_to_send_without_human_approval():
    root = Path(__file__).resolve().parents[1]
    run_id = f"pytest-release-{uuid.uuid4().hex[:8]}"
    env = {**os.environ, "BRIEFING_SKIP_DOTENV": "1"}
    demo = subprocess.run(
        [sys.executable, "briefing.py", "demo", "--run", run_id],
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
            [sys.executable, "briefing.py", removed_command, "--run", run_id],
            cwd=root,
            text=True,
            capture_output=True,
            env=env,
        )
        assert removed.returncode != 0
        assert "invalid choice" in removed.stderr

    unconfirmed_send = subprocess.run(
        [sys.executable, "briefing.py", "send", "--run", run_id],
        cwd=root,
        text=True,
        capture_output=True,
        env=env,
    )
    assert unconfirmed_send.returncode == 1
    assert "Refusing to send without --confirm-send" in unconfirmed_send.stderr
