"""Local time helpers. The assistant works in the machine's local timezone."""

from __future__ import annotations

from datetime import datetime


def local(now: float) -> datetime:
    return datetime.fromtimestamp(now).astimezone()


def iso(now: float) -> str:
    return local(now).isoformat(timespec="seconds")


def day_key(now: float) -> str:
    return local(now).strftime("%Y-%m-%d")


def day_start(now: float) -> float:
    """Local midnight of the day ``now`` falls in."""

    return local(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
