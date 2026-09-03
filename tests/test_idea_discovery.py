from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pytest

from briefing_skill.idea_discovery import (
    _candidate_semantic_errors,
    apply_candidate_task,
    prepare_candidate_tasks,
    prepare_promotion_task,
    stable_candidate_id,
)
from briefing_skill.knowledge_materialization import rebuild_knowledge_index
from briefing_skill.utils import read_json, source_identity_key, stable_hash, write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = (
    "idea.schema.json",
    "idea-candidate.schema.json",
    "idea-candidate-discovery.schema.json",
    "idea-promotion.schema.json",
    "knowledge-index.schema.json",
)


def _root(tmp_path: Path) -> Path:
    for name in SCHEMAS:
        target = tmp_path / "schemas" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / "schemas" / name, target)
    issue_dir = tmp_path / "archive" / "issues" / "2026-08-01"
    write_json(
        issue_dir / "issue.json",
        {
            "date_from": "2026-08-01",
            "date_to": "2026-08-01",
            "items": [
                {
                    "brief_item_id": "item_one",
                    "topic_id": "topic_a",
                    "topic_name": "专题 A",
                    "direction_id": "direction_a",
                    "direction_name": "方向 A",
                    "item_role": "core",
                    "title": "可验证机制",
                    "core_conclusion": "机制解决一个明确问题。",
                    "mechanism": "明确机制。",
                    "result": "可测量结果。",
                    "boundary": "适用边界。",
                    "project_relevance": "可做原型。",
                    "keywords": [],
                    "sources": [{"url": "https://example.com/one", "primary": True}],
                }
            ],
            "synthesis": {"radar_signals": []},
        },
    )
    write_json(issue_dir / "papers.json", [{"item_id": "item_one", "role": "core", "url": "https://example.com/one"}])
    write_json(tmp_path / "archive" / "index.json", {"issues": [{"date": "2026-08-01", "papers_file": "issues/2026-08-01/papers.json"}]})
    rebuild_knowledge_index(tmp_path)
    return tmp_path


def _candidate(*, disposition: str = "proposed") -> dict:
    identity = {"problem_key": "problem_a", "mechanism_key": "mechanism_a", "target_key": "target_a"}
    candidate_id = stable_candidate_id(identity)
    reason = "完整问题、机制、目标和可验证效果等待人工审阅。"
    return {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "identity": identity,
        "idea_type": "solution_concept",
        "title": "候选 A",
        "problem": "明确问题。",
        "hypothesis": "机制应改善目标。",
        "mechanism": "明确机制。",
        "target": "目标对象。",
        "expected_effect": "降低一项可测量成本。",
        "topic_ids": ["topic_a"],
        "origin": {"kind": "single_evidence", "trigger_issue": "2026-08-01", "rationale": "单条强证据包含完整框架。"},
        "evidence": [{"item_id": "item_one", "issue_date": "2026-08-01", "source_urls": ["https://example.com/one"], "reason": "支持机制。", "independence_group": source_identity_key("https://example.com/one")}],
        "evidence_item_ids": ["item_one"],
        "source_urls": ["https://example.com/one"],
        "independence_groups": [source_identity_key("https://example.com/one")],
        "unknowns": ["边界仍待验证。"],
        "validation_plan": {"mode": "prototype", "minimal_model": "最小原型。", "inputs": ["输入"], "baselines": ["基线"], "metrics": ["成本"], "support_criteria": ["成本下降"], "reject_criteria": ["成本不降"], "limitations": ["小样本"], "execution_status": "suggestion_only"},
        "disposition": disposition,
        "disposition_reason": reason,
        "related_candidate_ids": [],
        "related_idea_ids": [],
        "first_seen_issue": "2026-08-01",
        "last_updated_issue": "2026-08-01",
        "decision_log": [{"event_id": f"candidate_decision_{stable_hash(candidate_id, 'proposed', length=20)}", "issue_date": "2026-08-01", "decision": disposition, "from_disposition": None, "to_disposition": disposition, "reason": reason, "evidence_item_ids": ["item_one"], "actor": "agent"}],
    }


def test_direct_task_requires_coverage_and_apply_is_idempotent(tmp_path: Path):
    root = _root(tmp_path)
    tasks = prepare_candidate_tasks(root, issue_date="2026-08-01")
    direct = next(row for row in tasks if row["task_type"] == "idea_candidate_direct")
    input_data = read_json(root / direct["input_path"])
    write_json(
        root / direct["output_path"],
        {"_task": input_data["_task"], "candidates": [], "no_ops": [{"item_id": "item_one", "reason_code": "measurement_only", "reason": "只有测量建议，不形成新机制。"}], "covered_trigger_item_ids": ["item_one"]},
    )
    first = apply_candidate_task(root, direct["task_id"])
    second = apply_candidate_task(root, direct["task_id"])
    assert first["no_ops"][0]["reason_code"] == "measurement_only"
    assert second["idempotent"] is True
    assert read_json(root / "knowledge" / "index.json")["idea_candidates"] == []


def test_candidate_is_indexed_separately_and_duplicate_requires_lineage(tmp_path: Path):
    root = _root(tmp_path)
    direct = next(row for row in prepare_candidate_tasks(root, issue_date="2026-08-01") if row["task_type"] == "idea_candidate_direct")
    input_data = read_json(root / direct["input_path"])
    candidate = _candidate()
    write_json(root / direct["output_path"], {"_task": input_data["_task"], "candidates": [candidate], "no_ops": [], "covered_trigger_item_ids": ["item_one"]})
    apply_candidate_task(root, direct["task_id"])
    index = read_json(root / "knowledge" / "index.json")
    assert [row["candidate_id"] for row in index["idea_candidates"]] == [candidate["candidate_id"]]
    assert index["ideas"] == []

    duplicate = copy.deepcopy(candidate)
    duplicate["disposition"] = "duplicate"
    duplicate["decision_log"][0]["decision"] = "duplicate"
    duplicate["decision_log"][0]["to_disposition"] = "duplicate"
    errors = _candidate_semantic_errors(duplicate, evidence={"item_one": input_data["published_evidence"][0]}, known_candidate_ids={candidate["candidate_id"]}, known_idea_ids=set())
    assert any("duplicate candidate must point" in error for error in errors)


def test_promotion_rejects_stale_candidate_snapshot(tmp_path: Path):
    root = _root(tmp_path)
    candidate = _candidate()
    path = root / "knowledge" / "idea-candidates" / f"{candidate['candidate_id']}.json"
    write_json(path, candidate)
    rebuild_knowledge_index(root)
    task = prepare_promotion_task(root, candidate_id=candidate["candidate_id"])
    input_data = read_json(root / task["input_path"])
    write_json(root / task["output_path"], {"_task": input_data["_task"], "candidate_id": candidate["candidate_id"], "idea": {}})
    candidate["disposition_reason"] = "任务准备后发生变化。"
    write_json(path, candidate)
    from briefing_skill.idea_discovery import apply_promotion_task

    with pytest.raises(ValueError, match="Candidate changed after preparation"):
        apply_promotion_task(root, task["task_id"])


def test_radar_and_independence_group_semantics_are_enforced():
    candidate = _candidate()
    evidence = {"item_one": {"item_id": "item_one", "issue_date": "2026-08-01", "topic_id": "topic_a", "source_urls": ["https://example.com/one"], "evidence_kind": "discovery_signal", "claim_strength": "unverified"}}
    errors = _candidate_semantic_errors(candidate, evidence=evidence)
    assert any("unverified discovery signal" in error for error in errors)
    bad_group = copy.deepcopy(candidate)
    bad_group["evidence"][0]["independence_group"] = "invented:independent"
    bad_group["independence_groups"] = ["invented:independent"]
    errors = _candidate_semantic_errors(bad_group, evidence={"item_one": {**evidence["item_one"], "evidence_kind": "fact", "claim_strength": "supported"}})
    assert any("canonical source identity" in error for error in errors)


def test_candidate_backfill_cannot_skip_the_oldest_pending_issue(tmp_path: Path):
    root = _root(tmp_path)
    issue_dir = root / "archive" / "issues" / "2026-08-02"
    first = read_json(root / "archive" / "issues" / "2026-08-01" / "issue.json")["items"][0]
    second = {**first, "brief_item_id": "item_two", "title": "第二条机制", "published_at": "2026-08-02", "sources": [{"url": "https://example.com/two", "primary": True}]}
    write_json(issue_dir / "issue.json", {"date_from": "2026-08-02", "date_to": "2026-08-02", "items": [second], "synthesis": {"radar_signals": []}})
    write_json(issue_dir / "papers.json", [{"item_id": "item_two", "role": "core", "url": "https://example.com/two"}])
    write_json(root / "archive" / "index.json", {"issues": [{"date": "2026-08-01", "papers_file": "issues/2026-08-01/papers.json"}, {"date": "2026-08-02", "papers_file": "issues/2026-08-02/papers.json"}]})
    with pytest.raises(ValueError, match="oldest pending issue first: 2026-08-01"):
        prepare_candidate_tasks(root, issue_date="2026-08-02")


def test_candidate_apply_rolls_back_every_file_when_index_rebuild_fails(tmp_path: Path, monkeypatch):
    root = _root(tmp_path)
    direct = next(row for row in prepare_candidate_tasks(root, issue_date="2026-08-01") if row["task_type"] == "idea_candidate_direct")
    input_data = read_json(root / direct["input_path"])
    candidate = _candidate()
    write_json(root / direct["output_path"], {"_task": input_data["_task"], "candidates": [candidate], "no_ops": [], "covered_trigger_item_ids": ["item_one"]})
    original_index = (root / "knowledge" / "index.json").read_text(encoding="utf-8")

    def fail_rebuild(_root: Path):
        raise RuntimeError("injected index failure")

    monkeypatch.setattr("briefing_skill.idea_discovery.rebuild_knowledge_index", fail_rebuild)
    with pytest.raises(RuntimeError, match="injected index failure"):
        apply_candidate_task(root, direct["task_id"])
    assert not (root / "knowledge" / "idea-candidates" / f"{candidate['candidate_id']}.json").exists()
    assert not (root / "knowledge" / "candidate-applications" / f"{direct['task_id']}.json").exists()
    assert (root / "knowledge" / "index.json").read_text(encoding="utf-8") == original_index
    assert not (root / "knowledge" / ".candidate-transaction.json").exists()
