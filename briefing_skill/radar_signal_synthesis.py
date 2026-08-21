from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from .freshness import published_age_days
from .radar_direct import direct_copy_enabled
from .radar_taxonomy import classify_radar_category
from .reader_writing_contract import summary_is_reader_chinese, text_contains_chinese
from .utils import canonicalize_url, read_json


RADAR_CATEGORIES = ("AI Infra", "Agent生态", "KVCache生态", "存储与介质", "其他技术前沿")
MAX_CANDIDATES_PER_CATEGORY = 6
MAX_RADAR_CANDIDATES = 30
RADAR_SUMMARY_MAX_CHARS = 420
FORBIDDEN_SIGNAL_TEXT = (
    "high-confidence",
    "a-level rule match",
    "b-level rule match",
    "rule_score",
    "selection reason",
)


def _clean(value: Any, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    return text if limit is None or len(text) <= limit else text[:limit].rstrip()


def _normalise_title(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _category(title: str, summary: str) -> str:
    value = classify_radar_category(title, summary)
    return value if value != "其他" else "其他技术前沿"


def build_radar_candidates(task_service, run_id: str, issue_input: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a compact, broad candidate set for the already-existing synthesis task."""

    core_urls = {
        canonicalize_url(source.get("url"))
        for item in issue_input.get("items") or []
        for source in item.get("sources") or []
        if source.get("url")
    }
    history = task_service.db.fetchall("SELECT canonical_url,normalized_title FROM radar_history")
    history_urls = {
        canonicalize_url(row.get("canonical_url"))
        for row in history
        if row.get("canonical_url")
    }
    history_titles = {
        str(row.get("normalized_title") or "").lower()
        for row in history
        if row.get("normalized_title")
    }

    rows = task_service.db.fetchall(
        """
        SELECT r.id,r.title,r.summary,r.original_url,r.canonical_url,r.published_at,r.priority,
               r.discovery_source,r.source_id,r.source_level,r.discovery_only,
               c.relevance_reason
        FROM raw_items r
        LEFT JOIN candidates c ON c.raw_item_id=r.id AND c.run_id=?
        WHERE r.run_id=?
        ORDER BY r.priority DESC,r.published_at DESC,LENGTH(COALESCE(r.summary,'')) DESC,r.title
        """,
        (run_id, run_id),
    )

    level_rank = {"A": 0, "B": 1, "C": 2}
    rows.sort(
        key=lambda row: (
            level_rank.get(str(row.get("source_level") or "C").upper(), 3),
            -float(row.get("priority") or 0),
            published_age_days(row.get("published_at"))
            if published_age_days(row.get("published_at")) is not None
            else 9999,
            str(row.get("title") or ""),
        )
    )

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_urls: set[str] = set(history_urls)
    seen_titles: set[str] = set(history_titles)
    for row in rows:
        age = published_age_days(row.get("published_at"))
        if age is None or age > 7:
            continue
        url = str(row.get("original_url") or row.get("canonical_url") or "").strip()
        canonical = canonicalize_url(url)
        if not canonical or canonical in core_urls or canonical in seen_urls:
            continue
        # A concrete Chinese relevance reason outranks the raw (often English)
        # discovery abstract so judged sources stay usable as reader-facing Radar.
        reason = _clean(row.get("relevance_reason"), RADAR_SUMMARY_MAX_CHARS)
        summary = (
            reason
            if summary_is_reader_chinese(reason)
            else _clean(row.get("summary"), RADAR_SUMMARY_MAX_CHARS)
        )
        title = _clean(row.get("title"), 180)
        if not title or len(summary) < 20:
            continue
        title_key = _normalise_title(title)
        if title_key in seen_titles:
            continue
        category = _category(title, summary)
        if len(groups[category]) >= MAX_CANDIDATES_PER_CATEGORY:
            continue
        groups[category].append(
            {
                "candidate_id": str(row["id"]),
                "category": category,
                "title": title,
                "summary": summary,
                "url": url,
                "source_name": _clean(
                    row.get("discovery_source") or row.get("source_id") or "source", 80
                ),
                "source_level": str(row.get("source_level") or "C").upper(),
                "published_at": str(row.get("published_at") or "")[:10],
            }
        )
        seen_urls.add(canonical)
        seen_titles.add(title_key)

    # Round-robin categories so a hot AI-Infra stream cannot consume the synthesis input.
    result: list[dict[str, Any]] = []
    while len(result) < MAX_RADAR_CANDIDATES:
        added = False
        for name in RADAR_CATEGORIES:
            index = sum(1 for row in result if row["category"] == name)
            if index < len(groups.get(name, [])):
                result.append(groups[name][index])
                added = True
                if len(result) >= MAX_RADAR_CANDIDATES:
                    break
        if not added:
            break
    return result


def enrich_issue_synthesis_with_radar(task_service, run_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(input_data)
    payload["radar_candidates"] = build_radar_candidates(task_service, run_id, payload)
    payload["radar_policy"] = {
        "reader_goal": "compress article candidates into concrete technical signals, not an article list",
        "max_signals": 8,
        "allowed_categories": list(RADAR_CATEGORIES),
        "source_urls_must_be_exact": True,
        "no_fulltext_or_new_facts": True,
    }
    return payload


def radar_semantic_errors(task: dict[str, Any], input_data: dict[str, Any], data: dict[str, Any]) -> list[str]:
    if task.get("task_type") != "issue_synthesis":
        return []
    import json

    try:
        metadata = json.loads(task.get("metadata_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        metadata = {}
    if not metadata.get("radar_signals_required"):
        return []

    signals = data.get("radar_signals")
    if not isinstance(signals, list):
        return ["issue synthesis requires radar_signals"]

    candidates = input_data.get("radar_candidates") or []
    by_url = {str(item.get("url") or ""): item for item in candidates if item.get("url")}
    errors: list[str] = []
    used_urls: set[str] = set()
    if len(candidates) >= 4 and not signals:
        errors.append("radar_signals must contain at least one signal when >=4 candidates are available")

    for index, signal in enumerate(signals):
        if not isinstance(signal, dict):
            errors.append(f"radar signal {index} must be an object")
            continue
        category = str(signal.get("category") or "")
        if category not in RADAR_CATEGORIES:
            errors.append(f"radar signal {index} has unsupported category {category}")
        if not text_contains_chinese(signal.get("signal")) or not text_contains_chinese(
            signal.get("summary")
        ):
            errors.append(f"radar signal {index} must be written in Chinese")
        text = f"{signal.get('signal') or ''} {signal.get('summary') or ''}".lower()
        leaked = [phrase for phrase in FORBIDDEN_SIGNAL_TEXT if phrase in text]
        if leaked:
            errors.append(f"radar signal {index} leaks internal selection metadata")
        urls = [str(value) for value in signal.get("source_urls") or []]
        unknown = [url for url in urls if url not in by_url]
        if unknown:
            errors.append(f"radar signal {index} references unknown source_urls: {', '.join(unknown)}")
        if any(url in used_urls for url in urls):
            errors.append(f"radar signal {index} reuses a source already consumed by another signal")
        known = [by_url[url] for url in urls if url in by_url]
        if known and any(str(item.get("category") or "") != category for item in known):
            errors.append(f"radar signal {index} mixes sources from a different category")
        used_urls.update(urls)
    return errors


def _signal_groups(email_service, issue_id: str | None, issue_data: dict[str, Any] | None):
    synthesis = (issue_data or {}).get("synthesis") or {}
    signals = synthesis.get("radar_signals") or []
    if not signals and issue_id:
        issue = email_service.db.fetchone("SELECT synthesis_path FROM issues WHERE id=?", (issue_id,))
        if issue and issue.get("synthesis_path"):
            synthesis = read_json(email_service.root / issue["synthesis_path"], {})
            signals = synthesis.get("radar_signals") or []
    if not signals:
        return None

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    position = 0
    for signal in signals:
        urls = [str(url) for url in signal.get("source_urls") or [] if str(url)]
        if not urls:
            continue
        sources: list[dict[str, str]] = []
        newest_date = ""
        for url in urls:
            row = email_service.db.fetchone(
                """
                SELECT title,discovery_source,source_id,published_at FROM raw_items
                WHERE original_url=? OR canonical_url=? ORDER BY created_at DESC LIMIT 1
                """,
                (url, canonicalize_url(url)),
            )
            parsed = urlparse(url)
            # Radar signals link to the original source, so the reader-facing name is the
            # original hostname (arXiv/GitHub/domain). Never surface internal discovery-source
            # branding such as "AI HOT" / "YeeKal AI Daily" / "Follow Builders" here.
            _host = (parsed.hostname or "source").removeprefix("www.")
            if _host.endswith("arxiv.org"):
                _host = "arXiv"
            elif _host.endswith("github.com") or _host.endswith("github.io"):
                _host = "GitHub"
            source_name = _clean(_host, 60)
            published = str((row or {}).get("published_at") or "")[:10]
            newest_date = max(newest_date, published)
            sources.append(
                {
                    "url": url,
                    "name": source_name,
                    "title": _clean((row or {}).get("title") or source_name, 120),
                }
            )
        category = str(signal.get("category") or "其他技术前沿")
        item = {
            "title": _clean(signal.get("signal"), 100),
            "summary": _clean(signal.get("summary"), 260),
            "url": urls[0],
            "source_name": sources[0]["name"],
            "published_at": newest_date,
            "sources": sources,
        }
        groups[category].append(item)

        if issue_id:
            position += 1
            email_service.db.execute(
                """
                INSERT OR REPLACE INTO issue_radar_items(
                    issue_id,canonical_url,normalized_title,category,title,
                    summary,source_name,published_at,position
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    issue_id,
                    urls[0],
                    email_service._normalise_reference(item["title"]),
                    category,
                    item["title"],
                    item["summary"],
                    item["source_name"],
                    item["published_at"],
                    position,
                ),
            )
    return [{"name": name, "items": groups[name]} for name in RADAR_CATEGORIES if groups.get(name)]


def install_radar_signal_synthesis() -> None:
    """Use the existing issue-synthesis Agent to convert Radar articles into signals."""

    from . import demo as demo_module
    from .emailer import EmailService
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_radar_signal_synthesis_installed", False):
        return

    original_create = TaskService.create

    def create(self, *args, **kwargs):
        values = list(args)
        run_id = str(values[0] if values else kwargs.get("run_id") or "")
        task_type = values[1] if len(values) > 1 else kwargs.get("task_type")
        if task_type == "issue_synthesis" and not direct_copy_enabled(self):
            # Direct-copy mode owns radar end to end; the synthesis Agent only
            # writes judgements/watch-next/insights and never sees radar input.
            if len(values) > 3:
                values[3] = enrich_issue_synthesis_with_radar(self, run_id, dict(values[3]))
            else:
                kwargs["input_data"] = enrich_issue_synthesis_with_radar(
                    self, run_id, dict(kwargs.get("input_data") or {})
                )
            metadata = dict(kwargs.get("metadata") or {})
            metadata["radar_signals_required"] = True
            metadata["radar_signal_version"] = 1
            kwargs["metadata"] = metadata
        return original_create(self, *values, **kwargs)

    TaskService.create = create

    original_semantic_errors = TaskService._semantic_errors

    def semantic_errors(self, task, input_data, data):
        errors = list(original_semantic_errors(self, task, input_data, data))
        errors.extend(radar_semantic_errors(task, input_data, data))
        return errors

    TaskService._semantic_errors = semantic_errors

    original_demo = demo_module._demo_output

    def demo_output(task_type: str, data: dict[str, Any]):
        output = original_demo(task_type, data)
        if task_type != "issue_synthesis" or not isinstance(output, dict):
            return output
        if "radar_signals" in output:
            return output
        candidates = list(data.get("radar_candidates") or [])
        signals: list[dict[str, Any]] = []
        for candidate in candidates[:2]:
            signals.append(
                {
                    "category": candidate["category"],
                    "signal": f"{candidate['title']}出现值得继续观察的技术变化",
                    "summary": "该信号来自本期轻量候选摘要，用于验证Radar聚合链路；正式运行应提炼具体变化、机制与影响，而不是复述筛选理由。",
                    "source_urls": [candidate["url"]],
                }
            )
        output["radar_signals"] = signals
        return output

    demo_module._demo_output = demo_output

    original_aihot_groups = EmailService._aihot_groups

    def aihot_groups(self, issue_date=None, *, issue_id=None, issue_data=None):
        groups = _signal_groups(self, issue_id, issue_data)
        return groups if groups is not None else original_aihot_groups(
            self, issue_date, issue_id=issue_id, issue_data=issue_data
        )

    EmailService._aihot_groups = aihot_groups
    Pipeline._radar_signal_synthesis_installed = True
