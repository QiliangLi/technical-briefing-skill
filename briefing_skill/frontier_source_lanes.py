from __future__ import annotations

from collections import defaultdict
from typing import Any

from .freshness import published_age_days
from .utils import canonicalize_url


FRONTIER_TOPIC_ID = "frontier_exploration"
FRONTIER_CATEGORY = "边界探索"
BLOG_BUILDER_SOURCE_IDS = {
    "simon_willison",
    "latent_space",
    "interconnects",
    "semianalysis",
    "huggingface_papers",
    "ai_news",
    "follow_builders",
    "yeekal_daily",
    "agent_web_search",
}


def _append_unique(values: list[Any], value: str) -> None:
    if value not in {str(item) for item in values}:
        values.append(value)


def augment_frontier_bundle(bundle) -> None:
    efficiency = bundle.settings.setdefault("efficiency", {})
    radar_topics = efficiency.setdefault("radar_topics", [])
    _append_unique(radar_topics, FRONTIER_TOPIC_ID)

    # Fixed technical blogs/builders are genuine observation sources. They do not need
    # an A-level paper merely to be visible, but they remain explicitly outside Deep/Core.
    for source in bundle.sources.get("sources") or []:
        source_id = str(source.get("id") or "")
        if source_id not in BLOG_BUILDER_SOURCE_IDS:
            continue
        allowlist = source.get("topic_allowlist")
        if isinstance(allowlist, list):
            _append_unique(allowlist, FRONTIER_TOPIC_ID)
        boosts = source.get("topic_boosts")
        if isinstance(boosts, dict):
            boosts.setdefault(FRONTIER_TOPIC_ID, 1.25)


def _source_lane(row: dict[str, Any]) -> str:
    level = str(row.get("source_level") or "C").upper()
    source_id = str(row.get("source_id") or "")
    if source_id in BLOG_BUILDER_SOURCE_IDS or level == "B":
        return "industry_builder"
    if level == "A":
        return "academic_primary"
    return "discovery"


def _candidate_from_row(radar, row: dict[str, Any], category: str) -> dict[str, Any] | None:
    url = str(row.get("original_url") or row.get("canonical_url") or "").strip()
    if not url:
        return None
    reason = radar._clean(row.get("relevance_reason"), radar.RADAR_SUMMARY_MAX_CHARS)
    summary = reason if radar.summary_is_reader_chinese(reason) else radar._clean(
        row.get("summary"), radar.RADAR_SUMMARY_MAX_CHARS
    )
    title = radar._clean(row.get("title"), 180)
    if not title or len(summary) < 20:
        return None
    return {
        "candidate_id": str(row["id"]),
        "category": category,
        "title": title,
        "summary": summary,
        "url": url,
        "source_name": radar._clean(row.get("discovery_source") or row.get("source_id") or "source", 80),
        "source_level": str(row.get("source_level") or "C").upper(),
        "source_lane": _source_lane(row),
        "published_at": str(row.get("published_at") or "")[:10],
    }


def _radar_exclusions(
    task_service,
    issue_input: dict[str, Any],
) -> tuple[set[str], set[str]]:
    urls = {
        canonicalize_url(source.get("url"))
        for item in issue_input.get("items") or []
        for source in item.get("sources") or []
        if source.get("url")
    }
    history = task_service.db.fetchall(
        "SELECT canonical_url,normalized_title FROM radar_history"
    )
    urls.update(
        canonicalize_url(row.get("canonical_url"))
        for row in history
        if row.get("canonical_url")
    )
    titles = {
        str(row.get("normalized_title") or "").lower()
        for row in history
        if row.get("normalized_title")
    }
    return {value for value in urls if value}, titles


def _extra_observation_candidates(
    radar,
    task_service,
    run_id: str,
    issue_input: dict[str, Any],
) -> list[dict[str, Any]]:
    excluded_urls, excluded_titles = _radar_exclusions(task_service, issue_input)
    rows = task_service.db.fetchall(
        """
        SELECT r.id,r.title,r.summary,r.original_url,r.canonical_url,r.published_at,r.priority,
               r.discovery_source,r.source_id,r.source_level,r.discovery_only,
               c.topic_id,c.relevance_reason,c.relevant
        FROM raw_items r
        LEFT JOIN candidates c ON c.raw_item_id=r.id AND c.run_id=?
        WHERE r.run_id=? AND (r.source_level='B' OR c.topic_id=?)
        ORDER BY r.priority DESC,r.published_at DESC,LENGTH(COALESCE(r.summary,'')) DESC,r.title
        """,
        (run_id, run_id, FRONTIER_TOPIC_ID),
    )
    result: list[dict[str, Any]] = []
    seen_urls: set[str] = set(excluded_urls)
    seen_titles: set[str] = set(excluded_titles)
    for row in rows:
        age = published_age_days(row.get("published_at"))
        if age is None or age > 7:
            continue
        url = str(row.get("original_url") or row.get("canonical_url") or "").strip()
        canonical = canonicalize_url(url)
        if not canonical or canonical in seen_urls:
            continue
        title_key = radar._normalise_title(row.get("title"))
        if title_key and title_key in seen_titles:
            continue
        category = (
            FRONTIER_CATEGORY
            if str(row.get("topic_id") or "") == FRONTIER_TOPIC_ID
            else radar._category(str(row.get("title") or ""), str(row.get("summary") or ""))
        )
        candidate = _candidate_from_row(radar, row, category)
        if candidate is None:
            continue
        result.append(candidate)
        seen_urls.add(canonical)
        if title_key:
            seen_titles.add(title_key)
    return result


def _rebalance_candidates(radar, original: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[str] = set()
    for row in [*extra, *original]:
        canonical = canonicalize_url(row.get("url"))
        if not canonical or canonical in seen:
            continue
        copy = dict(row)
        copy.setdefault("source_lane", "academic_primary" if copy.get("source_level") == "A" else "industry_builder")
        by_category[str(copy.get("category") or "其他技术前沿")].append(copy)
        seen.add(canonical)

    selected_by_category: dict[str, list[dict[str, Any]]] = {}
    for category, rows in by_category.items():
        limit = 4 if category == FRONTIER_CATEGORY else radar.MAX_CANDIDATES_PER_CATEGORY
        builder = [row for row in rows if row.get("source_lane") == "industry_builder"]
        academic = [row for row in rows if row.get("source_lane") == "academic_primary"]
        other = [row for row in rows if row not in builder and row not in academic]
        # Observation lanes reserve visible room for industry/builder signals instead of
        # allowing A-level/arXiv rows to consume every category slot.
        if category == FRONTIER_CATEGORY:
            ordered = [*builder, *academic, *other]
        else:
            ordered = [*builder[:2], *academic, *builder[2:], *other]
        selected_by_category[category] = ordered[:limit]

    categories = list(radar.RADAR_CATEGORIES)
    result: list[dict[str, Any]] = []
    while len(result) < radar.MAX_RADAR_CANDIDATES:
        added = False
        for category in categories:
            index = sum(1 for row in result if row["category"] == category)
            rows = selected_by_category.get(category, [])
            if index < len(rows):
                result.append(rows[index])
                added = True
                if len(result) >= radar.MAX_RADAR_CANDIDATES:
                    break
        if not added:
            break
    return result


def install_frontier_source_lanes() -> None:
    from .config import ConfigBundle
    from . import radar_signal_synthesis as radar

    if getattr(ConfigBundle, "_frontier_source_lanes_installed", False):
        return

    original_load = ConfigBundle.load.__func__

    def load(cls, paths):
        bundle = original_load(cls, paths)
        augment_frontier_bundle(bundle)
        return bundle

    ConfigBundle.load = classmethod(load)

    if FRONTIER_CATEGORY not in radar.RADAR_CATEGORIES:
        radar.RADAR_CATEGORIES = (*radar.RADAR_CATEGORIES, FRONTIER_CATEGORY)
    original_build = radar.build_radar_candidates

    def build_radar_candidates(task_service, run_id: str, issue_input: dict[str, Any]):
        base = original_build(task_service, run_id, issue_input)
        extra = _extra_observation_candidates(radar, task_service, run_id, issue_input)
        return _rebalance_candidates(radar, base, extra)

    radar.build_radar_candidates = build_radar_candidates
    ConfigBundle._frontier_source_lanes_installed = True
