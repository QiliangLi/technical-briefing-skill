from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


def parse_publication_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def item_publication_date(item: dict[str, Any]) -> date | None:
    """Return an item's original publication date, never its discovery date."""

    published = parse_publication_date(item.get("published_at"))
    if published:
        return published
    sources = list(item.get("sources") or [])
    sources.sort(key=lambda source: not bool(source.get("primary")))
    for source in sources:
        published = parse_publication_date(source.get("published_at"))
        if published:
            return published
    return None


def item_is_within_lookback(
    item: dict[str, Any],
    *,
    issue_end: date,
    lookback_days: int,
) -> bool:
    published = item_publication_date(item)
    if not published:
        return False
    cutoff = issue_end - timedelta(days=max(1, int(lookback_days)))
    return cutoff <= published <= issue_end
