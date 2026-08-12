#!/usr/bin/env python3
"""Frozen-input seeding for the PR27-33 acceptance replay.

Forks the 619 frozen raw_items from the pr25-media replay run into a brand-new
run_id, WITHOUT re-running live collection or search. Content is copied
verbatim; only `id`, `run_id` and the media `local_fulltext_path` are rewritten.

This is the ONLY mutation of the shared SQLite DB for this replay, and it is
strictly additive: it inserts rows scoped to the new run_id and never touches
any other run. The source run (2026-08-08-200543-replay-pr25-media) is read-only.
"""
from __future__ import annotations

import json
import sqlite3
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # repo root
DB_PATH = ROOT / "workspace" / "briefing.sqlite"
SRC_RUN = "2026-08-08-200543-replay-pr25-media"
NEW_RUN = "2026-08-09-193020-replay-pr27-33"

RAW_COLS = [
    "id", "run_id", "source_id", "discovery_source", "source_level",
    "discovery_only", "title", "summary", "original_url", "aihot_url",
    "canonical_url", "published_at", "discovered_at", "authors_json",
    "external_id", "topic_hint", "direction_hint", "priority", "content_hash",
    "payload_json", "created_at", "identity_key",
]


def main() -> int:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    # Guard: never clobber an existing run.
    if cur.execute("SELECT 1 FROM runs WHERE id=?", (NEW_RUN,)).fetchone():
        raise SystemExit(f"Run already exists: {NEW_RUN}")

    src_items = cur.execute(
        f"SELECT * FROM raw_items WHERE run_id=? ORDER BY id", (SRC_RUN,)
    ).fetchall()
    if not src_items:
        raise SystemExit(f"Source run has no raw_items: {SRC_RUN}")

    # 1) runs row
    cur.execute(
        "INSERT INTO runs(id, created_at, updated_at, status, stage, note, issue_id) "
        "VALUES (?, datetime('now'), datetime('now'), ?, 'COLLECTED', ?, NULL)",
        (NEW_RUN, "ACTIVE", f"Offline replay of {SRC_RUN} (PR27-33 contracts)"),
    )

    # 2) fork raw_items with new ids (prefix keeps them disjoint from every other run)
    media_files = []
    inserted = 0
    for row in src_items:
        old_id = row["id"]
        new_id = f"rp33-{old_id}"
        payload = json.loads(row["payload_json"] or "{}")
        # Rewrite media local_fulltext_path to a run-relative path.
        if old_id.startswith("media-") and payload.get("local_fulltext_path"):
            fname = Path(payload["local_fulltext_path"]).name
            payload["local_fulltext_path"] = f"media-fulltext/{fname}"
            media_files.append((fname, payload["local_fulltext_path"]))
        values = []
        for col in RAW_COLS:
            if col == "id":
                values.append(new_id)
            elif col == "run_id":
                values.append(NEW_RUN)
            elif col == "payload_json":
                values.append(json.dumps(payload, ensure_ascii=False))
            else:
                values.append(row[col])
        placeholders = ",".join("?" for _ in RAW_COLS)
        cur.execute(
            f"INSERT INTO raw_items({','.join(RAW_COLS)}) VALUES ({placeholders})",
            values,
        )
        inserted += 1

    # 3) persist replay execution mode (provenance: replay may read production,
    #    production never consumes replay). BRIEFING_OFFLINE_REPLAY also forces this.
    cur.execute(
        "CREATE TABLE IF NOT EXISTS run_execution_provenance("
        "run_id TEXT PRIMARY KEY, execution_mode TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    cur.execute(
        "INSERT INTO run_execution_provenance(run_id, execution_mode, updated_at) "
        "VALUES (?, 'replay', datetime('now')) "
        "ON CONFLICT(run_id) DO UPDATE SET execution_mode=excluded.execution_mode, updated_at=excluded.updated_at",
        (NEW_RUN,),
    )
    db.commit()

    # 4) copy the 3 frozen media fulltexts into the new run (self-contained).
    src_dir = ROOT / "workspace" / "runs" / SRC_RUN
    new_dir = ROOT / "workspace" / "runs" / NEW_RUN
    media_dst = new_dir / "media-fulltext"
    media_dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for fname, _ in media_files:
        s = src_dir / "media-fulltext" / fname
        if s.exists():
            shutil.copy2(s, media_dst / fname)
            copied.append(fname)

    # summary
    n = cur.execute("SELECT COUNT(*) c FROM raw_items WHERE run_id=?", (NEW_RUN,)).fetchone()["c"]
    media_n = cur.execute(
        "SELECT COUNT(*) c FROM raw_items WHERE run_id=? AND id LIKE 'media-%'", (NEW_RUN,)
    ).fetchone()["c"]
    print(json.dumps({
        "new_run": NEW_RUN,
        "source_run": SRC_RUN,
        "forked_raw_items": inserted,
        "raw_items_in_new_run": n,
        "media_items": media_n,
        "media_fulltexts_copied": copied,
        "execution_mode": "replay",
        "network_search_performed": False,
    }, ensure_ascii=False, indent=2))
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
