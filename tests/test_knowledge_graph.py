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
from briefing_skill.knowledge_materialization import stable_idea_id, validate_knowledge_store
from briefing_skill.utils import read_json, write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = (
    "knowledge-graph.schema.json",
    "knowledge-index.schema.json",
    "roadmap.schema.json",
    "idea.schema.json",
    "frontier-clusters.schema.json",
)


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


def _identity() -> dict:
    return {"problem_key": "fixture_problem", "mechanism_key": "fixture_mechanism", "target_key": "fixture_target"}


def _idea(evidence_for: list[dict], evidence_against: list[dict] | None = None,
          last_updated_issue: str = "2026-08-08") -> dict:
    all_refs = [*evidence_for, *(evidence_against or [])]
    return {
        "schema_version": 1,
        "idea_id": stable_idea_id(_identity()),
        "identity": _identity(),
        "idea_type": "solution_concept",
        "title": "测试 Idea",
        "problem": "问题。",
        "hypothesis": "假设。",
        "mechanism": "机制。",
        "expected_effect": "预期。",
        "topic_ids": ["topic_a"],
        "status": "observing",
        "evidence_for": evidence_for,
        "evidence_against": evidence_against or [],
        "unknowns": ["未知一"],
        "validation_plan": {
            "mode": "simulation",
            "minimal_model": "带缓存与路由的最小模拟。",
            "inputs": ["热度参数"],
            "baselines": ["无复制基线"],
            "metrics": ["命中延迟"],
            "support_criteria": ["延迟下降。"],
            "reject_criteria": ["无改善。"],
            "limitations": ["建议未执行。"],
            "execution_status": "suggestion_only",
        },
        "first_seen_issue": min((ref["issue_date"] for ref in all_refs), default=last_updated_issue),
        "last_updated_issue": last_updated_issue,
        "decision_log": [
            {
                "event_id": "fixture_decision_1",
                "issue_date": last_updated_issue,
                "decision": "evidence_added",
                "from_status": "observing",
                "to_status": "observing",
                "reason": "补充已发布证据。",
                "evidence_item_ids": [ref["item_id"] for ref in all_refs],
            }
        ],
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
    _published_issue(tmp_path, "2026-08-08", [_item("item_three", "2026-08-08", url="https://example.com/three", title="第三条证据")])
    _published_issue(tmp_path, "2026-08-15", [_item("item_four", "2026-08-15", url="https://example.com/four", title="第四条证据")])
    _set_index(tmp_path, ["2026-08-01", "2026-08-08", "2026-08-15"])
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
                                {
                                    "item_id": "item_one",
                                    "issue_date": "2026-08-01",
                                    "source_urls": ["https://example.com/one"],
                                    "reason": "首见。",
                                }
                            ],
                            "open_questions": [],
                            "evidence_item_ids": ["item_one"],
                            "source_urls": ["https://example.com/one"],
                        }
                    ],
                )
            ],
            ideas=[
                _idea(
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
        # The graph build now validates the store first, so the fixture must
        # itself be a fully valid knowledge store.
        assert validate_knowledge_store(tmp_path) == []
    return tmp_path


def _fixture_idea_id() -> str:
    return stable_idea_id(_identity())


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
        f"idea:{_fixture_idea_id()}",
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
    assert ("idea:" + _fixture_idea_id(), "topic:topic_a", "relates_to") in edges
    assert ("item:item_two", "idea:" + _fixture_idea_id(), "supports_idea") in edges
    assert ("item:item_three", "idea:" + _fixture_idea_id(), "challenges_idea") in edges
    # The reverse direction must never appear for the same fact.
    assert ("direction:direction_a", "topic:topic_a", "has_direction") not in edges
    assert ("idea:" + _fixture_idea_id(), "item:item_two", "supports_idea") not in edges


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
    assert document["archive_through_issue"] == "2026-08-15"
    assert document["knowledge_through_issue"] == "2026-08-08"


def test_invalid_knowledge_store_fails_the_build_before_deriving_nodes(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    idea_path = root / "knowledge" / "ideas" / f"{_fixture_idea_id()}.json"
    idea = read_json(idea_path)
    # A schema-valid-looking edit that breaks the semantic identity contract.
    idea["idea_id"] = "idea_spoofed"
    write_json(idea_path, idea)
    with pytest.raises(ValueError, match="knowledge store failed validation"):
        build_knowledge_graph(root)
    # Store validation must run before any graph file is replaced.
    with pytest.raises(ValueError, match="knowledge store failed validation"):
        build_knowledge_graph_file(root)


def test_dangling_judgement_evidence_enters_unresolved_and_idea_refs_fail_the_store(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    issue_path = root / "archive" / "issues" / "2026-08-01" / "issue.json"
    issue = read_json(issue_path)
    issue["synthesis"]["judgements"].append(
        {"title": "悬空判断", "body": "引用不存在的条目。", "evidence_item_ids": ["missing_item"]}
    )
    write_json(issue_path, issue)
    document = build_knowledge_graph(root)
    reasons = {entry["reason"] for entry in document["unresolved"]}
    assert "dangling_judgement_evidence" in reasons
    # Dangling references never become drawn edges.
    assert all("item:missing_item" not in edge["data"]["source"] for edge in document["edges"])
    assert document["stats"]["unresolved_count"] == len(document["unresolved"])

    # Knowledge-side dangling references are semantic store errors: the build
    # must fail instead of silently shipping a graph built from broken inputs.
    idea_path = root / "knowledge" / "ideas" / f"{_fixture_idea_id()}.json"
    idea = read_json(idea_path)
    idea["evidence_for"].append(
        {"item_id": "ghost_item", "issue_date": "2026-08-01", "source_urls": ["https://example.com/x"], "reason": "悬空。"}
    )
    write_json(idea_path, idea)
    with pytest.raises(ValueError, match="knowledge store failed validation"):
        build_knowledge_graph(root)


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


def test_roadmap_only_direction_materializes_an_explicit_node(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    roadmap = read_json(root / "knowledge" / "roadmaps" / "topic_a.json")
    roadmap["branches"][0]["direction_ids"] = ["direction_only_in_roadmap"]
    write_json(root / "knowledge" / "roadmaps" / "topic_a.json", roadmap)
    document = build_knowledge_graph(root)
    edges = _edges(document)
    # A direction id that appears nowhere in the archive still materializes an
    # explicit node from the Roadmap structure; the organizes edge then links
    # branch -> direction with valid kinds.
    assert ("branch:topic_a:branch_a", "direction:direction_only_in_roadmap", "organizes") in edges
    assert "direction:direction_only_in_roadmap" in _node_ids(document)
    # Direction ids absent from both archive and Roadmap never appear.
    assert not any(edge[2] == "organizes" and "direction_a" == edge[1].split(":", 1)[1] for edge in edges)


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
    assert kinds["item"] == 4
    assert kinds["issue"] == 3
    assert kinds["topic"] == 1
    assert kinds["direction"] == 1
    assert kinds["judgement"] == 1
    assert kinds["roadmap"] == 1
    assert kinds["roadmap_branch"] == 1
    assert kinds["idea"] == 1
    assert document["stats"]["node_count"] == sum(kinds.values())


def test_duplicate_item_across_issues_merges_with_coverage_window(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    # Republish item_four (not cited by any knowledge object) in a later issue
    # under the same stable id; knowledge refs stay valid.
    repeat = _item("item_four", "2026-08-22", url="https://example.com/four-again", title="第四条证据（复现）")
    _published_issue(root, "2026-08-22", [repeat])
    _set_index(root, ["2026-08-01", "2026-08-08", "2026-08-15", "2026-08-22"])
    document = build_knowledge_graph(root)
    item_nodes = [node for node in document["nodes"] if node["data"]["id"] == "item:item_four"]
    assert len(item_nodes) == 1
    assert item_nodes[0]["data"]["first_issue_date"] == "2026-08-15"
    assert item_nodes[0]["data"]["last_issue_date"] == "2026-08-22"
    edges = _edges(document)
    assert ("item:item_four", "issue:2026-08-15", "published_in") in edges
    assert ("item:item_four", "issue:2026-08-22", "published_in") in edges
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


def test_committed_repo_builds_in_memory_and_matches_the_published_graph() -> None:
    # Build in memory and compare every stable field against the committed
    # document; the test suite must never rewrite the tracked artifact.
    document = build_knowledge_graph(REPO_ROOT)
    assert document["archive_through_issue"], "committed archive must produce a watermark"
    assert graph_schema_errors(REPO_ROOT, document) == []
    committed = read_json(REPO_ROOT / "knowledge" / "graph.json")
    for key in (
        "schema_version",
        "archive_through_issue",
        "knowledge_through_issue",
        "input_digest",
        "stats",
        "nodes",
        "edges",
        "unresolved",
    ):
        assert committed.get(key) == document.get(key), f"committed graph.json diverges on {key}"
    assert validate_knowledge_graph(REPO_ROOT) == []
