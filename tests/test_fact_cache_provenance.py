from __future__ import annotations

import json

from briefing_skill.db import Database
from briefing_skill.fact_cache_provenance import (
    FACT_CACHE_PROVENANCE_VERSION,
    _facts_hash,
    _synthetic_fact_output,
    ensure_fact_cache_provenance_schema,
    execution_mode,
    lookup_fact_cache_v2,
    readable_namespaces,
    set_run_execution_mode,
)
from briefing_skill.utils import now_iso, write_json


def _db(tmp_path):
    db = Database(tmp_path / "state.sqlite3")
    db.init()
    ensure_fact_cache_provenance_schema(db)
    return db


def _insert_cache(
    db,
    root,
    *,
    key="k1",
    namespace="production",
    producer_mode="production",
    source_fingerprint="source-v1",
    extractor_version="extractor-v1",
    source_content_hash="content-v1",
    source_text_hash="source-text-v1",
    evidence_hash="evidence-v1",
):
    facts = {
        "title": "real facts",
        "primary_source_resolved": True,
        "quality_score": 90,
        "source_notes": ["primary source"],
    }
    path = root / "workspace" / "cache" / "facts-v2" / namespace / f"{key}.json"
    provenance = {
        "provenance_version": FACT_CACHE_PROVENANCE_VERSION,
        "cache_namespace": namespace,
        "producer_mode": producer_mode,
        "producer_run_id": "producer-run",
        "source_fingerprint": source_fingerprint,
        "extractor_version": extractor_version,
        "source_content_hash": source_content_hash,
        "source_text_hash": source_text_hash,
        "evidence_hash": evidence_hash,
    }
    write_json(path, {"_cache_provenance": provenance, "facts": facts})
    now = now_iso()
    db.execute(
        """
        INSERT INTO fact_cache_v2(
          cache_key,cache_namespace,producer_mode,producer_run_id,provenance_version,
          source_fingerprint,extractor_version,source_url,source_identity,external_id,
          source_content_hash,source_text_hash,evidence_hash,facts_hash,json_path,
          quality_score,event_hint,raw_char_count,evidence_char_count,created_at,last_used_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            key,
            namespace,
            producer_mode,
            "producer-run",
            FACT_CACHE_PROVENANCE_VERSION,
            source_fingerprint,
            extractor_version,
            "https://example.com/source",
            "arxiv:2608.12345",
            "2608.12345v1",
            source_content_hash,
            source_text_hash,
            evidence_hash,
            _facts_hash(facts),
            str(path.relative_to(root)),
            90,
            None,
            1000,
            500,
            now,
            now,
        ),
    )
    return facts


def _lookup(db, root, mode="production", **overrides):
    values = {
        "source_fingerprint": "source-v1",
        "extractor_version": "extractor-v1",
        "source_content_hash": "content-v1",
        "source_text_hash": "source-text-v1",
        "evidence_hash": "evidence-v1",
    }
    values.update(overrides)
    return lookup_fact_cache_v2(db, root, mode=mode, **values)


def test_production_never_reads_fixture_or_demo_namespace(tmp_path):
    db = _db(tmp_path)
    _insert_cache(db, tmp_path, namespace="fixture", producer_mode="fixture")

    assert _lookup(db, tmp_path, mode="production") is None
    assert readable_namespaces("production") == ("production",)


def test_replay_can_reuse_production_but_production_cannot_reuse_replay(tmp_path):
    db = _db(tmp_path)
    expected = _insert_cache(db, tmp_path, namespace="production", producer_mode="production")

    hit = _lookup(db, tmp_path, mode="replay")
    assert hit is not None
    assert hit[1] == expected

    db.execute("DELETE FROM fact_cache_v2")
    _insert_cache(db, tmp_path, key="replay-k", namespace="replay", producer_mode="replay")
    assert _lookup(db, tmp_path, mode="production") is None
    assert _lookup(db, tmp_path, mode="replay") is not None


def test_changed_source_content_fulltext_or_evidence_hash_is_a_miss(tmp_path):
    db = _db(tmp_path)
    _insert_cache(db, tmp_path)

    assert _lookup(db, tmp_path, source_content_hash="changed") is None
    assert _lookup(db, tmp_path, source_text_hash="changed") is None
    assert _lookup(db, tmp_path, evidence_hash="changed") is None


def test_tampered_cached_fact_payload_is_rejected(tmp_path):
    db = _db(tmp_path)
    _insert_cache(db, tmp_path)
    row = db.fetchone("SELECT json_path FROM fact_cache_v2 WHERE cache_key='k1'")
    path = tmp_path / row["json_path"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["facts"]["title"] = "tampered"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert _lookup(db, tmp_path) is None


def test_legacy_fact_cache_rows_are_not_read_by_v2_lookup(tmp_path):
    db = _db(tmp_path)
    # Database.init creates the legacy table. Seed a row with the exact old identity;
    # v2 deliberately has no migration/read fallback, so it cannot satisfy lookup.
    now = now_iso()
    db.execute(
        """
        INSERT OR REPLACE INTO fact_cache(
          source_fingerprint,extractor_version,cache_key,source_url,source_identity,
          external_id,source_content_hash,json_path,quality_score,event_hint,
          raw_char_count,evidence_char_count,created_at,last_used_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "source-v1",
            "extractor-v1",
            "legacy-k",
            "https://example.com/source",
            "arxiv:2608.12345",
            "2608.12345v1",
            "content-v1",
            "workspace/cache/facts/legacy.json",
            99,
            None,
            1000,
            500,
            now,
            now,
        ),
    )

    assert _lookup(db, tmp_path) is None


def test_fixture_payload_forces_fixture_mode_even_if_run_was_marked_production(tmp_path):
    db = _db(tmp_path)
    set_run_execution_mode(db, "run-1", "production")
    raw = {"payload_json": json.dumps({"fixture": True})}

    assert execution_mode(db, "run-1", raw) == "fixture"


def test_demo_or_fixture_fact_output_cannot_mint_trusted_cache():
    demo = {
        "source_notes": ["DEMO ONLY — deterministic offline fixture"],
        "evaluation_context": "Synthetic fixture",
        "evidence": [],
    }
    real = {
        "source_notes": ["Primary source reviewed"],
        "evaluation_context": "Production paper",
        "evidence": [{"claim": "measured result", "condition": "H100"}],
    }

    assert _synthetic_fact_output(demo) is True
    assert _synthetic_fact_output(real) is False
