import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from tests.util_run_cleanup import purge_run


def test_demo_command_runs():
    root = Path(__file__).resolve().parents[1]
    run_id = f"pytest-demo-{uuid4().hex[:12]}"
    env = {**os.environ, "BRIEFING_SKIP_DOTENV": "1"}
    try:
        result = subprocess.run(
            [sys.executable, "briefing.py", "demo", "--run", run_id],
            cwd=root,
            text=True,
            capture_output=True,
            env=env,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        assert (root / "workspace" / "runs" / run_id / "email.html").exists()
    finally:
        purge_run(root, run_id)
