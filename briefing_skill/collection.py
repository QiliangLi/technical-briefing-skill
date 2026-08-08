from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable

from .adapters.aihot import AIHotCollector
from .adapters.arxiv import ArxivCollector
from .adapters.base import CollectedItem
from .adapters.fixtures import offline_fixture_items
from .adapters.follow_builders import FollowBuildersCollector
from .adapters.github import GitHubReleaseCollector
from .adapters.rss import RSSCollector
from .adapters.yeekal import YeeKalDailyCollector
from .config import ConfigBundle
from .db import Database
from .http import HttpClient
from .primary_source import promote_discovery_primary
from .utils import canonicalize_url, content_hash, now_iso, source_identity_key, stable_hash, write_json

LOGGER = logging.getLogger(__name__)
MAX_COLLECTION_WORKERS = 6


@dataclass
class CollectorRun:
    name: str
    items: list[CollectedItem]
    duration_seconds: float
    error: str | None = None

    def telemetry(self) -> dict[str, Any]:
        return {
            "collector": self.name,
            "count": len(self.items),
            "duration_seconds": round(self.duration_seconds, 3),
            "status": "ERROR" if self.error else "OK",
            "error": self.error,
        }


def bounded_collection_workers(requested: int, collector_count: int) -> int:
    """Bound collection concurrency without changing any collector-internal throttling."""

    if collector_count <= 0:
        return 1
    return max(1, min(int(requested), int(collector_count), MAX_COLLECTION_WORKERS))


def run_collectors_bounded(collectors: list[Any], *, max_workers: int) -> list[CollectorRun]:
    """Run independent collectors concurrently but return results in declared order.

    Each collector keeps its own internal request ordering/rate limits. In particular,
    ArxivCollector still serializes direction queries and sleeps between requests. The
    outer pool only overlaps independent collector lanes. Returning in declaration
    order keeps persistence and tie behaviour deterministic even when a later lane
    finishes first.
    """

    if not collectors:
        return []
    workers = bounded_collection_workers(max_workers, len(collectors))

    def run_one(collector: Any) -> CollectorRun:
        started = perf_counter()
        name = collector.__class__.__name__
        try:
            batch = list(collector.collect())
            duration = perf_counter() - started
            LOGGER.info("%s collected %d items in %.3fs", name, len(batch), duration)
            return CollectorRun(name=name, items=batch, duration_seconds=duration)
        except Exception as exc:
            duration = perf_counter() - started
            LOGGER.exception("Collector failed %s: %s", name, exc)
            return CollectorRun(
                name=name,
                items=[],
                duration_seconds=duration,
                error=f"{type(exc).__name__}: {exc}",
            )

    if workers == 1:
        return [run_one(collector) for collector in collectors]

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="briefing-collect") as executor:
        # Submit in fixed source order. We intentionally consume future results in the
        # same order rather than completion order so downstream persistence is stable.
        futures = [executor.submit(run_one, collector) for collector in collectors]
        return [future.result() for future in futures]


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
        started = perf_counter()
        collector_telemetry: list[dict[str, Any]] = []
        workers = 1
        if offline_fixture:
            items = offline_fixture_items()
            collector_telemetry.append(
                {
                    "collector": "OfflineFixture",
                    "count": len(items),
                    "duration_seconds": 0.0,
                    "status": "OK",
                    "error": None,
                }
            )
        else:
            collectors = [
                AIHotCollector(self.config, self.db, self.http),
                ArxivCollector(self.config, self.http),
                RSSCollector(self.config, self.http),
                GitHubReleaseCollector(self.config, self.http),
                FollowBuildersCollector(self.config, self.db, self.http, self.run_dir),
                YeeKalDailyCollector(self.config, self.db, self.http),
            ]
            policy = dict(self.config.settings.get("efficiency") or {})
            requested_workers = int(policy.get("collection_max_workers", 3))
            workers = bounded_collection_workers(requested_workers, len(collectors))
            runs = run_collectors_bounded(collectors, max_workers=workers)
            items = []
            for run in runs:
                items.extend(run.items)
                collector_telemetry.append(run.telemetry())

        persisted = self.persist(run_id, items)
        wall_seconds = perf_counter() - started
        write_json(
            self.run_dir / "collection.json",
            {
                "run_id": run_id,
                "count": len(persisted),
                "items": persisted,
                "execution": {
                    "mode": "offline_fixture" if offline_fixture else ("concurrent" if workers > 1 else "serial"),
                    "max_workers": workers,
                    "wall_seconds": round(wall_seconds, 3),
                    "collectors": collector_telemetry,
                },
            },
        )
        return items

    def persist(self, run_id: str, items: Iterable[CollectedItem]) -> list[dict]:
        rows: list[dict] = []
        for raw_item in items:
            # Discovery feeds often already expose a concrete original URL. Promote
            # only deterministic primary identities (arXiv/DOI/GitHub/OpenReview)
            # before candidate matching; generic blogs/news remain discovery-only.
            item = promote_discovery_primary(raw_item)
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
                "identity_key": source_identity_key(canonical, item.external_id),
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
                        priority, content_hash, payload_json, created_at, identity_key
                    ) VALUES (
                        :id, :run_id, :source_id, :discovery_source, :source_level, :discovery_only,
                        :title, :summary, :original_url, :aihot_url, :canonical_url, :published_at,
                        :discovered_at, :authors_json, :external_id, :topic_hint, :direction_hint,
                        :priority, :content_hash, :payload_json, :created_at, :identity_key
                    )
                    """,
                    row,
                )
            rows.append(row)
        return rows
