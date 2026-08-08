from __future__ import annotations

import json

from briefing_skill.db import Database
from briefing_skill.invalid_repair import install_invalid_targeted_repair
from briefing_skill.tasks import TASK_BINDING_KEY, TaskService
from briefing_skill.utils import read_json, write_json


def _restore(obj, name: str, value, existed: bool) -> None:
    if existed:
        setattr(obj, name, value)
    elif hasattr(obj, name):
        delattr(obj, name)


def test_reopen_invalid_uses_small_targeted_sidecar_for_repairable_output(tmp_path):
    snapshots = {
        "reopen": (TaskService.reopen_invalid, hasattr(TaskService, "reopen_invalid")),
        "instructions": (TaskService.instructions, hasattr(TaskService, "instructions")),
        "peek_group": (getattr(TaskService, "peek_group", None), hasattr(TaskService, "peek_group")),
        "flag": (getattr(TaskService, "_invalid_targeted_repair_installed", None), hasattr(TaskService, "_invalid_targeted_repair_installed")),
    }
    try:
        install_invalid_targeted_repair()
        root = tmp_path
        run_id = "invalid-repair-integration"
        db = Database(root / "workspace" / "briefing.sqlite")
        db.init()
        db.create_run(run_id)
        service = TaskService(db, root, root / "workspace" / "runs" / run_id)
        task = service.create(
            run_id,
            "item_writing",
            "event-1",
            {
                "event_id": "event-1",
                "topic": {"name": "TPN"},
                "direction": {"name": "KV transfer"},
                "score": 88,
                "facts": [{"mechanism": "very expensive evidence-derived facts"}],
                "sources": [{"url": "https://arxiv.org/abs/2608.12345"}],
                "length": {"min_chars": 180, "max_chars": 260},
            },
            prompt="item-writing.md",
            schema="brief-item.schema.json",
        )
        input_data = read_json(root / task["input_path"])
        write_json(
            root / task["output_path"],
            {
                TASK_BINDING_KEY: input_data[TASK_BINDING_KEY],
                "title": "Existing output",
                "core_conclusion": "Existing conclusion without final punctuation",
            },
        )
        db.execute(
            "UPDATE tasks SET status='INVALID',error=? WHERE id=?",
            ("core_conclusion must end with a complete sentence", task["id"]),
        )

        assert service.reopen_invalid(run_id) == 1
        reopened = db.fetchone("SELECT * FROM tasks WHERE id=?", (task["id"],))
        assert reopened["status"] == "PENDING"
        metadata = json.loads(reopened["metadata_json"])
        assert metadata["targeted_repair"] is True
        assert metadata["repair_input_chars"] < metadata["original_input_chars"]

        instructions = service.instructions(reopened)
        assert metadata["repair_input_path"] in instructions
        assert reopened["input_path"] not in instructions
        assert "Do NOT read the original task input" in instructions
        assert "task-output-repair.md" in instructions
    finally:
        _restore(TaskService, "reopen_invalid", *snapshots["reopen"])
        _restore(TaskService, "instructions", *snapshots["instructions"])
        _restore(TaskService, "peek_group", *snapshots["peek_group"])
        _restore(TaskService, "_invalid_targeted_repair_installed", *snapshots["flag"])
