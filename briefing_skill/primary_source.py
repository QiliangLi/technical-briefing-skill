from __future__ import annotations

from dataclasses import replace
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .adapters.base import CollectedItem
from .utils import canonicalize_url, source_identity_key


PRIMARY_RESOLUTION_METHOD = "deterministic-url-v1"


def primary_source_kind(url: str | None) -> str | None:
    """Return a conservative primary-source kind for URLs we can identify deterministically.

    This intentionally recognises only strong source identities. Generic company blogs
    and news sites stay discovery sources until a future resolver/allowlist verifies them.
    """

    canonical = canonicalize_url(url)
    if not canonical:
        return None
    try:
        parts = urlsplit(canonical)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    path = (parts.path or "").strip("/")

    identity = source_identity_key(canonical)
    if identity.startswith("arxiv:"):
        return "arxiv"
    if identity.startswith("doi:"):
        return "doi"
    if identity.startswith(("github:", "github-release:", "github-commit:")):
        return "github"

    if host in {"openreview.net", "www.openreview.net"}:
        query = parse_qs(parts.query)
        if path in {"forum", "pdf", "attachment"} and query.get("id"):
            return "openreview"

    return None


def promote_discovery_primary(item: CollectedItem) -> CollectedItem:
    """Promote discovery records when their original URL is itself a known primary source.

    The discovery provenance is preserved in payload. Only credibility/routing changes;
    title and summary are left untouched until the normal full-text stage fetches the
    actual primary artifact.
    """

    if str(item.source_level or "").upper() == "A" and not item.discovery_only:
        return item
    kind = primary_source_kind(item.original_url)
    if not kind:
        return item

    payload: dict[str, Any] = dict(item.payload or {})
    history = list(payload.get("discovered_via") or [])
    if item.discovery_source and item.discovery_source not in history:
        history.append(item.discovery_source)
    payload["discovered_via"] = history
    payload["primary_source_resolution"] = {
        "method": PRIMARY_RESOLUTION_METHOD,
        "kind": kind,
        "url": canonicalize_url(item.original_url),
    }
    return replace(
        item,
        source_level="A",
        discovery_only=False,
        payload=payload,
    )
