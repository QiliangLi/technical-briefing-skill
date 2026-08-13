from __future__ import annotations

from pathlib import Path

import pytest

import briefing_skill.demo as demo_module
import briefing_skill.pipeline as pipeline_module
import briefing_skill.tasks as tasks_module
from briefing_skill.issue_style_polish import (
    PATCH_SCHEMA,
    STYLE_FIELDS,
    TASK_TYPE,
    install_issue_style_polish,
)
from briefing_skill.utils import read_json, write_json


class _DB:
    def __init__(self, row: dict):
        self.row = row

    def fetchone(self, sql: str, args=()):
        if "FROM brief_items WHERE id=? AND run_id=?" in sql:
            return dict(self.row)
        return None


class _TaskResults:
    def __init__(self, output: dict):
        self.output = output

    def read_result(self, task: dict):
        return self.output


def _install_on_fakes(monkeypatch):
    class FakePipeline:
        def _maybe_prepare_checks(self):
            return None

        def _apply_task(self, task):
            raise AssertionError("legacy Pipeline._apply_task should not own item_style_polish")

    class FakeTaskService:
        def create(self, *args, **kwargs):
            return {}

        def _semantic_errors(self, task, input_data, data):
            return []

    monkeypatch.setattr(pipeline_module, "Pipeline", FakePipeline)
    monkeypatch.setattr(tasks_module, "TaskService", FakeTaskService)
    monkeypatch.setattr(demo_module, "_demo_output", lambda task_type, data: None)
    install_issue_style_polish()
    return FakePipeline


def _current_item() -> dict:
    return {
        "title": "原始标题",
        "core_conclusion": "原始结论。",
        "mechanism": "原机制表述。",
        "result": "原始结果。",
        "boundary": "原始边界。",
        "project_relevance": "原始启发。",
        "score": 91,
        "sources": [{"url": "https://example.org/source"}],
    }


def _pipeline_instance(FakePipeline, tmp_path: Path, output: dict):
    run_id = "run-apply"
    item_path = tmp_path / "workspace" / "runs" / run_id / "items" / "item-1.json"
    write_json(item_path, _current_item())
    pipeline = FakePipeline()
    pipeline.root = tmp_path
    pipeline.run_id = run_id
    pipeline.db = _DB(
        {
            "id": "item-1",
            "run_id": run_id,
            "json_path": str(item_path.relative_to(tmp_path)),
        }
    )
    pipeline.tasks = _TaskResults(output)
    return pipeline, item_path


def test_apply_task_sparse_branch_updates_only_requested_field(monkeypatch, tmp_path: Path):
    FakePipeline = _install_on_fakes(monkeypatch)
    output = {
        "patches": [
            {
                "brief_item_id": "item-1",
                "field": "mechanism",
                "before": "原机制表述。",
                "after": "机制表述更通顺。",
                "reason": "修复语序。",
            }
        ]
    }
    pipeline, item_path = _pipeline_instance(FakePipeline, tmp_path, output)
    input_path = tmp_path / "workspace" / "runs" / pipeline.run_id / "tasks" / "style.input.json"
    write_json(input_path, {"constraints": {"sparse_patch": True}})
    task = {
        "task_type": TASK_TYPE,
        "schema_path": f"schemas/{PATCH_SCHEMA}",
        "input_path": str(input_path.relative_to(tmp_path)),
    }

    FakePipeline._apply_task(pipeline, task)

    updated = read_json(item_path)
    assert updated["mechanism"] == "机制表述更通顺。"
    for field, value in _current_item().items():
        if field != "mechanism":
            assert updated[field] == value


def test_apply_task_sparse_branch_rejects_stale_before(monkeypatch, tmp_path: Path):
    FakePipeline = _install_on_fakes(monkeypatch)
    output = {
        "patches": [
            {
                "brief_item_id": "item-1",
                "field": "mechanism",
                "before": "已经过期的文本。",
                "after": "不应写入。",
                "reason": "stale fixture",
            }
        ]
    }
    pipeline, item_path = _pipeline_instance(FakePipeline, tmp_path, output)
    input_path = tmp_path / "workspace" / "runs" / pipeline.run_id / "tasks" / "style.input.json"
    write_json(input_path, {"constraints": {"sparse_patch": True}})
    task = {
        "task_type": TASK_TYPE,
        "schema_path": f"schemas/{PATCH_SCHEMA}",
        "input_path": str(input_path.relative_to(tmp_path)),
    }

    with pytest.raises(RuntimeError, match="Stale style patch before text"):
        FakePipeline._apply_task(pipeline, task)
    assert read_json(item_path) == _current_item()


def test_apply_task_legacy_resume_preserves_non_style_fields(monkeypatch, tmp_path: Path):
    FakePipeline = _install_on_fakes(monkeypatch)
    result = {"brief_item_id": "item-1"}
    for field in STYLE_FIELDS:
        result[field] = f"legacy-{field}。"
    pipeline, item_path = _pipeline_instance(FakePipeline, tmp_path, {"results": [result]})
    input_path = tmp_path / "workspace" / "runs" / pipeline.run_id / "tasks" / "legacy.input.json"
    write_json(input_path, {"items": [{"brief_item_id": "item-1"}]})
    task = {
        "task_type": TASK_TYPE,
        "schema_path": "schemas/item-style-polish.schema.json",
        "input_path": str(input_path.relative_to(tmp_path)),
    }

    FakePipeline._apply_task(pipeline, task)

    updated = read_json(item_path)
    for field in STYLE_FIELDS:
        assert updated[field] == f"legacy-{field}。"
    assert updated["score"] == 91
    assert updated["sources"] == [{"url": "https://example.org/source"}]
