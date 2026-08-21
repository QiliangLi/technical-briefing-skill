from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ..config import ConfigBundle
from ..db import Database
from ..http import HttpClient
from ..utils import canonicalize_url, content_hash, now_iso, read_json, stable_hash, unique_preserve, write_json
from .base import CollectedItem

LOGGER = logging.getLogger(__name__)

# Bump when lane coverage, freeze layout, or ledger fields change so a stale
# freeze file from an older connector is refetched instead of replayed.
AIHOT_CONNECTOR_VERSION = 2
AIHOT_PROVIDER = "aihot"

# Upstream item/story identities are only taken from officially returned links.
AIHOT_ITEM_ID_RE = re.compile(r"/items/([A-Za-z0-9_-]+)")
AIHOT_STORY_ID_RE = re.compile(r"/story/([A-Za-z0-9_-]+)")


def upstream_item_id(raw: dict[str, Any]) -> str:
    direct = str(raw.get("publicId") or raw.get("id") or "").strip()
    if direct:
        return direct
    aihot_url = (raw.get("links") or {}).get("aihot") if isinstance(raw.get("links"), dict) else None
    match = AIHOT_ITEM_ID_RE.search(str(aihot_url or ""))
    return match.group(1) if match else ""


def upstream_story_id(raw: dict[str, Any]) -> str:
    links = raw.get("links") if isinstance(raw.get("links"), dict) else {}
    for value in (links.get("story"), links.get("aihot")):
        match = AIHOT_STORY_ID_RE.search(str(value or ""))
        if match:
            return match.group(1)
    return ""


class AIHotCollector:
    """AI HOT v1 multi-lane collector.

    Lanes: ``selected`` (24h editor picks), ``all`` (per-direction keyword
    queries), ``paper`` (all + category=paper), ``daily`` (daily report items)
    and ``hot`` (hot-topic ranks). The hot lane never publishes cards by
    itself; it only adds rank/story identity to items seen in other lanes.

    Every run freezes the fetched responses under the run directory and, when
    the run is collected again (resume), replays the frozen payloads instead
    of re-requesting the upstream. A 304 response replays the cached body from
    ``source_state`` so unchanged content is still materialized into the new
    run. All lane observations are recorded in ``radar_upstream_records`` for
    internal traceability; nothing upstream is published.
    """

    def __init__(
        self,
        config: ConfigBundle,
        db: Database,
        http: HttpClient,
        *,
        run_id: str = "",
        run_dir: Path | None = None,
    ):
        self.config = config
        self.db = db
        self.http = http
        self.source = next(s for s in config.source_list() if s.get("id") == "aihot")
        self.run_id = run_id
        self.run_dir = run_dir
        self.endpoint = self.source["endpoint"]
        self.api_base = str(self.source.get("api_base") or re.sub(r"/items$", "", self.endpoint))
        self.freeze_path = run_dir / "source-cache" / "aihot" / "freeze.json" if run_dir else None
        self._frozen_lanes: dict[str, dict[str, Any]] | None = None
        self._lane_fetches: dict[str, dict[str, Any]] = {}
        self._upstream_records: list[dict[str, Any]] = []

    def collect(self) -> list[CollectedItem]:
        self._load_frozen()
        items: list[CollectedItem] = []

        base_limit = int(self.source.get("base_selected_limit", 50))
        selected_params = {"mode": "selected", "window": "24h", "by": "timeline", "limit": base_limit}
        items.extend(
            self._collect_items_lane(
                self._fetch_lane("selected", self.endpoint, selected_params),
                lane="selected",
                topic_hint="",
            )
        )

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
                lane_key = f"all:{topic['id']}:{direction_id}:{query}"
                request_items = self._collect_items_lane(
                    self._fetch_lane(
                        lane_key,
                        self.endpoint,
                        {"mode": "all", "window": self.source.get("window", "7d"), "by": "timeline", "limit": limit, "q": query},
                    ),
                    lane="all",
                    topic_hint=topic["id"],
                    direction_hint=direction_id,
                )
                for item in request_items:
                    item.priority += 20.0 * boost
                items.extend(request_items)
                # AI HOT public pool excludes arXiv unless paper is requested.
                if any(term in query.lower() for term in ("paper", "agent", "kv cache", "prefill", "code graph")):
                    paper_items = self._collect_items_lane(
                        self._fetch_lane(
                            f"paper:{topic['id']}:{direction_id}:{query}",
                            self.endpoint,
                            {
                                "mode": "all",
                                "category": "paper",
                                "window": self.source.get("window", "7d"),
                                "by": "timeline",
                                "limit": min(limit, 30),
                                "q": query,
                            },
                        ),
                        lane="paper",
                        topic_hint=topic["id"],
                        direction_hint=direction_id,
                    )
                    for item in paper_items:
                        item.priority += 22.0 * boost
                    items.extend(paper_items)

        items.extend(self._collect_daily_lane())
        hot_entries = self._collect_hot_lane()

        items = self._deduplicate(items)
        self._apply_hot_matches(items, hot_entries)
        self._write_ledger()
        self._write_freeze()
        return items

    # ------------------------------------------------------------------ lanes

    def _collect_daily_lane(self) -> list[CollectedItem]:
        if not self.source.get("daily_enabled", True):
            return []
        payload = self._fetch_lane("daily", f"{self.api_base}/dailies/latest", {})
        report = payload.get("report") if isinstance(payload.get("report"), dict) else payload
        daily_date = str(report.get("date") or "")
        items: list[CollectedItem] = []
        for section in report.get("sections") or []:
            label = str(section.get("label") or section.get("title") or "").strip()
            for raw in section.get("items") or []:
                entry = dict(raw)
                if label:
                    entry["daily_section"] = label
                if daily_date:
                    entry.setdefault("daily_date", daily_date)
                    # Daily entries carry no per-item publishedAt; the report
                    # window date is the best available publication date.
                    entry.setdefault("publishedAt", daily_date)
                self._record_upstream(entry, lane="daily")
                # A daily entry needs a complete title/summary/original triple
                # before it may become a radar candidate; partial entries stay
                # internal-only observations.
                if not (str(entry.get("title") or "").strip() and str(entry.get("summary") or "").strip()):
                    continue
                links = entry.get("links") or {}
                original = links.get("original") or entry.get("url") or ""
                if not original:
                    continue
                item = self._item_from_raw(
                    entry,
                    lane="daily",
                    topic_hint="",
                    extra_payload={"aihot_daily_section": label, "aihot_daily_date": daily_date},
                )
                if item is not None:
                    items.append(item)
        return items

    def _collect_hot_lane(self) -> list[dict[str, Any]]:
        if not self.source.get("hot_topics_enabled", True):
            return []
        payload = self._fetch_lane("hot", f"{self.api_base}/hot-topics", {})
        entries: list[dict[str, Any]] = []
        for raw in payload.get("items") or payload.get("data") or []:
            self._record_upstream(raw, lane="hot")
            links = raw.get("links") or {}
            original = str(links.get("original") or raw.get("url") or "")
            entry = {
                "item_id": upstream_item_id(raw),
                "canonical_original": canonicalize_url(original),
                "story_id": upstream_story_id(raw),
                "rank": raw.get("rank"),
                "source_count": raw.get("sourceCount"),
                "signal_count": raw.get("signalCount"),
            }
            if entry["item_id"] or entry["canonical_original"]:
                entries.append(entry)
        return entries

    def _apply_hot_matches(self, items: list[CollectedItem], hot_entries: list[dict[str, Any]]) -> None:
        """Boost items already seen in other lanes; unmatched hot topics stay internal."""
        by_item_id: dict[str, CollectedItem] = {}
        by_canonical: dict[str, CollectedItem] = {}
        for item in items:
            if item.external_id:
                by_item_id.setdefault(item.external_id, item)
            if item.payload.get("aihot_canonical_original"):
                by_canonical.setdefault(item.payload["aihot_canonical_original"], item)
        for entry in hot_entries:
            target = by_item_id.get(entry["item_id"] or "") or by_canonical.get(entry["canonical_original"])
            if target is None:
                continue
            lanes = target.payload.setdefault("aihot_lanes", [target.payload.get("aihot_lane")])
            if "hot" not in lanes:
                lanes.append("hot")
            target.payload["aihot_hot_rank"] = entry["rank"]
            if entry["story_id"]:
                target.payload["aihot_story_id"] = target.payload.get("aihot_story_id") or entry["story_id"]

    # ------------------------------------------------------------------ fetch

    def _fetch_lane(self, lane_key: str, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._frozen_lanes is not None:
            frozen = self._frozen_lanes.get(lane_key)
            if frozen is not None:
                self._lane_fetches[lane_key] = dict(frozen, from_cache=True)
                return frozen.get("payload") or {}
        full_url = f"{url}?{urlencode(params)}" if params else url
        state_key = f"aihot:{full_url}"
        state = self.db.get_source_state(state_key) or {}
        headers = {"If-None-Match": state["etag"]} if state.get("etag") else None
        response = self.http.get(url, params=params or None, headers=headers)
        from_cache = False
        if response.status_code == 304:
            body = (state.get("payload") or {}).get("body")
            if body is None:
                # Legacy cache rows only stored the ETag. A 304 without a
                # cached body must never surface as "no content this run";
                # force a full fetch instead.
                LOGGER.warning("AI HOT 304 without cached body, refetching: %s", full_url)
                response = self.http.get(url, params=params or None)
                response.raise_for_status()
                payload = response.json()
            else:
                LOGGER.debug("AI HOT unchanged, replaying cached body: %s", full_url)
                payload = body
                from_cache = True
        else:
            response.raise_for_status()
            payload = response.json()
        if not from_cache:
            self.db.upsert_source_state(
                state_key,
                etag=response.headers.get("ETag"),
                payload={"params": params, "body": payload},
            )
        self._lane_fetches[lane_key] = {
            "url": full_url,
            "etag": response.headers.get("ETag") if not from_cache else state.get("etag"),
            "retrieved_at": now_iso(),
            "from_cache": from_cache,
            "payload": payload,
        }
        return payload

    def _collect_items_lane(
        self,
        payload: dict[str, Any],
        *,
        lane: str,
        topic_hint: str,
        direction_hint: str = "",
    ) -> list[CollectedItem]:
        result: list[CollectedItem] = []
        for raw in payload.get("items") or payload.get("data") or []:
            self._record_upstream(raw, lane=lane)
            item = self._item_from_raw(raw, lane=lane, topic_hint=topic_hint, direction_hint=direction_hint)
            if item is not None:
                result.append(item)
        return result

    def _item_from_raw(
        self,
        raw: dict[str, Any],
        *,
        lane: str,
        topic_hint: str,
        direction_hint: str = "",
        extra_payload: dict[str, Any] | None = None,
    ) -> CollectedItem | None:
        links = raw.get("links") or {}
        source = raw.get("source") or {}
        original = links.get("original") or raw.get("url") or ""
        aihot_url = links.get("aihot") or raw.get("permalink") or ""
        if not original and not aihot_url:
            return None
        summary = raw.get("summary") or raw.get("description") or raw.get("reason") or ""
        source_name = source.get("name") if isinstance(source, dict) else str(source or "AI HOT")
        payload: dict[str, Any] = {
            "aihot": raw,
            "upstream_source": source_name,
            "aihot_lane": lane,
            "aihot_lanes": [lane],
            "aihot_canonical_original": canonicalize_url(original),
        }
        if raw.get("category") is not None:
            payload["aihot_category"] = raw.get("category")
        if raw.get("score") is not None:
            payload["aihot_score"] = raw.get("score")
        story_id = upstream_story_id(raw)
        if story_id:
            payload["aihot_story_id"] = story_id
        payload.update(extra_payload or {})
        return CollectedItem(
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
            external_id=upstream_item_id(raw),
            topic_hint=topic_hint,
            direction_hint=direction_hint,
            priority=15.0,
            payload=payload,
        )

    # ------------------------------------------------------- freeze and ledger

    def _load_frozen(self) -> None:
        if self.freeze_path is None or not self.freeze_path.exists():
            return
        frozen = read_json(self.freeze_path, {}) or {}
        if frozen.get("connector_version") != AIHOT_CONNECTOR_VERSION:
            LOGGER.warning("AI HOT freeze version mismatch (%s), refetching", frozen.get("connector_version"))
            return
        if frozen.get("run_id") != self.run_id:
            LOGGER.warning("AI HOT freeze belongs to another run, refetching")
            return
        self._frozen_lanes = frozen.get("lanes") or {}

    def _write_freeze(self) -> None:
        if self.freeze_path is None or self._frozen_lanes is not None:
            return
        write_json(
            self.freeze_path,
            {
                "connector_version": AIHOT_CONNECTOR_VERSION,
                "provider": AIHOT_PROVIDER,
                "run_id": self.run_id,
                "frozen_at": now_iso(),
                "lanes": self._lane_fetches,
            },
        )

    def _record_upstream(self, raw: dict[str, Any], *, lane: str) -> None:
        """Append one internal ledger observation; never published anywhere."""
        if not self.run_id:
            return
        links = raw.get("links") or {}
        original = str(links.get("original") or raw.get("url") or "")
        aihot_url = str(links.get("aihot") or raw.get("permalink") or "")
        canonical = canonicalize_url(original)
        item_id = upstream_item_id(raw)
        title = str(raw.get("title") or raw.get("originalTitle") or "")
        summary = str(raw.get("summary") or raw.get("description") or "")
        if not (item_id or canonical or title):
            return
        self._upstream_records.append(
            {
                "record_id": stable_hash(self.run_id, "aihot-upstream", lane, item_id or canonical or title),
                "run_id": self.run_id,
                "provider": AIHOT_PROVIDER,
                "upstream_lane": lane,
                "upstream_item_id": item_id or None,
                "upstream_story_id": upstream_story_id(raw) or None,
                "upstream_url": aihot_url or None,
                "original_url": original or None,
                "canonical_original_url": canonical or None,
                "published_at": raw.get("publishedAt") or raw.get("published_at") or raw.get("daily_date"),
                "discovered_at": raw.get("discoveredAt") or raw.get("discovered_at"),
                "retrieved_at": now_iso(),
                "etag": None,
                "title": title or None,
                "summary": summary or None,
                "reason": str(raw.get("reason") or "") or None,
                "title_hash": f"sha256:{content_hash(title)}" if title else None,
                "summary_hash": f"sha256:{content_hash(summary)}" if summary else None,
                "raw_payload_json": json.dumps(raw, ensure_ascii=False),
                "selected_for_radar": 0,
                "radar_id": None,
                "decision_reason": None,
                "created_at": now_iso(),
            }
        )

    def _write_ledger(self) -> None:
        if not self.run_id or not self._upstream_records:
            return
        self.db.upsert_radar_upstream_records(self._upstream_records)

    # ------------------------------------------------------------------ dedup

    @staticmethod
    def _deduplicate(items: list[CollectedItem]) -> list[CollectedItem]:
        best: dict[str, CollectedItem] = {}
        for item in items:
            key = item.payload.get("aihot_canonical_original") or canonicalize_url(item.original_url) or item.external_id or item.title.lower()
            existing = best.get(key)
            if not existing or item.priority > existing.priority:
                if existing is not None:
                    item.payload["aihot_lanes"] = unique_preserve(
                        [*(existing.payload.get("aihot_lanes") or []), *(item.payload.get("aihot_lanes") or [])]
                    )
                    item.payload["aihot_story_id"] = existing.payload.get("aihot_story_id") or item.payload.get("aihot_story_id")
                    item.topic_hint = item.topic_hint or existing.topic_hint
                    item.direction_hint = item.direction_hint or existing.direction_hint
                best[key] = item
            elif existing:
                existing.payload["aihot_lanes"] = unique_preserve(
                    [*(existing.payload.get("aihot_lanes") or []), *(item.payload.get("aihot_lanes") or [])]
                )
                existing.payload["aihot_story_id"] = existing.payload.get("aihot_story_id") or item.payload.get("aihot_story_id")
                existing.topic_hint = existing.topic_hint or item.topic_hint
                existing.direction_hint = existing.direction_hint or item.direction_hint
                existing.payload["matched_topics"] = unique_preserve(
                    [*(existing.payload.get("matched_topics") or []), item.topic_hint]
                )
        return list(best.values())
