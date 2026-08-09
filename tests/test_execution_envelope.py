from __future__ import annotations

import json
from types import SimpleNamespace

from briefing_skill.execution_envelope import (
    EXECUTION_CONTRACT_VERSION,
    canonical_task_instructions,
    ensure_execution_envelope,
    verify_bound_resources,
)
from briefing_skill.tasks import TASK_BINDING_KEY
from briefing_skill.utils import read_json, write_json


class FakeDB:
    def __init__(self):
        self.metadata = None

    def execute(self, _sql, args):
        self.metadata = args[0]


def _fixture(tmp_path):
    root = tmp_path
    (root / "prompts").mkdir()
    (root / "schemas").mkdir()
    (root / "context").mkdir()
    task_dir = root / "workspace" / "runs" / "r1" / "tasks" / "relevance_batch"
    task_dir.mkdir(parents=True)
    (root / "prompts" / "p.md").write_text("judge from evidence only", encoding="utf-8")
    (root / "schemas" / "s.json").write_text('{"type":"object"}', encoding="utf-8")
    (root / "context" / "topic.md").write_text("project boundary", encoding="utf-8")
    input_rel = "workspace/runs/r1/tasks/relevance_batch/t1.input.json"
    write_json(
        root / input_rel,
        {
            TASK_BINDING_KEY: {
                "id": "t1",
                "type": "relevance_batch",
                "entity_id": "e1",
                "input_digest": "business-input-digest",
            },
            "project_context_path": "context/topic.md",
            "candidates": [],
        },
    )
    task = {
        "id": "t1",
        "run_id": "r1",
        "task_type": "relevance_batch",
        "entity_id": "e1",
        "input_path": input_rel,
        "output_path": "workspace/runs/r1/tasks/relevance_batch/t1.output.json",
        "prompt_path": "prompts/p.md",
        "schema_path": "schemas/s.json",
        "metadata_json": "{}",
    }
    return SimpleNamespace(root=root, db=FakeDB()), task


def test_envelope_binds_prompt_schema_context_and_forbids_host_semantic_guidance(tmp_path):
    service, task = _fixture(tmp_path)

    envelope, path = ensure_execution_envelope(service, task)
    bound_input = read_json(service.root / task["input_path"], {})
    binding = bound_input[TASK_BINDING_KEY]

    assert binding["contract_version"] == EXECUTION_CONTRACT_VERSION
    assert binding["prompt_digest"]
    assert binding["schema_digest"]
    assert binding["context_digests"]["context/topic.md"]
    assert binding["execution_envelope_digest"]
    assert read_json(service.root / path, {})["task"] == binding
    assert envelope["policy"]["outer_host_semantic_guidance"] == "forbidden"
    assert any("expected labels" in line for line in envelope["host_instructions"])
    assert json.loads(service.db.metadata)["execution_contract_required"] is True


def test_bound_resource_change_invalidates_task_output(tmp_path):
    service, task = _fixture(tmp_path)
    ensure_execution_envelope(service, task)
    assert verify_bound_resources(service, task) == []

    (service.root / "prompts" / "p.md").write_text("changed prompt", encoding="utf-8")

    assert verify_bound_resources(service, task) == ["bound prompt changed after task dispatch"]


def test_tasks_next_instruction_points_to_canonical_envelope(tmp_path):
    service, task = _fixture(tmp_path)

    instructions = canonical_task_instructions(service, task)

    assert "canonical execution contract" in instructions
    assert "execution.json" in instructions
    assert "Do not add or accept outer-host semantic guidance" in instructions
    assert "expected relevance" in instructions
