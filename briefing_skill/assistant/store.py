"""Local state for the group assistant.

Everything lives under the ignored state directory: a SQLite ledger, semantic
task files and index snapshots. Group chat content must never leave it. The
store is the only writer of assistant state; each command runs in one
transaction, so a reply record and the decision behind it commit together.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from .timeutil import iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS arrivals (
    trigger_id TEXT NOT NULL,
    via TEXT NOT NULL,
    received_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    trigger_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    thread_key TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    is_bot INTEGER NOT NULL,
    is_mention INTEGER NOT NULL,
    is_direct INTEGER NOT NULL,
    is_reply INTEGER NOT NULL,
    created_ms INTEGER NOT NULL,
    text TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    first_via TEXT NOT NULL,
    received_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_thread ON events(thread_key, created_ms);

CREATE TABLE IF NOT EXISTS dispositions (
    trigger_id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    thread_key TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    history_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dispositions_decision ON dispositions(decision, updated_at);

CREATE TABLE IF NOT EXISTS threads (
    thread_key TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    root_message_id TEXT,
    anchor_idea_id TEXT,
    muted_at TEXT,
    last_activity_ms INTEGER,
    last_assessed_ms INTEGER,
    last_recommended_ms INTEGER,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    thread_key TEXT,
    trigger_id TEXT,
    policy_version TEXT NOT NULL,
    mode TEXT NOT NULL,
    outcome TEXT NOT NULL,
    rules_json TEXT NOT NULL,
    doc_ids_json TEXT NOT NULL,
    scores_json TEXT NOT NULL,
    draft TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    thread_key TEXT,
    trigger_id TEXT,
    status TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    created_ms INTEGER NOT NULL,
    expires_ms INTEGER NOT NULL,
    input_path TEXT NOT NULL,
    output_path TEXT NOT NULL,
    applied_at TEXT,
    result_json TEXT,
    error_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, created_ms);

CREATE TABLE IF NOT EXISTS outbox (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    reply_to TEXT NOT NULL,
    thread_key TEXT,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    message_id TEXT,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status, created_at);

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    idea_id TEXT,
    choice TEXT NOT NULL,
    operator_id TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registry (
    message_id TEXT PRIMARY KEY,
    idea_id TEXT NOT NULL,
    issue_date TEXT,
    pushed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cursors (
    chat_id TEXT PRIMARY KEY,
    cursor_ms INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pause_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._connection = sqlite3.connect(path, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.executescript(SCHEMA)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield self._connection
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        self._connection.execute(sql, params)

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        row = self._connection.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self._connection.execute(sql, params).fetchall()]

    def get_meta(self, key: str, default: Any = None) -> Any:
        row = self.fetchone("SELECT value FROM meta WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    def set_meta(self, key: str, value: Any, connection: sqlite3.Connection | None = None) -> None:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
        target = connection or self._connection
        target.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, payload),
        )

    def record_arrival(self, trigger_id: str, via: str, received_at: str) -> None:
        self._connection.execute(
            "INSERT INTO arrivals(trigger_id, via, received_at) VALUES(?, ?, ?)", (trigger_id, via, received_at)
        )

    def purge(self, retention_days: int, now: float, tasks_dir: Path | None = None) -> dict[str, int]:
        """Clear message bodies past the retention window; keep hashes and counts."""

        cutoff = iso(now - retention_days * 86400)
        with self.transaction() as connection:
            cleared = connection.execute(
                "UPDATE events SET text='' WHERE received_at < ? AND text <> ''", (cutoff,)
            ).rowcount
            old_arrivals = connection.execute("DELETE FROM arrivals WHERE received_at < ?", (cutoff,)).rowcount
        removed_tasks = 0
        if tasks_dir is not None and tasks_dir.exists():
            for directory in tasks_dir.iterdir():
                if directory.is_dir() and directory.stat().st_mtime < now - retention_days * 86400:
                    shutil.rmtree(directory, ignore_errors=True)
                    removed_tasks += 1
        return {"events_cleared": cleared, "arrivals_deleted": old_arrivals, "task_dirs_removed": removed_tasks}

    def close(self) -> None:
        self._connection.close()
