from __future__ import annotations

import copy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from briefing_skill.knowledge_materialization import (
    PublishedArchive,
    affected_topics,
    apply_knowledge_task,
    frontier_cluster_semantic_errors,
    idea_semantic_errors,
    prepare_knowledge_tasks,
    roadmap_semantic_errors,
    stable_idea_id,
    validate_knowledge_store,
)
from briefing_skill.utils import read_json, stable_hash, write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = (
    "frontier-clusters.schema.json",
    "roadmap.schema.json",
    "idea.schema.json",
    "knowledge-index.schema.json",
    "knowledge-materialization.schema.json",
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


def _add_radar(root: Path, issue_date: str, *, category: str, url: str, title: str) -> str:
    issue_path = root / "archive" / "issues" / issue_date / "issue.json"
    papers_path = root / "archive" / "issues" / issue_date / "papers.json"
    issue = read_json(issue_path)
    issue.setdefault("synthesis", {}).setdefault("radar_signals", []).append(
        {"category": category, "signal": title, "summary": "边界 Radar 公开信号。", "source_urls": [url]}
    )
    write_json(issue_path, issue)
    papers = read_json(papers_path)
    papers.append(
        {
            "paper_key": f"radar-{issue_date}",
            "title": title,
            "url": url,
            "topic_id": None,
            "topic_name": category,
            "direction_id": None,
            "role": "radar",
            "item_id": None,
            "issue_date": issue_date,
        }
    )
    write_json(papers_path, papers)
    return f"radar_{stable_hash(issue_date, url, length=20)}"


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


def _roadmap_output(task: dict, *, refs: list[dict], summary: str = "当前只够形成证据时间线。") -> dict:
    input_data = read_json(task["input_path"])
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


def _ref(item_id: str, issue_date: str, url: str) -> dict:
    return {
        "item_id": item_id,
        "issue_date": issue_date,
        "source_urls": [url],
        "reason": "该记录仅用于证据时间线。",
    }


def test_archive_loader_reads_only_published_machine_records(tmp_path: Path):
    root = _root(tmp_path)
    # An unlisted directory and reader projection must never enter knowledge evidence.
    _published_issue(
        root,
        "2026-08-02",
        [_item("unpublished", "2026-08-02", url="https://example.com/unpublished")],
    )
    write_json(root / "archive" / "issues" / "2026-08-01" / "reader.json", {"invented": True})

    archive = PublishedArchive(root)
    evidence = archive.evidence_through("2026-08-01")

    assert [item["item_id"] for item in evidence] == ["item_one"]
    assert evidence[0]["core_conclusion"] == "第一条证据的机器结论。"
    assert affected_topics(root, "2026-08-01") == [
        {"topic_id": "topic_a", "topic_name": "专题 A"}
    ]


def test_published_radar_is_frontier_evidence_with_category_and_direction(tmp_path: Path):
    root = _root(tmp_path)
    _add_radar(
        root,
        "2026-08-01",
        category="Agent生态",
        url="https://example.com/radar-agent",
        title="Agent 边界信号",
    )

    evidence = PublishedArchive(root).evidence_through("2026-08-01")
    radar = next(item for item in evidence if item["role"] == "radar")
    assert radar["topic_id"] == "frontier_exploration"
    assert radar["topic_name"] == "边界探索"
    assert radar["frontier_category"] == "Agent生态"
    assert radar["direction_id"] == "agent_ecosystem"
    assert {row["topic_id"] for row in affected_topics(root, "2026-08-01")} == {
        "topic_a",
        "frontier_exploration",
    }


def test_frontier_task_updates_only_clusters_and_is_idempotent(tmp_path: Path):
    root = _root(tmp_path)
    radar_id = _add_radar(
        root,
        "2026-08-01",
        category="其他技术前沿",
        url="https://example.com/radar-frontier",
        title="前沿信号",
    )
    task = prepare_knowledge_tasks(
        root, issue_date="2026-08-01", topic_ids=["frontier_exploration"]
    )[0]
    input_path = root / task["input_path"]
    output_path = root / task["output_path"]
    binding = read_json(input_path)["_task"]
    cluster = {
        "cluster_id": "frontier_other_frontier",
        "name": "其他技术前沿公开信号",
        "categories": ["其他技术前沿"],
        "status": "temporary",
        "first_seen_issue": "2026-08-01",
        "last_seen_issue": "2026-08-01",
        "evidence_item_ids": [radar_id],
        "source_urls": ["https://example.com/radar-frontier"],
        "idea_ids": [],
        "promotion_reason": None,
        "promotion_target": None,
    }
    write_json(
        output_path,
        {"_task": binding, "roadmap": None, "ideas": [], "frontier_clusters": [cluster]},
    )

    applied = apply_knowledge_task(root, task["task_id"])
    assert applied["change_type"] == "clusters_updated"
    assert applied["roadmap_version"] is None
    assert not (root / "knowledge" / "roadmaps" / "frontier_exploration.json").exists()
    assert read_json(root / "knowledge" / "frontier-clusters.json")["clusters"] == [cluster]
    assert apply_knowledge_task(root, task["task_id"])["idempotent"] is True
    assert prepare_knowledge_tasks(
        root, issue_date="2026-08-01", topic_ids=["frontier_exploration"]
    ) == []


def test_frontier_rejects_catch_all_roadmap_and_unbound_promotion(tmp_path: Path):
    root = _root(tmp_path)
    radar_id = _add_radar(
        root,
        "2026-08-01",
        category="AI Infra",
        url="https://example.com/radar-ai",
        title="AI Infra 信号",
    )
    task = prepare_knowledge_tasks(
        root, issue_date="2026-08-01", topic_ids=["frontier_exploration"]
    )[0]
    input_path = root / task["input_path"]
    output_path = root / task["output_path"]
    binding = read_json(input_path)["_task"]
    roadmap = _roadmap_output(
        {"input_path": input_path},
        refs=[_ref("item_one", "2026-08-01", "https://example.com/one")],
    )["roadmap"]
    roadmap["topic_id"] = "frontier_exploration"
    roadmap["topic_name"] = "边界探索"
    roadmap["roadmap_id"] = "roadmap_frontier_exploration"
    write_json(
        output_path,
        {"_task": binding, "roadmap": roadmap, "ideas": [], "frontier_clusters": []},
    )
    with pytest.raises(ValueError, match="roadmap must be null"):
        apply_knowledge_task(root, task["task_id"])

    evidence = PublishedArchive(root).evidence_through("2026-08-01")
    promoted = {
        "cluster_id": "frontier_ai_infra",
        "name": "AI Infra 公开信号",
        "categories": ["AI Infra"],
        "status": "promoted",
        "first_seen_issue": "2026-08-01",
        "last_seen_issue": "2026-08-01",
        "evidence_item_ids": [radar_id],
        "source_urls": ["https://example.com/radar-ai"],
        "idea_ids": [],
        "promotion_reason": "形成稳定机制。",
        "promotion_target": None,
    }
    errors = frontier_cluster_semantic_errors(
        [promoted],
        topic_id="frontier_exploration",
        evidence=evidence,
        allowed_idea_ids=set(),
    )
    assert "frontier cluster 0 promotion requires a stable target" in errors


def test_promoted_frontier_evidence_only_enters_exact_bound_branch(tmp_path: Path):
    root = _root(tmp_path)
    radar_id = _add_radar(
        root,
        "2026-08-01",
        category="Agent生态",
        url="https://example.com/radar-bound",
        title="可晋升信号",
    )
    evidence = PublishedArchive(root).evidence_through("2026-08-01")
    cluster = {
        "cluster_id": "frontier_agent_ecosystem",
        "name": "Agent 公开信号",
        "categories": ["Agent生态"],
        "status": "promoted",
        "first_seen_issue": "2026-08-01",
        "last_seen_issue": "2026-08-01",
        "evidence_item_ids": [radar_id],
        "source_urls": ["https://example.com/radar-bound"],
        "idea_ids": [],
        "promotion_reason": "已经形成稳定机制。",
        "promotion_target": {
            "topic_id": "topic_a",
            "topic_name": "专题 A",
            "branch_id": "direction_a",
        },
    }
    radar_ref = _ref(radar_id, "2026-08-01", "https://example.com/radar-bound")
    roadmap = {
        "roadmap_id": "roadmap_topic_a",
        "topic_id": "topic_a",
        "topic_name": "专题 A",
        "evidence_scope": "published_archive_only",
        "updated_by_issue": "2026-08-01",
        "summary": "显式晋升证据进入目标分支。",
        "view_mode": "evidence_timeline",
        "branches": [
            {
                "branch_id": "direction_a",
                "name": "方向 A",
                "direction_ids": ["direction_a"],
                "status": "emerging",
                "stages": [],
                "evidence_timeline": [radar_ref],
                "open_questions": [],
                "evidence_item_ids": [radar_id],
                "source_urls": ["https://example.com/radar-bound"],
            }
        ],
    }
    assert roadmap_semantic_errors(
        roadmap,
        topic_id="topic_a",
        issue_date="2026-08-01",
        evidence=evidence,
        promoted_clusters=[cluster],
    ) == []

    wrong_target = copy.deepcopy(cluster)
    wrong_target["promotion_target"]["branch_id"] = "another_branch"
    errors = roadmap_semantic_errors(
        roadmap,
        topic_id="topic_a",
        issue_date="2026-08-01",
        evidence=evidence,
        promoted_clusters=[wrong_target],
    )
    assert any("out-of-scope item_id" in error for error in errors)


def test_incremental_apply_is_topic_scoped_noop_aware_and_idempotent(tmp_path: Path):
    root = _root(tmp_path)
    first = prepare_knowledge_tasks(root, issue_date="2026-08-01")[0]
    first["input_path"] = root / first["input_path"]
    first["output_path"] = root / first["output_path"]
    write_json(
        first["output_path"],
        _roadmap_output(
            first,
            refs=[_ref("item_one", "2026-08-01", "https://example.com/one")],
        ),
    )
    applied = apply_knowledge_task(root, first["task_id"])
    assert applied["change_type"] == "material_change"
    assert applied["roadmap_version"] == 1

    again = apply_knowledge_task(root, first["task_id"])
    assert again["idempotent"] is True
    assert len(read_json(root / "knowledge" / "roadmaps" / "topic_a.json")["change_log"]) == 1

    _published_issue(
        root,
        "2026-08-02",
        [_item("item_two", "2026-08-02", url="https://example.com/two", title="第二条证据")],
    )
    _set_index(root, ["2026-08-01", "2026-08-02"])
    second = prepare_knowledge_tasks(root, issue_date="2026-08-02")[0]
    second["input_path"] = root / second["input_path"]
    second["output_path"] = root / second["output_path"]
    refs = [
        _ref("item_one", "2026-08-01", "https://example.com/one"),
        _ref("item_two", "2026-08-02", "https://example.com/two"),
    ]
    write_json(second["output_path"], _roadmap_output(second, refs=refs))
    applied = apply_knowledge_task(root, second["task_id"])

    roadmap = read_json(root / "knowledge" / "roadmaps" / "topic_a.json")
    assert applied["change_type"] == "no_material_change"
    assert roadmap["version"] == 1
    assert [row["change_type"] for row in roadmap["change_log"]] == [
        "material_change",
        "no_material_change",
    ]
    assert len(roadmap["history"]) == 1


def test_apply_rejects_cross_task_output_and_invented_source_url(tmp_path: Path):
    root = _root(tmp_path)
    task = prepare_knowledge_tasks(root, issue_date="2026-08-01")[0]
    task["input_path"] = root / task["input_path"]
    task["output_path"] = root / task["output_path"]
    output = _roadmap_output(
        task,
        refs=[_ref("item_one", "2026-08-01", "https://evil.example/invented")],
    )
    output["_task"] = {**output["_task"], "issue_date": "2026-07-31"}
    write_json(task["output_path"], output)
    with pytest.raises(ValueError, match="binding mismatch"):
        apply_knowledge_task(root, task["task_id"])

    output = _roadmap_output(
        task,
        refs=[_ref("item_one", "2026-08-01", "https://evil.example/invented")],
    )
    write_json(task["output_path"], output)
    with pytest.raises(ValueError, match="source_urls must be a non-empty subset"):
        apply_knowledge_task(root, task["task_id"])
    assert not (root / "knowledge" / "roadmaps" / "topic_a.json").exists()


def test_stable_idea_identity_does_not_merge_distinct_mechanisms():
    same_problem = "reduce_agent_tool_cost"
    first = stable_idea_id(
        {
            "problem_key": same_problem,
            "mechanism_key": "structured_tool_interface",
            "target_key": "coding_agent",
        }
    )
    second = stable_idea_id(
        {
            "problem_key": same_problem,
            "mechanism_key": "speculative_tool_execution",
            "target_key": "coding_agent",
        }
    )
    assert first != second
    assert first == stable_idea_id(
        {
            "problem_key": same_problem,
            "mechanism_key": "structured_tool_interface",
            "target_key": "coding_agent",
        }
    )


def test_cli_exposes_bounded_knowledge_commands():
    result = subprocess.run(
        [sys.executable, "briefing.py", "knowledge", "--help"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "prepare" in result.stdout


def test_committed_seed_is_public_path_resolvable_and_honest():
    assert validate_knowledge_store(REPO_ROOT) == []
    index = read_json(REPO_ROOT / "knowledge" / "index.json")
    assert index["schema_version"] == 1
    assert len(index["roadmaps"]) == 8
    assert len(index["ideas"]) == 6
    assert len(index["frontier_clusters"]) == 5
    assert all(cluster["status"] == "temporary" for cluster in index["frontier_clusters"])
    assert all(cluster["promotion_target"] is None for cluster in index["frontier_clusters"])
    assert "frontier_exploration" not in {entry["topic_id"] for entry in index["roadmaps"]}
    for entry in [*index["roadmaps"], *index["ideas"]]:
        assert entry["path"].startswith("knowledge/")
        assert (REPO_ROOT / entry["path"]).is_file()
    for entry in index["roadmaps"]:
        roadmap = read_json(REPO_ROOT / entry["path"])
        assert roadmap["view_mode"] == "evidence_timeline"
        assert all(not branch["stages"] for branch in roadmap["branches"])
        assert all(branch["evidence_timeline"] for branch in roadmap["branches"])
    for entry in index["ideas"]:
        idea = read_json(REPO_ROOT / entry["path"])
        assert idea["validation_plan"]["execution_status"] == "suggestion_only"


def test_rejection_and_reopen_require_append_only_audit_records():
    archive = PublishedArchive(REPO_ROOT)
    evidence = archive.evidence_through(archive.issue_dates()[-1])
    index = read_json(REPO_ROOT / "knowledge" / "index.json")
    idea_path = next(
        REPO_ROOT / entry["path"]
        for entry in index["ideas"]
        if entry["idea_type"] == "research_hypothesis" and "cross_region" in entry["topic_ids"]
    )
    previous = read_json(idea_path)

    invalid = copy.deepcopy(previous)
    invalid["status"] = "rejected"
    errors = idea_semantic_errors(
        invalid,
        issue_date=invalid["last_updated_issue"],
        evidence=evidence,
        previous=previous,
    )
    assert "an automatically rejected idea requires evidence_against" in errors
    assert "rejected status requires an appended rejected decision" in errors

    rejected = copy.deepcopy(previous)
    rejected["status"] = "rejected"
    cited_ids = {ref["item_id"] for ref in rejected["evidence_for"]}
    contrary_item = next(
        item
        for item in evidence
        if item["topic_id"] == "cross_region"
        and item["item_id"] not in cited_ids
        and item["source_urls"]
    )
    contrary = {
        "item_id": contrary_item["item_id"],
        "issue_date": contrary_item["issue_date"],
        "source_urls": contrary_item["source_urls"],
        "reason": "新增证据否定了该机制的关键前提。",
    }
    rejected["evidence_against"] = [contrary]
    rejected["decision_log"].append(
        {
            "event_id": "decision_rejected_test",
            "issue_date": rejected["last_updated_issue"],
            "decision": "rejected",
            "from_status": previous["status"],
            "to_status": "rejected",
            "reason": "反对证据否定关键前提。",
            "evidence_item_ids": [contrary["item_id"]],
        }
    )
    assert idea_semantic_errors(
        rejected,
        issue_date=rejected["last_updated_issue"],
        evidence=evidence,
        previous=previous,
    ) == []

    reopened = copy.deepcopy(rejected)
    reopened["status"] = "observing"
    reopened["decision_log"].append(
        {
            "event_id": "decision_reopened_test",
            "issue_date": reopened["last_updated_issue"],
            "decision": "reopened",
            "from_status": "rejected",
            "to_status": "observing",
            "reason": "保留新证据后重新打开观察。",
            "evidence_item_ids": [contrary["item_id"]],
        }
    )
    assert idea_semantic_errors(
        reopened,
        issue_date=reopened["last_updated_issue"],
        evidence=evidence,
        previous=rejected,
    ) == []
