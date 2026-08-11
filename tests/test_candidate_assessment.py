from __future__ import annotations

import json
from pathlib import Path

from briefing_skill.candidate_assessment import (
    _identity,
    apply_unified_cached_assessment,
    ensure_candidate_assessment_schema,
    persist_candidate_assessment,
)
from briefing_skill.cost_schema import ensure_cost_schema
from briefing_skill.db import Database
from briefing_skill.deep_eligibility import ensure_deep_eligibility_schema
from briefing_skill.technology_value import ensure_technology_value_schema
from briefing_skill.utils import now_iso


class _Config:
    settings = {"efficiency": {"relevance_summary_max_chars": 5000}}
    scoring = {"freshness_days": {2: 5, 7: 4, 30: 2, 60: 1}}

    def topic(self, topic_id: str):
        return {
            "id": topic_id,
            "name": "TPN",
            "current_questions": ["KVCache状态如何进入网络调度？"],
            "valuable_evidence": ["端到端调度机制"],
        }

    def direction(self, topic_id: str, direction_id: str):
        return {"id": direction_id, "name": "KV传输", "include_terms": ["KVCache"]}

    def context_path(self, _paths, topic_id: str):
        return Path("missing-project-context.md")


def _db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "state.sqlite3")
    db.init()
    ensure_cost_schema(db)
    ensure_technology_value_schema(db)
    ensure_deep_eligibility_schema(db)
    ensure_candidate_assessment_schema(db)
    return db


def _insert_candidate(db: Database, *, run_id: str, raw_id: str, candidate_id: str) -> None:
    now = now_iso()
    db.execute(
        """
        INSERT INTO raw_items(
          id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
          original_url,canonical_url,identity_key,published_at,discovered_at,external_id,
          priority,content_hash,payload_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            raw_id, run_id, "arxiv", "arxiv", "A", 0, "State-aware KV scheduling",
            "A stable summary for assessment caching.", "https://arxiv.org/abs/2608.12345v1",
            "https://arxiv.org/abs/2608.12345v1", "arxiv:2608.12345", "2026-08-11",
            now, "2608.12345v1", 90, "content-v1", "{}", now,
        ),
    )
    db.execute(
        """
        INSERT INTO candidates(
          id,run_id,raw_item_id,topic_id,direction_id,rule_score,relevant,relevance_score,
          relevance_reason,fulltext_required,status,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (candidate_id, run_id, raw_id, "tpn", "kv_transfer", 90, None, None, None, 0, "PENDING_RELEVANCE", now),
    )


def test_schema_extends_relevance_cache_and_creates_assessment_table(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with db.connect() as conn:
        cache_columns = {row[1] for row in conn.execute("PRAGMA table_info(relevance_cache)")}
        assessment_columns = {row[1] for row in conn.execute("PRAGMA table_info(candidate_assessments)")}

    assert {"technology_value_score", "technology_value_json", "topic_fit", "deep_eligible"} <= cache_columns
    assert {"candidate_id", "assessment_json", "provenance", "deep_eligibility_reason"} <= assessment_columns


def test_one_commit_persists_all_assessment_signals_and_one_cache_record(tmp_path: Path) -> None:
    db = _db(tmp_path)
    config = _Config()
    _insert_candidate(db, run_id="run-1", raw_id="raw-1", candidate_id="candidate-1")
    row = db.fetchone(
        """
        SELECT c.*,r.source_id,r.identity_key,r.external_id,r.content_hash,r.canonical_url,
               r.original_url,r.title,r.summary,r.payload_json,r.published_at
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id WHERE c.id='candidate-1'
        """
    )
    fingerprint, topic_id, direction_id, version = _identity(config, tmp_path, row)
    now = now_iso()
    db.execute(
        """
        INSERT INTO relevance_cache(
          cache_key,source_fingerprint,topic_id,direction_id,evaluator_version,source_url,
          source_identity,relevant,relevance_score,relevance_reason,fulltext_required,created_at,last_used_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "cache-1", fingerprint, topic_id, direction_id, version,
            "https://arxiv.org/abs/2608.12345v1", "arxiv:2608.12345", 1, 82,
            "directly relevant", 1, now, now,
        ),
    )
    technology = {
        "novelty": {"score": 4, "reason": "new"},
        "architecture_impact": {"score": 4, "reason": "path"},
        "industry_signal": {"score": 3, "reason": "signal"},
        "project_alignment": {"score": 4, "reason": "aligned"},
        "total_score": 15,
    }
    db.execute(
        """
        UPDATE candidates SET relevant=1,relevance_score=82,relevance_reason='directly relevant',
          technology_value_score=15,technology_value_json=?,topic_fit='direct',
          core_contribution='kv_transfer',boundary_conflict=0,matched_direction_id='kv_transfer',
          deep_eligible=1,deep_eligibility_reason='passes contract',fulltext_required=1,status='RELEVANT'
        WHERE id='candidate-1'
        """,
        (json.dumps(technology),),
    )

    assert persist_candidate_assessment(config, db, tmp_path, "candidate-1", provenance="agent_relevance_batch")

    cache = db.fetchone("SELECT * FROM relevance_cache WHERE cache_key='cache-1'")
    persisted = db.fetchone("SELECT * FROM candidate_assessments WHERE candidate_id='candidate-1'")
    payload = json.loads(persisted["assessment_json"])
    assert cache["technology_value_score"] == 15
    assert cache["topic_fit"] == "direct"
    assert cache["deep_eligible"] == 1
    assert payload["technology_value_score"] == 15
    assert payload["core_contribution"] == "kv_transfer"
    assert payload["deep_eligible"] is True
    assert persisted["provenance"] == "agent_relevance_batch"


def test_warm_cache_rehydrates_complete_candidate_assessment(tmp_path: Path) -> None:
    db = _db(tmp_path)
    config = _Config()
    _insert_candidate(db, run_id="run-1", raw_id="raw-1", candidate_id="candidate-1")
    source = db.fetchone(
        """
        SELECT c.*,r.source_id,r.identity_key,r.external_id,r.content_hash,r.canonical_url,
               r.original_url,r.title,r.summary,r.payload_json,r.published_at
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id WHERE c.id='candidate-1'
        """
    )
    fingerprint, topic_id, direction_id, version = _identity(config, tmp_path, source)
    now = now_iso()
    db.execute(
        """
        INSERT INTO relevance_cache(
          cache_key,source_fingerprint,topic_id,direction_id,evaluator_version,source_url,
          source_identity,relevant,relevance_score,relevance_reason,fulltext_required,created_at,last_used_at,
          technology_value_score,technology_value_json,topic_fit,core_contribution,boundary_conflict,
          matched_direction_id,deep_eligible,deep_eligibility_reason
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "cache-1", fingerprint, topic_id, direction_id, version,
            "https://arxiv.org/abs/2608.12345v1", "arxiv:2608.12345", 1, 84,
            "cached relevant", 1, now, now, 16, '{"total_score":16}', "direct", "kv_transfer",
            0, "kv_transfer", 1, "cached deep pass",
        ),
    )
    _insert_candidate(db, run_id="run-2", raw_id="raw-2", candidate_id="candidate-2")
    row = db.fetchone(
        """
        SELECT c.*,r.source_id,r.identity_key,r.external_id,r.content_hash,r.canonical_url,
               r.original_url,r.title,r.summary,r.payload_json,r.published_at
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id WHERE c.id='candidate-2'
        """
    )

    assert apply_unified_cached_assessment(config, db, tmp_path, row) is True
    candidate = db.fetchone("SELECT * FROM candidates WHERE id='candidate-2'")
    assessment = db.fetchone("SELECT * FROM candidate_assessments WHERE candidate_id='candidate-2'")
    assert candidate["relevance_score"] == 84
    assert candidate["technology_value_score"] == 16
    assert candidate["topic_fit"] == "direct"
    assert candidate["deep_eligible"] == 1
    assert candidate["status"] == "RELEVANT"
    assert assessment["provenance"] == "relevance_cache"


def test_partial_legacy_cache_fails_closed_to_fresh_assessment(tmp_path: Path) -> None:
    db = _db(tmp_path)
    config = _Config()
    _insert_candidate(db, run_id="run-1", raw_id="raw-1", candidate_id="candidate-1")
    row = db.fetchone(
        """
        SELECT c.*,r.source_id,r.identity_key,r.external_id,r.content_hash,r.canonical_url,
               r.original_url,r.title,r.summary,r.payload_json,r.published_at
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id WHERE c.id='candidate-1'
        """
    )
    fingerprint, topic_id, direction_id, version = _identity(config, tmp_path, row)
    now = now_iso()
    db.execute(
        """
        INSERT INTO relevance_cache(
          cache_key,source_fingerprint,topic_id,direction_id,evaluator_version,source_url,
          source_identity,relevant,relevance_score,relevance_reason,fulltext_required,created_at,last_used_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("legacy", fingerprint, topic_id, direction_id, version, "url", "identity", 1, 80, "legacy", 1, now, now),
    )
    db.execute("UPDATE candidates SET relevant=1,relevance_score=80,status='RELEVANT' WHERE id='candidate-1'")

    assert apply_unified_cached_assessment(config, db, tmp_path, row) is False
    candidate = db.fetchone("SELECT * FROM candidates WHERE id='candidate-1'")
    assert candidate["relevant"] is None
    assert candidate["technology_value_score"] is None
    assert candidate["deep_eligible"] is None
    assert candidate["status"] == "PENDING_RELEVANCE"
