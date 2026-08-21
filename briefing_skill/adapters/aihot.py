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
AIHOT_CONNECTOR_VERSION = 3
AIHOT_PROVIDER = "aihot"

# Public copy may only come from these upstream fields. `reason` is the AI Hot
# editorial recommendation: internal ordering/ledger only, never reader copy.
PUBLIC_SUMMARY_FIELDS = ("summary", "description")

# Copy variants are preferred in this lane order when several lanes carry the
# same item but only some have a usable Chinese complete-sentence summary.
VARIANT_LANE_PREFERENCE = ("selected", "daily", "all", "paper")

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


def _summary_variant(raw: dict[str, Any]) -> dict[str, str] | None:
    """The one public copy candidate this raw item contributes, if any."""
    for field in PUBLIC_SUMMARY_FIELDS:
        text = " ".join(str(raw.get(field) or "").split())
        if text:
            return {"source_field": field, "summary": text}
    return None


class AIHotCollector:
    """AI HOT v1 multi-lane collector.

    Lanes: ``selected`` (24h editor picks), ``all``/``paper`` (per-direction
    keyword queries), ``daily`` (daily report items) and ``hot`` (hot-topic
    ranks). The hot lane never publishes cards by itself; it only adds
    rank/story identity to items seen in other lanes.

    Every run freezes the full lane plan plus responses under the run
    directory; a valid freeze replays every lane offline (a lane missing from
    a valid freeze is an error, never a live request). A 304 response replays
    the cached body from ``source_state`` so unchanged content is still
    materialized into the new run. Individual lane failures never discard the
    results of lanes that already succeeded; only a total provider failure
    raises. All lane observations land in ``radar_upstream_records`` with the
    full lane key/query context for internal traceability.
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

    # ------------------------------------------------------------------ plan

    def _planned_lanes(self) -> list[dict[str, Any]]:
        """Deterministic lane plan derived only from versioned config."""
        lanes: list[dict[str, Any]] = []
        base_limit = int(self.source.get("base_selected_limit", 50))
        lanes.append(
            {
                "key": "selected",
                "lane": "selected",
                "url": self.endpoint,
                "params": {"mode": "selected", "window": "24h", "by": "timeline", "limit": base_limit},
                "topic_hint": "",
                "direction_hint": "",
                "query": "",
                "boost": 0.0,
            }
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
                base_params = {
                    "mode": "all",
                    "window": self.source.get("window", "7d"),
                    "by": "timeline",
                    "limit": limit,
                    "q": query,
                }
                lanes.append(
                    {
                        "key": f"all:{topic['id']}:{direction_id}:{query}",
                        "lane": "all",
                        "url": self.endpoint,
                        "params": dict(base_params),
                        "topic_hint": topic["id"],
                        "direction_hint": direction_id,
                        "query": query,
                        "boost": 20.0 * boost,
                    }
                )
                # AI HOT public pool excludes arXiv unless paper is requested.
                if any(term in query.lower() for term in ("paper", "agent", "kv cache", "prefill", "code graph")):
                    paper_params = dict(base_params, category="paper", limit=min(limit, 30))
                    lanes.append(
                        {
                            "key": f"paper:{topic['id']}:{direction_id}:{query}",
                            "lane": "paper",
                            "url": self.endpoint,
                            "params": paper_params,
                            "topic_hint": topic["id"],
                            "direction_hint": direction_id,
                            "query": query,
                            "boost": 22.0 * boost,
                        }
                    )
        if self.source.get("daily_enabled", True):
            lanes.append(
                {
                    "key": "daily",
                    "lane": "daily",
                    "url": f"{self.api_base}/dailies/latest",
                    "params": {},
                    "topic_hint": "",
                    "direction_hint": "",
                    "query": "",
                    "boost": 0.0,
                }
            )
        if self.source.get("hot_topics_enabled", True):
            lanes.append(
                {
                    "key": "hot",
                    "lane": "hot",
                    "url": f"{self.api_base}/hot-topics",
                    "params": {},
                    "topic_hint": "",
                    "direction_hint": "",
                    "query": "",
                    "boost": 0.0,
                }
            )
        return lanes

    def _lane_plan_hash(self, lanes: list[dict[str, Any]]) -> str:
        plan = [
            {"key": lane["key"], "url": lane["url"], "params": lane["params"]}
            for lane in lanes
        ]
        return stable_hash(json.dumps(plan, ensure_ascii=False, sort_keys=True), length=32)

    # --------------------------------------------------------------- collect

    def collect(self) -> list[CollectedItem]:
        self._load_frozen()
        plan = self._planned_lanes()
        plan_hash = self._lane_plan_hash(plan)
        if self._frozen_lanes is not None:
            frozen = getattr(self, "_frozen_doc", {}) or {}
            if frozen.get("lane_plan_hash") != plan_hash:
                # A frozen run is immutable: refetching under a changed lane
                # plan would overwrite the freeze while INSERT OR IGNORE keeps
                # the old raw_items, splitting run state in two. Fail loudly
                # and require a fresh run instead.
                raise RuntimeError(
                    "AI Hot lane plan changed after this run was frozen "
                    f"(stored={frozen.get('lane_plan_hash')} current={plan_hash}); "
                    "create a new run for the new lane configuration"
                )

        items: list[CollectedItem] = []
        hot_entries: list[dict[str, Any]] = []
        lane_errors: dict[str, str] = {}
        succeeded_lanes: set[str] = set()
        for lane in plan:
            try:
                payload = self._fetch_lane(lane)
                if self._lane_fetches.get(lane["key"], {}).get("error"):
                    lane_errors[lane["key"]] = str(self._lane_fetches[lane["key"]]["error"])
                    continue
                succeeded_lanes.add(lane["key"])
                if lane["lane"] == "hot":
                    hot_entries = self._collect_hot_lane(payload)
                elif lane["lane"] == "daily":
                    items.extend(self._collect_daily_lane(lane, payload))
                else:
                    items.extend(self._collect_items_lane(lane, payload))
            except Exception as exc:
                lane_errors[lane["key"]] = f"{type(exc).__name__}: {exc}"
                self._lane_fetches[lane["key"]] = {
                    "url": lane["url"],
                    "retrieved_at": now_iso(),
                    "error": lane_errors[lane["key"]],
                }
                LOGGER.warning("AI HOT lane %s failed: %s", lane["key"], exc)

        if plan and not succeeded_lanes:
            raise RuntimeError(
                f"AI Hot provider failure: every planned lane failed ({'; '.join(sorted(lane_errors))})"
            )

        items = self._deduplicate(items)
        self._apply_hot_matches(items, hot_entries)
        self._write_ledger()
        self._write_freeze(plan_hash)
        return items

    # ------------------------------------------------------------------ lanes

    def _collect_daily_lane(self, lane: dict[str, Any], payload: dict[str, Any]) -> list[CollectedItem]:
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
                    # The daily date is the recall window, never the original
                    # publication date: it must not leak into publishedAt.
                    entry["daily_date"] = daily_date
                self._record_upstream(entry, lane)
                # A daily entry needs a complete title/public-copy/original
                # triple before it may become a radar candidate; partial
                # entries stay internal-only observations.
                if not (str(entry.get("title") or "").strip() and _summary_variant(entry)):
                    continue
                links = entry.get("links") or {}
                original = links.get("original") or entry.get("url") or ""
                if not original:
                    continue
                item = self._item_from_raw(
                    entry,
                    lane=lane,
                    extra_payload={"aihot_daily_section": label, "aihot_daily_date": daily_date},
                )
                if item is not None:
                    items.append(item)
        return items

    def _collect_hot_lane(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for raw in payload.get("items") or payload.get("data") or []:
            self._record_upstream(raw, self._hot_lane)
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

    def _fetch_lane(self, lane: dict[str, Any]) -> dict[str, Any]:
        lane_key = lane["key"]
        url = lane["url"]
        params = lane["params"]
        if self._frozen_lanes is not None:
            frozen = self._frozen_lanes.get(lane_key)
            if frozen is not None:
                self._lane_fetches[lane_key] = dict(frozen, from_cache=True)
                return frozen.get("payload") or {}
            # A valid freeze must cover the whole planned lane set; a missing
            # lane is recorded as an error instead of silently going online.
            self._lane_fetches[lane_key] = {
                "url": url,
                "retrieved_at": now_iso(),
                "error": "missing_from_freeze",
            }
            return {}
        full_url = f"{url}?{urlencode(sorted(params.items()))}" if params else url
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
        etag = state.get("etag") if from_cache else response.headers.get("ETag")
        if not from_cache:
            self.db.upsert_source_state(
                state_key,
                etag=response.headers.get("ETag"),
                payload={"params": params, "body": payload},
            )
        self._lane_fetches[lane_key] = {
            "url": full_url,
            "etag": etag,
            "retrieved_at": now_iso(),
            "from_cache": from_cache,
            "payload": payload,
        }
        return payload

    def _collect_items_lane(self, lane: dict[str, Any], payload: dict[str, Any]) -> list[CollectedItem]:
        result: list[CollectedItem] = []
        for raw in payload.get("items") or payload.get("data") or []:
            self._record_upstream(raw, lane)
            item = self._item_from_raw(raw, lane=lane)
            if item is not None:
                if lane["boost"]:
                    item.priority += lane["boost"]
                result.append(item)
        return result

    def _item_from_raw(
        self,
        raw: dict[str, Any],
        *,
        lane: dict[str, Any],
        extra_payload: dict[str, Any] | None = None,
    ) -> CollectedItem | None:
        links = raw.get("links") or {}
        source = raw.get("source") or {}
        original = links.get("original") or raw.get("url") or ""
        aihot_url = links.get("aihot") or raw.get("permalink") or ""
        if not original and not aihot_url:
            return None
        variant = _summary_variant(raw)
        summary = variant["summary"] if variant else ""
        source_name = source.get("name") if isinstance(source, dict) else str(source or "AI HOT")
        payload: dict[str, Any] = {
            "aihot": raw,
            "upstream_source": source_name,
            "aihot_lane": lane["lane"],
            "aihot_lanes": [lane["lane"]],
            "aihot_canonical_original": canonicalize_url(original),
            # Every lane's copy candidate is kept (with its precise lane key)
            # so direct-copy can fall back to another lane's usable Chinese
            # summary and later prove exactly which frozen lane produced it.
            "aihot_copy_variants": [
                {
                    "lane": lane["lane"],
                    "lane_key": lane["key"],
                    "source_field": variant["source_field"],
                    "summary": summary,
                }
            ]
            if variant
            else [],
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
            topic_hint=lane["topic_hint"],
            direction_hint=lane["direction_hint"],
            priority=15.0,
            payload=payload,
        )

    # ------------------------------------------------------- freeze and ledger

    def _load_frozen(self) -> None:
        self._frozen_doc = {}
        if self.freeze_path is None or not self.freeze_path.exists():
            return
        frozen = read_json(self.freeze_path, {}) or {}
        if frozen.get("connector_version") != AIHOT_CONNECTOR_VERSION:
            LOGGER.warning("AI HOT freeze version mismatch (%s), refetching", frozen.get("connector_version"))
            return
        if frozen.get("run_id") != self.run_id:
            LOGGER.warning("AI HOT freeze belongs to another run, refetching")
            return
        self._frozen_doc = frozen
        self._frozen_lanes = frozen.get("lanes") or {}

    def _write_freeze(self, plan_hash: str) -> None:
        if self.freeze_path is None or self._frozen_lanes is not None:
            return
        write_json(
            self.freeze_path,
            {
                "connector_version": AIHOT_CONNECTOR_VERSION,
                "provider": AIHOT_PROVIDER,
                "run_id": self.run_id,
                "frozen_at": now_iso(),
                "lane_plan_hash": plan_hash,
                "ledger_error": getattr(self, "_ledger_error", None),
                "lanes": self._lane_fetches,
            },
        )

    @property
    def _hot_lane(self) -> dict[str, Any]:
        return {
            "key": "hot",
            "lane": "hot",
            "url": f"{self.api_base}/hot-topics",
            "params": {},
            "topic_hint": "",
            "direction_hint": "",
            "query": "",
            "boost": 0.0,
        }

    def _record_upstream(self, raw: dict[str, Any], lane: dict[str, Any]) -> None:
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
        fetched = self._lane_fetches.get(lane["key"]) or {}
        retrieved_at = now_iso()
        self._upstream_records.append(
            {
                "record_id": stable_hash(self.run_id, "aihot-upstream", lane["key"], item_id or canonical or title),
                "run_id": self.run_id,
                "provider": AIHOT_PROVIDER,
                "upstream_lane": lane["lane"],
                "lane_key": lane["key"],
                "lane_query": lane["query"] or None,
                "topic_hint": lane["topic_hint"] or None,
                "direction_hint": lane["direction_hint"] or None,
                "upstream_item_id": item_id or None,
                "upstream_story_id": upstream_story_id(raw) or None,
                "upstream_url": aihot_url or None,
                "original_url": original or None,
                "canonical_original_url": canonical or None,
                "published_at": raw.get("publishedAt") or raw.get("published_at"),
                "discovered_at": raw.get("discoveredAt") or raw.get("discovered_at"),
                "retrieved_at": retrieved_at,
                "retrieved_at_first": retrieved_at,
                "etag": fetched.get("etag"),
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
        try:
            self.db.upsert_radar_upstream_records(self._upstream_records)
        except Exception as exc:  # noqa: BLE001
            # The audit ledger must never zero out successfully collected
            # public candidates: record the failure for the freeze/telemetry
            # and keep the collected items.
            self._ledger_error = f"{type(exc).__name__}: {exc}"
            LOGGER.exception("AI HOT upstream ledger write failed (continuing with collected items)")

    # ------------------------------------------------------------------ dedup

    @staticmethod
    def _merge_variants(target: dict[str, Any], other: dict[str, Any]) -> None:
        merged: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for variant in [*(target.get("aihot_copy_variants") or []), *(other.get("aihot_copy_variants") or [])]:
            key = (
                str(variant.get("lane_key") or ""),
                str(variant.get("source_field") or ""),
                str(variant.get("summary") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(variant)
        target["aihot_copy_variants"] = merged

    @staticmethod
    def _deduplicate(items: list[CollectedItem]) -> list[CollectedItem]:
        best: dict[str, CollectedItem] = {}
        for item in items:
            key = item.payload.get("aihot_canonical_original") or canonicalize_url(item.original_url) or item.external_id or item.title.lower()
            existing = best.get(key)
            if not existing or item.priority > existing.priority:
                if existing is not None:
                    AIHotCollector._merge_into(item, existing)
                best[key] = item
            else:
                AIHotCollector._merge_into(existing, item)
        return list(best.values())

    @staticmethod
    def _merge_into(target: CollectedItem, other: CollectedItem) -> None:
        target.payload["aihot_lanes"] = unique_preserve(
            [*(target.payload.get("aihot_lanes") or []), *(other.payload.get("aihot_lanes") or [])]
        )
        target.payload["aihot_story_id"] = target.payload.get("aihot_story_id") or other.payload.get("aihot_story_id")
        target.topic_hint = target.topic_hint or other.topic_hint
        target.direction_hint = target.direction_hint or other.direction_hint
        target.payload["matched_topics"] = unique_preserve(
            [*(target.payload.get("matched_topics") or []), other.topic_hint]
        )
        AIHotCollector._merge_variants(target.payload, other.payload)
        # If the weaker record carries a usable public copy and the stronger
        # one does not, keep the weaker copy as the reader-facing summary so a
        # boost-driven English winner cannot silently kill a Chinese summary.
        if not str(target.summary or "").strip() and str(other.summary or "").strip():
            target.summary = other.summary
