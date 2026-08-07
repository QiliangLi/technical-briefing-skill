from __future__ import annotations

import json
from types import SimpleNamespace

from briefing_skill.db import Database
from briefing_skill.invalid_repair import (
    deterministic_constraints,
    is_targeted_repairable,
    prepare_targeted_repair,
)
from briefing_skill.safe_efficiency import (
    _defer_fallback_fact_input,
    _editorial_score_floor,
    dedupe_exact_primary_candidates,
)
from briefing_skill.tasks import TASK_BINDING_KEY, TaskService
from briefing_skill.utils import now_iso, read_json, write_json


def _insert_raw(
    db: Database,
    *,
    run_id: str,
    raw_id: str,
    source_id: str,
    discovery_source: str,
    identity_key: str,
    priority: float,
    payload: dict,
) -> None:
    created = now_iso()
    url = "https://arxiv.org/abs/2608.12345"
    db.execute(
        """
        INSERT INTO raw_items(
            id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
            original_url,aihot_url,canonical_url,identity_key,published_at,discovered_at,
            authors_json,external_id,topic_hint,direction_hint,priority,content_hash,payload_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            raw_id,
            run_id,
            source_id,
            discovery_source,
            "A",
            0,
            "Exact primary paper",
            f"summary from {discovery_source}",
            url,
            "",
            url,
            identity_key,
            created,
            created,
            "[]",
            "2608.12345v1",
            "tpn",
            "kv_transfer",
            priority,
            f"hash-{raw_id}",
            json.dumps(payload, ensure_ascii=False),
            created,
        ),
    )


def _insert_candidate(db: Database, *, run_id: str, candidate_id: str, raw_id: str, score: float) -> None:
    db.execute(
        """
        INSERT INTO candidates(
            id,run_id,raw_item_id,topic_id,direction_id,rule_score,status,created_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            candidate_id,
            run_id,
            raw_id,
            "tpn",
            "kv_transfer",
            score,
            "PENDING_RELEVANCE",
            now_iso(),
        ),
    )


def test_exact_primary_dedup_keeps_one_candidate_and_merges_discovery_provenance(tmp_path):
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_id = "dedup-run"
    db.create_run(run_id)
    identity = "arxiv:2608.12345"
    _insert_raw(
        db,
        run_id=run_id,
        raw_id="raw-aihot",
        source_id="aihot",
        discovery_source="AI HOT",
        identity_key=identity,
        priority=10,
        payload={"primary_source_resolution": {"kind": "arxiv"}, "discovered_via": ["AI HOT"]},
    )
    _insert_raw(
        db,
        run_id=run_id,
        raw_id="raw-arxiv",
        source_id="arxiv",
        discovery_source="arXiv",
        identity_key=identity,
        priority=18,
        payload={"pdf_url": "https://arxiv.org/pdf/2608.12345"},
    )
    _insert_candidate(db, run_id=run_id, candidate_id="candidate-aihot", raw_id="raw-aihot", score=81)
    _insert_candidate(db, run_id=run_id, candidate_id="candidate-arxiv", raw_id="raw-arxiv", score=91)

    assert dedupe_exact_primary_candidates(db, run_id) == 1
    pending = db.fetchall("SELECT * FROM candidates WHERE run_id=? AND status='PENDING_RELEVANCE'", (run_id,))
    duplicate = db.fetchall("SELECT * FROM candidates WHERE run_id=? AND status='DUPLICATE_PRIMARY'", (run_id,))
    assert [row["id"] for row in pending] == ["candidate-arxiv"]
    assert [row["id"] for row in duplicate] == ["candidate-aihot"]
    winner_raw = db.fetchone("SELECT payload_json FROM raw_items WHERE id='raw-arxiv'")
    assert set(json.loads(winner_raw["payload_json"])["discovered_via"]) == {"AI HOT", "arXiv"}


def test_exact_primary_dedup_does_not_collapse_different_routing_contexts(tmp_path):
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_id = "routing-run"
    db.create_run(run_id)
    identity = "arxiv:2608.12345"
    _insert_raw(
        db,
        run_id=run_id,
        raw_id="raw-1",
        source_id="arxiv",
        discovery_source="arXiv",
        identity_key=identity,
        priority=18,
        payload={},
    )
    _insert_raw(
        db,
        run_id=run_id,
        raw_id="raw-2",
        source_id="aihot",
        discovery_source="AI HOT",
        identity_key=identity,
        priority=12,
        payload={"primary_source_resolution": {"kind": "arxiv"}},
    )
    _insert_candidate(db, run_id=run_id, candidate_id="candidate-1", raw_id="raw-1", score=90)
    db.execute(
        """
        INSERT INTO candidates(id,run_id,raw_item_id,topic_id,direction_id,rule_score,status,created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        ("candidate-2", run_id, "raw-2", "cross_region", "kv_cross_region", 88, "PENDING_RELEVANCE", now_iso()),
    )

    assert dedupe_exact_primary_candidates(db, run_id) == 0
    assert db.fetchone("SELECT COUNT(*) AS n FROM candidates WHERE run_id=? AND status='PENDING_RELEVANCE'", (run_id,))["n"] == 2


def test_fetch_fallback_gate_only_blocks_summary_fallbacks():
    assert _defer_fallback_fact_input({"document": {"fetch_status": "FALLBACK"}})
    assert not _defer_fallback_fact_input({"document": {"fetch_status": "FETCHED"}})
    assert not _defer_fallback_fact_input(
        {"document": {"fetch_status": "FALLBACK", "fact_cache_hit": True}}
    )


def test_editorial_score_floor_matches_the_lowest_selectable_role():
    expanded = SimpleNamespace(
        settings={"issue_mode": "expanded_v2"},
        scoring={"expanded_v2": {"observation_score": 61}},
    )
    compact = SimpleNamespace(
        settings={"issue_mode": "compact"},
        scoring={"thresholds": {"issue_minimum": 72}},
    )
    assert _editorial_score_floor(expanded) == 61
    assert _editorial_score_floor(compact) == 72


def test_only_deterministic_validation_failures_use_targeted_repair():
    assert is_targeted_repairable("core_conclusion must end with a complete sentence")
    assert is_targeted_repairable("item score must exactly match the deterministic input score")
    assert is_targeted_repairable("task binding mismatch: output must echo _task")
    assert not is_targeted_repairable("'mechanism' is a required property")
    assert not is_targeted_repairable("primary_source_resolved requires a fetched source document")


def test_targeted_repair_sidecar_omits_expensive_evidence_and_is_one_shot(tmp_path):
    root = tmp_path
    run_id = "repair-run"
    db = Database(root / "workspace" / "briefing.sqlite")
    db.init()
    db.create_run(run_id)
    run_dir = root / "workspace" / "runs" / run_id
    service = TaskService(db, root, run_dir)
    row = service.create(
        run_id,
        "item_writing",
        "event-1",
        {
            "event_id": "event-1",
            "topic": {"name": "TPN"},
            "direction": {"name": "KV transfer"},
            "score": 88,
            "facts": [{"mechanism": "existing fact"}],
            "sources": [{"url": "https://arxiv.org/abs/2608.12345"}],
            "length": {"min_chars": 180, "max_chars": 260},
        },
        prompt="item-writing.md",
        schema="brief-item.schema.json",
    )
    task = db.fetchone("SELECT * FROM tasks WHERE id=?", (row["id"],))
    task_input = read_json(root / task["input_path"])
    write_json(
        root / task["output_path"],
        {
            TASK_BINDING_KEY: task_input[TASK_BINDING_KEY],
            "title": "existing title",
            "core_conclusion": "existing conclusion",
        },
    )
    db.execute(
        "UPDATE tasks SET status='INVALID',error=? WHERE id=?",
        ("core_conclusion must end with a complete sentence", task["id"]),
    )
    task = db.fetchone("SELECT * FROM tasks WHERE id=?", (task["id"],))

    repair_path = prepare_targeted_repair(service, task)
    assert repair_path
    sidecar = read_json(root / repair_path)
    assert sidecar["deterministic_constraints"]["score"] == 88
    assert sidecar["deterministic_constraints"]["required_task_binding"] == task_input[TASK_BINDING_KEY]
    encoded = json.dumps(sidecar, ensure_ascii=False)
    assert "Evidence Pack" in encoded
    assert "facts" not in sidecar

    repaired_task = db.fetchone("SELECT * FROM tasks WHERE id=?", (task["id"],))
    metadata = json.loads(repaired_task["metadata_json"])
    assert metadata["targeted_repair_attempts"] == 1
    db.execute(
        "UPDATE tasks SET status='INVALID',error=? WHERE id=?",
        ("core_conclusion must end with a complete sentence", task["id"]),
    )
    repaired_task = db.fetchone("SELECT * FROM tasks WHERE id=?", (task["id"],))
    assert prepare_targeted_repair(service, repaired_task) is None


def test_deterministic_constraints_for_synthesis_only_expose_allowed_ids_and_topics():
    task = {"id": "t1", "task_type": "issue_synthesis", "entity_id": "issue-1"}
    input_data = {
        TASK_BINDING_KEY: {"id": "t1"},
        "items": [
            {"brief_item_id": "a", "topic_name": "TPN"},
            {"brief_item_id": "b", "topic_name": "DPU"},
        ],
        "max_judgements": 3,
    }
    result = deterministic_constraints(task, input_data)
    assert result["allowed_evidence_item_ids"] == ["a", "b"]
    assert result["required_topic_names"] == ["DPU", "TPN"]
    assert result["max_judgements"] == 3
