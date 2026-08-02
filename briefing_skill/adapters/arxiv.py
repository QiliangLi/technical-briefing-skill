from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from ..config import ConfigBundle
from ..http import HttpClient, HttpRetryError
from ..feed import parse_feed
from .base import CollectedItem

LOGGER = logging.getLogger(__name__)
ARXIV_NS = "http://arxiv.org/schemas/atom"


class ArxivCollector:
    def __init__(self, config: ConfigBundle, http: HttpClient, *, sleep_fn=time.sleep):
        self.config = config
        self.http = http
        self.sleep_fn = sleep_fn
        self.source = next(s for s in config.source_list() if s.get("id") == "arxiv")

    def collect(self) -> list[CollectedItem]:
        result: list[CollectedItem] = []
        seen_entries: set[str] = set()
        max_results = int(self.source.get("max_results_per_direction", 20))
        request_interval = float(self.source.get("request_interval_seconds", 3.0))
        if request_interval < 0:
            raise RuntimeError("arXiv request_interval_seconds must be non-negative")
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        request_started = False
        for topic, direction in self.config.iter_directions():
            terms = [str(term) for term in direction.get("include_terms", []) if len(str(term)) >= 3][:4]
            if not terms:
                continue
            term_query = " OR ".join(f'all:"{term.replace(chr(34), "")}"' for term in terms)
            categories = self.source.get("categories", [])
            category_query = " OR ".join(f"cat:{category}" for category in categories)
            query = direction.get("arxiv_query") or term_query
            search_query = f"({category_query}) AND ({query})" if category_query else f"({query})"
            params = {
                "search_query": search_query,
                "start": 0,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            if request_started and request_interval:
                self.sleep_fn(request_interval)
            request_started = True
            try:
                response = self.http.get(self.source["endpoint"], params=params)
            except (HttpRetryError, httpx.HTTPError) as exc:
                LOGGER.warning("arXiv direction failed %s/%s: %s", topic.get("id"), direction.get("id"), exc)
                continue
            if response.status_code >= 400:
                LOGGER.warning("arXiv query failed %s: %s", query, response.status_code)
                continue
            entries = parse_feed(response.content)
            for entry in entries:
                published = entry.published
                try:
                    from ..utils import parse_datetime
                    dt = parse_datetime(published)
                    if dt and dt < cutoff:
                        continue
                except Exception:
                    pass
                entry_key = (entry.id or entry.link or " ".join(entry.title.lower().split())).strip()
                if entry_key in seen_entries:
                    continue
                seen_entries.add(entry_key)
                pdf_url = ""
                for link in entry.links:
                    if link.get("type") == "application/pdf" or link.get("title") == "pdf":
                        pdf_url = link.get("href", "")
                        break
                authors = entry.authors
                result.append(
                    CollectedItem(
                        source_id="arxiv",
                        discovery_source="arXiv",
                        source_level="A",
                        discovery_only=False,
                        title=" ".join(entry.title.split()),
                        summary=" ".join(entry.summary.split()),
                        original_url=entry.link,
                        published_at=published,
                        authors=authors,
                        external_id=entry.id,
                        topic_hint=topic["id"],
                        direction_hint=direction["id"],
                        priority=18.0,
                        payload={"pdf_url": pdf_url, "tags": entry.tags},
                    )
                )
        return result
