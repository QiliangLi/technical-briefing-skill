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
from typing import Any
from urllib.parse import urlparse

from .config import ConfigBundle
from .freshness import published_age_days
from .radar_taxonomy import classify_radar_category
from .reader_writing_contract import text_contains_chinese
from .utils import canonicalize_url, content_hash, normalize_text, read_json, stable_hash, write_json

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


def direct_copy_enabled(service_or_root) -> bool:
    """Read the ``radar.direct_copy`` switch (default on once installed)."""
    config = getattr(service_or_root, "config", None)
    scoring = dict(getattr(config, "scoring", None) or {})
    if not scoring:
        root = getattr(service_or_root, "root", None)
        if root is not None:
            from .paths import Paths

            scoring = dict(ConfigBundle.load(Paths(root)).scoring or {})
    policy = dict(scoring.get("radar") or {})
    return bool(policy.get("direct_copy", True))


def _clean_text(value: Any, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    return text if limit is None or len(text) <= limit else text[:limit].rstrip()


def _normalise_title(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def public_source_name(url: str) -> str:
    """Radar cards link to the original web page; never to the discovery brand."""
    host = (urlparse(url).hostname or "source").removeprefix("www.")
    if host.endswith("arxiv.org"):
        return "arXiv"
    if host.endswith("github.com") or host.endswith("github.io"):
        return "GitHub"
    return _clean_text(host, 60)


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


def _summary_source_field(row: dict[str, Any]) -> str:
    payload = _payload(row)
    raw = payload.get("aihot")
    if isinstance(raw, dict):
        normalized = " ".join(str(row.get("summary") or "").split())
        for field in ("summary", "description", "reason"):
            value = " ".join(str(raw.get(field) or "").split())
            if value and value == normalized:
                return field
    return "summary"


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


def _identity(candidate: dict[str, Any]) -> str:
    for key in ("story_id", "upstream_item_id", "canonical_url", "identity_key"):
        value = str(candidate.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    return f"title:{candidate.get('normalized_title') or ''}"


def _candidate_from_row(
    row: dict[str, Any],
    *,
    run_id: str,
    frontier: bool,
    topic_priority: dict[str, str],
) -> dict[str, Any] | None:
    payload = _payload(row)
    raw = payload.get("aihot") if isinstance(payload.get("aihot"), dict) else {}
    url = str(row.get("original_url") or row.get("canonical_url") or "").strip()
    canonical = canonicalize_url(url)
    if not canonical:
        return None
    age = published_age_days(row.get("published_at"))
    if age is None or age > RADAR_MAX_AGE_DAYS:
        return None
    title = _clean_text(row.get("title"), RADAR_TITLE_MAX_CHARS)
    if not title or len(title) < RADAR_TITLE_MIN_CHARS:
        return None
    if canonical in topic_priority["history_urls"]:
        return None
    title_key = _normalise_title(title)
    if title_key and normalize_text(title_key) in topic_priority["history_titles"]:
        return None
    summary = str(row.get("summary") or "").strip()
    copy = select_public_summary(summary)
    if copy is None:
        return None
    public_summary, span_start, span_end = copy
    source_text = " ".join(summary.split())
    candidate = {
        "candidate_id": str(row.get("id") or ""),
        "run_id": run_id,
        "title": title,
        "summary": public_summary,
        "url": url,
        "source_name": public_source_name(url),
        "source_level": str(row.get("source_level") or "C").upper(),
        "source_id": str(row.get("source_id") or ""),
        "published_at": str(row.get("published_at") or "")[:10],
        "category": _category(title, public_summary, frontier=frontier),
        "age_days": age,
        "upstream_lanes": list(payload.get("aihot_lanes") or []),
        "upstream_item_id": str(row.get("external_id") or "") if row.get("source_id") == "aihot" else "",
        "story_id": str(payload.get("aihot_story_id") or ""),
        "canonical_url": canonical,
        "identity_key": str(row.get("identity_key") or ""),
        "github_project": _github_project(url),
        "normalized_title": title_key,
        "topic_priority": topic_priority["topics"].get(str(row.get("topic_hint") or ""), "low"),
        "upstream_score": raw.get("score"),
        "evidence_kind": "discovery_signal",
        "reader_copy_mode": "upstream_verbatim",
        "copy_provenance": {
            "source_field": _summary_source_field(row),
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

    Scope, freshness, history dedup and Chinese-copy checks happen here so the
    ``raw_eligible`` publication contract only counts legal candidates. Deep
    and appendix collisions are filtered by the caller once the final issue
    content is known.
    """
    db = service.db
    rows = db.fetchall("SELECT * FROM raw_items WHERE run_id=?", (run_id,))
    history = db.fetchall("SELECT canonical_url, normalized_title FROM radar_history")
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
        "history_urls": {
            canonicalize_url(row.get("canonical_url")) for row in history if row.get("canonical_url")
        },
        "history_titles": {
            normalize_text(row.get("normalized_title")) for row in history if row.get("normalized_title")
        },
    }

    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate = _candidate_from_row(
            row,
            run_id=run_id,
            frontier=str(row.get("id")) in frontier_ids,
            topic_priority=context,
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


def select_radar_items(candidates: list[dict[str, Any]], *, total_max: int, per_category: int) -> list[dict[str, Any]]:
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

    # Pass one spreads coverage across categories before any category doubles.
    for candidate in ordered:
        if state["category"].get(candidate["category"], 0) == 0:
            take(candidate)
    # Pass two fills remaining capacity strictly by internal priority.
    for candidate in sorted(candidates, key=lambda c: -float(c["internal_priority"])):
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
    """Prove the public summary is an exact substring of a frozen upstream field."""
    provenance = item.get("copy_provenance") or {}
    source_text = str(provenance.get("source_text") or "")
    public_text = str(item.get("summary") or "")
    start = int(provenance.get("selected_span_start") or 0)
    end = int(provenance.get("selected_span_end") or 0)
    if not source_text or not public_text:
        return ["missing copy provenance text"]
    errors: list[str] = []
    if source_text[start:end] != public_text:
        errors.append("public summary is not the recorded span of the frozen source text")
    if provenance.get("source_text_hash") != f"sha256:{content_hash(source_text)}":
        errors.append("source text hash mismatch")
    if provenance.get("public_text_hash") != f"sha256:{content_hash(public_text)}":
        errors.append("public text hash mismatch")
    if not _COMPLETE_END_RE.search(public_text):
        errors.append("public summary ends with dangling punctuation")
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
    recorded selection can no longer drift from the rendered cards. No-op when
    the final cards are not direct-copy candidates.
    """
    final_items = [dict(item) for group in final_groups or [] for item in group.get("items") or []]
    if not final_items or not all(item.get("copy_provenance") for item in final_items):
        return
    for item in final_items:
        item.setdefault("radar_id", stable_hash("radar", run_id, canonicalize_url(item.get("url"))))

    _write_provenance_file(service, run_id, final_items, contract)
    _write_compat_synthesis(service, issue_id, run_id, final_items)
    pool = _run_candidates(service, run_id, None) or []
    _update_ledger_decisions(run_id, pool, final_items, service)


def _write_provenance_file(service, run_id: str, final_items: list[dict[str, Any]], contract: dict[str, Any]) -> None:
    path = service.root / "workspace" / "runs" / run_id / "issue" / "radar-direct.json"
    write_json(
        path,
        {
            "version": RADAR_DIRECT_COPY_VERSION,
            "run_id": run_id,
            "radar_taxonomy_version": RADAR_TAXONOMY_VERSION,
            "radar_selection_policy_version": RADAR_SELECTION_POLICY_VERSION,
            "selection_hash": stable_hash(
                run_id, *[canonicalize_url(item.get("url")) for item in final_items], length=32
            ),
            "selection_contract": contract,
            "items": [
                {
                    "radar_id": item["radar_id"],
                    "category": item.get("category"),
                    "title": item.get("title"),
                    "summary": item.get("summary"),
                    "source_urls": [item.get("url")],
                    "published_at": item.get("published_at"),
                    "upstream_item_id": item.get("upstream_item_id") or None,
                    "story_id": item.get("story_id") or None,
                    "upstream_lanes": item.get("upstream_lanes") or [],
                    "internal_priority": item.get("internal_priority"),
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
    candidates = _run_candidates(service, run_id, issue_data)
    if candidates is None:
        return None

    policy = dict(getattr(service.config, "scoring", {}).get("radar") or {})
    total_max = max(1, int(policy.get("total_max", 8)))
    per_category = max(1, int(policy.get("max_per_category", 2)))

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

    selected = select_radar_items(pool, total_max=total_max, per_category=per_category)

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
