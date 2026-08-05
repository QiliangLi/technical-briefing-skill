from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from briefing_skill.db import Database
from briefing_skill.tasks import TASK_BINDING_KEY, TaskService, issue_synthesis_validation_errors
from briefing_skill.utils import read_json, write_json


def input_data() -> dict:
    return {
        "issue_id": "issue-1",
        "items": [
            {"brief_item_id": "a", "title": "项目A更新", "topic_name": "TPN", "core_conclusion": "缓存位置进入网络调度。"},
            {"brief_item_id": "b", "title": "项目B更新", "topic_name": "Agent", "core_conclusion": "仓库索引进入工具选择。"},
        ],
    }


def valid_output() -> dict:
    return {
        "headline": "运行时状态正从观测信息变成执行决策的一部分。",
        "judgements": [
            {
                "title": "状态进入执行链",
                "body": "缓存位置和代码索引只有进入带宽调度与工具选择，才能形成可验证的系统收益。",
                "evidence_item_ids": ["a", "b"],
            }
        ],
        "topic_names": ["TPN", "Agent"],
        "watch_next": [],
    }


def test_issue_synthesis_schema_and_semantics_accept_structured_judgement() -> None:
    schema = json.loads((Path(__file__).parents[1] / "schemas" / "issue-synthesis.schema.json").read_text())
    assert list(Draft202012Validator(schema).iter_errors(valid_output())) == []
    assert issue_synthesis_validation_errors(valid_output(), input_data()) == []


def test_issue_synthesis_rejects_unknown_ids_copying_and_correspondence_label() -> None:
    output = valid_output()
    output["headline"] = "本期筛选出2条信息。"
    output["judgements"] = [
        {"title": "项目A更新", "body": "对应：缓存位置进入网络调度。", "evidence_item_ids": ["missing"]}
    ]

    errors = issue_synthesis_validation_errors(output, input_data())

    assert any("unknown" in error for error in errors)
    assert any("对应" in error for error in errors)
    assert any("copy" in error for error in errors)
    assert any("selection process" in error for error in errors)


def test_required_skills_are_listed_and_replace_existing_requeues_task(tmp_path: Path) -> None:
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    db.create_run("run-1")
    service = TaskService(db, tmp_path, tmp_path / "workspace" / "runs" / "run-1")
    task = service.create(
        "run-1",
        "issue_synthesis",
        "issue-1",
        input_data(),
        prompt="issue-synthesis.md",
        schema="issue-synthesis.schema.json",
        metadata={"required_skills": ["human-writing", "humanizer"]},
    )
    output_path = tmp_path / task["output_path"]
    write_json(output_path, {TASK_BINDING_KEY: read_json(tmp_path / task["input_path"])[TASK_BINDING_KEY], **valid_output()})
    db.execute("UPDATE tasks SET status='APPLIED', error='old' WHERE id=?", (task["id"],))

    replaced = service.create(
        "run-1",
        "issue_synthesis",
        "issue-1",
        {**input_data(), "max_judgements": 3},
        prompt="issue-synthesis.md",
        schema="issue-synthesis.schema.json",
        metadata={"required_skills": ["human-writing", "humanizer"]},
        replace_existing=True,
    )

    assert not output_path.exists()
    assert db.fetchone("SELECT status,error FROM tasks WHERE id=?", (task["id"],)) == {"status": "PENDING", "error": None}
    instructions = service.instructions(replaced)
    assert "$human-writing, $humanizer" in instructions
    assert instructions.index("$human-writing") < instructions.index("$humanizer")
