from __future__ import annotations

import json
from typing import Any

from .utils import now_iso


ASSESSMENT_COLUMNS = {
    "technology_value_score": "REAL",
    "technology_value_json": "TEXT",
    "topic_fit": "TEXT",
    "core_contribution": "TEXT",
    "boundary_conflict": "INTEGER",
    "matched_direction_id": "TEXT",
    "deep_eligible": "INTEGER",
    "deep_eligibility_reason": "TEXT",
}

ASSESSMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate_assessments (
    run_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    direction_id TEXT NOT NULL,
    evaluator_version TEXT NOT NULL,
    relevant INTEGER,
    relevance_score REAL,
    relevance_reason TEXT,
    technology_value_score REAL,
    technology_value_json TEXT,
    topic_fit TEXT,
    core_contribution TEXT,
    boundary_conflict INTEGER,
    matched_direction_id TEXT,
    deep_eligible INTEGER,
    deep_eligibility_reason TEXT,
    fulltext_required INTEGER NOT NULL DEFAULT 0,
    status TEXT,
    provenance TEXT NOT NULL,
    assessment_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(run_id, candidate_id)
);
CREATE INDEX IF NOT EXISTS idx_candidate_assessments_identity
ON candidate_assessments(source_fingerprint,topic_id,direction_id,evaluator_version);
"""


def ensure_candidate_assessment_schema(db) -> None:
    with db.connect() as conn:
        cache_columns = {row[1] for row in conn.execute("PRAGMA table_info(relevance_cache)")}
        if cache_columns:
            for name, sql_type in ASSESSMENT_COLUMNS.items():
                if name not in cache_columns:
                    conn.execute(f"ALTER TABLE relevance_cache ADD COLUMN {name} {sql_type}")
        conn.executescript(ASSESSMENT_SCHEMA)


def _identity(config, root, row: dict[str, Any]) -> tuple[str, str, str, str]:
    from . import relevance_efficiency

    topic_id = str(row.get("topic_id") or "")
    direction_id = str(row.get("direction_id") or "")
    fingerprint = relevance_efficiency.relevance_source_fingerprint(row)
    version = relevance_efficiency.relevance_evaluator_version(
        config, root, topic_id, direction_id, row.get("published_at")
    )
    return fingerprint, topic_id, direction_id, version


def _candidate_row(db, candidate_id: str) -> dict[str, Any] | None:
    return db.fetchone(
        """
        SELECT c.*,r.source_id,r.identity_key,r.external_id,r.content_hash,
               r.canonical_url,r.original_url,r.title,r.summary,r.payload_json,r.published_at
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id WHERE c.id=?
        """,
        (candidate_id,),
    )


def _assessment_payload(row: dict[str, Any]) -> dict[str, Any]:
    try:
        technology = json.loads(row.get("technology_value_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        technology = {}
    return {
        "relevant": None if row.get("relevant") is None else bool(row.get("relevant")),
        "relevance_score": row.get("relevance_score"),
        "relevance_reason": row.get("relevance_reason"),
        "technology_value": technology,
        "technology_value_score": row.get("technology_value_score"),
        "topic_fit": row.get("topic_fit"),
        "core_contribution": row.get("core_contribution"),
        "boundary_conflict": None if row.get("boundary_conflict") is None else bool(row.get("boundary_conflict")),
        "matched_direction_id": row.get("matched_direction_id"),
        "deep_eligible": None if row.get("deep_eligible") is None else bool(row.get("deep_eligible")),
        "deep_eligibility_reason": row.get("deep_eligibility_reason"),
        "fulltext_required": bool(row.get("fulltext_required")),
        "status": row.get("status"),
    }


def persist_candidate_assessment(config, db, root, candidate_id: str, *, provenance: str) -> bool:
    """Persist one final assessment and make relevance_cache its single cross-run owner."""

    ensure_candidate_assessment_schema(db)
    row = _candidate_row(db, candidate_id)
    if not row or row.get("relevant") is None or row.get("technology_value_score") is None:
        return False
    fingerprint, topic_id, direction_id, version = _identity(config, root, row)
    assessment = _assessment_payload(row)
    now = now_iso()

    db.execute(
        """
        UPDATE relevance_cache SET
          relevant=?,relevance_score=?,relevance_reason=?,fulltext_required=?,
          technology_value_score=?,technology_value_json=?,topic_fit=?,core_contribution=?,
          boundary_conflict=?,matched_direction_id=?,deep_eligible=?,deep_eligibility_reason=?,
          last_used_at=?
        WHERE source_fingerprint=? AND topic_id=? AND direction_id=? AND evaluator_version=?
        """,
        (
            row.get("relevant"), row.get("relevance_score"), row.get("relevance_reason"),
            row.get("fulltext_required"), row.get("technology_value_score"),
            row.get("technology_value_json") or "{}", row.get("topic_fit"),
            row.get("core_contribution"), row.get("boundary_conflict"),
            row.get("matched_direction_id"), row.get("deep_eligible"),
            row.get("deep_eligibility_reason"), now,
            fingerprint, topic_id, direction_id, version,
        ),
    )
    db.execute(
        """
        INSERT INTO candidate_assessments(
          run_id,candidate_id,source_fingerprint,topic_id,direction_id,evaluator_version,
          relevant,relevance_score,relevance_reason,technology_value_score,technology_value_json,
          topic_fit,core_contribution,boundary_conflict,matched_direction_id,deep_eligible,
          deep_eligibility_reason,fulltext_required,status,provenance,assessment_json,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(run_id,candidate_id) DO UPDATE SET
          relevant=excluded.relevant,relevance_score=excluded.relevance_score,
          relevance_reason=excluded.relevance_reason,technology_value_score=excluded.technology_value_score,
          technology_value_json=excluded.technology_value_json,topic_fit=excluded.topic_fit,
          core_contribution=excluded.core_contribution,boundary_conflict=excluded.boundary_conflict,
          matched_direction_id=excluded.matched_direction_id,deep_eligible=excluded.deep_eligible,
          deep_eligibility_reason=excluded.deep_eligibility_reason,
          fulltext_required=excluded.fulltext_required,status=excluded.status,
          provenance=excluded.provenance,assessment_json=excluded.assessment_json,updated_at=excluded.updated_at
        """,
        (
            row["run_id"], candidate_id, fingerprint, topic_id, direction_id, version,
            row.get("relevant"), row.get("relevance_score"), row.get("relevance_reason"),
            row.get("technology_value_score"), row.get("technology_value_json") or "{}",
            row.get("topic_fit"), row.get("core_contribution"), row.get("boundary_conflict"),
            row.get("matched_direction_id"), row.get("deep_eligible"), row.get("deep_eligibility_reason"),
            int(bool(row.get("fulltext_required"))), row.get("status"), provenance,
            json.dumps(assessment, ensure_ascii=False, sort_keys=True), now, now,
        ),
    )
    return True


def _reset_legacy_cache_hit(db, candidate_id: str) -> None:
    db.execute(
        """
        UPDATE candidates SET relevant=NULL,relevance_score=NULL,relevance_reason=NULL,
          technology_value_score=NULL,technology_value_json=NULL,fulltext_required=0,
          status='PENDING_RELEVANCE',topic_fit=NULL,core_contribution=NULL,
          boundary_conflict=NULL,matched_direction_id=NULL,deep_eligible=NULL,
          deep_eligibility_reason=NULL WHERE id=?
        """,
        (candidate_id,),
    )


def apply_unified_cached_assessment(config, db, root, row: dict[str, Any]) -> bool:
    """Apply one complete cached assessment or fail closed to a fresh review."""

    from .deep_eligibility import deep_entry_contract

    ensure_candidate_assessment_schema(db)
    fingerprint, topic_id, direction_id, version = _identity(config, root, row)
    cache = db.fetchone(
        """
        SELECT * FROM relevance_cache
        WHERE source_fingerprint=? AND topic_id=? AND direction_id=? AND evaluator_version=?
        """,
        (fingerprint, topic_id, direction_id, version),
    )
    requires_deep = deep_entry_contract(topic_id) is not None
    if (
        not cache
        or cache.get("technology_value_score") is None
        or (requires_deep and cache.get("deep_eligible") is None)
    ):
        _reset_legacy_cache_hit(db, str(row["id"]))
        return False

    deep = None if cache.get("deep_eligible") is None else bool(cache.get("deep_eligible"))
    relevant = bool(cache.get("relevant"))
    fulltext = bool(cache.get("fulltext_required"))
    status = "RELEVANT" if fulltext else ("RADAR" if relevant else "REJECTED")
    db.execute(
        """
        UPDATE candidates SET relevant=?,relevance_score=?,relevance_reason=?,fulltext_required=?,status=?,
          technology_value_score=?,technology_value_json=?,topic_fit=?,core_contribution=?,
          boundary_conflict=?,matched_direction_id=?,deep_eligible=?,deep_eligibility_reason=?
        WHERE id=?
        """,
        (
            int(relevant), cache.get("relevance_score"), cache.get("relevance_reason"), int(fulltext), status,
            cache.get("technology_value_score"), cache.get("technology_value_json"), cache.get("topic_fit"),
            cache.get("core_contribution"), cache.get("boundary_conflict"), cache.get("matched_direction_id"),
            None if deep is None else int(deep), cache.get("deep_eligibility_reason"), row["id"],
        ),
    )
    persist_candidate_assessment(config, db, root, str(row["id"]), provenance="relevance_cache")
    return True


def install_candidate_assessment() -> None:
    """Make one persisted CandidateAssessment and one relevance-cache record authoritative."""

    from . import deep_eligibility, relevance_efficiency, technology_value
    from .db import Database
    from .pipeline import Pipeline

    if getattr(Pipeline, "_candidate_assessment_installed", False):
        return

    original_db_init = Database.init

    def db_init(self) -> None:
        original_db_init(self)
        ensure_candidate_assessment_schema(self)

    Database.init = db_init
    ensure_candidate_assessment_schema

    # The old component caches remain as readable historical tables/functions, but new
    # runtime writes are owned by the final CandidateAssessment commit below.
    technology_value.store_technology_value_cache = lambda *_args, **_kwargs: True
    deep_eligibility.store_deep_eligibility_cache = lambda *_args, **_kwargs: None
    technology_value._apply_cached_technology_value = lambda *_args, **_kwargs: None

    original_cached = relevance_efficiency.apply_cached_relevance

    def apply_cached_relevance(config, db, root, row: dict[str, Any]) -> bool:
        hit = original_cached(config, db, root, row)
        if not hit:
            return False
        return apply_unified_cached_assessment(config, db, root, row)

    relevance_efficiency.apply_cached_relevance = apply_cached_relevance

    original_apply = Pipeline._apply_task

    def apply_task(self, task: dict[str, Any]) -> None:
        original_apply(self, task)
        if task.get("task_type") != "relevance_batch":
            return
        task_input = read_json(self.root / task["input_path"], {})
        for candidate in task_input.get("candidates") or []:
            candidate_id = str(candidate.get("candidate_id") or "")
            if candidate_id:
                persist_candidate_assessment(
                    self.config, self.db, self.root, candidate_id, provenance="agent_relevance_batch"
                )

    from .utils import read_json

    Pipeline._apply_task = apply_task
    Pipeline._candidate_assessment_installed = True
