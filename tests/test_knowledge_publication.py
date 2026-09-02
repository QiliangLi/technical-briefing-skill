from __future__ import annotations

import copy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from briefing_skill.knowledge_graph import build_knowledge_graph_file
from briefing_skill.knowledge_materialization import (
    apply_knowledge_task,
    prepare_knowledge_tasks,
)
from briefing_skill.knowledge_publication import (
    build_issue_diff,
    build_manifest,
    issue_diff_semantic_errors,
    validate_issue_diffs,
    validate_manifest,
    write_issue_diff,
    write_manifest,
)
from briefing_skill.utils import read_json, write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = (
    "frontier-clusters.schema.json",
    "roadmap.schema.json",
    "idea.schema.json",
    "knowledge-index.schema.json",
    "knowledge-materialization.schema.json",
    "knowledge-graph.schema.json",
    "knowledge-manifest.schema.json",
    "issue-change-projection.schema.json",
)


def _item(item_id: str, issue_date: str, *, url: str, title: str = "证据") -> dict:
    return {
        "brief_item_id": item_id,
        "topic_id": "topic_a",
        "topic_name": "专题 A",
        "direction_id": "direction_a",
        "direction_name": "方向 A",
        "item_role": "core",
        "title": title,
        "published_at": issue_date,
        "core_conclusion": f"{title}的机器结论。",
        "mechanism": "明确机制。",
        "result": "已有结果。",
        "boundary": "仍有边界。",
        "project_relevance": "需要继续验证。",
        "keywords": ["测试"],
        "sources": [{"url": url, "source_level": "A", "primary": True}],
    }


def _published_issue(root: Path, issue_date: str, items: list[dict]) -> None:
    issue_dir = root / "archive" / "issues" / issue_date
    write_json(
        issue_dir / "issue.json",
        {
            "id": f"issue-{issue_date}",
            "date_from": issue_date,
            "date_to": issue_date,
            "items": items,
            "core_items": items,
            "observations": [],
            "synthesis": {"headline": "测试", "radar_signals": []},
        },
    )
    write_json(
        issue_dir / "papers.json",
        [
            {
                "item_id": item["brief_item_id"],
                "role": "core",
                "url": item["sources"][0]["url"],
                "issue_date": issue_date,
            }
            for item in items
        ],
    )


def _set_index(root: Path, dates: list[str]) -> None:
    write_json(
        root / "archive" / "index.json",
        {"issues": [{"date": date, "papers_file": f"issues/{date}/papers.json"} for date in dates]},
    )


def _ref(item_id: str, issue_date: str, url: str) -> dict:
    return {"item_id": item_id, "issue_date": issue_date, "source_urls": [url], "reason": "时间线记录。"}


def _root(tmp_path: Path) -> Path:
    for name in SCHEMAS:
        target = tmp_path / "schemas" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / "schemas" / name, target)
    _published_issue(
        tmp_path,
        "2026-08-01",
        [_item("item_one", "2026-08-01", url="https://example.com/one", title="第一条证据")],
    )
    _set_index(tmp_path, ["2026-08-01"])
    return tmp_path


def _roadmap_output(root: Path, task: dict, *, refs: list[dict], summary: str) -> dict:
    input_data = read_json(root / task["input_path"])
    binding = input_data["_task"]
    return {
        "_task": binding,
        "roadmap": {
            "roadmap_id": "roadmap_topic_a",
            "topic_id": "topic_a",
            "topic_name": "专题 A",
            "evidence_scope": "published_archive_only",
            "updated_by_issue": binding["issue_date"],
            "summary": summary,
            "view_mode": "evidence_timeline",
            "branches": [
                {
                    "branch_id": "direction_a",
                    "name": "方向 A",
                    "direction_ids": ["direction_a"],
                    "status": "emerging",
                    "stages": [],
                    "evidence_timeline": refs,
                    "open_questions": [],
                    "evidence_item_ids": [ref["item_id"] for ref in refs],
                    "source_urls": sorted({url for ref in refs for url in ref["source_urls"]}),
                }
            ],
        },
        "ideas": [],
        "frontier_clusters": [],
    }


def _apply_first_task(root: Path, *, summary: str) -> dict:
    (task,) = prepare_knowledge_tasks(root, issue_date="2026-08-01")
    refs = [_ref("item_one", "2026-08-01", "https://example.com/one")]
    output_path = root / task["output_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, _roadmap_output(root, task, refs=refs, summary=summary))
    return apply_knowledge_task(root, task["task_id"])


def test_manifest_states_move_archive_only_to_knowledge_complete(tmp_path: Path):
    root = _root(tmp_path)
    build_knowledge_graph_file(root)

    # Nothing materialized yet: archive_only with the head issue pending.
    manifest = write_manifest(root)
    assert manifest["publication_state"] == "archive_only"
    assert manifest["pending_issues"] == ["2026-08-01"]
    assert validate_manifest(root) == []

    # Preparing tasks flips the state to analysis_pending.
    prepare_knowledge_tasks(root, issue_date="2026-08-01")
    manifest = write_manifest(root)
    assert manifest["publication_state"] == "analysis_pending"
    assert manifest["analysis_target_issue"] == "2026-08-01"
    assert manifest["affected_topics"] == 1
    assert manifest["completed_topics"] == 0
    assert validate_manifest(root) == []

    # Applying the task completes the watermark; diff + graph + manifest chain.
    _apply_first_task(root, summary="方向 A 已有一条已发布证据支持早期机制信号，当前按证据时间线观察，出现第二条独立复现后可升级判断。")
    build_knowledge_graph_file(root)
    diff = write_issue_diff(root, issue_date="2026-08-01")
    assert diff["status"] == "complete"
    manifest = write_manifest(root)
    assert manifest["publication_state"] == "knowledge_complete"
    assert manifest["pending_issues"] == []
    assert manifest["materialized_through_issue"] == "2026-08-01"
    assert manifest["snapshot_id"] == diff["knowledge_snapshot_id"]
    assert validate_manifest(root) == []
    assert validate_issue_diffs(root) == []


def test_manifest_gate_fails_on_premature_knowledge_complete(tmp_path: Path):
    root = _root(tmp_path)
    _apply_first_task(root, summary="方向 A 已有一条已发布证据支持早期机制信号，当前按证据时间线观察，出现第二条独立复现后可升级判断。")
    build_knowledge_graph_file(root)
    write_issue_diff(root, issue_date="2026-08-01")
    manifest = write_manifest(root)
    assert manifest["publication_state"] == "knowledge_complete"

    # A newer archive issue breaks knowledge_complete: the manifest must then
    # fail validation (and the Pages gate stops) until the backlog is analyzed.
    _published_issue(
        root,
        "2026-08-02",
        [_item("item_two", "2026-08-02", url="https://example.com/two", title="第二条证据")],
    )
    _set_index(root, ["2026-08-01", "2026-08-02"])
    errors = validate_manifest(root)
    assert errors, "knowledge_complete must fail once the archive head moves ahead"
    assert any("knowledge_complete" in error for error in errors)


def test_issue_diff_rejects_seed_template_judgements(tmp_path: Path):
    root = _root(tmp_path)
    _apply_first_task(root, summary="方向 A 已有一条已发布证据支持早期机制信号，当前按证据时间线观察，出现第二条独立复现后可升级判断。")
    diff = build_issue_diff(root, issue_date="2026-08-01")
    assert len(diff["topic_changes"]) == 1
    row = diff["topic_changes"][0]
    assert row["change_kind"] == "material_change"
    assert row["origin"] == "applied_task"
    assert row["current_judgement"].startswith("方向 A")
    assert row["evidence_item_ids"] == ["item_one"]
    assert issue_diff_semantic_errors(root, diff) == []

    template = "现有公开归档为“专题 A”积累了 1 条专题证据，但时间跨度和跨期关联仍不足以可靠划分技术阶段，首版先保留可追溯的证据时间线。"
    with_template = copy.deepcopy(diff)
    with_template["topic_changes"][0]["current_judgement"] = template
    errors = issue_diff_semantic_errors(root, with_template)
    assert any("current_judgement" in error for error in errors)

    without_judgement = copy.deepcopy(diff)
    del without_judgement["topic_changes"][0]["current_judgement"]
    errors = issue_diff_semantic_errors(root, without_judgement)
    assert any("current_judgement" in error for error in errors)

    with pytest.raises(ValueError, match="issue is not published"):
        build_issue_diff(root, issue_date="2030-01-01")


def test_cli_manifest_and_diff_commands(tmp_path: Path):
    root = _root(tmp_path)
    build_knowledge_graph_file(root)
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "briefing.py"), "--root", str(root), "knowledge", "manifest", "build"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "archive_only" in result.stdout
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "briefing.py"), "--root", str(root), "knowledge", "manifest", "validate"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"valid": true' in result.stdout
    # The diff subcommand exists and rejects unknown issue dates.
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "briefing.py"),
            "--root",
            str(root),
            "knowledge",
            "diff",
            "build",
            "--issue",
            "2030-01-01",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
