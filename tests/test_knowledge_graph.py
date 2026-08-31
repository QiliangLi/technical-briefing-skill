from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from briefing_skill.knowledge_graph import (
    MAX_UNRESOLVED,
    build_knowledge_graph,
    build_knowledge_graph_file,
    graph_schema_errors,
    validate_knowledge_graph,
)
from briefing_skill.utils import read_json, write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ("knowledge-graph.schema.json",)


def _item(item_id: str, issue_date: str, *, url: str, title: str = "证据", topic_id: str = "topic_a",
           topic_name: str = "专题 A", direction_id: str = "direction_a", direction_name: str = "方向 A") -> dict:
    return {
        "brief_item_id": item_id,
        "topic_id": topic_id,
        "topic_name": topic_name,
        "direction_id": direction_id,
        "direction_name": direction_name,
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


def _published_issue(root: Path, issue_date: str, items: list[dict], judgements: list[dict] | None = None) -> None:
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
            "synthesis": {"headline": "测试", "radar_signals": [], "judgements": judgements or []},
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
                "source_level": "A",
            }
            for item in items
        ],
    )


def _set_index(root: Path, dates: list[str]) -> None:
    write_json(
        root / "archive" / "index.json",
        {"issues": [{"date": date, "papers_file": f"issues/{date}/papers.json"} for date in dates]},
    )


def _roadmap(topic_id: str, updated_by_issue: str, branches: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "roadmap_id": f"roadmap_{topic_id}",
        "topic_id": topic_id,
        "topic_name": f"专题 {topic_id}",
        "version": 1,
        "evidence_scope": "published_archive_only",
        "updated_by_issue": updated_by_issue,
        "change_type": "material_change",
        "view_mode": "evidence_timeline",
        "summary": "测试 Roadmap。",
        "branches": branches,
        "history": [],
        "change_log": [],
    }


def _idea(idea_id: str, *, topic_ids: list[str], evidence_for: list[dict], evidence_against: list[dict] | None = None,
          last_updated_issue: str = "2026-08-01") -> dict:
    return {
        "schema_version": 1,
        "idea_id": idea_id,
        "identity": {"problem_key": "p", "mechanism_key": "m", "target_key": "t"},
        "idea_type": "solution_concept",
        "title": f"Idea {idea_id}",
        "problem": "问题。",
        "hypothesis": "假设。",
        "mechanism": "机制。",
        "expected_effect": "预期。",
        "topic_ids": topic_ids,
        "status": "observing",
        "evidence_for": evidence_for,
        "evidence_against": evidence_against or [],
        "unknowns": ["未知一"],
        "validation_plan": None,
        "first_seen_issue": last_updated_issue,
        "last_updated_issue": last_updated_issue,
        "decision_log": [],
    }


def _write_knowledge(root: Path, *, roadmaps: list[dict], ideas: list[dict]) -> None:
    for roadmap in roadmaps:
        write_json(root / "knowledge" / "roadmaps" / f"{roadmap['topic_id']}.json", roadmap)
    for idea in ideas:
        write_json(root / "knowledge" / "ideas" / f"{idea['idea_id']}.json", idea)
    write_json(
        root / "knowledge" / "index.json",
        {
            "schema_version": 1,
            "evidence_scope": "published_archive_only",
            "roadmaps": [
                {
                    "topic_id": roadmap["topic_id"],
                    "topic_name": roadmap["topic_name"],
                    "path": f"knowledge/roadmaps/{roadmap['topic_id']}.json",
                    "version": 1,
                    "change_type": "material_change",
                    "updated_by_issue": roadmap["updated_by_issue"],
                    "summary": roadmap["summary"],
                }
                for roadmap in roadmaps
            ],
            "ideas": [
                {
                    "idea_id": idea["idea_id"],
                    "title": idea["title"],
                    "idea_type": idea["idea_type"],
                    "status": idea["status"],
                    "topic_ids": idea["topic_ids"],
                    "path": f"knowledge/ideas/{idea['idea_id']}.json",
                    "last_updated_issue": idea["last_updated_issue"],
                }
                for idea in ideas
            ],
            "frontier_clusters": [],
        },
    )


def _fixture_root(tmp_path: Path, *, with_knowledge: bool = True) -> Path:
    for name in SCHEMAS:
        target = tmp_path / "schemas" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / "schemas" / name, target)
    items = [
        _item("item_one", "2026-08-01", url="https://example.com/one", title="第一条证据"),
        _item("item_two", "2026-08-01", url="https://example.com/two", title="第二条证据"),
    ]
    judgements = [
        {
            "title": "编辑判断一",
            "body": "两条证据共同支持一个判断。",
            "evidence_item_ids": ["item_one", "item_two"],
        }
    ]
    _published_issue(tmp_path, "2026-08-01", items, judgements)
    _item_three = _item("item_three", "2026-08-08", url="https://example.com/three", title="第三条证据")
    _published_issue(tmp_path, "2026-08-08", [_item_three])
    _set_index(tmp_path, ["2026-08-01", "2026-08-08"])
    if with_knowledge:
        _write_knowledge(
            tmp_path,
            roadmaps=[
                _roadmap(
                    "topic_a",
                    "2026-08-01",
                    [
                        {
                            "branch_id": "branch_a",
                            "name": "分支 A",
                            "direction_ids": ["direction_a"],
                            "status": "emerging",
                            "stages": [],
                            "evidence_timeline": [
                                {"item_id": "item_one", "issue_date": "2026-08-01", "source_urls": [], "reason": "首见。"}
                            ],
                            "open_questions": [],
                            "evidence_item_ids": ["item_one"],
                            "source_urls": [],
                        }
                    ],
                )
            ],
            ideas=[
                _idea(
                    "idea_test_one",
                    topic_ids=["topic_a"],
                    evidence_for=[
                        {
                            "item_id": "item_two",
                            "issue_date": "2026-08-01",
                            "source_urls": ["https://example.com/two"],
                            "reason": "支持理由。",
                        }
                    ],
                    evidence_against=[
                        {
                            "item_id": "item_three",
                            "issue_date": "2026-08-08",
                            "source_urls": ["https://example.com/three"],
                            "reason": "反对理由。",
                        }
                    ],
                )
            ],
        )
    return tmp_path


def _node_ids(document: dict) -> set[str]:
    return {node["data"]["id"] for node in document["nodes"]}


def _edges(document: dict) -> set[tuple[str, str, str]]:
    return {(edge["data"]["source"], edge["data"]["target"], edge["data"]["relation"]) for edge in document["edges"]}


def test_build_is_deterministic_and_schema_valid(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    first = build_knowledge_graph(root)
    second = build_knowledge_graph(root)
    assert first == second
    assert graph_schema_errors(root, first) == []


def test_build_through_issue_limits_watermark(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    document = build_knowledge_graph(root, issue_date="2026-08-01")
    assert document["archive_through_issue"] == "2026-08-01"
    ids = _node_ids(document)
    assert "item:item_three" not in ids
    assert "issue:2026-08-08" not in ids
    for expected in (
        "topic:topic_a",
        "direction:direction_a",
        "item:item_one",
        "item:item_two",
        "issue:2026-08-01",
        "roadmap:topic_a",
        "branch:topic_a:branch_a",
        "idea:idea_test_one",
    ):
        assert expected in ids
    assert sum(1 for node in document["nodes"] if node["data"]["kind"] == "judgement") == 1


def test_explicit_relations_use_contract_directions(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    document = build_knowledge_graph(root)
    edges = _edges(document)
    assert ("topic:topic_a", "direction:direction_a", "has_direction") in edges
    assert ("direction:direction_a", "item:item_one", "has_item") in edges
    assert ("item:item_one", "issue:2026-08-01", "published_in") in edges
    assert ("item:item_two", "judgement:2026-08-01:" + _judgement_digest_of(document), "supports_judgement") in edges
    assert ("roadmap:topic_a", "topic:topic_a", "tracks") in edges
    assert ("branch:topic_a:branch_a", "direction:direction_a", "organizes") in edges
    assert ("branch:topic_a:branch_a", "item:item_one", "uses_evidence") in edges
    assert ("idea:idea_test_one", "topic:topic_a", "relates_to") in edges
    assert ("item:item_two", "idea:idea_test_one", "supports_idea") in edges
    assert ("item:item_three", "idea:idea_test_one", "challenges_idea") in edges
    # The reverse direction must never appear for the same fact.
    assert ("direction:direction_a", "topic:topic_a", "has_direction") not in edges
    assert ("idea:idea_test_one", "item:item_two", "supports_idea") not in edges


def _judgement_digest_of(document: dict) -> str:
    return next(
        node["data"]["id"].split(":", 2)[2] for node in document["nodes"] if node["data"]["kind"] == "judgement"
    )


def test_judgement_digest_ignores_evidence_order_and_uses_title(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    first = build_knowledge_graph(root)
    # Reorder evidence ids in the source; the stable digest must not change.
    issue_path = root / "archive" / "issues" / "2026-08-01" / "issue.json"
    issue = read_json(issue_path)
    issue["synthesis"]["judgements"][0]["evidence_item_ids"] = ["item_two", "item_one"]
    write_json(issue_path, issue)
    second = build_knowledge_graph(root)
    assert _judgement_digest_of(first) == _judgement_digest_of(second)
    issue["synthesis"]["judgements"][0]["title"] = "编辑判断一（改）"
    write_json(issue_path, issue)
    third = build_knowledge_graph(root)
    assert _judgement_digest_of(first) != _judgement_digest_of(third)


def test_watermarks_are_layered_not_merged(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    document = build_knowledge_graph(root)
    assert document["archive_through_issue"] == "2026-08-08"
    assert document["knowledge_through_issue"] == "2026-08-01"


def test_dangling_references_enter_unresolved(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    issue_path = root / "archive" / "issues" / "2026-08-01" / "issue.json"
    issue = read_json(issue_path)
    issue["synthesis"]["judgements"].append(
        {"title": "悬空判断", "body": "引用不存在的条目。", "evidence_item_ids": ["missing_item"]}
    )
    write_json(issue_path, issue)
    idea_path = root / "knowledge" / "ideas" / "idea_test_one.json"
    idea = read_json(idea_path)
    idea["evidence_for"].append({"item_id": "ghost_item", "issue_date": "2026-08-01", "source_urls": ["https://example.com/x"], "reason": "悬空。"})
    write_json(idea_path, idea)
    document = build_knowledge_graph(root)
    reasons = {entry["reason"] for entry in document["unresolved"]}
    assert "dangling_judgement_evidence" in reasons
    assert "dangling_idea_evidence" in reasons
    # Dangling references never become drawn edges.
    assert all("item:missing_item" not in edge["data"]["source"] for edge in document["edges"])
    assert document["stats"]["unresolved_count"] == len(document["unresolved"])


def test_unresolved_over_budget_fails_the_build(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    issue_path = root / "archive" / "issues" / "2026-08-01" / "issue.json"
    issue = read_json(issue_path)
    for index in range(MAX_UNRESOLVED + 1):
        issue["synthesis"]["judgements"].append(
            {"title": f"悬空判断 {index}", "body": "x", "evidence_item_ids": [f"missing_{index}"]}
        )
    write_json(issue_path, issue)
    with pytest.raises(ValueError, match="unresolved"):
        build_knowledge_graph(root)


def test_relation_kind_mismatch_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    roadmap = read_json(root / "knowledge" / "roadmaps" / "topic_a.json")
    roadmap["branches"][0]["direction_ids"] = []
    write_json(root / "knowledge" / "roadmaps" / "topic_a.json", roadmap)
    document = build_knowledge_graph(root)
    edges = _edges(document)
    assert all(relation != "organizes" for _, _, relation in edges)
    # A direction id that appears nowhere still materializes an explicit node;
    # the organizes edge then links branch -> direction with valid kinds.
    roadmap["branches"][0]["direction_ids"] = ["direction_only_in_roadmap"]
    write_json(root / "knowledge" / "roadmaps" / "topic_a.json", roadmap)
    document = build_knowledge_graph(root)
    assert ("branch:topic_a:branch_a", "direction:direction_only_in_roadmap", "organizes") in _edges(document)
    assert "direction:direction_only_in_roadmap" in _node_ids(document)


def test_missing_direction_records_unresolved_without_edge(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    broken = _item("item_broken", "2026-08-08", url="https://example.com/broken", topic_id="", direction_id="")
    issue_path = root / "archive" / "issues" / "2026-08-08" / "issue.json"
    issue = read_json(issue_path)
    issue["items"].append(broken)
    write_json(issue_path, issue)
    papers_path = root / "archive" / "issues" / "2026-08-08" / "papers.json"
    papers = read_json(papers_path)
    papers.append({"item_id": "item_broken", "role": "core", "url": "https://example.com/broken", "issue_date": "2026-08-08"})
    write_json(papers_path, papers)
    document = build_knowledge_graph(root)
    assert any(entry["reason"] == "missing_item_direction" and entry["source_ref"] == "item:item_broken"
               for entry in document["unresolved"])
    assert not any(edge["data"]["source"] == "item:item_broken" and edge["data"]["relation"] == "has_item"
                   for edge in document["edges"])
    # The item itself still exists with its published_in edge.
    assert ("item:item_broken", "issue:2026-08-08", "published_in") in _edges(document)


def test_positions_are_stable_and_layered(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    first = build_knowledge_graph(root)
    second = build_knowledge_graph(root)
    positions_first = {node["data"]["id"]: node["position"] for node in first["nodes"]}
    positions_second = {node["data"]["id"]: node["position"] for node in second["nodes"]}
    assert positions_first == positions_second
    assert len({(p["x"], p["y"]) for p in positions_first.values()}) == len(positions_first)
    columns = {node["data"]["kind"]: node["position"]["x"] for node in first["nodes"]}
    assert columns["topic"] < columns["direction"] < columns["item"] < columns["judgement"]


def test_output_order_is_kind_then_topic_then_direction_then_date(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    document = build_knowledge_graph(root)
    keys = [
        (
            {"roadmap": 0, "topic": 1, "roadmap_branch": 2, "direction": 3, "item": 4, "judgement": 5, "issue": 5, "idea": 6}[node["data"]["kind"]],
            node["data"].get("topic_id") or "",
            node["data"].get("direction_id") or "",
            node["data"].get("issue_date") or "",
            node["data"]["id"],
        )
        for node in document["nodes"]
    ]
    assert keys == sorted(keys)


def test_source_date_epoch_pins_generated_at_and_double_write_is_idempotent(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    import os
    from datetime import datetime, timezone

    os.environ["SOURCE_DATE_EPOCH"] = "1800000000"
    try:
        expected = (
            datetime.fromtimestamp(1800000000, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        first = build_knowledge_graph_file(root)
        second = build_knowledge_graph_file(root)
        assert first == second
        assert first["generated_at"] == expected
        on_disk = read_json(root / "knowledge" / "graph.json")
        assert on_disk == first
    finally:
        del os.environ["SOURCE_DATE_EPOCH"]


def test_failed_build_preserves_previous_graph_file(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    good = build_knowledge_graph_file(root)
    # Break an input after a successful build.
    issue_path = root / "archive" / "issues" / "2026-08-01" / "issue.json"
    issue_path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValueError):
        build_knowledge_graph_file(root)
    assert read_json(root / "knowledge" / "graph.json") == good


def test_validate_detects_stale_digest_and_passes_when_fresh(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    build_knowledge_graph_file(root)
    assert validate_knowledge_graph(root) == []
    # Any authoritative input change must invalidate the published document.
    issue_path = root / "archive" / "issues" / "2026-08-01" / "issue.json"
    issue = read_json(issue_path)
    issue["synthesis"]["judgements"][0]["title"] = "编辑判断一（更新）"
    write_json(issue_path, issue)
    errors = validate_knowledge_graph(root)
    assert errors
    assert any("input_digest" in error or "nodes" in error for error in errors)
    build_knowledge_graph_file(root)
    assert validate_knowledge_graph(root) == []


def test_validate_flags_missing_file(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    errors = validate_knowledge_graph(root)
    assert errors and "missing" in errors[0]


def test_archive_counts_match_graph_stats(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    document = build_knowledge_graph(root)
    kinds = {}
    for node in document["nodes"]:
        kinds[node["data"]["kind"]] = kinds.get(node["data"]["kind"], 0) + 1
    assert kinds["item"] == 3
    assert kinds["issue"] == 2
    assert kinds["topic"] == 1
    assert kinds["direction"] == 1
    assert kinds["judgement"] == 1
    assert kinds["roadmap"] == 1
    assert kinds["roadmap_branch"] == 1
    assert kinds["idea"] == 1
    assert document["stats"]["node_count"] == sum(kinds.values())


def test_duplicate_item_across_issues_merges_with_coverage_window(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    repeat = _item("item_one", "2026-08-15", url="https://example.com/one-again", title="第一条证据（复现）")
    _published_issue(root, "2026-08-15", [repeat])
    _set_index(root, ["2026-08-01", "2026-08-08", "2026-08-15"])
    document = build_knowledge_graph(root)
    item_nodes = [node for node in document["nodes"] if node["data"]["id"] == "item:item_one"]
    assert len(item_nodes) == 1
    assert item_nodes[0]["data"]["first_issue_date"] == "2026-08-01"
    assert item_nodes[0]["data"]["last_issue_date"] == "2026-08-15"
    edges = _edges(document)
    assert ("item:item_one", "issue:2026-08-01", "published_in") in edges
    assert ("item:item_one", "issue:2026-08-15", "published_in") in edges
    assert len({node["position"]["x"] for node in document["nodes"]}) > 1


def test_cli_exposes_graph_build_and_validate(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    result = subprocess.run(
        [sys.executable, "briefing.py", "knowledge", "graph", "--help"],
        cwd=REPO_ROOT, check=True, capture_output=True, text=True,
    )
    assert "build" in result.stdout
    assert "validate" in result.stdout
    build = subprocess.run(
        [sys.executable, "briefing.py", "--root", str(root), "knowledge", "graph", "build"],
        cwd=REPO_ROOT, check=True, capture_output=True, text=True,
    )
    assert '"written": "knowledge/graph.json"' in build.stdout
    validate = subprocess.run(
        [sys.executable, "briefing.py", "--root", str(root), "knowledge", "graph", "validate"],
        cwd=REPO_ROOT, check=True, capture_output=True, text=True,
    )
    assert '"valid": true' in validate.stdout


def test_committed_repo_builds_and_validates() -> None:
    document = build_knowledge_graph(REPO_ROOT)
    assert document["archive_through_issue"], "committed archive must produce a watermark"
    assert graph_schema_errors(REPO_ROOT, document) == []
    write_json(REPO_ROOT / "knowledge" / "graph.json", document)
    assert validate_knowledge_graph(REPO_ROOT) == []
