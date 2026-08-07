from __future__ import annotations

from .db import Database


COST_SCHEMA = """
CREATE TABLE IF NOT EXISTS fact_cache (
    cache_key TEXT PRIMARY KEY,
    source_fingerprint TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    source_url TEXT,
    source_identity TEXT,
    external_id TEXT,
    source_content_hash TEXT,
    json_path TEXT NOT NULL,
    quality_score REAL,
    event_hint TEXT,
    raw_char_count INTEGER NOT NULL DEFAULT 0,
    evidence_char_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    UNIQUE(source_fingerprint, extractor_version)
);

CREATE INDEX IF NOT EXISTS idx_fact_cache_source
ON fact_cache(source_fingerprint, extractor_version);

CREATE TABLE IF NOT EXISTS task_metrics (
    task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    input_chars INTEGER NOT NULL DEFAULT 0,
    prompt_chars INTEGER NOT NULL DEFAULT 0,
    output_chars INTEGER NOT NULL DEFAULT 0,
    document_chars INTEGER NOT NULL DEFAULT 0,
    evidence_chars INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    invalid_count INTEGER NOT NULL DEFAULT 0,
    cache_hit INTEGER NOT NULL DEFAULT 0,
    first_started_at TEXT,
    last_started_at TEXT,
    completed_at TEXT,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_task_metrics_run
ON task_metrics(run_id, task_type);
"""


def ensure_cost_schema(db: Database) -> None:
    with db.connect() as conn:
        conn.executescript(COST_SCHEMA)


def install_cost_schema() -> None:
    """Make cost/cache tables available to every normal CLI context."""

    if getattr(Database, "_cost_schema_installed", False):
        return
    original_init = Database.init

    def init(self: Database) -> None:
        original_init(self)
        ensure_cost_schema(self)

    Database.init = init
    Database._cost_schema_installed = True
