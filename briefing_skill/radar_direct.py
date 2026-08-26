"""Deterministic Radar selection with direct upstream copy.

The Radar lane used to send discovery candidates through the issue-synthesis
Agent, which rewrote already-good upstream Chinese summaries. This module
selects candidates and copies their frozen upstream title/summary fields
verbatim (or as a contiguous span of complete sentences) without any model
call, records hash/span provenance for every published character, and keeps
the upstream provider identity internal-only: public cards expose nothing but
the original web page's name and URL.

Selection happens after Deep/appendix URLs are known (the email build), and
the publication finalize stage records the final provenance once the final
card set can no longer change.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import ConfigBundle
from .freshness import published_age_days
from .radar_taxonomy import classify_radar_category
from .reader_writing_contract import text_contains_chinese
from .utils import canonicalize_url, content_hash, read_json, stable_hash, write_json

RADAR_DIRECT_COPY_VERSION = 1
RADAR_TAXONOMY_VERSION = 1
RADAR_SELECTION_POLICY_VERSION = 1

RADAR_TITLE_MAX_CHARS = 160
RADAR_TITLE_MIN_CHARS = 8
RADAR_PUBLIC_SUMMARY_MAX_CHARS = 260
RADAR_PUBLIC_SUMMARY_MIN_CHARS = 20
RADAR_MAX_AGE_DAYS = 7

# Classification preference from the radar taxonomy: concrete verticals win
# over the horizontal buckets, and the generic frontier comes last.
CATEGORY_PREFERENCE = ("存储与介质", "KVCache生态", "Agent生态", "AI Infra", "边界探索", "其他技术前沿")

TOPIC_PRIORITY_SCORE = {"highest": 20, "high": 15, "medium": 8, "low": 0}

ACADEMIC_SOURCE_HOSTS = {
    "arxiv.org",
    "openreview.net",
    "doi.org",
    "acm.org",
    "dl.acm.org",
    "ieee.org",
    "ieeexplore.ieee.org",
}
SOCIAL_SOURCE_HOSTS = {"x.com", "twitter.com", "youtube.com", "youtu.be"}
NEWS_ANALYSIS_HOSTS = {
    "reuters.com",
    "marktechpost.com",
    "the-decoder.com",
    "techcrunch.com",
    "venturebeat.com",
}

# Deterministic out-of-scope blocklist (design §9.2): financing, executive
# statements, policy/legal disputes, consumer apps and ranking-only news.
SCOPE_BLOCKED_TERMS = (
    "palantir", "alex karp", "ceo", "chief strategy officer", "cfo", "earnings", "quarterly",
    "stock", "shares", "revenue", "valuation", "market cap", "ipo", "融资", "财报", "股价", "营收",
    "估值", "市值", "上市", "募资", "并购", "收购", "高管",
    "marxism", "马克思主义", "ai act", "regulation", "regulator", "government", "senate", "congress",
    "copyright", "lawsuit", "法院", "法案", "监管", "版权", "政策争议",
    "electronic arts", " ea ", "playable game", "game world", "gaming", "suno", "steam",
    "游戏", "影视", "音乐版权", "consumer app", "消费应用",
    "leaderboard", "排行榜", "登顶榜单",
)
# A candidate needs at least one concrete technical allow term; blocked terms
# then disqualify it unless the story is really about the technical change.
SCOPE_ALLOWED_TERMS = (
    "agent", "智能体", "coding", "code search", "repository", "tool call", "context",
    "llm", "model", "benchmark", "reasoning", "模型", "大模型", "评测", "推理",
    "serving", "inference", "runtime", "compiler", "kernel", "quantization", "调度", "运行时", "编译器",
    "gpu", "accelerator", "hbm", "hbf", "cxl", "nvme", "nand", "qlc", "tlc", "zns",
    "rdma", "smartnic", "dpu", "npu", "tpu", "asic", "chiplet",
    "memory", "cache", "storage", "network", "optical", "interconnect", "fabric",
    "芯片", "加速器", "内存", "缓存", "存储", "网络", "光互联",
    "distributed training", "collective", "cluster", "observability", "failure recovery",
    "分布式训练", "集群", "可观测", "故障恢复", "ai infrastructure", "ai infra",
)

_SENTENCE_END_RE = re.compile(r"[。！？!?]|\.(?=\s|$)")
_COMPLETE_END_RE = re.compile(r"[。！？.!?](?:[”’\"』」）)\]]*)$")


def configured_timezone(root) -> str | None:
    """The configured timezone name, or None when no config is readable."""
    from .config import ConfigError
    from .paths import Paths

    try:
        settings = dict(ConfigBundle.load(Paths(Path(root))).settings or {})
    except (ConfigError, OSError):
        return None
    return str(settings.get("timezone") or "Asia/Shanghai")


def direct_copy_mode(service_or_root) -> bool | None:
    """Direct-copy mode from config; ``None`` when no config is readable.

    ``None`` callers (e.g. the release gate on a bare fixture tree) must treat
    the presence of radar-direct.json as "direct records exist and must
    verify" instead of assuming either mode.
    """
    if isinstance(service_or_root, (str, Path)):
        from .config import ConfigError
        from .paths import Paths

        try:
            bundle = ConfigBundle.load(Paths(Path(service_or_root)))
        except (ConfigError, OSError):
            return None
        policy = dict(bundle.scoring.get("radar") or {})
    else:
        config = getattr(service_or_root, "config", None)
        scoring = getattr(config, "scoring", None)
        if scoring is None:
            return None
        policy = dict(scoring.get("radar") or {})
    return bool(policy.get("direct_copy", True))


def direct_copy_enabled(service_or_root) -> bool:
    """Read the ``radar.direct_copy`` switch (default on once installed)."""
    mode = direct_copy_mode(service_or_root)
    if mode is not None:
        return mode
    # Unreadable config: keep the default-on, fail-closed posture.
    return True


def _clean_text(value: Any, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    return text if limit is None or len(text) <= limit else text[:limit].rstrip()


# Same normalization the send path uses for radar_history titles, so cross-period
# title dedup cannot be bypassed by whitespace/casing differences.
_REFERENCE_STRIP_RE = re.compile(r"[^0-9a-zA-Z\u4e00-\u9fff²]+")


def _normalise_reference(value: Any) -> str:
    return _REFERENCE_STRIP_RE.sub("", str(value or "")).lower()


def public_source_name(url: str) -> str:
    """Radar cards link to the original web page; never to the discovery brand."""
    host = (urlparse(url).hostname or "source").removeprefix("www.")
    if host.endswith("arxiv.org"):
        return "arXiv"
    if host.endswith("github.com") or host.endswith("github.io"):
        return "GitHub"
    return _clean_text(host, 60)


def public_source_lane(url: str) -> str:
    """Classify the original linked page, independent of the AI HOT provider.

    AI HOT supplies the frozen Chinese reader copy. The linked page may be in
    any language; this lane exists only to preserve a useful mix of papers,
    official company/engineering posts, individual builders, news and social.
    """

    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if any(host == value or host.endswith(f".{value}") for value in ACADEMIC_SOURCE_HOSTS):
        return "academic_primary"
    if any(host == value or host.endswith(f".{value}") for value in SOCIAL_SOURCE_HOSTS):
        return "social"
    if any(host == value or host.endswith(f".{value}") for value in NEWS_ANALYSIS_HOSTS):
        return "news_analysis"
    return "industry_builder"


def _github_project(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() not in {"github.com", "www.github.com"}:
        return ""
    parts = [part.lower() for part in parsed.path.split("/") if part]
    return f"github:{parts[0]}/{parts[1]}" if len(parts) >= 2 else ""


def radar_scope_is_technical(title: str, summary: str) -> bool:
    text = f" {title} {summary} ".lower()
    if not any(term in text for term in SCOPE_ALLOWED_TERMS):
        return False
    return not any(term in text for term in SCOPE_BLOCKED_TERMS)


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in _SENTENCE_END_RE.finditer(text):
        end = match.end()
        while end < len(text) and text[end] in "”’\"』」）)]":
            end += 1
        spans.append((spans[-1][1] if spans else 0, end))
    return spans


def select_public_summary(summary: str, *, limit: int = RADAR_PUBLIC_SUMMARY_MAX_CHARS) -> tuple[str, int, int] | None:
    """Pick the whole frozen summary or a contiguous span of complete sentences.

    Returns ``(public_text, span_start, span_end)`` into the whitespace-
    normalized source summary so tests can prove the published characters are
    an exact substring with no new facts. ``None`` means the candidate has no
    usable complete Chinese sentence and must be dropped, never rewritten.
    """
    text = " ".join(str(summary or "").split()).strip()
    if not text or not text_contains_chinese(text):
        return None
    if len(text) <= limit and _COMPLETE_END_RE.search(text):
        return text, 0, len(text)
    spans = _sentence_spans(text)
    # Allow starting at the first or second sentence at most: skipping the
    # opening sentence entirely would misrepresent the upstream summary.
    for start_index in (0, 1):
        if start_index >= len(spans):
            break
        chosen_start = spans[start_index][0]
        count = 0
        last_end = chosen_start
        for _, end in spans[start_index:]:
            if count >= 2:
                break
            if end - chosen_start > limit:
                break
            last_end = end
            count += 1
        total = last_end - chosen_start
        if count and RADAR_PUBLIC_SUMMARY_MIN_CHARS <= total <= limit:
            public = text[chosen_start:last_end]
            if _COMPLETE_END_RE.search(public) and text_contains_chinese(public):
                return public, chosen_start, last_end
    return None


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    try:
        value = row.get("payload_json") or row.get("payload")
        return json.loads(value) if isinstance(value, str) else dict(value or {})
    except (TypeError, json.JSONDecodeError):
        return {}


# Copy variants are tried in this lane order so a boost-driven English or
# truncated winner never silently kills another lane's usable Chinese copy.
VARIANT_LANE_ORDER = {"selected": 0, "daily": 1, "all": 2, "paper": 3}


def _category(title: str, summary: str, *, frontier: bool) -> str:
    value = classify_radar_category(title, summary)
    if value == "其他":
        return "边界探索" if frontier else "其他技术前沿"
    return value


def _internal_priority(candidate: dict[str, Any]) -> float:
    """Deterministic ordering only; never published and never a model call."""
    lanes = candidate["upstream_lanes"]
    score = 0.0
    if "hot" in lanes:
        score += 40
    if "selected" in lanes:
        score += 30
    if "daily" in lanes:
        score += 20
    score += TOPIC_PRIORITY_SCORE.get(str(candidate.get("topic_priority") or "low"), 0)
    if str(candidate.get("source_level") or "").upper() == "A":
        score += 10
    if len(set(lanes)) >= 2:
        score += 5
    if candidate.get("age_days") is not None and candidate["age_days"] <= 1:
        score += 5
    return score


def _ordered_variants(payload: dict[str, Any], primary_summary: str, primary_field: str) -> list[dict[str, Any]]:
    variants = [
        {
            "lane": str(variant.get("lane") or ""),
            "lane_key": str(variant.get("lane_key") or ""),
            "source_field": str(variant.get("source_field") or ""),
            "summary": str(variant.get("summary") or ""),
        }
        for variant in payload.get("aihot_copy_variants") or []
    ]
    if primary_summary and not any(variant["summary"] == primary_summary for variant in variants):
        variants.append(
            {
                "lane": str(payload.get("aihot_lane") or ""),
                "lane_key": "",
                "source_field": primary_field,
                "summary": primary_summary,
            }
        )
    variants.sort(key=lambda variant: VARIANT_LANE_ORDER.get(variant["lane"], 9))
    return variants


def _title_source_field(payload: dict[str, Any], title: str) -> str:
    raw = payload.get("aihot")
    if isinstance(raw, dict):
        normalized = " ".join(str(title or "").split())
        for field in ("title", "originalTitle"):
            if " ".join(str(raw.get(field) or "").split()) == normalized:
                return field
    return "title"


def _report_date_reference(date_to: str, settings: dict[str, Any]):
    """End of the report day in the CONFIGURED timezone, then aware datetime.

    A bare report date is the active run's ``date_to``; interpreting it as
    UTC day-end would silently drop timezone-boundary items (AGENTS: the
    final date must come from the active run and configured timezone).
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz_name = str((settings or {}).get("timezone") or "Asia/Shanghai")
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid configured timezone for radar freshness: {tz_name}") from exc
    try:
        day = datetime.strptime(str(date_to).strip()[:10], "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"invalid active run report date: {date_to}") from exc
    return day.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=tz)


def _public_url_error(url: str) -> str | None:
    """Public radar cards link to a specific original page, never the upstream."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return "not an absolute http(s) URL"
    if host == "aihot.virxact.com" or host.endswith(".aihot.virxact.com"):
        return "upstream discovery URL"
    path = (parsed.path or "").strip("/")
    query = (parsed.query or "").strip()
    if not path and not query:
        return "site-root URL, not a specific original page"
    if not path and query:
        # Query-routed article URLs (e.g. example.com/?p=123) are specific
        # pages even though the path is empty.
        return None
    return None


def _candidate_from_row(
    row: dict[str, Any],
    *,
    run_id: str,
    reference_date: str,
    frontier: bool,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    payload = _payload(row)
    raw = payload.get("aihot") if isinstance(payload.get("aihot"), dict) else {}
    # The public URL must be the original web page; aihot-only or relative
    # fallbacks stay internal observations.
    url = str(row.get("original_url") or "").strip()
    url_error = _public_url_error(url) if url else "missing original URL"
    if url_error:
        return None
    canonical = canonicalize_url(url)
    if not canonical:
        return None

    # Freshness is measured against the active run's report date (end of day
    # in the configured timezone) so the same frozen run replays identically
    # no matter when it is resumed. Daily items without their own upstream
    # date use the daily window as an internal recall bound only — the public
    # card shows no fabricated date.
    recall_reference = str(row.get("published_at") or "") or str(payload.get("aihot_daily_date") or "")
    age = published_age_days(recall_reference or None, reference=_report_date_reference(reference_date, context["settings"]))
    if age is None or age > RADAR_MAX_AGE_DAYS:
        return None

    # Titles are never hard-truncated: a title that does not fit the public
    # contract is dropped rather than cut mid-structure.
    title = _clean_text(row.get("title"))
    if not title or len(title) < RADAR_TITLE_MIN_CHARS or len(title) > RADAR_TITLE_MAX_CHARS:
        return None
    if canonical in context["history_urls"]:
        return None
    title_key = _normalise_reference(title)
    if title_key and title_key in context["history_titles"]:
        return None
    # Cross-period identity also covers the upstream story/item ids so the
    # same event cannot republish under a new report URL and title.
    upstream_item_id = str(row.get("external_id") or "") if row.get("source_id") == "aihot" else ""
    story_id = str(payload.get("aihot_story_id") or "")
    if upstream_item_id and upstream_item_id in context["history_item_ids"]:
        return None
    if story_id and story_id in context["history_story_ids"]:
        return None

    primary_summary = " ".join(str(row.get("summary") or "").split())
    primary_field = "summary"
    if primary_summary:
        if isinstance(raw, dict):
            for field in ("summary", "description"):
                if " ".join(str(raw.get(field) or "").split()) == primary_summary:
                    primary_field = field
                    break
    copy: tuple[str, int, int, str, str] | None = None
    for variant in _ordered_variants(payload, primary_summary, primary_field):
        if variant["source_field"] not in ("summary", "description"):
            # `reason` is the upstream editorial recommendation: internal only.
            continue
        selected = select_public_summary(variant["summary"])
        if selected is not None:
            public_summary, span_start, span_end = selected
            copy = (public_summary, span_start, span_end, variant["source_field"], variant.get("lane_key") or "")
            break
    if copy is None:
        return None
    public_summary, span_start, span_end, source_field, variant_lane_key = copy
    source_text = " ".join(str(variant["summary"]).split())
    published_source = "upstream_item" if row.get("published_at") else "none"
    candidate = {
        "candidate_id": str(row.get("id") or ""),
        "run_id": run_id,
        "title": title,
        "summary": public_summary,
        "url": url,
        "source_name": public_source_name(url),
        "source_lane": public_source_lane(url),
        "source_level": str(row.get("source_level") or "C").upper(),
        "source_id": str(row.get("source_id") or ""),
        "published_at": str(row.get("published_at") or "")[:10],
        "published_at_source": published_source,
        "category": _category(title, public_summary, frontier=frontier),
        "age_days": age,
        "upstream_lanes": list(payload.get("aihot_lanes") or []),
        "upstream_item_id": upstream_item_id,
        "story_id": story_id,
        "canonical_url": canonical,
        "identity_key": str(row.get("identity_key") or ""),
        "github_project": _github_project(url),
        "normalized_title": title_key,
        "topic_priority": context["topics"].get(str(row.get("topic_hint") or ""), "low"),
        "upstream_score": raw.get("score"),
        "evidence_kind": "discovery_signal",
        "reader_copy_mode": "upstream_verbatim",
        "title_provenance": {
            "source_field": _title_source_field(payload, title),
            "source_text": title,
            "selected_span_start": 0,
            "selected_span_end": len(title),
            "public_text_hash": f"sha256:{content_hash(title)}",
        },
        "copy_provenance": {
            "source_field": source_field,
            "lane_key": variant_lane_key,
            "source_text": source_text,
            "source_text_hash": f"sha256:{content_hash(source_text)}",
            "selected_span_start": span_start,
            "selected_span_end": span_end,
            "public_text_hash": f"sha256:{content_hash(public_summary)}",
        },
    }
    candidate["internal_priority"] = _internal_priority(candidate)
    if not radar_scope_is_technical(title, public_summary):
        candidate["excluded_reason"] = "out_of_scope"
    return candidate


def normalized_radar_candidates(service, run_id: str, issue_data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Normalize this run's discovery rows into direct-copy candidates.

    Scope, freshness (relative to the active run's report date), history dedup
    and Chinese-copy checks happen here so the ``raw_eligible`` publication
    contract only counts legal candidates. Deep and appendix collisions are
    filtered by the caller once the final issue content is known.
    """
    reference_date = str((issue_data or {}).get("date_to") or "")
    if not reference_date:
        raise ValueError(
            "direct-copy radar requires the active run report date (issue date_to); "
            "refusing to fall back to the wall clock"
        )
    db = service.db
    rows = db.fetchall("SELECT * FROM raw_items WHERE run_id=?", (run_id,))
    history = db.fetchall(
        "SELECT canonical_url, normalized_title, upstream_item_id, story_id FROM radar_history"
    )
    frontier_ids = {
        str(row.get("raw_item_id"))
        for row in db.fetchall(
            "SELECT DISTINCT raw_item_id FROM candidates WHERE run_id=? AND topic_id='frontier_exploration'",
            (run_id,),
        )
    }
    context = {
        "topics": {
            str(topic.get("id")): str(topic.get("aihot_priority") or "low")
            for topic in service.config.topic_list()
        },
        "settings": dict(getattr(service.config, "settings", None) or {}),
        "history_urls": {
            canonicalize_url(row.get("canonical_url")) for row in history if row.get("canonical_url")
        },
        "history_titles": {_normalise_reference(row.get("normalized_title")) for row in history if row.get("normalized_title")},
        "history_item_ids": {str(row.get("upstream_item_id")) for row in history if row.get("upstream_item_id")},
        "history_story_ids": {str(row.get("story_id")) for row in history if row.get("story_id")},
    }

    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate = _candidate_from_row(
            row,
            run_id=run_id,
            reference_date=reference_date,
            frontier=str(row.get("id")) in frontier_ids,
            context=context,
        )
        if candidate is None:
            continue
        key = _identity(candidate)
        existing = merged.get(key)
        if existing is None:
            merged[key] = candidate
            continue
        # Same identity seen in another lane/source: keep the stronger record
        # but preserve every lane and the story identity of either row.
        lanes = list(dict.fromkeys([*existing["upstream_lanes"], *candidate["upstream_lanes"]]))
        story = existing.get("story_id") or candidate.get("story_id")
        base = candidate if candidate["internal_priority"] > existing["internal_priority"] else existing
        base["upstream_lanes"] = lanes
        base["story_id"] = story
        merged[key] = base
        if story:
            merged[f"story_id:{story}"] = base

    candidates = [c for c in merged.values() if not c.get("excluded_reason")]
    candidates.sort(
        key=lambda c: (
            -float(c["internal_priority"]),
            -float(c.get("upstream_score") or 0),
            str(c.get("published_at") or ""),
            str(c.get("canonical_url") or ""),
        )
    )
    return candidates


def _identity(candidate: dict[str, Any]) -> str:
    for key in ("story_id", "upstream_item_id", "canonical_url", "identity_key"):
        value = str(candidate.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    return f"title:{candidate.get('normalized_title') or ''}"


_SAME_EVENT_STOP_TOKENS = frozenset({
    "and", "or", "the", "with", "for", "from", "new", "into", "via", "its", "their",
    "introduces", "introducing", "unveils", "unveiling", "launches", "launching",
    "announces", "announcing", "announced", "releases", "released", "official",
    "blog", "news", "press", "big", "leap", "more", "most", "first", "ai",
    "performance", "compute",
    "全新", "推出", "发布", "搭载", "性能", "算力", "大幅", "跃升", "提升",
})

# Consumer-availability signatures: same-launch posts that mainly announce
# pre-order/ship dates are product news; the technical change post wins.
_AVAILABILITY_MARKERS = (
    "预购", "开售", "发售", "即日起", "购买", "售价", "起售",
    "pre-order", "preorder", "pre order", "available today", "on sale",
    "goes on sale", "ships today", "order today",
)


def _has_availability_marker(candidate: dict[str, Any]) -> bool:
    text = f" {candidate.get('title') or ''} {candidate.get('summary') or ''} ".lower()
    return any(marker in text for marker in _AVAILABILITY_MARKERS)


def _identifier_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9\-]+", str(text or "").lower())
        if len(token) >= 2 and token not in _SAME_EVENT_STOP_TOKENS and not token.isdigit()
    }


def _same_event_tokens(candidate: dict[str, Any]) -> set[str]:
    """Distinctive identifiers come from the title and the URL path slug only.

    Scheme, host and TLD fragments (https, www, com, ...) are shared by every
    item of a publisher and must never count as event identifiers.
    """

    path = urlparse(str(candidate.get("url") or "")).path
    return _identifier_tokens(f"{candidate.get('title') or ''} {path}")


def _registrable_domain(url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").lower().removeprefix("www.")
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _technical_scope_score(candidate: dict[str, Any]) -> int:
    text = f" {candidate.get('title') or ''} {candidate.get('summary') or ''} ".lower()
    return sum(1 for term in SCOPE_ALLOWED_TERMS if term in text)


def _drop_same_event_duplicates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse same-launch announce posts: one publisher, one day, shared identifiers.

    The upstream hot-list ranks launch-day posts from the same vendor as separate
    stories (for example a product-availability post next to the chip-architecture
    post). Same publisher domain plus same publication date plus at least two shared
    distinctive identifier tokens (model names, product lines) is treated as one
    story, matching the "one card per story" publication rule. GitHub candidates are
    exempt because project-level dedup already applies. The surviving card prefers
    the one without consumer-availability markers, then the strongest technical
    scope vocabulary, then the higher priority.
    """

    parents = list(range(len(candidates)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        parents[find(left)] = find(right)

    prepared: list[dict[str, Any] | None] = []
    for candidate in candidates:
        if candidate.get("github_project"):
            prepared.append(None)
            continue
        tokens = _same_event_tokens(candidate)
        prepared.append(
            {
                "domain": _registrable_domain(candidate.get("canonical_url") or candidate.get("url") or ""),
                "date": str(candidate.get("published_at") or "")[:10],
                "tokens": tokens,
            }
        )
    for i in range(len(candidates)):
        left = prepared[i]
        if not left or not left["domain"] or not left["date"]:
            continue
        for j in range(i + 1, len(candidates)):
            right = prepared[j]
            if not right or left["domain"] != right["domain"] or left["date"] != right["date"]:
                continue
            domain_token = left["domain"].split(".")[0]
            shared = {token for token in left["tokens"] & right["tokens"] if token != domain_token}
            if len(shared) >= 2:
                union(i, j)
    groups: dict[int, list[int]] = {}
    for index in range(len(candidates)):
        groups.setdefault(find(index), []).append(index)
    dropped: set[int] = set()
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(
            key=lambda idx: (
                1 if _has_availability_marker(candidates[idx]) else 0,
                -_technical_scope_score(candidates[idx]),
                -float(candidates[idx].get("internal_priority") or 0),
                str(candidates[idx].get("canonical_url") or ""),
            )
        )
        for index in members[1:]:
            dropped.add(index)
    return [candidate for index, candidate in enumerate(candidates) if index not in dropped]


def select_radar_items(
    candidates: list[dict[str, Any]],
    *,
    total_max: int,
    per_category: int,
    industry_builder_min: int = 0,
) -> list[dict[str, Any]]:
    """Deterministic bounded selection: <= total_max, <= per_category, one per story/project."""
    category_rank = {name: index for index, name in enumerate(CATEGORY_PREFERENCE)}
    ordered = sorted(candidates, key=lambda c: category_rank.get(c["category"], 99))

    selected: list[dict[str, Any]] = []
    state: dict[str, Any] = {"total": 0, "category": {}, "story": set(), "project": set(), "url": set()}

    def take(candidate: dict[str, Any]) -> bool:
        if state["total"] >= total_max:
            return False
        category = candidate["category"]
        if state["category"].get(category, 0) >= per_category:
            return False
        if candidate.get("story_id") and candidate["story_id"] in state["story"]:
            return False
        if candidate.get("github_project") and candidate["github_project"] in state["project"]:
            return False
        if candidate["canonical_url"] in state["url"]:
            return False
        selected.append(candidate)
        state["total"] += 1
        state["category"][category] = state["category"].get(category, 0) + 1
        if candidate.get("story_id"):
            state["story"].add(candidate["story_id"])
        if candidate.get("github_project"):
            state["project"].add(candidate["github_project"])
        state["url"].add(candidate["canonical_url"])
        return True

    priority_order = sorted(candidates, key=lambda c: -float(c["internal_priority"]))

    # Pass one spreads coverage across categories. When an industry/builder
    # reserve is configured, prefer an official company/engineering/individual
    # source in each category while continuing to publish AI HOT's frozen Chinese
    # copy and linking the original page in whatever language it uses.
    for category in CATEGORY_PREFERENCE:
        rows = [candidate for candidate in priority_order if candidate["category"] == category]
        if not rows:
            continue
        preferred = next(
            (row for row in rows if row.get("source_lane") == "industry_builder"),
            rows[0],
        ) if industry_builder_min else rows[0]
        take(preferred)

    # Pass two meets the configured source-mix floor without weakening category,
    # story, project or URL deduplication.
    target = min(max(0, industry_builder_min), total_max)
    while sum(row.get("source_lane") == "industry_builder" for row in selected) < target:
        added = False
        for candidate in priority_order:
            if candidate.get("source_lane") != "industry_builder" or candidate in selected:
                continue
            if take(candidate):
                added = True
                break
        if not added:
            break

    # Pass three fills remaining capacity strictly by internal priority.
    for candidate in priority_order:
        take(candidate)
    return selected


def _category_order() -> tuple[str, ...]:
    from . import radar_signal_synthesis as radar

    categories = tuple(radar.RADAR_CATEGORIES)
    if "边界探索" not in categories:
        categories = (*categories, "边界探索")
    return categories


def _run_candidates(service, run_id: str, issue_data: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    """Shared per-build cache so email groups and reserve fill agree exactly."""
    if not run_id:
        return None
    cache = getattr(service, "_radar_direct_cache", None)
    if cache is None:
        cache = {}
        service._radar_direct_cache = cache
    if run_id not in cache:
        cache[run_id] = normalized_radar_candidates(service, run_id, issue_data)
        reference = getattr(service, "_radar_direct_reference", None)
        if reference is None:
            reference = {}
            service._radar_direct_reference = reference
        settings = dict(getattr(service.config, "settings", None) or {})
        reference[run_id] = {
            "date": str((issue_data or {}).get("date_to") or ""),
            "timezone": str(settings.get("timezone") or "Asia/Shanghai"),
        }
    return cache[run_id]


def direct_copy_reserve_candidates(
    service, run_id: str, issue_data: dict[str, Any] | None = None
) -> list[dict[str, Any]] | None:
    """Ordered legal candidates for the publication reserve contract.

    Returns ``None`` when direct copy is disabled (or the caller is a service
    without run data access) so the legacy synthesis reserve path keeps
    working unchanged.
    """
    if not direct_copy_enabled(service) or not run_id or not getattr(service, "db", None):
        return None
    return _run_candidates(service, run_id, issue_data)


def verify_copy_integrity(item: dict[str, Any]) -> list[str]:
    """Prove the public title and summary are exact spans of frozen upstream fields."""
    errors: list[str] = []
    provenance = item.get("copy_provenance") or {}
    source_text = str(provenance.get("source_text") or "")
    public_text = str(item.get("summary") or "")
    start = int(provenance.get("selected_span_start") or 0)
    end = int(provenance.get("selected_span_end") or 0)
    if not source_text or not public_text:
        return ["missing copy provenance text"]
    if provenance.get("source_field") == "reason":
        errors.append("public summary comes from the upstream editorial `reason`, which is internal-only")
    if source_text[start:end] != public_text:
        errors.append("public summary is not the recorded span of the frozen source text")
    if provenance.get("source_text_hash") != f"sha256:{content_hash(source_text)}":
        errors.append("source text hash mismatch")
    if provenance.get("public_text_hash") != f"sha256:{content_hash(public_text)}":
        errors.append("public text hash mismatch")
    if not _COMPLETE_END_RE.search(public_text):
        errors.append("public summary ends with dangling punctuation")

    title_provenance = item.get("title_provenance")
    public_title = str(item.get("title") or "")
    if not title_provenance or not public_title:
        errors.append("missing title provenance")
    else:
        t_start = int(title_provenance.get("selected_span_start") or 0)
        t_end = int(title_provenance.get("selected_span_end") or 0)
        title_source = str(title_provenance.get("source_text") or "")
        if not title_source or title_source[t_start:t_end] != public_title:
            errors.append("public title is not the recorded span of the frozen title field")
        if title_provenance.get("public_text_hash") != f"sha256:{content_hash(public_title)}":
            errors.append("public title hash mismatch")
    return errors


def record_direct_publication(
    service,
    *,
    issue_id: str | None,
    run_id: str,
    final_groups: list[dict[str, Any]],
    contract: dict[str, Any],
) -> None:
    """Persist provenance, compat radar_signals and ledger decisions for the FINAL set.

    Called by the publication finalize stage after deep/appendix dedup so the
    recorded selection can no longer drift from the rendered cards. In direct
    mode the provenance file is written even for an empty final set so the
    release gate can fail closed on a missing record.
    """
    if not direct_copy_enabled(service):
        return
    final_items = [
        dict(item, category=item.get("category") or item.get("category_key") or group.get("name"))
        for group in final_groups or []
        for item in group.get("items") or []
    ]
    if final_items and not all(item.get("copy_provenance") for item in final_items):
        return
    for item in final_items:
        item.setdefault("radar_id", stable_hash("radar", run_id, canonicalize_url(item.get("url"))))

    _write_provenance_file(service, run_id, final_items, contract)
    _write_compat_synthesis(service, issue_id, run_id, final_items)
    # Link the manifest back to this exact provenance document.
    document = read_json(service.root / "workspace" / "runs" / run_id / "issue" / "radar-direct.json", {}) or {}
    if document.get("selection_hash"):
        contract["selection_hash"] = document["selection_hash"]
    # The candidate pool is only needed for ledger decisions; reuse the
    # same-build cache instead of rebuilding (which would need issue_data).
    pool = (getattr(service, "_radar_direct_cache", None) or {}).get(run_id) or []
    _update_ledger_decisions(run_id, pool, final_items, service)


def _frozen_input_sha256(service, run_id: str) -> str | None:
    """Bind the selection to the exact frozen AI Hot responses it was derived from."""
    import hashlib

    path = service.root / "workspace" / "runs" / run_id / "source-cache" / "aihot" / "freeze.json"
    if not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _selection_binding(document: dict[str, Any]) -> dict[str, Any]:
    """Bind over the PERSISTED version fields, not live code constants.

    Old runs keep verifying against the versions that produced them, and a
    tampered version field changes the recomputed hash instead of passing.
    """
    from .adapters.aihot import AIHOT_CONNECTOR_VERSION

    items = document.get("items") or []
    return {
        "connector_version": document.get("connector_version", AIHOT_CONNECTOR_VERSION),
        "direct_copy_version": document.get("direct_copy_version", RADAR_DIRECT_COPY_VERSION),
        "taxonomy_version": document.get("radar_taxonomy_version", RADAR_TAXONOMY_VERSION),
        "selection_policy_version": document.get(
            "radar_selection_policy_version", RADAR_SELECTION_POLICY_VERSION
        ),
        "run_id": document.get("run_id"),
        "reference_date": document.get("reference_date"),
        "timezone": document.get("timezone"),
        "frozen_input_sha256": document.get("frozen_input_sha256"),
        "contract": document.get("selection_contract"),
        "items": [
            {
                "radar_id": item.get("radar_id"),
                "category": item.get("category"),
                "title_hash": content_hash(item.get("title")),
                "summary_hash": content_hash(item.get("summary")),
                "source_name_hash": content_hash(item.get("source_name")),
                "url": canonicalize_url((item.get("source_urls") or [None])[0]),
                "published_at": item.get("published_at"),
            }
            for item in items
        ],
    }


def _selection_hash(service, run_id: str, final_items: list[dict[str, Any]], contract: dict[str, Any]) -> str:
    """Bind the selection to frozen input, rule versions and every public field.

    Design §7.4: the selection hash must cover the frozen input hash, taxonomy
    and selection-policy versions, and the public field hashes — not just the
    URL list, so an upstream copy change under a stable URL invalidates it.
    """
    reference = (getattr(service, "_radar_direct_reference", None) or {}).get(run_id) or {}
    binding = _selection_binding(
        {
            "run_id": run_id,
            "reference_date": reference.get("date") or "",
            "timezone": reference.get("timezone") or "",
            "frozen_input_sha256": _frozen_input_sha256(service, run_id),
            "selection_contract": contract,
            "items": [
                {**item, "source_urls": [item.get("url")]} for item in final_items
            ],
        }
    )
    return stable_hash(json.dumps(binding, ensure_ascii=False, sort_keys=True), length=32)


def recompute_selection_hash(document: dict[str, Any]) -> str:
    """Recompute the selection hash from a persisted radar-direct document.

    Pure function of the recorded fields (including the stored
    frozen_input_sha256, so a stale freeze hash is caught separately instead
    of silently re-binding to a tampered input).
    """
    return stable_hash(json.dumps(_selection_binding(document), ensure_ascii=False, sort_keys=True), length=32)


def freeze_file_sha256(root, run_id: str) -> str | None:
    """Hash of the run's actual frozen AI Hot responses (None if absent)."""
    import hashlib

    path = Path(root) / "workspace" / "runs" / run_id / "source-cache" / "aihot" / "freeze.json"
    if not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _lane_observations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every raw upstream observation in one lane payload.

    Item lanes expose ``items``/``data`` at the top level; the daily report
    nests them under ``report.sections[].items``.
    """
    observations: list[dict[str, Any]] = []
    for raw in payload.get("items") or payload.get("data") or []:
        if isinstance(raw, dict):
            observations.append(raw)
    report = payload.get("report") if isinstance(payload.get("report"), dict) else None
    for section in (report or {}).get("sections") or []:
        for raw in section.get("items") or []:
            if isinstance(raw, dict):
                observations.append(raw)
    return observations


def _observation_identity(raw: dict[str, Any]) -> tuple[str, str]:
    links = raw.get("links") or {}
    raw_id = str(raw.get("publicId") or raw.get("id") or "")
    from .adapters.aihot import AIHOT_ITEM_ID_RE

    if not raw_id:
        match = AIHOT_ITEM_ID_RE.search(str(links.get("aihot") or ""))
        raw_id = match.group(1) if match else ""
    return raw_id, canonicalize_url(links.get("original") or raw.get("url") or "")


def locate_frozen_source(freeze: dict[str, Any], item: dict[str, Any]) -> dict[str, str | None] | None:
    """Locate the true upstream title/summary text for an item inside the freeze.

    The item may appear in several lanes with different copy variants; the
    chosen public copy can come from any of them. Every identity-matching
    observation is therefore scanned until one whose field text equals the
    recorded provenance is found, so cross-lane Chinese fallbacks anchor to
    the lane that actually produced the copy. Returns ``None`` when no
    identity-matching observation exists at all.
    """
    item_id = str(item.get("upstream_item_id") or "")
    url = canonicalize_url((item.get("source_urls") or [None])[0])
    provenance = item.get("copy_provenance") or {}
    title_provenance = item.get("title_provenance") or {}
    summary_field = str(provenance.get("source_field") or "summary")
    title_field = str(title_provenance.get("source_field") or "title")
    wanted_summary = " ".join(str(provenance.get("source_text") or "").split())
    wanted_title = " ".join(str(title_provenance.get("source_text") or "").split())

    matched = False
    summary_text: str | None = None
    title_text: str | None = None
    preferred_lane_key = str(provenance.get("lane_key") or "")
    ordered_lanes = sorted(
        (freeze.get("lanes") or {}).items(),
        key=lambda pair: 0 if pair[0] == preferred_lane_key else 1,
    )
    for _, lane in ordered_lanes:
        payload = lane.get("payload") if isinstance(lane, dict) else None
        if not isinstance(payload, dict):
            continue
        for raw in _lane_observations(payload):
            raw_id, raw_url = _observation_identity(raw)
            if not ((item_id and raw_id == item_id) or (url and raw_url == url)):
                continue
            matched = True
            if summary_text is None and " ".join(str(raw.get(summary_field) or "").split()) == wanted_summary:
                summary_text = wanted_summary
            if title_text is None and " ".join(str(raw.get(title_field) or "").split()) == wanted_title:
                title_text = wanted_title
    if not matched:
        return None
    return {"summary": summary_text, "title": title_text}


def _write_provenance_file(service, run_id: str, final_items: list[dict[str, Any]], contract: dict[str, Any]) -> None:
    path = service.root / "workspace" / "runs" / run_id / "issue" / "radar-direct.json"
    from .adapters.aihot import AIHOT_CONNECTOR_VERSION

    reference = (getattr(service, "_radar_direct_reference", None) or {}).get(run_id) or {}
    write_json(
        path,
        {
            "version": RADAR_DIRECT_COPY_VERSION,
            "run_id": run_id,
            "connector_version": AIHOT_CONNECTOR_VERSION,
            "direct_copy_version": RADAR_DIRECT_COPY_VERSION,
            "radar_taxonomy_version": RADAR_TAXONOMY_VERSION,
            "radar_selection_policy_version": RADAR_SELECTION_POLICY_VERSION,
            "reference_date": reference.get("date") or "",
            "timezone": reference.get("timezone") or "",
            "frozen_input_sha256": _frozen_input_sha256(service, run_id),
            "selection_hash": _selection_hash(service, run_id, final_items, contract),
            "selection_contract": contract,
            "items": [
                {
                    "radar_id": item["radar_id"],
                    "category": item.get("category"),
                    "title": item.get("title"),
                    "summary": item.get("summary"),
                    "source_name": item.get("source_name"),
                    "source_urls": [item.get("url")],
                    "published_at": item.get("published_at"),
                    "published_at_source": item.get("published_at_source") or "upstream_item",
                    "upstream_item_id": item.get("upstream_item_id") or None,
                    "story_id": item.get("story_id") or None,
                    "upstream_lanes": item.get("upstream_lanes") or [],
                    "internal_priority": item.get("internal_priority"),
                    "title_provenance": item.get("title_provenance"),
                    "copy_provenance": item.get("copy_provenance"),
                }
                for item in final_items
            ],
        },
    )


def _write_compat_synthesis(service, issue_id: str | None, run_id: str, final_items: list[dict[str, Any]]) -> None:
    """Keep ``synthesis.radar_signals`` consumers (archive/Pages) working.

    The writer is now deterministic code instead of the synthesis Agent; the
    object shape stays {category, signal, summary, source_urls}.
    """
    if not issue_id:
        return
    issue = service.db.fetchone("SELECT issue_json_path, synthesis_path FROM issues WHERE id=?", (issue_id,))
    if not issue:
        return
    signals = [
        {
            "category": item.get("category"),
            "signal": item.get("title"),
            "summary": item.get("summary"),
            "source_urls": [item.get("url")],
        }
        for item in final_items
    ]
    for column in ("synthesis_path", "issue_json_path"):
        relative = issue.get(column)
        if not relative:
            continue
        path = service.root / relative
        if not path.exists():
            continue
        document = read_json(path, {})
        synthesis = document if column == "synthesis_path" else document.get("synthesis")
        if not isinstance(synthesis, dict):
            continue
        if synthesis.get("radar_signals") == signals:
            continue
        synthesis["radar_signals"] = signals
        write_json(path, document)


def _update_ledger_decisions(run_id: str, pool: list[dict[str, Any]], final_items: list[dict[str, Any]], service) -> None:
    final_urls = {canonicalize_url(item.get("url")) for item in final_items}
    radar_ids = {canonicalize_url(item.get("url")): item.get("radar_id") for item in final_items}
    decisions = []
    for candidate in pool:
        if candidate.get("source_id") != "aihot":
            continue
        selected = candidate["canonical_url"] in final_urls
        decisions.append(
            {
                "upstream_item_id": candidate.get("upstream_item_id") or "",
                "canonical_original_url": candidate["canonical_url"],
                "selected_for_radar": selected,
                "radar_id": radar_ids.get(candidate["canonical_url"]) if selected else None,
                "decision_reason": "direct_copy_selected" if selected else "not_selected",
            }
        )
    service.db.update_radar_upstream_decisions(run_id, decisions)


def direct_copy_groups(service, issue_id: str | None, issue_data: dict[str, Any] | None):
    """Deterministic radar groups for the email build, or ``None`` to fall back."""
    if not direct_copy_enabled(service) or not getattr(service, "db", None):
        return None
    run_id = str((issue_data or {}).get("run_id") or "")
    if run_id:
        try:
            provenance = service.db.fetchone(
                "SELECT execution_mode FROM run_execution_provenance WHERE run_id=?",
                (run_id,),
            )
        except Exception:
            provenance = None
        if str((provenance or {}).get("execution_mode") or "") in {
            "demo",
            "fixture",
            "test",
        }:
            # Synthetic runs have no authentic frozen AI Hot response and must
            # never mint production direct-copy provenance from fixture text or
            # fall back to persisted production Radar rows.
            return []
    candidates = _run_candidates(service, run_id, issue_data)
    if candidates is None:
        return None

    policy = dict(getattr(service.config, "scoring", {}).get("radar") or {})
    total_max = max(1, int(policy.get("total_max", 8)))
    per_category = max(1, int(policy.get("max_per_category", 2)))
    industry_builder_min = max(0, int(policy.get("industry_builder_min", 0)))

    # Deep/appendix collisions are known by build time: exclude them before
    # selection so the selected set equals the final published set.
    from .publication_manifest import _appendix_urls, _github_projects

    forbidden = {
        canonicalize_url(source.get("url"))
        for item in (issue_data or {}).get("items") or []
        for source in item.get("sources") or []
        if canonicalize_url(source.get("url"))
    } | _appendix_urls(service)
    forbidden_projects = _github_projects(forbidden)
    pool = [
        candidate
        for candidate in candidates
        if candidate["canonical_url"] not in forbidden
        and not (candidate.get("github_project") and candidate["github_project"] in forbidden_projects)
    ]
    pool = _drop_same_event_duplicates(pool)

    selected = select_radar_items(
        pool,
        total_max=total_max,
        per_category=per_category,
        industry_builder_min=industry_builder_min,
    )

    groups: dict[str, list[dict[str, Any]]] = {}
    for candidate in selected:
        groups.setdefault(candidate["category"], []).append(
            {
                "title": candidate["title"],
                "summary": candidate["summary"],
                "url": candidate["url"],
                "source_name": candidate["source_name"],
                "published_at": candidate["published_at"],
                "sources": [
                    {
                        "url": candidate["url"],
                        "name": candidate["source_name"],
                        "title": candidate["title"],
                    }
                ],
                # internal candidate fields ride along so the publication
                # finalize stage can record provenance for the final set
                "category_key": candidate["category"],
                "canonical_url": candidate["canonical_url"],
                "copy_provenance": candidate["copy_provenance"],
                "title_provenance": candidate["title_provenance"],
                "published_at_source": candidate["published_at_source"],
                "upstream_lanes": candidate["upstream_lanes"],
                "upstream_item_id": candidate["upstream_item_id"],
                "story_id": candidate["story_id"],
                "internal_priority": candidate["internal_priority"],
                "evidence_kind": candidate["evidence_kind"],
                "reader_copy_mode": candidate["reader_copy_mode"],
            }
        )
    return [{"name": name, "items": groups[name]} for name in _category_order() if groups.get(name)]


def install_radar_direct_copy() -> None:
    """Prefer deterministic direct-copy radar over Agent-synthesized signals."""

    from .emailer import EmailService
    from .pipeline import Pipeline

    if getattr(Pipeline, "_radar_direct_copy_installed", False):
        return

    original_aihot_groups = EmailService._aihot_groups

    def aihot_groups(self, issue_date=None, *, issue_id=None, issue_data=None):
        groups = direct_copy_groups(self, issue_id, issue_data)
        if groups is not None:
            return groups
        return original_aihot_groups(self, issue_date, issue_id=issue_id, issue_data=issue_data)

    EmailService._aihot_groups = aihot_groups
    Pipeline._radar_direct_copy_installed = True
