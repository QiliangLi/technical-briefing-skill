from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

from ..config import ConfigBundle
from ..db import Database
from ..http import HttpClient
from ..utils import canonicalize_url, unique_preserve
from .base import CollectedItem

LOGGER = logging.getLogger(__name__)


class AIHotCollector:
    """AI HOT v1 collector.

    AI HOT receives elevated query priority for AI/Agent/KVCache topics, but all
    returned records remain discovery items until links.original is resolved.
    """

    def __init__(self, config: ConfigBundle, db: Database, http: HttpClient):
        self.config = config
        self.db = db
        self.http = http
        self.source = next(s for s in config.source_list() if s.get("id") == "aihot")

    def collect(self) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        base_limit = int(self.source.get("base_selected_limit", 50))
        items.extend(self._request({"mode": "selected", "window": "24h", "by": "timeline", "limit": base_limit}, topic_hint=""))

        query_limits = self.source.get("query_limits", {})
        for topic in self.config.topic_list():
            priority_name = str(topic.get("aihot_priority", "low"))
            limit = int(query_limits.get(priority_name, 0))
            if limit <= 0:
                continue
            boost = float(self.source.get("topic_boosts", {}).get(topic["id"], 1.0))
            queries: list[tuple[str, str]] = []
            for direction in topic.get("directions", []):
                for query in direction.get("aihot_queries", [])[:4]:
                    queries.append((direction["id"], query))
            for direction_id, query in queries:
                request_items = self._request(
                    {"mode": "all", "window": self.source.get("window", "7d"), "by": "timeline", "limit": limit, "q": query},
                    topic_hint=topic["id"],
                    direction_hint=direction_id,
                )
                for item in request_items:
                    item.priority += 20.0 * boost
                items.extend(request_items)
                # AI HOT public pool excludes arXiv unless paper is requested.
                if any(term in query.lower() for term in ("paper", "agent", "kv cache", "prefill", "code graph")):
                    paper_items = self._request(
                        {"mode": "all", "category": "paper", "window": self.source.get("window", "7d"), "by": "timeline", "limit": min(limit, 30), "q": query},
                        topic_hint=topic["id"],
                        direction_hint=direction_id,
                    )
                    for item in paper_items:
                        item.priority += 22.0 * boost
                    items.extend(paper_items)
        return self._deduplicate(items)

    def _request(self, params: dict[str, Any], *, topic_hint: str, direction_hint: str = "") -> list[CollectedItem]:
        endpoint = self.source["endpoint"]
        full_url = f"{endpoint}?{urlencode(params)}"
        state_key = f"aihot:{full_url}"
        state = self.db.get_source_state(state_key) or {}
        headers = {"If-None-Match": state["etag"]} if state.get("etag") else None
        response = self.http.get(endpoint, params=params, headers=headers)
        if response.status_code == 304:
            LOGGER.debug("AI HOT unchanged: %s", full_url)
            return []
        response.raise_for_status()
        payload = response.json()
        self.db.upsert_source_state(state_key, etag=response.headers.get("ETag"), payload={"params": params})
        raw_items = payload.get("items") or payload.get("data") or []
        result: list[CollectedItem] = []
        for raw in raw_items:
            links = raw.get("links") or {}
            source = raw.get("source") or {}
            original = links.get("original") or raw.get("url") or ""
            aihot_url = links.get("aihot") or raw.get("permalink") or ""
            summary = raw.get("summary") or raw.get("description") or raw.get("reason") or ""
            source_name = source.get("name") if isinstance(source, dict) else str(source or "AI HOT")
            result.append(
                CollectedItem(
                    source_id="aihot",
                    discovery_source="AI HOT",
                    source_level="B",
                    discovery_only=True,
                    title=raw.get("title") or raw.get("originalTitle") or "Untitled",
                    summary=summary,
                    original_url=original,
                    aihot_url=aihot_url,
                    published_at=raw.get("publishedAt") or raw.get("published_at"),
                    discovered_at=raw.get("discoveredAt") or raw.get("discovered_at"),
                    authors=raw.get("authors") or [],
                    external_id=str(raw.get("publicId") or raw.get("id") or ""),
                    topic_hint=topic_hint,
                    direction_hint=direction_hint,
                    priority=15.0,
                    payload={"aihot": raw, "upstream_source": source_name},
                )
            )
        return result

    @staticmethod
    def _deduplicate(items: list[CollectedItem]) -> list[CollectedItem]:
        best: dict[str, CollectedItem] = {}
        for item in items:
            key = canonicalize_url(item.original_url) or item.external_id or item.title.lower()
            existing = best.get(key)
            if not existing or item.priority > existing.priority:
                best[key] = item
            elif existing:
                existing.topic_hint = existing.topic_hint or item.topic_hint
                existing.direction_hint = existing.direction_hint or item.direction_hint
                existing.payload["matched_topics"] = unique_preserve(
                    [*(existing.payload.get("matched_topics") or []), item.topic_hint]
                )
        return list(best.values())
