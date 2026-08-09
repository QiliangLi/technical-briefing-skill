from __future__ import annotations

from datetime import date

from briefing_skill.item_freshness import (
    item_is_within_lookback,
    item_publication_date,
)


def test_item_publication_date_prefers_original_item_date():
    item = {
        "published_at": "2026-07-16T09:00:00Z",
        "sources": [{"published_at": "2026-07-17", "primary": True}],
    }

    assert item_publication_date(item) == date(2026, 7, 16)


def test_item_freshness_rejects_old_future_and_missing_dates():
    issue_end = date(2026, 8, 9)

    assert item_is_within_lookback(
        {"published_at": "2026-06-10"},
        issue_end=issue_end,
        lookback_days=60,
    )
    assert not item_is_within_lookback(
        {"published_at": "2025-07-09"},
        issue_end=issue_end,
        lookback_days=60,
    )
    assert not item_is_within_lookback(
        {"published_at": "2026-08-10"},
        issue_end=issue_end,
        lookback_days=60,
    )
    assert not item_is_within_lookback(
        {}, issue_end=issue_end, lookback_days=60
    )
