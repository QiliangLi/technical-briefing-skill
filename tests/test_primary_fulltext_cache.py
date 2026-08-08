from __future__ import annotations

import json
from types import SimpleNamespace

from briefing_skill.db import Database
from briefing_skill.fulltext import FulltextService
from briefing_skill.primary_fulltext_cache import install_primary_fulltext_cache


def _restore(obj, name: str, value, existed: bool) -> None:
    if existed:
        setattr(obj, name, value)
    elif hasattr(obj, name):
        delattr(obj, name)


def test_promoted_versioned_arxiv_reuses_raw_text_across_discovery_runs(tmp_path):
    snapshots = {
        "fetch": (FulltextService._fetch, hasattr(FulltextService, "_fetch")),
        "flag": (
            getattr(FulltextService, "_primary_fulltext_cache_installed", None),
            hasattr(FulltextService, "_primary_fulltext_cache_installed"),
        ),
    }
    calls = {"n": 0}

    def fake_fetch(self, url: str, raw: dict):
        calls["n"] += 1
        return "# Abstract\nimmutable paper body", "text/plain"

    try:
        FulltextService._fetch = fake_fetch
        if hasattr(FulltextService, "_primary_fulltext_cache_installed"):
            delattr(FulltextService, "_primary_fulltext_cache_installed")
        install_primary_fulltext_cache()

        config = SimpleNamespace(settings={"http_timeout_seconds": 1, "max_fulltext_chars": 140000})
        db = Database(tmp_path / "workspace" / "briefing.sqlite")
        db.init()
        raw = {
            "source_id": "aihot",
            "source_level": "A",
            "discovery_only": 0,
            "identity_key": "arxiv:2608.12345",
            "external_id": "discovery-record",
            "original_url": "https://arxiv.org/abs/2608.12345v2",
            "canonical_url": "https://arxiv.org/abs/2608.12345v2",
            "payload_json": json.dumps(
                {
                    "pdf_url": "https://arxiv.org/pdf/2608.12345v2.pdf",
                    "primary_source_resolution": {
                        "kind": "arxiv",
                        "url": "https://arxiv.org/abs/2608.12345v2",
                    },
                }
            ),
        }

        first = FulltextService(config, db, tmp_path / "workspace" / "runs" / "r1")
        second = FulltextService(config, db, tmp_path / "workspace" / "runs" / "r2")
        try:
            text1, media1 = first._fetch(raw["original_url"], raw)
            text2, media2 = second._fetch(raw["original_url"], raw)
        finally:
            first.close()
            second.close()

        assert text1 == text2 == "# Abstract\nimmutable paper body"
        assert media1 == media2 == "text/plain"
        assert calls["n"] == 1
        assert second._raw_fulltext_cache_hit is True
        assert str(second._raw_fulltext_cache_key).startswith("primary:")
    finally:
        _restore(FulltextService, "_fetch", *snapshots["fetch"])
        _restore(FulltextService, "_primary_fulltext_cache_installed", *snapshots["flag"])
