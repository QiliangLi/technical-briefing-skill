from __future__ import annotations

import shutil
from pathlib import Path

from briefing_skill.db import Database
from briefing_skill.tasks import TASK_BINDING_KEY, TaskService
from briefing_skill.utils import read_json, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _service(tmp_path: Path, *schemas: str) -> tuple[Database, TaskService]:
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    db.create_run("run-1")
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir(parents=True)
    for schema in schemas:
        shutil.copy(PROJECT_ROOT / "schemas" / schema, schema_dir / schema)
    run_dir = tmp_path / "workspace" / "runs" / "run-1"
    return db, TaskService(db, tmp_path, run_dir)


def _facts(title: str) -> dict:
    return {
        "title": title,
        "event_hint": title,
        "problem": "具体问题。",
        "mechanism": "具体机制。",
        "evidence": [],
        "evaluation_context": "测试环境。",
        "limitations": "适用范围有限。",
        "project_relevance": "项目侧需要进一步验证。",
        "primary_source_resolved": True,
        "quality_score": 80,
    }


def _fact_input(candidate_id: str, source_id: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "source": {
            "title": f"Source {source_id}",
            "url": f"https://arxiv.org/abs/{source_id}",
            "discovery_only": False,
        },
        "document": {"document_id": source_id, "fetch_status": "FETCHED"},
    }


def test_swapped_fact_outputs_fail_closed_before_advance(tmp_path: Path) -> None:
    db, service = _service(tmp_path, "facts.schema.json")
    task_a = service.create(
        "run-1",
        "fact_extraction",
        "candidate-a",
        _fact_input("candidate-a", "2608.00001"),
        prompt="fact-extraction.md",
        schema="facts.schema.json",
    )
    task_b = service.create(
        "run-1",
        "fact_extraction",
        "candidate-b",
        _fact_input("candidate-b", "2608.00002"),
        prompt="fact-extraction.md",
        schema="facts.schema.json",
    )
    binding_a = read_json(tmp_path / task_a["input_path"])[TASK_BINDING_KEY]
    binding_b = read_json(tmp_path / task_b["input_path"])[TASK_BINDING_KEY]

    write_json(tmp_path / task_a["output_path"], {TASK_BINDING_KEY: binding_b, **_facts("Source B")})
    write_json(tmp_path / task_b["output_path"], {TASK_BINDING_KEY: binding_a, **_facts("Source A")})

    assert service.sync("run-1") == (0, 2)
    rows = db.fetchall("SELECT status, error FROM tasks ORDER BY id")
    assert all(row["status"] == "INVALID" for row in rows)
    assert all("task binding mismatch" in row["error"] for row in rows)


def test_correct_task_binding_is_removed_before_schema_validation(tmp_path: Path) -> None:
    _db, service = _service(tmp_path, "relevance.schema.json")
    task = service.create(
        "run-1",
        "relevance_review",
        "candidate-a",
        {"candidate_id": "candidate-a"},
        prompt="relevance-review.md",
        schema="relevance.schema.json",
    )
    binding = read_json(tmp_path / task["input_path"])[TASK_BINDING_KEY]
    result = {
        "relevant": True,
        "score": 80,
        "reason": "直接相关。",
        "fulltext_required": True,
    }
    write_json(tmp_path / task["output_path"], {TASK_BINDING_KEY: binding, **result})

    assert service.sync("run-1") == (1, 0)
    assert service.read_result(task) == result


def test_fact_extraction_rejects_wrong_article_even_with_correct_binding(tmp_path: Path) -> None:
    db, service = _service(tmp_path, "facts.schema.json")
    task = service.create(
        "run-1",
        "fact_extraction",
        "candidate-a",
        _fact_input("candidate-a", "2608.00001"),
        prompt="fact-extraction.md",
        schema="facts.schema.json",
    )
    binding = read_json(tmp_path / task["input_path"])[TASK_BINDING_KEY]
    write_json(
        tmp_path / task["output_path"],
        {TASK_BINDING_KEY: binding, **_facts("A completely different paper")},
    )

    assert service.sync("run-1") == (0, 1)
    error = db.fetchone("SELECT error FROM tasks WHERE id=?", (task["id"],))["error"]
    assert "tasked source title" in error


def test_fact_extraction_accepts_workspace_local_primary_source(tmp_path: Path) -> None:
    db, service = _service(tmp_path, "facts.schema.json")
    task_input = _fact_input("candidate-a", "2608.00001")
    task_input["document"]["fetch_status"] = "LOCAL_SOURCE"
    task = service.create(
        "run-1",
        "fact_extraction",
        "candidate-a",
        task_input,
        prompt="fact-extraction.md",
        schema="facts.schema.json",
    )
    binding = read_json(tmp_path / task["input_path"])[TASK_BINDING_KEY]
    write_json(
        tmp_path / task["output_path"],
        {TASK_BINDING_KEY: binding, **_facts("Source 2608.00001")},
    )

    assert service.sync("run-1") == (1, 0)
    assert db.fetchone("SELECT status FROM tasks WHERE id=?", (task["id"],))["status"] == "COMPLETED"


def test_item_writing_rejects_wrong_topic_and_invented_source(tmp_path: Path) -> None:
    db, service = _service(tmp_path, "brief-item.schema.json")
    task = service.create(
        "run-1",
        "item_writing",
        "event-a",
        {
            "event_id": "event-a",
            "topic": {"name": "AI Infra横向动态"},
            "direction": {"name": "推理服务"},
            "score": 80,
            "sources": [{"url": "https://arxiv.org/abs/2608.00001"}],
            "length": {"min_chars": 100, "max_chars": 1000},
        },
        prompt="item-writing.md",
        schema="brief-item.schema.json",
    )
    binding = read_json(tmp_path / task["input_path"])[TASK_BINDING_KEY]
    result = {
        "title": "错误专题的完整技术条目",
        "type": "论文",
        "topic_name": "Agent语义加速",
        "direction_name": "工具执行链",
        "published_at": "2026-08-05",
        "importance": "值得关注",
        "core_conclusion": "该方案面向具体系统瓶颈，通过可复现的机制降低关键路径开销，并在明确负载下报告了实验结果。",
        "mechanism": "系统通过分阶段调度、显式状态管理和受控资源分配降低关键路径开销。",
        "result": "实验在明确负载和硬件条件下相对基线获得稳定收益，并完整报告了边界条件。",
        "boundary": "结果尚未覆盖生产环境中的长尾负载和异常恢复场景。",
        "project_relevance": "判断：项目侧应先复现实验，再决定是否进入正式技术路线。",
        "keywords": ["系统", "推理", "调度"],
        "sources": [
            {
                "publisher": "arXiv",
                "url": "https://arxiv.org/abs/2608.99999",
                "source_level": "A",
                "primary": True,
                "published_at": "2026-08-05",
            }
        ],
        "score": 80,
    }
    write_json(tmp_path / task["output_path"], {TASK_BINDING_KEY: binding, **result})

    assert service.sync("run-1") == (0, 1)
    error = db.fetchone("SELECT error FROM tasks WHERE id=?", (task["id"],))["error"]
    assert "topic_name" in error
    assert "tasked source URLs" in error


def test_fact_check_cannot_pass_with_arxiv_homepage(tmp_path: Path) -> None:
    db, service = _service(tmp_path, "fact-check.schema.json", "brief-item.schema.json")
    task = service.create(
        "run-1",
        "fact_check",
        "item-a",
        {
            "brief_item": {
                "sources": [
                    {
                        "publisher": "arXiv",
                        "url": "https://arxiv.org",
                        "source_level": "A",
                        "primary": True,
                    }
                ]
            },
            "facts": [{"primary_source_resolved": True}],
        },
        prompt="fact-check.md",
        schema="fact-check.schema.json",
    )
    binding = read_json(tmp_path / task["input_path"])[TASK_BINDING_KEY]
    write_json(
        tmp_path / task["output_path"],
        {TASK_BINDING_KEY: binding, "pass": True, "issues": [], "corrected_item": None},
    )

    assert service.sync("run-1") == (0, 1)
    error = db.fetchone("SELECT error FROM tasks WHERE id=?", (task["id"],))["error"]
    assert "resolved primary A-level source URL" in error
