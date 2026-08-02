import os
import subprocess
import sys
from pathlib import Path


def test_demo_command_runs():
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "BRIEFING_SKIP_DOTENV": "1"}
    result = subprocess.run([sys.executable, "briefing.py", "demo", "--run", "pytest-demo"], cwd=root, text=True, capture_output=True, env=env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert (root / "workspace" / "runs" / "pytest-demo" / "email.html").exists()
