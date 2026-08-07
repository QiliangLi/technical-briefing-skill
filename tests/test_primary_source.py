from __future__ import annotations

import json

from briefing_skill.adapters.base import CollectedItem
from briefing_skill.collection import CollectionService
from briefing_skill.db import Database
from briefing_skill.primary_source import primary_pdf_url, primary_source_kind, promote_discovery_primary


def _item(url: str) -> CollectedItem:
    return CollectedItem(
        source_id="aihot",
        discovery_source="AI HOT",
        source_level="B",
        discovery_only=True,
        title="Discovered technical work",
        summary="A discovery summary used only for routing.",
        original_url=url,
        topic_hint="tpn",
        direction_hint="kv_transfer",
        payload={"aihot": {"id": "x"}},
    )


def test_primary_source_kind_is_conservative():
    assert primary_source_kind("https://arxiv.org/abs/2608.12345") == "arxiv"
    assert primary_source_kind("https://doi.org/10.1145/123.456") == "doi"
    assert primary_source_kind("https://github.com/LMCache/LMCache/releases/tag/v1.0") == "github"
    assert primary_source_kind("https://openreview.net/forum?id=abc123") == "openreview"
    assert primary_source_kind("https://example.com/news/interesting-paper") is None
    assert primary_source_kind("https://github.com") is None


def test_primary_paper_pdf_urls_are_deterministic():
    assert primary_pdf_url("https://arxiv.org/abs/2608.12345v2") == "https://arxiv.org/pdf/2608.12345v2.pdf"
    assert primary_pdf_url("https://openreview.net/forum?id=abc123") == "https://openreview.net/pdf?id=abc123"
    assert primary_pdf_url("https://doi.org/10.1145/123.456") is None


def test_discovery_item_promotes_only_when_original_url_is_known_primary():
    promoted = promote_discovery_primary(_item("https://arxiv.org/abs/2608.12345"))
    assert promoted.source_level == "A"
    assert promoted.discovery_only is False
    assert promoted.discovery_source == "AI HOT"
    assert promoted.payload["discovered_via"] == ["AI HOT"]
    assert promoted.payload["primary_source_resolution"]["kind"] == "arxiv"
    assert promoted.payload["pdf_url"] == "https://arxiv.org/pdf/2608.12345.pdf"

    openreview = promote_discovery_primary(_item("https://openreview.net/forum?id=abc123"))
    assert openreview.payload["pdf_url"] == "https://openreview.net/pdf?id=abc123"

    untouched = promote_discovery_primary(_item("https://example.com/news/interesting-paper"))
    assert untouched.source_level == "B"
    assert untouched.discovery_only is True
    assert "primary_source_resolution" not in untouched.payload


def test_collection_persists_promoted_primary_with_discovery_provenance(tmp_path):
    run_id = "primary-resolution-run"
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    db.create_run(run_id)
    run_dir = tmp_path / "workspace" / "runs" / run_id
    run_dir.mkdir(parents=True)

    config = type("Config", (), {"settings": {"http_timeout_seconds": 1}})()
    service = CollectionService(config, db, run_dir)
    try:
        rows = service.persist(run_id, [_item("https://arxiv.org/abs/2608.12345")])
    finally:
        service.close()

    assert len(rows) == 1
    row = db.fetchone("SELECT * FROM raw_items WHERE id=?", (rows[0]["id"],))
    assert row["source_level"] == "A"
    assert row["discovery_only"] == 0
    payload = json.loads(row["payload_json"])
    assert payload["discovered_via"] == ["AI HOT"]
    assert payload["primary_source_resolution"]["method"] == "deterministic-url-v1"
    assert payload["pdf_url"] == "https://arxiv.org/pdf/2608.12345.pdf"
