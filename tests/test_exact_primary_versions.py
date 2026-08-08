from __future__ import annotations

import json

from briefing_skill.db import Database
from briefing_skill.safe_efficiency import dedupe_exact_primary_candidates, exact_primary_version_key
from briefing_skill.utils import now_iso


def _insert(db: Database, run_id: str, raw_id: str, candidate_id: str, version: str) -> None:
    created = now_iso()
    versioned = f"2608.12345{version}"
    url = f"https://arxiv.org/abs/{versioned}"
    db.execute(
        """
        INSERT INTO raw_items(
            id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
            original_url,aihot_url,canonical_url,identity_key,published_at,discovered_at,
            authors_json,external_id,topic_hint,direction_hint,priority,content_hash,payload_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            raw_id, run_id, "arxiv", "arXiv", "A", 0,
            "Versioned paper", f"summary {version}", url, "", url,
            "arxiv:2608.12345", created, created, "[]", url,
            "tpn", "kv_transfer", 18, f"hash-{version}",
            json.dumps({"pdf_url": f"https://arxiv.org/pdf/{versioned}.pdf"}), created,
        ),
    )
    db.execute(
        """
        INSERT INTO candidates(id,run_id,raw_item_id,topic_id,direction_id,rule_score,status,created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (candidate_id, run_id, raw_id, "tpn", "kv_transfer", 90, "PENDING_RELEVANCE", created),
    )


def test_arxiv_revision_is_part_of_exact_pre_relevance_dedup_key(tmp_path):
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_id = "versions"
    db.create_run(run_id)
    _insert(db, run_id, "raw-v1", "candidate-v1", "v1")
    _insert(db, run_id, "raw-v2", "candidate-v2", "v2")

    rows = db.fetchall(
        """
        SELECT c.*, r.identity_key, r.source_level, r.discovery_only,
               r.external_id, r.original_url, r.canonical_url, r.payload_json
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
        WHERE c.run_id=? ORDER BY c.id
        """,
        (run_id,),
    )
    assert exact_primary_version_key(rows[0]) == "arxiv:2608.12345@v1"
    assert exact_primary_version_key(rows[1]) == "arxiv:2608.12345@v2"
    assert dedupe_exact_primary_candidates(db, run_id) == 0
    assert db.fetchone(
        "SELECT COUNT(*) AS n FROM candidates WHERE run_id=? AND status='PENDING_RELEVANCE'",
        (run_id,),
    )["n"] == 2


def test_unversioned_arxiv_is_not_pre_relevance_deduplicated(tmp_path):
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_id = "unversioned"
    db.create_run(run_id)
    created = now_iso()
    discoveries = (
        ("aihot", "AI HOT"),
        ("yeekal", "YeeKal AI Daily"),
    )
    for index, (source_id, discovery_source) in enumerate(discoveries):
        raw_id = f"raw-{index}"
        candidate_id = f"candidate-{index}"
        url = "https://arxiv.org/abs/2608.54321"
        db.execute(
            """
            INSERT INTO raw_items(
                id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
                original_url,aihot_url,canonical_url,identity_key,published_at,discovered_at,
                authors_json,external_id,topic_hint,direction_hint,priority,content_hash,payload_json,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                raw_id, run_id, source_id, discovery_source, "A", 0,
                "Unversioned paper", "summary", url, "", url,
                "arxiv:2608.54321", created, created, "[]", f"discovery-{index}",
                "tpn", "kv_transfer", 10, f"hash-{index}",
                json.dumps({"primary_source_resolution": {"kind": "arxiv", "url": url}}), created,
            ),
        )
        db.execute(
            """
            INSERT INTO candidates(id,run_id,raw_item_id,topic_id,direction_id,rule_score,status,created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (candidate_id, run_id, raw_id, "tpn", "kv_transfer", 80, "PENDING_RELEVANCE", created),
        )

    assert dedupe_exact_primary_candidates(db, run_id) == 0
    assert db.fetchone(
        "SELECT COUNT(*) AS n FROM candidates WHERE run_id=? AND status='PENDING_RELEVANCE'",
        (run_id,),
    )["n"] == 2
