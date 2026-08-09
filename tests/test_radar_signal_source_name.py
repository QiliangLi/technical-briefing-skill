"""Regression test: radar signal source_name must not leak internal discovery
brands (AI HOT / YeeKal / Follow Builders). The signal links to the original
source, so the reader-facing name is the original hostname (arXiv/GitHub/domain).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from briefing_skill.db import Database
from briefing_skill.radar_signal_synthesis import _signal_groups


def _stub_service(tmp_path: Path, discovery_source: str) -> SimpleNamespace:
    db = Database(tmp_path / "t.db")
    db.init()
    db.execute(
        "INSERT INTO raw_items(id,run_id,source_id,discovery_source,source_level,title,"
        "original_url,canonical_url,published_at,payload_json,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("r1", "run1", "src", discovery_source, "A", "Some paper",
         "https://arxiv.org/abs/2608.99999", "https://arxiv.org/abs/2608.99999",
         "2026-08-08T00:00:00Z", "{}", "2026-08-08T00:00:00Z"),
    )

    def _normalise_reference(text: str) -> str:
        return text.strip().lower()

    return SimpleNamespace(db=db, root=tmp_path, _normalise_reference=_normalise_reference)


def test_radar_signal_uses_hostname_not_internal_discovery_brand(tmp_path):
    svc = _stub_service(tmp_path, "AI HOT")
    issue_data = {"synthesis": {"radar_signals": [
        {"category": "Agent生态", "signal": "A concrete technical change described here.",
         "summary": "What changed and why it matters for the reader, with enough detail.",
         "source_urls": ["https://arxiv.org/abs/2608.99999"]},
    ]}}
    groups = _signal_groups(svc, issue_id=None, issue_data=issue_data)
    assert groups, "expected one signal group"
    name = groups[0]["items"][0]["source_name"]
    assert name == "arXiv", f"internal brand leaked: {name!r}"
    assert "ai hot" not in name.lower()
