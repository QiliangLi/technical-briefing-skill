from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from .utils import now_iso, source_identity_key


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    note TEXT,
    issue_id TEXT
);

CREATE TABLE IF NOT EXISTS source_state (
    source_key TEXT PRIMARY KEY,
    etag TEXT,
    cursor TEXT,
    last_success_at TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS raw_items (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    discovery_source TEXT NOT NULL,
    source_level TEXT NOT NULL,
    discovery_only INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    summary TEXT,
    original_url TEXT,
    aihot_url TEXT,
    canonical_url TEXT,
    identity_key TEXT,
    published_at TEXT,
    discovered_at TEXT,
    authors_json TEXT,
    external_id TEXT,
    topic_hint TEXT,
    direction_hint TEXT,
    priority REAL NOT NULL DEFAULT 0,
    content_hash TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, source_id, canonical_url, title)
);

CREATE INDEX IF NOT EXISTS idx_raw_run ON raw_items(run_id);
CREATE INDEX IF NOT EXISTS idx_raw_canonical ON raw_items(canonical_url);

CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    raw_item_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    direction_id TEXT NOT NULL,
    rule_score REAL NOT NULL,
    relevant INTEGER,
    relevance_score REAL,
    relevance_reason TEXT,
    fulltext_required INTEGER,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(raw_item_id) REFERENCES raw_items(id)
);

CREATE INDEX IF NOT EXISTS idx_candidate_run ON candidates(run_id);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    url TEXT,
    media_type TEXT,
    text_path TEXT,
    char_count INTEGER,
    fetch_status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(candidate_id) REFERENCES candidates(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    entity_id TEXT,
    input_path TEXT NOT NULL,
    output_path TEXT NOT NULL,
    prompt_path TEXT NOT NULL,
    schema_path TEXT NOT NULL,
    status TEXT NOT NULL,
    priority REAL NOT NULL DEFAULT 0,
    metadata_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(run_id, task_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_run_status ON tasks(run_id, status, priority DESC);

CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    json_path TEXT NOT NULL,
    quality_score REAL,
    event_hint TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL,
    direction_id TEXT NOT NULL,
    canonical_title TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    event_key TEXT,
    score REAL NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_updated_at TEXT NOT NULL,
    last_pushed_at TEXT,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_members (
    event_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    PRIMARY KEY(event_id, candidate_id),
    FOREIGN KEY(event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS brief_items (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    json_path TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    fact_check_status TEXT,
    approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, event_id)
);

CREATE TABLE IF NOT EXISTS issues (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    status TEXT NOT NULL,
    date_from TEXT,
    date_to TEXT,
    subject TEXT,
    synthesis_path TEXT,
    issue_json_path TEXT,
    email_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS issue_items (
    issue_id TEXT NOT NULL,
    brief_item_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    visual_plan_path TEXT,
    item_role TEXT NOT NULL DEFAULT 'core',
    PRIMARY KEY(issue_id, brief_item_id),
    FOREIGN KEY(issue_id) REFERENCES issues(id),
    FOREIGN KEY(brief_item_id) REFERENCES brief_items(id)
);

CREATE TABLE IF NOT EXISTS send_history (
    issue_id TEXT PRIMARY KEY,
    sent_at TEXT NOT NULL,
    recipients TEXT NOT NULL,
    message_id TEXT,
    status TEXT NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS issue_radar_items (
    issue_id TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    source_name TEXT NOT NULL,
    published_at TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY(issue_id, canonical_url),
    FOREIGN KEY(issue_id) REFERENCES issues(id)
);

CREATE TABLE IF NOT EXISTS radar_history (
    canonical_url TEXT PRIMARY KEY,
    normalized_title TEXT NOT NULL,
    last_pushed_at TEXT NOT NULL,
    issue_id TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(issue_items)")}
            if "item_role" not in columns:
                conn.execute("ALTER TABLE issue_items ADD COLUMN item_role TEXT NOT NULL DEFAULT 'core'")
            raw_columns = {row[1] for row in conn.execute("PRAGMA table_info(raw_items)")}
            if "identity_key" not in raw_columns:
                conn.execute("ALTER TABLE raw_items ADD COLUMN identity_key TEXT")
            event_columns = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
            if "event_key" not in event_columns:
                conn.execute("ALTER TABLE events ADD COLUMN event_key TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_identity ON raw_items(identity_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event_key ON events(event_key)")

            for row in conn.execute(
                "SELECT id, canonical_url, external_id FROM raw_items WHERE identity_key IS NULL OR identity_key=''"
            ).fetchall():
                identity = source_identity_key(row[1], row[2])
                if identity:
                    conn.execute("UPDATE raw_items SET identity_key=? WHERE id=?", (identity, row[0]))

            missing_events = conn.execute(
                "SELECT id FROM events WHERE event_key IS NULL OR event_key=''"
            ).fetchall()
            for (event_id,) in missing_events:
                identity_row = conn.execute(
                    """
                    SELECT r.identity_key
                    FROM event_members em
                    JOIN candidates c ON c.id=em.candidate_id
                    JOIN raw_items r ON r.id=c.raw_item_id
                    WHERE em.event_id=? AND r.identity_key IS NOT NULL AND r.identity_key!=''
                    ORDER BY r.source_level='A' DESC, r.created_at
                    LIMIT 1
                    """,
                    (event_id,),
                ).fetchone()
                if identity_row:
                    conn.execute("UPDATE events SET event_key=? WHERE id=?", (identity_row[0], event_id))

            # Historical duplicate events may already exist. Propagate the sent
            # marker across the shared stable identity so they cannot reappear.
            conn.execute(
                """
                UPDATE events
                SET last_pushed_at=(
                    SELECT MAX(e2.last_pushed_at) FROM events e2
                    WHERE e2.event_key=events.event_key
                )
                WHERE event_key IS NOT NULL AND event_key!=''
                """
            )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        with self.connect() as conn:
            conn.execute(sql, params)

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> None:
        with self.connect() as conn:
            conn.executemany(sql, rows)

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def upsert_source_state(
        self,
        source_key: str,
        *,
        etag: str | None = None,
        cursor: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO source_state(source_key, etag, cursor, last_success_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    etag=excluded.etag,
                    cursor=COALESCE(excluded.cursor, source_state.cursor),
                    last_success_at=excluded.last_success_at,
                    payload_json=excluded.payload_json
                """,
                (source_key, etag, cursor, now_iso(), json.dumps(payload or {}, ensure_ascii=False)),
            )

    def get_source_state(self, source_key: str) -> dict[str, Any] | None:
        row = self.fetchone("SELECT * FROM source_state WHERE source_key=?", (source_key,))
        if row and row.get("payload_json"):
            row["payload"] = json.loads(row["payload_json"])
        return row

    def create_run(self, run_id: str, stage: str = "INIT") -> None:
        now = now_iso()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO runs(id, created_at, updated_at, status, stage) VALUES (?, ?, ?, ?, ?)",
                (run_id, now, now, "ACTIVE", stage),
            )

    def update_run(self, run_id: str, *, stage: str | None = None, status: str | None = None, note: str | None = None, issue_id: str | None = None) -> None:
        current = self.fetchone("SELECT * FROM runs WHERE id=?", (run_id,))
        if not current:
            raise KeyError(f"Unknown run: {run_id}")
        self.execute(
            "UPDATE runs SET updated_at=?, stage=?, status=?, note=?, issue_id=? WHERE id=?",
            (
                now_iso(),
                stage or current["stage"],
                status or current["status"],
                note if note is not None else current.get("note"),
                issue_id if issue_id is not None else current.get("issue_id"),
                run_id,
            ),
        )

    def latest_run(self) -> dict[str, Any] | None:
        return self.fetchone("SELECT * FROM runs ORDER BY created_at DESC LIMIT 1")

    def json_column(self, row: dict[str, Any], name: str) -> Any:
        value = row.get(name)
        return json.loads(value) if value else None
