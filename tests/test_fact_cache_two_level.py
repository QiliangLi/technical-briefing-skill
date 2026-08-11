from __future__ import annotations

from briefing_skill.cost_schema import ensure_cost_schema
from briefing_skill.db import Database
from briefing_skill.fact_cache_provenance import (
    FACT_CACHE_PROVENANCE_VERSION,
    _facts_hash,
    ensure_fact_cache_provenance_schema,
)
from briefing_skill.fact_cache_two_level import (
    _post_fetch_l1_hit,
    immutable_source_key,
    lookup_immutable_fact_cache,
)
from briefing_skill.utils import now_iso, write_json


def _db(tmp_path):
    db = Database(tmp_path / "state.sqlite3")
    db.init()
    ensure_cost_schema(db)
    ensure_fact_cache_provenance_schema(db)
    return db


def _insert_cache(db, root):
    facts = {
        "title": "cached",
        "primary_source_resolved": True,
        "quality_score": 92,
        "source_notes": ["primary source"],
    }
    path = root / "workspace" / "cache" / "facts-v2" / "production" / "cache-k.json"
    provenance = {
        "provenance_version": FACT_CACHE_PROVENANCE_VERSION,
        "cache_namespace": "production",
        "producer_mode": "production",
        "producer_run_id": "producer",
        "source_fingerprint": "fingerprint-v1",
        "extractor_version": "extractor-v1",
        "source_content_hash": "",
        "source_text_hash": "text-v1",
        "evidence_hash": "evidence-v1",
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
            "cache-k",
            "production",
            "production",
            "producer",
            FACT_CACHE_PROVENANCE_VERSION,
            "fingerprint-v1",
            "extractor-v1",
            "https://arxiv.org/abs/2608.12345v1",
            "arxiv:2608.12345",
            "2608.12345v1",
            "",
            "text-v1",
            "evidence-v1",
            _facts_hash(facts),
            str(path.relative_to(root)),
            92,
            None,
            10000,
            5000,
            now,
            now,
        ),
    )
    return facts


def test_l0_gate_accepts_only_provably_immutable_versions() -> None:
    arxiv_v1 = {
        "source_level": "A",
        "discovery_only": 0,
        "identity_key": "arxiv:2608.12345",
        "external_id": "2608.12345v1",
        "original_url": "https://arxiv.org/abs/2608.12345v1",
        "payload_json": "{}",
    }
    arxiv_unversioned = {**arxiv_v1, "external_id": "2608.12345", "original_url": "https://arxiv.org/abs/2608.12345"}
    mutable_tag = {
        "source_level": "A",
        "discovery_only": 0,
        "identity_key": "github-tag:owner/repo:v1",
        "external_id": "v1",
        "original_url": "https://github.com/owner/repo/releases/tag/v1",
        "payload_json": '{"repo":"owner/repo","tag":"v1"}',
    }
    commit = {
        "source_level": "A",
        "discovery_only": 0,
        "identity_key": "github-commit:owner/repo:0123456789abcdef",
        "external_id": "0123456789abcdef",
        "original_url": "https://github.com/owner/repo/commit/0123456789abcdef",
        "payload_json": "{}",
    }

    assert immutable_source_key(arxiv_v1) == "arxiv:2608.12345@v1"
    assert immutable_source_key(arxiv_unversioned) is None
    assert immutable_source_key(mutable_tag) is None
    assert immutable_source_key(commit) == "github-commit:owner/repo:0123456789abcdef"


def test_l0_lookup_reuses_valid_v2_payload_without_recomputed_hashes(tmp_path) -> None:
    db = _db(tmp_path)
    expected = _insert_cache(db, tmp_path)

    hit = lookup_immutable_fact_cache(
        db,
        tmp_path,
        mode="production",
        source_fingerprint="fingerprint-v1",
        extractor_version="extractor-v1",
        source_content_hash="",
    )

    assert hit is not None
    assert hit[0]["cache_key"] == "cache-k"
    assert hit[1] == expected


def test_l0_still_requires_exact_fingerprint_extractor_and_content_metadata(tmp_path) -> None:
    db = _db(tmp_path)
    _insert_cache(db, tmp_path)

    assert lookup_immutable_fact_cache(
        db, tmp_path, mode="production", source_fingerprint="changed",
        extractor_version="extractor-v1", source_content_hash=""
    ) is None
    assert lookup_immutable_fact_cache(
        db, tmp_path, mode="production", source_fingerprint="fingerprint-v1",
        extractor_version="changed", source_content_hash=""
    ) is None
    assert lookup_immutable_fact_cache(
        db, tmp_path, mode="production", source_fingerprint="fingerprint-v1",
        extractor_version="extractor-v1", source_content_hash="changed"
    ) is None


def test_l1_rechecks_cache_immediately_after_fetch_hashes_exist(tmp_path) -> None:
    db = _db(tmp_path)
    expected = _insert_cache(db, tmp_path)
    hit = _post_fetch_l1_hit(
        db,
        tmp_path,
        mode="production",
        source_fingerprint="fingerprint-v1",
        extractor_version="extractor-v1",
        source_content_hash="",
        manifest={
            "fetch_status": "FETCHED",
            "source_text_hash": "text-v1",
            "evidence_hash": "evidence-v1",
        },
    )

    assert hit is not None
    assert hit[1] == expected


def test_l1_post_fetch_does_not_accept_fallback_or_incomplete_hashes(tmp_path) -> None:
    db = _db(tmp_path)
    _insert_cache(db, tmp_path)
    common = {
        "mode": "production",
        "source_fingerprint": "fingerprint-v1",
        "extractor_version": "extractor-v1",
        "source_content_hash": "",
    }

    assert _post_fetch_l1_hit(db, tmp_path, **common, manifest={"fetch_status": "FALLBACK", "source_text_hash": "text-v1", "evidence_hash": "evidence-v1"}) is None
    assert _post_fetch_l1_hit(db, tmp_path, **common, manifest={"fetch_status": "FETCHED", "source_text_hash": "", "evidence_hash": "evidence-v1"}) is None
