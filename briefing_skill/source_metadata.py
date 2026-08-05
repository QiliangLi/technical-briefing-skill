from __future__ import annotations

import json
from typing import Any, Iterable

from bs4 import BeautifulSoup

from .utils import parse_datetime


def _json_ld_dates(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        date = value.get("datePublished")
        if isinstance(date, str):
            yield date
        for nested in value.values():
            yield from _json_ld_dates(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _json_ld_dates(nested)


def _normalise_date(value: str | None) -> str | None:
    parsed = parse_datetime(value)
    return parsed.isoformat() if parsed else None


def extract_published_at(html: str, url: str) -> str | None:
    """Extract an original publication timestamp without using discovery time."""
    soup = BeautifulSoup(html or "", "html.parser")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or script.get_text("", strip=True))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        for value in _json_ld_dates(payload):
            if normalised := _normalise_date(value):
                return normalised

    meta_candidates = (
        ("property", "article:published_time"),
        ("name", "date"),
        ("name", "datePublished"),
        ("name", "datepublished"),
        ("name", "publish-date"),
        ("itemprop", "datePublished"),
    )
    for attribute, expected in meta_candidates:
        tag = soup.find(
            "meta",
            attrs={attribute: lambda value: isinstance(value, str) and value.lower() == expected.lower()},
        )
        if tag and (normalised := _normalise_date(tag.get("content"))):
            return normalised

    for time_tag in soup.find_all("time", attrs={"datetime": True}):
        if normalised := _normalise_date(time_tag.get("datetime")):
            return normalised
    return None
