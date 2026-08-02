from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ..config import ConfigBundle
from ..http import HttpClient
from ..feed import parse_feed
from ..utils import parse_datetime
from .base import CollectedItem

LOGGER = logging.getLogger(__name__)


class RSSCollector:
    def __init__(self, config: ConfigBundle, http: HttpClient):
        self.config = config
        self.http = http

    def collect(self) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=10)
        for source in self.config.source_list():
            if not source.get("enabled") or source.get("type") != "rss":
                continue
            try:
                response = self.http.get(source["url"])
                response.raise_for_status()
                entries = parse_feed(response.content)
            except Exception as exc:
                LOGGER.warning("RSS failed %s: %s", source.get("name"), exc)
                continue
            for entry in entries:
                published = entry.published or entry.updated
                dt = parse_datetime(published)
                if dt and dt < cutoff:
                    continue
                summary = entry.summary
                items.append(
                    CollectedItem(
                        source_id=source["id"],
                        discovery_source=source["name"],
                        source_level=source.get("source_level", "B"),
                        discovery_only=bool(source.get("discovery_only", False)),
                        title=" ".join((entry.title or "Untitled").split()),
                        summary=summary,
                        original_url=entry.link,
                        published_at=published,
                        authors=[entry.author] if entry.author else [],
                        external_id=entry.id,
                        priority=12.0,
                        payload={"topic_allowlist": source.get("topic_allowlist", [])},
                    )
                )
        return items
