from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from .adapters.base import CollectedItem
from .collection import CollectionService
from .feed import parse_feed
from .http import HttpClient, HttpRetryError
from .utils import (
    canonicalize_url,
    now_iso,
    parse_datetime,
    source_identity_key,
    stable_hash,
    write_json,
)

LOGGER = logging.getLogger(__name__)
STATE_PREFIX = "historical_backfill:v1"
CAMPAIGN_KEY = f"{STATE_PREFIX}:campaign"
ROTATION_KEY = f"{STATE_PREFIX}:rotation"
TERMINAL_LANE_STATES = {"COMPLETE", "FAILED_PERMANENT"}


@dataclass
class BackfillResult:
    items: list[CollectedItem]
    report: dict[str, Any]


def _policy(config) -> dict[str, Any]:
    efficiency = dict(config.settings.get("efficiency") or {})
    configured = dict(efficiency.get("historical_backfill") or {})
    configured.setdefault("enabled", True)
    configured.setdefault("lookback_days", int(efficiency.get("deep_lookback_days", 60)))
    configured.setdefault("auto_requests_per_collect", 4)
    configured.setdefault("manual_max_requests", 32)
    configured.setdefault("arxiv_page_size", 50)
    configured.setdefault("github_page_size", 50)
    return configured


def _safe_int(value: Any, default: int, *, minimum: int = 1, maximum: int = 10000) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _state_payload(db, key: str) -> dict[str, Any]:
    row = db.get_source_state(key) or {}
    payload = row.get("payload")
    return dict(payload) if isinstance(payload, dict) else {}


def _lane_key(lane: dict[str, Any]) -> str:
    return str(lane["state_key"])


def _interleave(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    count = max(len(primary), len(secondary))
    for index in range(count):
        if index < len(primary):
            result.append(primary[index])
        if index < len(secondary):
            result.append(secondary[index])
    return result


def historical_backfill_status(config, db) -> dict[str, Any]:
    policy = _policy(config)
    campaign = _state_payload(db, CAMPAIGN_KEY)
    lanes, unsupported = HistoricalBackfillService.describe_lanes(config)
    lane_rows = []
    for lane in lanes:
        state = _state_payload(db, _lane_key(lane))
        lane_rows.append(
            {
                "lane_id": lane["lane_id"],
                "kind": lane["kind"],
                "label": lane["label"],
                "status": state.get("status", "NOT_STARTED"),
                "cursor": state.get("cursor"),
                "requests": int(state.get("requests") or 0),
                "fetched_items": int(state.get("fetched_items") or 0),
                "oldest_seen_at": state.get("oldest_seen_at"),
                "last_error": state.get("last_error"),
            }
        )
    complete = sum(row["status"] == "COMPLETE" for row in lane_rows)
    failed = sum(row["status"] == "FAILED_PERMANENT" for row in lane_rows)
    active = len(lane_rows) - complete - failed
    return {
        "status": campaign.get("status", "NOT_STARTED"),
        "window_days": campaign.get("window_days", policy.get("lookback_days")),
        "cutoff": campaign.get("cutoff"),
        "started_at": campaign.get("started_at"),
        "completed_at": campaign.get("completed_at"),
        "supported_lanes": len(lane_rows),
        "complete_lanes": complete,
        "failed_lanes": failed,
        "active_lanes": active,
        "lanes": lane_rows,
        "unsupported_sources": unsupported,
    }


class HistoricalBackfillService:
    """Resumable, request-budgeted historical collection for deterministic A-level feeds.

    Historical items are fetched into a separate raw-item pool. They do not become
    Agent tasks directly; normal runs later drain them through the existing rolling
    backlog budget. Every network request advances exactly one persisted source lane.
    """

    def __init__(
        self,
        config,
        db,
        http: HttpClient,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
        now_fn: Callable[[], datetime] | None = None,
    ):
        self.config = config
        self.db = db
        self.http = http
        self.sleep_fn = sleep_fn
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._arxiv_requested = False

    @staticmethod
    def describe_lanes(config) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        deep_topics = set((config.settings.get("efficiency") or {}).get("deep_topics") or [])
        sources = list(config.source_list())
        arxiv = next((source for source in sources if source.get("id") == "arxiv" and source.get("enabled")), None)
        github = next(
            (source for source in sources if source.get("id") == "github_releases" and source.get("enabled")),
            None,
        )

        arxiv_lanes: list[dict[str, Any]] = []
        if arxiv:
            for topic, direction in config.iter_directions():
                topic_id = str(topic.get("id") or "")
                direction_id = str(direction.get("id") or "")
                if topic_id not in deep_topics:
                    continue
                terms = [str(term) for term in direction.get("include_terms") or [] if len(str(term)) >= 3]
                if not direction.get("arxiv_query") and not terms:
                    continue
                lane_id = f"arxiv:{topic_id}:{direction_id}"
                arxiv_lanes.append(
                    {
                        "lane_id": lane_id,
                        "kind": "arxiv",
                        "label": f"arXiv {topic_id}/{direction_id}",
                        "state_key": f"{STATE_PREFIX}:{lane_id}",
                        "topic": topic,
                        "direction": direction,
                        "source": arxiv,
                    }
                )

        github_lanes: list[dict[str, Any]] = []
        if github:
            for spec in github.get("repositories") or []:
                if spec.get("enabled", True) is False:
                    continue
                repo = str(spec.get("repo") or "").strip()
                if not repo:
                    continue
                lane_id = f"github:{repo.lower()}"
                github_lanes.append(
                    {
                        "lane_id": lane_id,
                        "kind": "github",
                        "label": f"GitHub Releases {repo}",
                        "state_key": f"{STATE_PREFIX}:{lane_id}",
                        "spec": spec,
                        "source": github,
                    }
                )

        # GitHub release lanes are cheap and few; interleave them with arXiv so
        # a small automatic request budget cannot starve one source family.
        lanes = _interleave(github_lanes, arxiv_lanes)

        supported_ids = {"arxiv", "github_releases"}
        unsupported = []
        for source in sources:
            if not source.get("enabled") or str(source.get("source_level") or "").upper() != "A":
                continue
            if source.get("id") in supported_ids:
                continue
            unsupported.append(
                {
                    "source_id": source.get("id"),
                    "name": source.get("name"),
                    "type": source.get("type"),
                    "reason": "no deterministic paginated historical collector",
                }
            )
        return lanes, unsupported

    def _reset(self) -> None:
        self.db.execute("DELETE FROM source_state WHERE source_key LIKE ?", (f"{STATE_PREFIX}:%",))

    def _campaign(self, days: int, *, reset: bool) -> tuple[dict[str, Any], datetime]:
        if reset:
            self._reset()
        existing = _state_payload(self.db, CAMPAIGN_KEY)
        if existing and int(existing.get("window_days") or 0) != days:
            # A different requested window starts a new campaign. Existing raw
            # items remain deduplicated history; only cursors are restarted.
            self._reset()
            existing = {}
        if existing:
            cutoff = parse_datetime(existing.get("cutoff"))
            if cutoff is not None:
                return existing, cutoff

        now = self.now_fn().astimezone(timezone.utc)
        cutoff = now - timedelta(days=days)
        campaign = {
            "status": "IN_PROGRESS",
            "window_days": days,
            "cutoff": cutoff.isoformat(),
            "started_at": now.isoformat(),
            "completed_at": None,
        }
        self.db.upsert_source_state(CAMPAIGN_KEY, payload=campaign)
        return campaign, cutoff

    def _arxiv_query(self, lane: dict[str, Any]) -> str:
        direction = lane["direction"]
        source = lane["source"]
        terms = [str(term) for term in direction.get("include_terms", []) if len(str(term)) >= 3][:4]
        term_query = " OR ".join(f'all:"{term.replace(chr(34), "")}"' for term in terms)
        categories = source.get("categories", [])
        category_query = " OR ".join(f"cat:{category}" for category in categories)
        query = direction.get("arxiv_query") or term_query
        return f"({category_query}) AND ({query})" if category_query else f"({query})"

    def _step_arxiv(
        self,
        lane: dict[str, Any],
        *,
        cutoff: datetime,
        days: int,
        page_size: int,
    ) -> tuple[list[CollectedItem], dict[str, Any], bool]:
        state_key = _lane_key(lane)
        state = _state_payload(self.db, state_key)
        start = int(state.get("cursor") or 0)
        source = lane["source"]
        interval = max(0.0, float(source.get("request_interval_seconds", 3.0)))
        if self._arxiv_requested and interval:
            self.sleep_fn(interval)
        self._arxiv_requested = True
        query = self._arxiv_query(lane)
        params = {
            "search_query": query,
            "start": start,
            "max_results": page_size,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            response = self.http.get(source["endpoint"], params=params)
            response.raise_for_status()
            entries = parse_feed(response.content)
        except (HttpRetryError, httpx.HTTPError, ValueError) as exc:
            payload = {
                **state,
                "status": "ERROR",
                "cursor": start,
                "last_error": str(exc),
                "last_attempt_at": now_iso(),
            }
            self.db.upsert_source_state(state_key, cursor=str(start), payload=payload)
            return [], payload, True

        items: list[CollectedItem] = []
        reached_cutoff = False
        consumed = 0
        oldest: datetime | None = None
        for entry in entries:
            published = entry.published
            dt = parse_datetime(published)
            if dt is not None:
                oldest = dt if oldest is None or dt < oldest else oldest
                if dt < cutoff:
                    reached_cutoff = True
                    break
            consumed += 1
            pdf_url = ""
            for link in entry.links:
                if link.get("type") == "application/pdf" or link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                    break
            items.append(
                CollectedItem(
                    source_id="arxiv",
                    discovery_source="arXiv",
                    source_level="A",
                    discovery_only=False,
                    title=" ".join(entry.title.split()),
                    summary=" ".join(entry.summary.split()),
                    original_url=entry.link,
                    published_at=published,
                    discovered_at=now_iso(),
                    authors=entry.authors,
                    external_id=entry.id,
                    topic_hint=str(lane["topic"].get("id") or ""),
                    direction_hint=str(lane["direction"].get("id") or ""),
                    priority=18.0,
                    payload={
                        "pdf_url": pdf_url,
                        "tags": entry.tags,
                        "historical_backfill": {"window_days": days, "lane": lane["lane_id"]},
                    },
                )
            )

        # When the cutoff appears inside a page, preserve the boundary cursor.
        # A future campaign with a wider window can restart cleanly without a
        # silent hole. A short page also proves the query has been exhausted.
        complete = reached_cutoff or len(entries) < page_size or not entries
        next_start = start + consumed
        payload = {
            **state,
            "status": "COMPLETE" if complete else "IN_PROGRESS",
            "cursor": next_start,
            "requests": int(state.get("requests") or 0) + 1,
            "fetched_items": int(state.get("fetched_items") or 0) + len(items),
            "oldest_seen_at": oldest.isoformat() if oldest else state.get("oldest_seen_at"),
            "last_error": None,
            "last_attempt_at": now_iso(),
            "completed_at": now_iso() if complete else None,
        }
        self.db.upsert_source_state(state_key, cursor=str(next_start), payload=payload)
        return items, payload, False

    def _github_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _step_github(
        self,
        lane: dict[str, Any],
        *,
        cutoff: datetime,
        days: int,
        page_size: int,
    ) -> tuple[list[CollectedItem], dict[str, Any], bool]:
        state_key = _lane_key(lane)
        state = _state_payload(self.db, state_key)
        page = int(state.get("cursor") or 1)
        spec = lane["spec"]
        repo = str(spec["repo"])
        url = f"https://api.github.com/repos/{repo}/releases"
        try:
            response = self.http.get(
                url,
                headers=self._github_headers(),
                params={"per_page": page_size, "page": page},
            )
            if response.status_code == 404:
                payload = {
                    **state,
                    "status": "FAILED_PERMANENT",
                    "cursor": page,
                    "last_error": f"GitHub releases endpoint not found: {repo}",
                    "last_attempt_at": now_iso(),
                }
                self.db.upsert_source_state(state_key, cursor=str(page), payload=payload)
                return [], payload, True
            response.raise_for_status()
            releases = response.json()
            if not isinstance(releases, list):
                raise ValueError("GitHub releases response is not a list")
        except (HttpRetryError, httpx.HTTPError, ValueError) as exc:
            payload = {
                **state,
                "status": "ERROR",
                "cursor": page,
                "last_error": str(exc),
                "last_attempt_at": now_iso(),
            }
            self.db.upsert_source_state(state_key, cursor=str(page), payload=payload)
            return [], payload, True

        items: list[CollectedItem] = []
        reached_cutoff = False
        oldest: datetime | None = None
        for release in releases:
            published = release.get("published_at") or release.get("created_at")
            dt = parse_datetime(published)
            if dt is not None:
                oldest = dt if oldest is None or dt < oldest else oldest
                if dt < cutoff:
                    reached_cutoff = True
                    break
            items.append(
                CollectedItem(
                    source_id="github_releases",
                    discovery_source="GitHub Release",
                    source_level="A",
                    discovery_only=False,
                    title=f"{repo} {release.get('name') or release.get('tag_name')}",
                    summary=release.get("body") or "",
                    original_url=release.get("html_url") or "",
                    published_at=published,
                    discovered_at=now_iso(),
                    authors=[(release.get("author") or {}).get("login", "")],
                    external_id=str(release.get("id") or release.get("tag_name") or ""),
                    topic_hint=spec.get("topic", ""),
                    direction_hint=spec.get("direction", ""),
                    priority=20.0,
                    payload={
                        "repo": repo,
                        "tag": release.get("tag_name"),
                        "historical_backfill": {"window_days": days, "lane": lane["lane_id"]},
                    },
                )
            )

        complete = reached_cutoff or len(releases) < page_size or not releases
        next_page = page + 1
        payload = {
            **state,
            "status": "COMPLETE" if complete else "IN_PROGRESS",
            "cursor": next_page,
            "requests": int(state.get("requests") or 0) + 1,
            "fetched_items": int(state.get("fetched_items") or 0) + len(items),
            "oldest_seen_at": oldest.isoformat() if oldest else state.get("oldest_seen_at"),
            "last_error": None,
            "last_attempt_at": now_iso(),
            "completed_at": now_iso() if complete else None,
        }
        self.db.upsert_source_state(state_key, cursor=str(next_page), payload=payload)
        return items, payload, False

    def _deduplicate_new(self, items: list[CollectedItem]) -> tuple[list[CollectedItem], int]:
        rows = self.db.fetchall("SELECT identity_key, canonical_url FROM raw_items")
        existing = {
            str(row.get("identity_key") or row.get("canonical_url") or "")
            for row in rows
            if row.get("identity_key") or row.get("canonical_url")
        }
        result: list[CollectedItem] = []
        duplicate_count = 0
        for item in items:
            canonical = canonicalize_url(item.original_url or item.aihot_url)
            identity = source_identity_key(canonical, item.external_id)
            key = identity or canonical or stable_hash(item.source_id, item.external_id, item.title)
            if key in existing:
                duplicate_count += 1
                continue
            existing.add(key)
            result.append(item)
        return result, duplicate_count

    def run(
        self,
        *,
        days: int | None = None,
        max_requests: int | None = None,
        reset: bool = False,
    ) -> BackfillResult:
        policy = _policy(self.config)
        if not bool(policy.get("enabled", True)):
            return BackfillResult([], {"status": "DISABLED", "requests_used": 0, "new_items": 0})
        days = _safe_int(days, int(policy.get("lookback_days", 60)), minimum=1, maximum=3650)
        max_requests = _safe_int(
            max_requests,
            int(policy.get("manual_max_requests", 32)),
            minimum=1,
            maximum=500,
        )
        arxiv_page_size = _safe_int(policy.get("arxiv_page_size"), 50, minimum=5, maximum=100)
        github_page_size = _safe_int(policy.get("github_page_size"), 50, minimum=5, maximum=100)
        campaign, cutoff = self._campaign(days, reset=reset)
        lanes, unsupported = self.describe_lanes(self.config)
        if not lanes:
            campaign = {**campaign, "status": "PARTIAL", "completed_at": now_iso()}
            self.db.upsert_source_state(CAMPAIGN_KEY, payload=campaign)
            return BackfillResult(
                [],
                {
                    **historical_backfill_status(self.config, self.db),
                    "requests_used": 0,
                    "fetched_items": 0,
                    "new_items": 0,
                    "duplicates_skipped": 0,
                    "unsupported_sources": unsupported,
                },
            )

        rotation = _state_payload(self.db, ROTATION_KEY)
        cursor = int(rotation.get("cursor") or 0) % len(lanes)
        requests_used = 0
        fetched: list[CollectedItem] = []
        failed_this_run: set[str] = set()
        idle_scans = 0

        while requests_used < max_requests and idle_scans < len(lanes):
            lane = lanes[cursor]
            cursor = (cursor + 1) % len(lanes)
            state = _state_payload(self.db, _lane_key(lane))
            if state.get("status") in TERMINAL_LANE_STATES or lane["lane_id"] in failed_this_run:
                idle_scans += 1
                continue

            idle_scans = 0
            if lane["kind"] == "arxiv":
                items, _, failed = self._step_arxiv(
                    lane,
                    cutoff=cutoff,
                    days=days,
                    page_size=arxiv_page_size,
                )
            else:
                items, _, failed = self._step_github(
                    lane,
                    cutoff=cutoff,
                    days=days,
                    page_size=github_page_size,
                )
            requests_used += 1
            fetched.extend(items)
            if failed:
                failed_this_run.add(lane["lane_id"])

        self.db.upsert_source_state(ROTATION_KEY, cursor=str(cursor), payload={"cursor": cursor})
        new_items, duplicates = self._deduplicate_new(fetched)

        status = historical_backfill_status(self.config, self.db)
        if status["active_lanes"] == 0:
            overall = "COMPLETE" if status["failed_lanes"] == 0 else "PARTIAL"
            campaign = {
                **campaign,
                "status": overall,
                "completed_at": campaign.get("completed_at") or now_iso(),
            }
        else:
            campaign = {**campaign, "status": "IN_PROGRESS", "completed_at": None}
        self.db.upsert_source_state(CAMPAIGN_KEY, payload=campaign)

        report = historical_backfill_status(self.config, self.db)
        report.update(
            {
                "request_budget": max_requests,
                "requests_used": requests_used,
                "fetched_items": len(fetched),
                "new_items": len(new_items),
                "duplicates_skipped": duplicates,
                "failed_this_run": sorted(failed_this_run),
            }
        )
        return BackfillResult(new_items, report)


def execute_historical_backfill(
    root: Path,
    paths,
    config,
    db,
    *,
    days: int | None = None,
    max_requests: int | None = None,
    reset: bool = False,
    reason: str = "manual",
) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    batch_id = f"historical-{stamp}"
    backfill_dir = paths.workspace / "backfill"
    batch_dir = backfill_dir / batch_id
    collector = CollectionService(config, db, batch_dir)
    try:
        result = HistoricalBackfillService(config, db, collector.http).run(
            days=days,
            max_requests=max_requests,
            reset=reset,
        )
        persisted = collector.persist(batch_id, result.items)
    finally:
        collector.close()

    report = {
        **result.report,
        "batch_id": batch_id,
        "reason": reason,
        "persisted_items": len(persisted),
        "backlog_materialize_per_run": int(
            (config.settings.get("efficiency") or {}).get("backlog_materialize_per_run", 120)
        ),
    }
    write_json(batch_dir / "historical-backfill.json", report)
    write_json(backfill_dir / "latest.json", report)
    return report


def install_historical_backfill() -> None:
    """Add explicit and background-budgeted backfill without changing core CLI files."""

    from . import cli

    if getattr(cli, "_historical_backfill_installed", False):
        return
    original_build_parser = cli.build_parser
    original_cmd_collect = cli.cmd_collect

    def cmd_backfill(args) -> int:
        root, paths, config, db = cli._context(args)
        policy = _policy(config)
        report = execute_historical_backfill(
            root,
            paths,
            config,
            db,
            days=args.days,
            max_requests=args.max_requests or int(policy.get("manual_max_requests", 32)),
            reset=bool(args.reset),
            reason="manual",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    def cmd_backfill_status(args) -> int:
        _, _, config, db = cli._context(args)
        print(json.dumps(historical_backfill_status(config, db), ensure_ascii=False, indent=2))
        return 0

    def cmd_collect(args) -> int:
        if not getattr(args, "offline_fixture", False):
            root, paths, config, db = cli._context(args)
            policy = _policy(config)
            budget = int(policy.get("auto_requests_per_collect", 4))
            if bool(policy.get("enabled", True)) and budget > 0:
                report = execute_historical_backfill(
                    root,
                    paths,
                    config,
                    db,
                    days=int(policy.get("lookback_days", 60)),
                    max_requests=budget,
                    reason="auto-collect",
                )
                LOGGER.info(
                    "Historical backfill %s: requests=%d new=%d complete=%d/%d",
                    report.get("status"),
                    report.get("requests_used", 0),
                    report.get("persisted_items", 0),
                    report.get("complete_lanes", 0),
                    report.get("supported_lanes", 0),
                )
        return original_cmd_collect(args)

    def build_parser():
        parser = original_build_parser()
        subparsers_action = next(
            action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
        )
        p = subparsers_action.add_parser("backfill")
        p.add_argument("--days", type=int)
        p.add_argument("--max-requests", type=int)
        p.add_argument("--reset", action="store_true")
        p.set_defaults(func=cmd_backfill)
        p = subparsers_action.add_parser("backfill-status")
        p.set_defaults(func=cmd_backfill_status)
        return parser

    # Existing production cron calls `collect` directly. `cmd_run` also resolves
    # `cmd_collect` from the CLI module at runtime, so patching collection covers
    # both paths exactly once instead of double-spending the request budget.
    cli.cmd_collect = cmd_collect
    cli.build_parser = build_parser
    cli._historical_backfill_installed = True
