from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from .item_freshness import item_is_within_lookback, parse_publication_date
from .reader_writing_contract import (
    GENERIC_READER_PHRASES,
    issue_writing_contract_errors,
    item_writing_contract_errors,
)
from .utils import canonicalize_url, read_json, write_json


APPENDIX_PREFIX = "TOPIC_APPENDIX:"


def _source_urls(items: list[dict[str, Any]]) -> set[str]:
    return {
        canonicalize_url(source.get("url"))
        for item in items
        for source in item.get("sources") or []
        if canonicalize_url(source.get("url"))
    }


def _reference_restore_is_valid(service, item: dict[str, Any]) -> bool:
    policy = dict(service.config.settings.get("efficiency") or {})
    if not bool(policy.get("allow_fact_checked_reference_restores", False)):
        return False
    reference_run = str(item.get("restored_from_run") or "")
    reference_item_id = str(item.get("restored_brief_item_id") or "")
    if not reference_run or not reference_item_id:
        return False
    row = service.db.fetchone(
        """
        SELECT * FROM brief_items
        WHERE id=? AND run_id=? AND fact_check_status='PASS'
        """,
        (reference_item_id, reference_run),
    )
    if not row:
        return False
    restored = read_json(service.root / row["json_path"], {})
    return bool(_source_urls([item])) and _source_urls([item]) == _source_urls([restored])


def _appendix_urls(service) -> set[str]:
    urls: set[str] = set()
    for items in (getattr(service, "_topic_appendix_cache", {}) or {}).values():
        for item in items:
            for value in [item.get("url"), *(link.get("url") for link in item.get("links") or [])]:
                canonical = canonicalize_url(value)
                if canonical:
                    urls.add(canonical)
    return urls


def _item_urls(item: dict[str, Any]) -> set[str]:
    return {
        canonicalize_url(value)
        for value in [
            item.get("url"),
            *(source.get("url") for source in item.get("sources") or []),
        ]
        if canonicalize_url(value)
    }


def _github_projects(urls: set[str]) -> set[str]:
    projects: set[str] = set()
    for url in urls:
        parsed = urlparse(url)
        if (parsed.hostname or "").lower() not in {"github.com", "www.github.com"}:
            continue
        parts = [part.lower() for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            projects.add(f"github:{parts[0]}/{parts[1]}")
    return projects


def _fill_from_reference_radar(
    service,
    groups: list[dict[str, Any]],
    *,
    issue_data: dict[str, Any] | None,
    forbidden: set[str],
    forbidden_projects: set[str],
) -> list[dict[str, Any]]:
    """Refill post-dedup Radar gaps from the named local reference issue."""

    audit = dict((issue_data or {}).get("rebuild_audit") or {})
    reference_run = str(audit.get("reference_run") or "")
    if not reference_run:
        return groups
    radar_policy = dict(getattr(service.config, "scoring", {}).get("radar") or {})
    target = max(0, int(radar_policy.get("reference_fill_min", 0)))
    total_max = max(target, int(radar_policy.get("total_max", 8)))
    per_category = max(1, int(radar_policy.get("max_per_category", 2)))
    if sum(len(group.get("items") or []) for group in groups) >= target:
        return groups

    row = service.db.fetchone(
        "SELECT issue_json_path FROM issues WHERE run_id=?", (reference_run,)
    )
    if not row or not row.get("issue_json_path"):
        return groups
    reference_issue = read_json(service.root / row["issue_json_path"], {})
    from .radar_signal_synthesis import _signal_groups

    reference_groups = _signal_groups(service, None, reference_issue) or []
    merged = [{**group, "items": list(group.get("items") or [])} for group in groups]
    by_name = {str(group.get("name") or ""): group for group in merged}
    seen = {
        url for group in merged for item in group.get("items") or [] for url in _item_urls(item)
    }
    total = sum(len(group.get("items") or []) for group in merged)
    for reference_group in reference_groups:
        if total >= target or total >= total_max:
            break
        name = str(reference_group.get("name") or "其他技术前沿")
        destination = by_name.get(name)
        if destination is None:
            destination = {"name": name, "items": []}
            merged.append(destination)
            by_name[name] = destination
        for item in reference_group.get("items") or []:
            if total >= target or total >= total_max:
                break
            urls = _item_urls(item)
            if (
                not urls
                or urls & forbidden
                or urls & seen
                or _github_projects(urls) & forbidden_projects
            ):
                continue
            if len(destination["items"]) >= per_category:
                continue
            # Every restored Radar source must also exist in this run's frozen
            # source set. This keeps the refill reproducible and auditable.
            if any(
                not service.db.fetchone(
                    """
                    SELECT 1 FROM raw_items
                    WHERE run_id=? AND (canonical_url=? OR original_url=?) LIMIT 1
                    """,
                    (str((issue_data or {}).get("run_id") or ""), url, url),
                )
                for url in urls
            ):
                continue
            destination["items"].append(item)
            seen.update(urls)
            total += 1
    return [group for group in merged if group.get("items")]


def filter_final_radar_groups(
    service,
    groups: list[dict[str, Any]],
    *,
    issue_id: str | None,
    issue_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Drop Radar signals that repeat final Deep/Observation/appendix sources."""

    issue_items = list((issue_data or {}).get("items") or [])
    forbidden = _source_urls(issue_items) | _appendix_urls(service)
    forbidden_projects = _github_projects(forbidden)
    filtered: list[dict[str, Any]] = []
    for group in groups or []:
        kept: list[dict[str, Any]] = []
        for item in group.get("items") or []:
            urls = _item_urls(item)
            if urls & forbidden or _github_projects(urls) & forbidden_projects:
                continue
            kept.append(item)
        if kept:
            filtered.append({**group, "items": kept})

    filtered = _fill_from_reference_radar(
        service,
        filtered,
        issue_data=issue_data,
        forbidden=forbidden,
        forbidden_projects=forbidden_projects,
    )

    if issue_id:
        service.db.execute(
            "DELETE FROM issue_radar_items WHERE issue_id=? AND category NOT LIKE ?",
            (issue_id, f"{APPENDIX_PREFIX}%"),
        )
        position = 0
        for group in filtered:
            for item in group.get("items") or []:
                position += 1
                service.db.execute(
                    """
                    INSERT OR REPLACE INTO issue_radar_items(
                        issue_id,canonical_url,normalized_title,category,title,
                        summary,source_name,published_at,position
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        issue_id,
                        item.get("url"),
                        service._normalise_reference(str(item.get("title") or "")),
                        group.get("name") or "其他技术前沿",
                        item.get("title") or "",
                        item.get("summary") or "",
                        item.get("source_name") or "source",
                        item.get("published_at") or "",
                        position,
                    ),
                )
    return filtered


def _links(node) -> set[str]:
    urls: set[str] = set()
    for link in node.find_all("a", href=True):
        href = str(link.get("href") or "")
        if href.startswith("#"):
            continue
        canonical = canonicalize_url(href)
        if canonical:
            urls.add(canonical)
    return urls


def normalise_orphan_card_widths(email_html: str) -> str:
    """Make the final rendered DOM robust even when Jinja batch padding is absent.

    Jinja's `batch(2, none)` does not pad because `none` is the filter's default
    sentinel, so source-template checks against `row[1] is none` can miss a one-item
    row. Normalize the actual final DOM after all HTML post-processors instead.
    """

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(email_html, "html.parser")
    specs = (
        ('tr[data-reader-row="deep-row"]', '[data-reader-role="deep-card"]'),
        ('tr[data-reader-row="observation-row"]', '[data-reader-role="observation-card"]'),
    )
    for row_selector, card_selector in specs:
        for row in soup.select(row_selector):
            cards = row.select(card_selector)
            if len(cards) != 1:
                continue
            card = cards[0]
            card["width"] = "100%"
            style = str(card.get("style") or "")
            if style:
                # Existing one-card rows are the first column and therefore carry a
                # right gap intended only for a sibling. Remove that gap as well.
                style = style.replace("padding:0 5px 0 0", "padding:0")
                card["style"] = style
    # Radar rows do not currently carry a row marker. A single radar card's nearest
    # presentation row can still be normalized safely because the role is unique.
    for card in soup.select('[data-reader-role="radar-card"]'):
        row = card.find_parent("tr")
        if row is None:
            continue
        cards = row.select('[data-reader-role="radar-card"]')
        if len(cards) == 1:
            card["width"] = "100%"
            style = str(card.get("style") or "").replace("padding:0 5px 0 0", "padding:0")
            card["style"] = style
    return str(soup)


def html_reader_contract_errors(
    email_html: str,
    *,
    radar_max_per_category: int = 2,
) -> list[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(email_html, "html.parser")
    errors: list[str] = []

    deep_urls: set[str] = set()
    for card in soup.select('[data-reader-role="deep-card"]'):
        deep_urls |= _links(card)
    appendix_urls: set[str] = set()
    for row in soup.select('tr[data-topic-appendix="1"]'):
        appendix_urls |= _links(row)
    radar_cards = soup.select('[data-reader-role="radar-card"]')
    radar_urls: set[str] = set()
    for card in radar_cards:
        radar_urls |= _links(card)
        if not any(
            str(row.get("data-reader-row") or "") == "radar-row"
            for row in card.find_parents("tr")
        ):
            errors.append("Every Radar card must belong to a structured Radar row")

    radar_categories: list[str] = []
    for row in soup.select('tr[data-reader-row="radar-row"]'):
        cards = row.select('[data-reader-role="radar-card"]')
        if len(cards) > 2:
            errors.append("A Radar row may contain at most two category cards")
        if len(cards) == 1 and str(cards[0].get("width") or "") != "100%":
            errors.append("A single Radar category card in a row must render at 100% width")
        for card in cards:
            category = str(card.get("data-radar-category") or "").strip()
            if not category:
                errors.append("Every Radar card must identify one category")
            else:
                radar_categories.append(category)
            if len(card.select('[data-reader-role="radar-item"]')) > radar_max_per_category:
                errors.append(
                    "A Radar category card may contain at most "
                    f"{radar_max_per_category} signals"
                )
    if len(radar_categories) != len(set(radar_categories)):
        errors.append("Radar signals from the same category must share one category card")

    if deep_urls & appendix_urls:
        errors.append("Deep and topic appendix reuse the same reader-facing source URL")
    if radar_urls & deep_urls:
        errors.append("Radar repeats a source already used by a detailed item")
    if radar_urls & appendix_urls:
        errors.append("Radar repeats a source already used by a topic appendix")

    for row in soup.select('tr[data-reader-row="deep-row"]'):
        cards = row.select('[data-reader-role="deep-card"]')
        if len(cards) == 1 and str(cards[0].get("width") or "") != "100%":
            errors.append("A single final Deep card in a row must render at 100% width")
        if len(cards) > 2:
            errors.append("A Deep row may contain at most two cards")

    for meta in soup.select('[data-reader-meta="1"]'):
        if "分" in meta.get_text(" ", strip=True):
            errors.append("Reader-facing item metadata must not expose internal selection scores")
            break

    visible = soup.get_text(" ", strip=True)
    for phrase in GENERIC_READER_PHRASES:
        if phrase in visible:
            errors.append(f"Reader-facing email contains generic boilerplate: {phrase}")
    return errors


def _core_selection_errors(service, run_id: str, data: dict[str, Any]) -> list[str]:
    """Check final detailed items only for topics governed by the Deep Top4 contract."""

    errors: list[str] = []
    deep_topics = set((service.config.settings.get("efficiency") or {}).get("deep_topics") or [])
    lookback_days = max(
        1,
        int(
            (service.config.settings.get("efficiency") or {}).get(
                "deep_lookback_days", 60
            )
        ),
    )
    issue_end = parse_publication_date(data.get("date_to"))
    if not issue_end:
        errors.append("final issue has no valid date_to for detailed-item freshness checks")
    core = data.get("core_items")
    if core is None:
        core = [item for item in data.get("items") or [] if item.get("item_role", "core") == "core"]
    counts: dict[str, int] = defaultdict(int)
    for item in core:
        topic_id = str(item.get("topic_id") or "")
        if topic_id not in deep_topics:
            continue
        counts[topic_id] += 1
        if counts[topic_id] > 4:
            errors.append(f"{topic_id}: final detailed item count exceeds topic-local Top4")
            continue
        if item.get("restored_from_run") or item.get("restored_brief_item_id"):
            if not issue_end or not item_is_within_lookback(
                item,
                issue_end=issue_end,
                lookback_days=lookback_days,
            ):
                errors.append(
                    f"{topic_id}: restored detailed item is outside the {lookback_days}-day window or lacks an original publication date: {item.get('title')}"
                )
                continue
            if _reference_restore_is_valid(service, item):
                continue
            errors.append(
                f"{topic_id}: restored detailed item lacks valid fact-checked reference provenance: {item.get('title')}"
            )
            continue
        urls = [
            canonicalize_url(source.get("url"))
            for source in item.get("sources") or []
            if canonicalize_url(source.get("url"))
        ]
        if not urls:
            continue
        placeholders = ",".join("?" for _ in urls)
        row = service.db.fetchone(
            f"""
            SELECT c.id,c.deep_eligible,c.fulltext_required,c.topic_id
            FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
            WHERE c.run_id=? AND c.topic_id=?
              AND (r.canonical_url IN ({placeholders}) OR r.original_url IN ({placeholders}))
            ORDER BY COALESCE(c.deep_eligible,0) DESC,COALESCE(c.fulltext_required,0) DESC
            LIMIT 1
            """,
            (run_id, topic_id, *urls, *urls),
        )
        if (
            not row
            or int(row.get("deep_eligible") or 0) < 1
            or int(row.get("fulltext_required") or 0) != 1
        ):
            errors.append(f"{topic_id}: final detailed item is not backed by a Deep-eligible candidate: {item.get('title')}")
    return errors


def final_reader_contract_errors(service, run_id: str) -> list[str]:
    issue = service.db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
    if not issue or not issue.get("issue_json_path"):
        return ["Final reader contract requires a persisted issue JSON"]
    data = read_json(service.root / issue["issue_json_path"], {})
    errors: list[str] = []

    for item in data.get("items") or []:
        if item.get("item_role", "core") == "core":
            if item.get("restored_from_run") or item.get("restored_brief_item_id"):
                if not _reference_restore_is_valid(service, item):
                    errors.append(
                        f"{item.get('title')}: restored item provenance is not a fact-checked reference"
                    )
                # Provenance permits reusing verified facts; it does not exempt
                # restored prose from current reader-facing title/summary rules.
            errors.extend(f"{item.get('title')}: {value}" for value in item_writing_contract_errors(item))
    errors.extend(issue_writing_contract_errors(data.get("synthesis") or {}))
    errors.extend(_core_selection_errors(service, run_id, data))

    email_path = service.root / str(issue.get("email_path") or "")
    if not email_path.is_file():
        errors.append("Final reader contract requires rendered email.html")
    else:
        radar_policy = dict(getattr(service.config, "scoring", {}).get("radar") or {})
        radar_max_per_category = max(
            1, int(radar_policy.get("max_per_category", 2))
        )
        errors.extend(
            html_reader_contract_errors(
                email_path.read_text(encoding="utf-8"),
                radar_max_per_category=radar_max_per_category,
            )
        )
    return list(dict.fromkeys(errors))


def install_final_reader_contract() -> None:
    """Filter final Radar and make reader-facing invariants release-blocking."""

    from .emailer import EmailService
    from .pipeline import Pipeline
    from .rendering import Renderer

    if getattr(Pipeline, "_final_reader_contract_installed", False):
        return

    original_aihot_groups = EmailService._aihot_groups

    def aihot_groups(self, issue_date=None, *, issue_id=None, issue_data=None):
        groups = original_aihot_groups(
            self, issue_date, issue_id=issue_id, issue_data=issue_data
        )
        return filter_final_radar_groups(
            self,
            groups,
            issue_id=str(issue_id) if issue_id else None,
            issue_data=issue_data,
        )

    EmailService._aihot_groups = aihot_groups

    original_build = EmailService.build

    def build(self, run_id: str, *args, **kwargs):
        path = original_build(self, run_id, *args, **kwargs)
        path.write_text(
            normalise_orphan_card_widths(path.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        return path

    EmailService.build = build

    original_validate = Renderer.validate

    def validate(self, run_id: str):
        report = original_validate(self, run_id)
        failures = final_reader_contract_errors(self, run_id)
        if failures:
            report.setdefault("failures", []).extend(failures)
        else:
            report.setdefault("passes", []).append(
                "Final reader output satisfies selection, writing, layout, score, and Radar de-dup contracts"
            )
        report["failures"] = list(dict.fromkeys(report.get("failures") or []))
        report["warnings"] = list(dict.fromkeys(report.get("warnings") or []))
        report["passes"] = list(dict.fromkeys(report.get("passes") or []))
        write_json(self.root / "workspace" / "runs" / run_id / "validation.json", report)
        return report

    Renderer.validate = validate
    Pipeline._final_reader_contract_installed = True
