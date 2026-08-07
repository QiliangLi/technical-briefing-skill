from __future__ import annotations

from pathlib import Path

from briefing_skill.config import ConfigBundle
from briefing_skill.cost_schema import ensure_cost_schema
from briefing_skill.db import Database
from briefing_skill.paths import Paths
from briefing_skill.relevance_efficiency import (
    apply_cached_relevance,
    compact_relevance_batch_input,
    plan_relevance_rows_bounded,
    relevance_freshness_bucket,
    store_relevance_candidate,
)


ROOT = Path(__file__).resolve().parents[1]


def _config() -> ConfigBundle:
    return ConfigBundle.load(Paths(ROOT))


def _db(tmp_path) -> Database:
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    ensure_cost_schema(db)
    return db


def _insert_arxiv_raw(db: Database, *, raw_id: str, run_id: str, summary: str = "same summary") -> None:
    db.execute(
        """
        INSERT INTO raw_items(
            id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
            original_url,canonical_url,identity_key,published_at,authors_json,external_id,
            priority,content_hash,payload_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            raw_id,
            run_id,
            "arxiv",
            "arXiv",
            "A",
            0,
            "Same Paper",
            summary,
            "https://arxiv.org/abs/2608.00001v1",
            "https://arxiv.org/abs/2608.00001v1",
            "arxiv:2608.00001",
            "2026-08-01T00:00:00Z",
            "[]",
            "http://arxiv.org/abs/2608.00001v1",
            18,
            "stable-content",
            "{}",
            "2026-08-01T00:00:00Z",
        ),
    )


def _insert_candidate(
    db: Database,
    *,
    candidate_id: str,
    raw_id: str,
    run_id: str,
    relevant=None,
    score=None,
    reason=None,
    fulltext=None,
    status="PENDING_RELEVANCE",
) -> None:
    db.execute(
        """
        INSERT INTO candidates(
            id,run_id,raw_item_id,topic_id,direction_id,rule_score,relevant,
            relevance_score,relevance_reason,fulltext_required,status,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            candidate_id,
            run_id,
            raw_id,
            "tpn",
            "kv_transfer",
            72,
            relevant,
            score,
            reason,
            fulltext,
            status,
            "2026-08-07T00:00:00Z",
        ),
    )


def _candidate_row(db: Database, candidate_id: str):
    return db.fetchone(
        """
        SELECT c.*, r.source_id, r.title, r.summary, r.original_url, r.canonical_url,
               r.identity_key, r.external_id, r.content_hash, r.payload_json,
               r.source_level, r.discovery_only, r.published_at
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
        WHERE c.id=?
        """,
        (candidate_id,),
    )


def test_relevance_cache_reuses_exact_versioned_source_across_runs(tmp_path):
    config = _config()
    db = _db(tmp_path)
    _insert_arxiv_raw(db, raw_id="r1", run_id="run1")
    _insert_candidate(
        db,
        candidate_id="c1",
        raw_id="r1",
        run_id="run1",
        relevant=1,
        score=78,
        reason="该论文直接讨论KV跨节点传输，并给出可用于项目判断的机制。",
        fulltext=1,
        status="RELEVANT",
    )
    assert store_relevance_candidate(config, db, ROOT, "c1")

    _insert_arxiv_raw(db, raw_id="r2", run_id="run2")
    _insert_candidate(db, candidate_id="c2", raw_id="r2", run_id="run2")
    assert apply_cached_relevance(config, db, ROOT, _candidate_row(db, "c2"))

    reused = db.fetchone("SELECT * FROM candidates WHERE id='c2'")
    assert reused["relevant"] == 1
    assert reused["relevance_score"] == 78
    assert reused["fulltext_required"] == 1
    assert reused["status"] == "RELEVANT"
    assert db.fetchone("SELECT COUNT(*) AS n FROM relevance_cache_usage WHERE run_id='run2'")["n"] == 1


def test_relevance_cache_misses_when_source_summary_changes(tmp_path):
    config = _config()
    db = _db(tmp_path)
    _insert_arxiv_raw(db, raw_id="r1", run_id="run1")
    _insert_candidate(
        db,
        candidate_id="c1",
        raw_id="r1",
        run_id="run1",
        relevant=1,
        score=70,
        reason="cached",
        fulltext=0,
        status="RADAR",
    )
    assert store_relevance_candidate(config, db, ROOT, "c1")

    _insert_arxiv_raw(db, raw_id="r2", run_id="run2", summary="materially changed summary")
    _insert_candidate(db, candidate_id="c2", raw_id="r2", run_id="run2")
    assert not apply_cached_relevance(config, db, ROOT, _candidate_row(db, "c2"))
    assert db.fetchone("SELECT status FROM candidates WHERE id='c2'")["status"] == "PENDING_RELEVANCE"


def test_relevance_freshness_bucket_forces_recheck_at_configured_boundaries():
    config = _config()
    assert relevance_freshness_bucket(
        config,
        "2026-08-06T00:00:00Z",
        reference="2026-08-07T12:00:00Z",
    ) == "age<=2"
    assert relevance_freshness_bucket(
        config,
        "2026-08-01T00:00:00Z",
        reference="2026-08-07T12:00:00Z",
    ) == "age<=7"
    assert relevance_freshness_bucket(
        config,
        "2026-07-20T00:00:00Z",
        reference="2026-08-07T12:00:00Z",
    ) == "age<=30"
    assert relevance_freshness_bucket(
        config,
        "2026-06-15T00:00:00Z",
        reference="2026-08-07T12:00:00Z",
    ) == "age<=60"


def test_compact_batch_deduplicates_direction_config_and_bounds_long_summary():
    long_summary = ("A concrete technical update with benchmark details. " * 300).strip()
    input_data = {
        "batch_id": "tpn-1",
        "topic": {
            "id": "tpn",
            "name": "Token Performance Network",
            "current_questions": ["How should KV move?"],
            "valuable_evidence": ["bandwidth", "latency"],
            "directions": [{"large": "payload" * 100}],
        },
        "project_context_path": "config/project-context/tpn.md",
        "candidates": [
            {
                "candidate_id": "a",
                "title": "A",
                "summary": long_summary,
                "direction": {
                    "id": "kv_transfer",
                    "name": "KV transfer",
                    "include_terms": ["kv cache", "transfer"],
                    "queries": ["this query should not be repeated per candidate"],
                },
            },
            {
                "candidate_id": "b",
                "title": "B",
                "summary": "short",
                "direction": {
                    "id": "kv_transfer",
                    "name": "KV transfer",
                    "include_terms": ["kv cache", "transfer"],
                    "queries": ["this query should not be repeated per candidate"],
                },
            },
        ],
    }
    settings = {"efficiency": {"relevance_summary_max_chars": 1200}}
    compact = compact_relevance_batch_input(input_data, settings)

    assert "directions" not in compact["topic"]
    assert len(compact["directions"]) == 1
    assert compact["directions"][0]["id"] == "kv_transfer"
    assert "queries" not in compact["directions"][0]
    assert "direction" not in compact["candidates"][0]
    assert compact["candidates"][0]["direction_id"] == "kv_transfer"
    assert compact["candidates"][0]["summary_excerpted"] is True
    assert len(compact["candidates"][0]["summary"]) <= 1200


def test_relevance_plan_uses_larger_count_bound_without_changing_candidate_set():
    settings = {
        "max_relevance_batch": 24,
        "efficiency": {
            "auto_accept_rule_score": 101,
            "auto_reject_rule_score": 25,
            "radar_promotion_rule_score": 88,
            "relevance_batch_max_input_chars": 48000,
            "relevance_summary_max_chars": 5000,
        },
    }
    rows = [
        {
            "id": f"c{index}",
            "rule_score": 50,
            "source_level": "A",
            "discovery_only": False,
            "topic_id": "tpn",
            "title": f"paper {index}",
            "summary": "short abstract",
            "original_url": f"https://example.com/{index}",
        }
        for index in range(50)
    ]
    plan = plan_relevance_rows_bounded(rows, settings)
    flattened = [row["id"] for batch in plan.batches for row in batch]
    assert len(plan.batches) == 3
    assert sorted(flattened) == sorted(row["id"] for row in rows)
    assert max(len(batch) for batch in plan.batches) <= 24
