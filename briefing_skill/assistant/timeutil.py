"""Local time helpers. The assistant works in the machine's local timezone."""

from __future__ import annotations

from datetime import datetime


def local(now: float) -> datetime:
    return datetime.fromtimestamp(now).astimezone()


def iso(now: float) -> str:
    return local(now).isoformat(timespec="seconds")


def day_key(now: float) -> str:
    return local(now).strftime("%Y-%m-%d")
