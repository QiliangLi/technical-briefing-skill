"""Regression test for the offline-replay fulltext guard.

The guard lets an offline replay reuse cached fulltext without any network
access: on a cache MISS it must raise (caught upstream -> fetch_status=FALLBACK
-> candidate deferred) instead of calling http.get.
"""
from __future__ import annotations

import pytest

from briefing_skill.fulltext import FulltextService


def _bare_service() -> FulltextService:
    # Construct without running __init__ (no config/db/http needed to test _fetch gating).
    return FulltextService.__new__(FulltextService)


def test_offline_guard_raises_when_enabled(monkeypatch):
    monkeypatch.setenv("BRIEFING_OFFLINE_REPLAY", "1")
    svc = _bare_service()
    with pytest.raises(RuntimeError, match="offline replay"):
        svc._fetch("https://example.com/paper", {"payload_json": "{}"})


def test_offline_guard_inactive_by_default(monkeypatch):
    monkeypatch.delenv("BRIEFING_OFFLINE_REPLAY", raising=False)
    svc = _bare_service()
    # Env off -> the offline RuntimeError must NOT fire; the normal empty-url
    # validation path runs instead.
    with pytest.raises(ValueError, match="No original URL"):
        svc._fetch("", {"payload_json": "{}"})
