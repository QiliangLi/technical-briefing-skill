from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from ..config import ConfigBundle
from ..http import HttpClient, HttpRetryError
from ..feed import parse_feed
from ..freshness import freshness_limits
from .base import CollectedItem

LOGGER = logging.getLogger(__name__)
ARXIV_NS = "http://arxiv.org/schemas/atom"


class ArxivCollector:
    def __init__(self, config: ConfigBundle, http: HttpClient, *, sleep_fn=time.sleep):
        self.config = config
        self.http = http
        self.sleep_fn = sleep_fn
        self.source = next(s for s in config.source_list() if s.get("id") == "arxiv")
        # Set when the rate-limit circuit breaker stops the lane this run; the
        # discovery stage uses it to plan a supplemental web-search batch.
        self.circuit_open = False
        # Optional per-source transport override: export.arxiv.org sits behind
        # an edge that differentiates on client characteristics, and it has
        # answered 406 to httpx requests (notably complex OR/quoted queries)
        # that requests/curl complete with 200. Sources configured with
        # http_transport: requests get a requests-backed HttpClient.
        self.http_transport = str(self.source.get("http_transport", "httpx"))

    def collect(self) -> list[CollectedItem]:
        result: list[CollectedItem] = []
        seen_entries: set[str] = set()
        configured_max = int(self.source.get("max_results_per_direction", 20))
        rolling_max = int((self.config.settings.get("efficiency") or {}).get("arxiv_results_per_direction", 40))
        max_results = max(configured_max, rolling_max)
        request_interval = float(self.source.get("request_interval_seconds", 3.0))
        if request_interval < 0:
            raise RuntimeError("arXiv request_interval_seconds must be non-negative")
        # export.arxiv.org sits behind an edge that answers 406 both when it
        # scores request/client characteristics (generic UA, unspecified Accept
        # on complex queries, client fingerprint) and from rolling throttles
        # that only clear after a quiet window. Retry a blocked direction with
        # a growing backoff, and stop the whole lane for this run once several
        # consecutive directions stay blocked, so one run cannot keep the
        # blocklist hot for the next.
        retry_attempts = max(0, int(self.source.get("rate_limit_retry_attempts", 2)))
        backoff_seconds = float(self.source.get("rate_limit_backoff_seconds", 30.0))
        breaker_limit = max(0, int(self.source.get("rate_limit_circuit_breaker", 3)))
        consecutive_blocked = 0
        # arXiv asks for a descriptive UA with contact info and serves Atom XML;
        # the export.arxiv.org edge also scores request characteristics, so we
        # declare the exact representation we consume. Generic bot-like UAs and
        # an unspecified Accept on complex OR/quoted queries are what their
        # moderation rejects with 406 in the first place.
        request_headers = {"Accept": "application/atom+xml"}
        if self.source.get("user_agent"):
            request_headers["User-Agent"] = str(self.source["user_agent"])
        cutoff = datetime.now(timezone.utc) - timedelta(days=freshness_limits(self.config)["absolute"])
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
            response = None
            try:
                for attempt in range(retry_attempts + 1):
                    response = self.http.get(
                        self.source["endpoint"], params=params, headers=request_headers
                    )
                    if response.status_code != 406:
                        break
                    if attempt < retry_attempts:
                        self.sleep_fn(backoff_seconds * (2**attempt))
            except (HttpRetryError, httpx.HTTPError) as exc:
                LOGGER.warning("arXiv direction failed %s/%s: %s", topic.get("id"), direction.get("id"), exc)
                response = None
            if response is not None and response.status_code == 406:
                edge_headers = {
                    key: response.headers.get(key)
                    for key in ("server", "via", "x-served-by", "x-cache", "x-cache-hits", "age")
                    if response.headers.get(key)
                }
                LOGGER.warning(
                    "arXiv query still rejected with 406 after %d retries (edge headers: %s): %s",
                    retry_attempts,
                    edge_headers or "none",
                    query,
                )
            if response is None or response.status_code == 406:
                consecutive_blocked += 1
                if breaker_limit and consecutive_blocked >= breaker_limit:
                    LOGGER.warning(
                        "arXiv rate-limit circuit breaker opened after %d consecutive blocked directions; "
                        "skipping the remaining arXiv directions this run",
                        consecutive_blocked,
                    )
                    self.circuit_open = True
                    break
                continue
            consecutive_blocked = 0
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
