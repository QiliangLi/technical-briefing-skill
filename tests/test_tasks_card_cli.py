"""`tasks card --task <id>` renders the canonical single-task card by explicit id.

The action exists for orchestrators (briefing-run workflow wave dispatch) that
need per-task cards without consuming `tasks next`'s group dispatch. It must be
read-only on task state, mirror `tasks next` telemetry, and print exactly the
same canonical card `tasks next-single` would print for the sole pending task.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from tests.util_run_cleanup import isolated_demo_root

SEED = r"""
import sys
from pathlib import Path

from briefing_skill.cost_schema import ensure_cost_schema
from briefing_skill.db import Database
from briefing_skill.execution_envelope import install_execution_envelope_contract
from briefing_skill.paths import Paths
from briefing_skill.session_grouping import install_session_grouping
from briefing_skill.tasks import TaskService

root = Path(sys.argv[1])
paths = Paths(root)
paths.ensure()
db = Database(paths.db)
db.init()
ensure_cost_schema(db)
now = "2026-10-18T00:00:00Z"
db.execute(
    "INSERT INTO runs (id, created_at, updated_at, status, stage) VALUES (?,?,?,?,?)",
    ("r1", now, now, "ACTIVE", "COLLECTED"),
)
install_execution_envelope_contract()
install_session_grouping()
service = TaskService(db, root, paths.runs / "r1")
task = service.create(
    "r1",
    "relevance_batch",
    "e1",
    {
        "project_context_path": "config/project-context/tpn.md",
        "topic": {"id": "tpn", "name": "状态感知网络、TPN"},
        "candidates": [],
    },
    prompt="prompts/relevance-batch.md",
    schema="schemas/relevance-batch.schema.json",
    priority=10,
)
db.execute(
    "INSERT INTO task_metrics (task_id, run_id, task_type) VALUES (?,?,?)",
    (task["id"], "r1", "relevance_batch"),
)
print(task["id"])
"""


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    source_root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "BRIEFING_SKIP_DOTENV": "1"}
    return subprocess.run(
        [sys.executable, "briefing.py", "--root", str(root), *args],
        cwd=source_root,
        text=True,
        capture_output=True,
        env=env,
    )


def _seed(root: Path) -> str:
    source_root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "BRIEFING_SKIP_DOTENV": "1"}
    result = subprocess.run(
        [sys.executable, "-c", SEED, str(root)],
        cwd=source_root,
        text=True,
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


def test_tasks_card_renders_canonical_card_keeps_state_and_counts_attempt(tmp_path):
    source_root = Path(__file__).resolve().parents[1]
    root = isolated_demo_root(tmp_path, source_root)
    task_id = _seed(root)

    card = _cli(root, "tasks", "card", "--task", task_id, "--run", "r1")
    assert card.returncode == 0, card.stderr
    lines = card.stdout.strip().splitlines()
    assert lines[0].startswith(f"Task {task_id} (relevance_batch) — canonical execution contract v")
    assert any(
        line.startswith("1. Read the canonical envelope first: workspace/runs/r1/tasks/relevance_batch/")
        for line in lines
    )

    # 与 tasks next-single 对同一唯一待办任务打印完全相同的 canonical 卡
    nxt = _cli(root, "tasks", "next-single", "--run", "r1")
    assert nxt.returncode == 0, nxt.stderr
    assert nxt.stdout == card.stdout

    with sqlite3.connect(root / "workspace" / "briefing.sqlite") as conn:
        status = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()[0]
        metric = conn.execute(
            "SELECT attempts, last_started_at FROM task_metrics WHERE task_id=?", (task_id,)
        ).fetchone()
    assert status == "PENDING"
    # card 镜像 `tasks next` 的尝试计数；next-single 走原始路径本就不计数，故仍为 1
    assert metric[0] == 1
    assert metric[1]

    missing = _cli(root, "tasks", "card", "--task", "nope", "--run", "r1")
    assert missing.returncode == 1
    assert "Task not found" in missing.stdout
