from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .config import ConfigBundle
from .utils import parse_datetime


def freshness_limits(config: ConfigBundle) -> dict[str, int]:
    configured = config.scoring.get("freshness_gates", {})
    return {
        "core": int(configured.get("core_max_age_days", 3)),
        "adjacent": int(configured.get("adjacent_max_age_days", 7)),
        "absolute": int(configured.get("absolute_max_age_days", 14)),
    }


def reference_datetime(value: str | date | datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.max.time(), tzinfo=timezone.utc)
    elif value:
        parsed = parse_datetime(str(value))
        if parsed is None:
            raise ValueError(f"Invalid freshness reference date: {value}")
        if len(str(value).strip()) == 10:
            parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def published_age_days(published_at: str | None, *, reference: str | date | datetime | None = None) -> int | None:
    published = parse_datetime(published_at)
    if published is None:
        return None
    delta = reference_datetime(reference) - published
    # Future timestamps usually indicate timezone or source metadata errors.
    return max(0, delta.days)


def item_age_days(item: dict[str, Any], *, reference: str | date | datetime | None = None) -> int | None:
    published_at = item.get("source_published_at") or item.get("published_at")
    return published_age_days(str(published_at) if published_at else None, reference=reference)


def candidate_is_fresh(
    published_at: str | None,
    config: ConfigBundle,
    *,
    reference: str | date | datetime | None = None,
) -> bool:
    age = published_age_days(published_at, reference=reference)
    return age is not None and age <= freshness_limits(config)["absolute"]
