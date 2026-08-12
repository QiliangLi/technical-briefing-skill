from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def briefing_timezone(config) -> ZoneInfo:
    name = str(config.settings.get("timezone", "Asia/Shanghai"))
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(f"Invalid timezone in config/settings.yaml: {name}") from exc


def briefing_now(config, now: datetime | None = None) -> datetime:
    """Return the briefing-local wall clock for business decisions.

    UTC remains appropriate for persisted timestamps such as created_at/sent_at; this
    helper is only for reader-facing/report/search dates whose calendar day matters.
    """

    tz = briefing_timezone(config)
    return now.astimezone(tz) if now is not None else datetime.now(tz)


def briefing_date(config, now: datetime | None = None) -> date:
    return briefing_now(config, now).date()
