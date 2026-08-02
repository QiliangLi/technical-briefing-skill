from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

from .adapters.aihot import AIHotCollector
from .adapters.arxiv import ArxivCollector
from .adapters.base import CollectedItem
from .adapters.fixtures import offline_fixture_items
from .adapters.github import GitHubReleaseCollector
from .adapters.rss import RSSCollector
from .config import ConfigBundle
from .db import Database
from .http import HttpClient
from .utils import canonicalize_url, content_hash, now_iso, stable_hash, write_json

LOGGER = logging.getLogger(__name__)


class CollectionService:
    def __init__(self, config: ConfigBundle, db: Database, run_dir: Path):
        self.config = config
        self.db = db
        self.run_dir = run_dir
        self.http = HttpClient(
            timeout=float(config.settings.get("http_timeout_seconds", 25)),
            user_agent=config.settings.get("http_user_agent", "TechnicalBriefingSkill/0.1"),
        )

    def close(self) -> None:
        self.http.close()

    def collect(self, run_id: str, *, offline_fixture: bool = False) -> list[CollectedItem]:
        if offline_fixture:
            items = offline_fixture_items()
        else:
            items = []
            collectors = [
                AIHotCollector(self.config, self.db, self.http),
                ArxivCollector(self.config, self.http),
                RSSCollector(self.config, self.http),
                GitHubReleaseCollector(self.config, self.http),
            ]
            for collector in collectors:
                try:
                    batch = collector.collect()
                    LOGGER.info("%s collected %d items", collector.__class__.__name__, len(batch))
                    items.extend(batch)
                except Exception as exc:
                    LOGGER.exception("Collector failed %s: %s", collector.__class__.__name__, exc)
        persisted = self.persist(run_id, items)
        write_json(self.run_dir / "collection.json", {"run_id": run_id, "count": len(persisted), "items": persisted})
        return items

    def persist(self, run_id: str, items: Iterable[CollectedItem]) -> list[dict]:
        rows: list[dict] = []
        for item in items:
            canonical = canonicalize_url(item.original_url or item.aihot_url)
            item_id = stable_hash(run_id, item.source_id, item.external_id, canonical, item.title)
            row = {
                "id": item_id,
                "run_id": run_id,
                "source_id": item.source_id,
                "discovery_source": item.discovery_source,
                "source_level": item.source_level,
                "discovery_only": int(item.discovery_only),
                "title": item.title.strip(),
                "summary": item.summary.strip(),
                "original_url": item.original_url,
                "aihot_url": item.aihot_url,
                "canonical_url": canonical,
                "published_at": item.published_at,
                "discovered_at": item.discovered_at,
                "authors_json": json.dumps(item.authors, ensure_ascii=False),
                "external_id": item.external_id,
                "topic_hint": item.topic_hint,
                "direction_hint": item.direction_hint,
                "priority": item.priority,
                "content_hash": content_hash(item.title + "\n" + item.summary),
                "payload_json": json.dumps(item.payload, ensure_ascii=False),
                "created_at": now_iso(),
            }
            with self.db.connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO raw_items(
                        id, run_id, source_id, discovery_source, source_level, discovery_only,
                        title, summary, original_url, aihot_url, canonical_url, published_at,
                        discovered_at, authors_json, external_id, topic_hint, direction_hint,
                        priority, content_hash, payload_json, created_at
                    ) VALUES (
                        :id, :run_id, :source_id, :discovery_source, :source_level, :discovery_only,
                        :title, :summary, :original_url, :aihot_url, :canonical_url, :published_at,
                        :discovered_at, :authors_json, :external_id, :topic_hint, :direction_hint,
                        :priority, :content_hash, :payload_json, :created_at
                    )
                    """,
                    row,
                )
            rows.append(row)
        return rows
