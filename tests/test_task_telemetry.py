from __future__ import annotations

import json
from pathlib import Path

from briefing_skill.cost_schema import ensure_cost_schema
from briefing_skill.db import Database
from briefing_skill.tasks import TASK_BINDING_KEY, TaskService
from briefing_skill.telemetry import install_task_telemetry, run_stats
from briefing_skill.utils import read_json, write_json


def test_task_telemetry_records_attempt_output_and_cost_proxy(tmp_path):
    root = tmp_path
    run_id = "telemetry-run"
    run_dir = root / "workspace" / "runs" / run_id
    (root / "prompts").mkdir(parents=True)
    (root / "schemas").mkdir(parents=True)
    (root / "prompts" / "dummy.md").write_text("Read the input and return x.", encoding="utf-8")
    write_json(
        root / "schemas" / "dummy.schema.json",
        {
            "type": "object",
            "required": ["x"],
            "properties": {"x": {"type": "integer"}},
            "additionalProperties": False,
        },
    )

    db = Database(root / "workspace" / "briefing.sqlite")
    db.init()
    ensure_cost_schema(db)
    db.create_run(run_id)

    install_task_telemetry()
    service = TaskService(db, root, run_dir)
    task = service.create(
        run_id,
        "dummy",
        "entity",
        {"payload": "abc", "document": {"raw_char_count": 10000, "evidence_char_count": 2000}},
        prompt="dummy.md",
        schema="dummy.schema.json",
    )
    picked = service.next(run_id)
    assert picked["id"] == task["id"]
    task_input = read_json(root / task["input_path"])
    write_json(root / task["output_path"], {TASK_BINDING_KEY: task_input[TASK_BINDING_KEY], "x": 1})
    completed, failed = service.sync(run_id)
    assert (completed, failed) == (1, 0)

    stats = run_stats(db, root, run_id)
    assert stats["totals"]["tasks"] == 1
    assert stats["totals"]["attempts"] == 1
    assert stats["totals"]["document_chars"] == 10000
    assert stats["totals"]["evidence_chars"] == 2000
    assert stats["totals"]["evidence_reduction_ratio"] == 0.8
    assert stats["by_task_type"]["dummy"]["output_chars"] > 0
    assert stats["quality"]["facts"] == 0
    assert stats["quality"]["primary_resolve_rate"] is None
    assert stats["quality"]["fact_check_pass_rate"] is None


def test_quality_telemetry_counts_resolved_conditioned_facts(tmp_path):
    root = tmp_path
    run_id = "quality-run"
    run_dir = root / "workspace" / "runs" / run_id
    facts_dir = run_dir / "facts"
    facts_dir.mkdir(parents=True)
    db = Database(root / "workspace" / "briefing.sqlite")
    db.init()
    ensure_cost_schema(db)
    db.create_run(run_id)

    facts_path = facts_dir / "candidate.json"
    write_json(
        facts_path,
        {
            "primary_source_resolved": True,
            "evidence_gaps": [],
            "evidence": [
                {"claim": "P99 improves", "value": "31%", "baseline": "Baseline-X", "condition": "8xA100"},
                {"claim": "Architecture uses batching", "value": None},
            ],
            "_provenance": {"repair_of_task_id": "fact-1"},
        },
    )
    db.execute(
        """
        INSERT INTO facts(id,run_id,candidate_id,json_path,quality_score,event_hint,created_at)
        VALUES (?,?,?,?,?,?,datetime('now'))
        """,
        ("fact", run_id, "candidate", str(facts_path.relative_to(root)), 90, "event"),
    )

    stats = run_stats(db, root, run_id)
    quality = stats["quality"]
    assert quality["facts"] == 1
    assert quality["resolved_primary_facts"] == 1
    assert quality["primary_resolve_rate"] == 1.0
    assert quality["numeric_evidence_records"] == 1
    assert quality["numeric_condition_coverage"] == 1.0
    assert quality["repaired_facts"] == 1


def test_stats_command_is_installed():
    install_task_telemetry()
    from briefing_skill import cli

    parser = cli.build_parser()
    args = parser.parse_args(["stats", "--run", "latest"])
    assert args.run == "latest"
    assert callable(args.func)
