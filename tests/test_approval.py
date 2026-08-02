import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path


def test_issue_requires_and_accepts_human_approval():
    root = Path(__file__).resolve().parents[1]
    run_id = f"pytest-approval-{uuid.uuid4().hex[:8]}"
    env = {**os.environ, "BRIEFING_SKIP_DOTENV": "1"}
    demo = subprocess.run([sys.executable, "briefing.py", "demo", "--run", run_id], cwd=root, text=True, capture_output=True, env=env)
    assert demo.returncode == 0, demo.stderr + demo.stdout

    with sqlite3.connect(root / "workspace" / "briefing.sqlite") as conn:
        status = conn.execute("SELECT status FROM issues WHERE run_id=?", (run_id,)).fetchone()[0]
        minimum_score = conn.execute("SELECT MIN(score) FROM brief_items WHERE run_id=?", (run_id,)).fetchone()[0]
    assert status == "AWAITING_APPROVAL"
    assert minimum_score >= 80

    approve = subprocess.run([sys.executable, "briefing.py", "approve", "--run", run_id, "--all"], cwd=root, text=True, capture_output=True, env=env)
    assert approve.returncode == 0, approve.stderr + approve.stdout
    with sqlite3.connect(root / "workspace" / "briefing.sqlite") as conn:
        status = conn.execute("SELECT status FROM issues WHERE run_id=?", (run_id,)).fetchone()[0]
    assert status == "APPROVED"
