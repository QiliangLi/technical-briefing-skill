from __future__ import annotations

from collections import defaultdict
from typing import Any

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


def _appendix_urls(service) -> set[str]:
    urls: set[str] = set()
    for items in (getattr(service, "_topic_appendix_cache", {}) or {}).values():
        for item in items:
            for value in [item.get("url"), *(link.get("url") for link in item.get("links") or [])]:
                canonical = canonicalize_url(value)
                if canonical:
                    urls.add(canonical)
    return urls


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
    filtered: list[dict[str, Any]] = []
    for group in groups or []:
        kept: list[dict[str, Any]] = []
        for item in group.get("items") or []:
            urls = {
                canonicalize_url(value)
                for value in [
                    item.get("url"),
                    *(source.get("url") for source in item.get("sources") or []),
                ]
                if canonicalize_url(value)
            }
            if urls & forbidden:
                continue
            kept.append(item)
        if kept:
            filtered.append({**group, "items": kept})

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


def html_reader_contract_errors(email_html: str) -> list[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(email_html, "html.parser")
    errors: list[str] = []

    deep_urls: set[str] = set()
    for card in soup.select('[data-reader-role="deep-card"]'):
        deep_urls |= _links(card)
    appendix_urls: set[str] = set()
    for row in soup.select('tr[data-topic-appendix="1"]'):
        appendix_urls |= _links(row)
    radar_urls: set[str] = set()
    for card in soup.select('[data-reader-role="radar-card"]'):
        radar_urls |= _links(card)

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
        if not row or int(row.get("deep_eligible") or 0) != 1 or int(row.get("fulltext_required") or 0) != 1:
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
            errors.extend(f"{item.get('title')}: {value}" for value in item_writing_contract_errors(item))
    errors.extend(issue_writing_contract_errors(data.get("synthesis") or {}))
    errors.extend(_core_selection_errors(service, run_id, data))

    email_path = service.root / str(issue.get("email_path") or "")
    if not email_path.is_file():
        errors.append("Final reader contract requires rendered email.html")
    else:
        errors.extend(html_reader_contract_errors(email_path.read_text(encoding="utf-8")))
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
