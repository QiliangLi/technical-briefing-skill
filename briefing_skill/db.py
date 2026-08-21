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
    upstream_item_id TEXT,
    story_id TEXT,
    PRIMARY KEY(issue_id, canonical_url),
    FOREIGN KEY(issue_id) REFERENCES issues(id)
);

CREATE TABLE IF NOT EXISTS radar_history (
    canonical_url TEXT PRIMARY KEY,
    normalized_title TEXT NOT NULL,
    last_pushed_at TEXT NOT NULL,
    issue_id TEXT NOT NULL,
    upstream_item_id TEXT,
    story_id TEXT
);

CREATE TABLE IF NOT EXISTS radar_upstream_records (
    record_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    upstream_lane TEXT NOT NULL,
    lane_key TEXT,
    lane_query TEXT,
    topic_hint TEXT,
    direction_hint TEXT,
    upstream_item_id TEXT,
    upstream_story_id TEXT,
    upstream_url TEXT,
    original_url TEXT,
    canonical_original_url TEXT,
    published_at TEXT,
    discovered_at TEXT,
    retrieved_at TEXT,
    retrieved_at_first TEXT,
    etag TEXT,
    title TEXT,
    summary TEXT,
    reason TEXT,
    title_hash TEXT,
    summary_hash TEXT,
    raw_payload_json TEXT,
    selected_for_radar INTEGER NOT NULL DEFAULT 0,
    radar_id TEXT,
    decision_reason TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, provider, lane_key, upstream_item_id)
);

CREATE INDEX IF NOT EXISTS idx_radar_upstream_run ON radar_upstream_records(run_id);
CREATE INDEX IF NOT EXISTS idx_radar_upstream_item ON radar_upstream_records(run_id, upstream_item_id);
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
            radar_history_columns = {row[1] for row in conn.execute("PRAGMA table_info(radar_history)")}
            if "upstream_item_id" not in radar_history_columns:
                conn.execute("ALTER TABLE radar_history ADD COLUMN upstream_item_id TEXT")
            if "story_id" not in radar_history_columns:
                conn.execute("ALTER TABLE radar_history ADD COLUMN story_id TEXT")
            issue_radar_columns = {row[1] for row in conn.execute("PRAGMA table_info(issue_radar_items)")}
            if "upstream_item_id" not in issue_radar_columns:
                conn.execute("ALTER TABLE issue_radar_items ADD COLUMN upstream_item_id TEXT")
            if "story_id" not in issue_radar_columns:
                conn.execute("ALTER TABLE issue_radar_items ADD COLUMN story_id TEXT")
            ledger_columns = {row[1] for row in conn.execute("PRAGMA table_info(radar_upstream_records)")}
            for column in ("lane_key", "lane_query", "topic_hint", "direction_hint", "retrieved_at_first"):
                if column not in ledger_columns:
                    conn.execute(f"ALTER TABLE radar_upstream_records ADD COLUMN {column} TEXT")
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
            self._migrate_radar_upstream_unique(conn)

    @staticmethod
    def _migrate_radar_upstream_unique(conn: sqlite3.Connection) -> None:
        """Rebuild the ledger when it still carries the pre-lane-key UNIQUE.

        The original constraint UNIQUE(run_id, provider, upstream_lane,
        upstream_item_id) collides once two same-type query lanes (both
        ``all``) hit the same item with distinct full lane keys. SQLite cannot
        drop a table constraint, so the table is rebuilt once, copying rows.
        """
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='radar_upstream_records'"
        ).fetchone()
        if not row or not row[0]:
            return
        normalized = " ".join(str(row[0]).split()).lower()
        if "unique(run_id, provider, lane_key, upstream_item_id)" in normalized:
            return
        if "unique(run_id, provider, upstream_lane, upstream_item_id)" not in normalized:
            return
        columns = [
            "record_id", "run_id", "provider", "upstream_lane", "lane_key", "lane_query",
            "topic_hint", "direction_hint", "upstream_item_id", "upstream_story_id",
            "upstream_url", "original_url", "canonical_original_url", "published_at",
            "discovered_at", "retrieved_at", "retrieved_at_first", "etag", "title",
            "summary", "reason", "title_hash", "summary_hash", "raw_payload_json",
            "selected_for_radar", "radar_id", "decision_reason", "created_at",
        ]
        existing = {info[1] for info in conn.execute("PRAGMA table_info(radar_upstream_records)")}
        usable = [name for name in columns if name in existing]
        column_list = ",".join(usable)
        conn.executescript(
            """
            CREATE TABLE radar_upstream_records_new(
                record_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                upstream_lane TEXT NOT NULL,
                lane_key TEXT,
                lane_query TEXT,
                topic_hint TEXT,
                direction_hint TEXT,
                upstream_item_id TEXT,
                upstream_story_id TEXT,
                upstream_url TEXT,
                original_url TEXT,
                canonical_original_url TEXT,
                published_at TEXT,
                discovered_at TEXT,
                retrieved_at TEXT,
                retrieved_at_first TEXT,
                etag TEXT,
                title TEXT,
                summary TEXT,
                reason TEXT,
                title_hash TEXT,
                summary_hash TEXT,
                raw_payload_json TEXT,
                selected_for_radar INTEGER NOT NULL DEFAULT 0,
                radar_id TEXT,
                decision_reason TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(run_id, provider, lane_key, upstream_item_id)
            );
            """
        )
        conn.execute(
            f"INSERT OR IGNORE INTO radar_upstream_records_new({column_list}) "
            f"SELECT {column_list} FROM radar_upstream_records"
        )
        conn.execute("DROP TABLE radar_upstream_records")
        conn.execute("ALTER TABLE radar_upstream_records_new RENAME TO radar_upstream_records")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_radar_upstream_run ON radar_upstream_records(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_radar_upstream_item ON radar_upstream_records(run_id, upstream_item_id)")

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

    def upsert_radar_upstream_records(self, rows: Sequence[dict[str, Any]]) -> None:
        """Refresh upstream lane observations while preserving selection decisions.

        ``retrieved_at_first`` keeps the original capture time across replays so
        resume never overwrites the fetch identity of an earlier collection.
        """
        if not rows:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO radar_upstream_records(
                    record_id, run_id, provider, upstream_lane, lane_key, lane_query,
                    topic_hint, direction_hint, upstream_item_id, upstream_story_id,
                    upstream_url, original_url, canonical_original_url, published_at, discovered_at,
                    retrieved_at, retrieved_at_first, etag, title, summary, reason,
                    title_hash, summary_hash,
                    raw_payload_json, selected_for_radar, radar_id, decision_reason, created_at
                ) VALUES (
                    :record_id, :run_id, :provider, :upstream_lane, :lane_key, :lane_query,
                    :topic_hint, :direction_hint, :upstream_item_id, :upstream_story_id,
                    :upstream_url, :original_url, :canonical_original_url, :published_at, :discovered_at,
                    :retrieved_at, :retrieved_at_first, :etag, :title, :summary, :reason,
                    :title_hash, :summary_hash,
                    :raw_payload_json, :selected_for_radar, :radar_id, :decision_reason, :created_at
                )
                ON CONFLICT(record_id) DO UPDATE SET
                    lane_key=excluded.lane_key,
                    lane_query=excluded.lane_query,
                    topic_hint=excluded.topic_hint,
                    direction_hint=excluded.direction_hint,
                    upstream_story_id=excluded.upstream_story_id,
                    upstream_url=excluded.upstream_url,
                    original_url=excluded.original_url,
                    canonical_original_url=excluded.canonical_original_url,
                    published_at=excluded.published_at,
                    discovered_at=excluded.discovered_at,
                    retrieved_at=excluded.retrieved_at,
                    retrieved_at_first=COALESCE(radar_upstream_records.retrieved_at_first, excluded.retrieved_at_first),
                    etag=excluded.etag,
                    title=excluded.title,
                    summary=excluded.summary,
                    reason=excluded.reason,
                    title_hash=excluded.title_hash,
                    summary_hash=excluded.summary_hash,
                    raw_payload_json=excluded.raw_payload_json
                """,
                [dict(row) for row in rows],
            )

    def list_radar_upstream_records(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.fetchall(
            "SELECT * FROM radar_upstream_records WHERE run_id=? ORDER BY upstream_lane, record_id",
            (run_id,),
        )
        for row in rows:
            if row.get("raw_payload_json"):
                row["raw_payload"] = json.loads(row["raw_payload_json"])
        return rows

    def update_radar_upstream_decisions(self, run_id: str, decisions: Sequence[dict[str, Any]]) -> None:
        """Record which upstream items the deterministic radar selection adopted."""
        if not decisions:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                UPDATE radar_upstream_records
                SET selected_for_radar=:selected_for_radar,
                    radar_id=:radar_id,
                    decision_reason=:decision_reason
                WHERE run_id=:run_id AND provider=:provider
                  AND ((:upstream_item_id != '' AND upstream_item_id=:upstream_item_id)
                       OR (:canonical_original_url != '' AND canonical_original_url=:canonical_original_url))
                """,
                [
                    {
                        "run_id": run_id,
                        "provider": "aihot",
                        "upstream_item_id": str(decision.get("upstream_item_id") or ""),
                        "canonical_original_url": str(decision.get("canonical_original_url") or ""),
                        "selected_for_radar": int(bool(decision.get("selected_for_radar"))),
                        "radar_id": decision.get("radar_id"),
                        "decision_reason": decision.get("decision_reason"),
                    }
                    for decision in decisions
                ],
            )

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
