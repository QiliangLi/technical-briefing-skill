import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from tests.util_run_cleanup import isolated_demo_root, purge_run


def test_demo_command_runs(tmp_path):
    source_root = Path(__file__).resolve().parents[1]
    root = isolated_demo_root(tmp_path, source_root)
    run_id = f"pytest-demo-{uuid4().hex[:12]}"
    env = {**os.environ, "BRIEFING_SKIP_DOTENV": "1"}
    try:
        result = subprocess.run(
            [sys.executable, "briefing.py", "--root", str(root), "demo", "--run", run_id],
            cwd=source_root,
            text=True,
            capture_output=True,
            env=env,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        assert (root / "workspace" / "runs" / run_id / "email.html").exists()
    finally:
        purge_run(root, run_id)
