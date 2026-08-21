from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .radar_direct import direct_copy_reserve_candidates, record_direct_publication
from .radar_signal_synthesis import build_radar_candidates
from .reader_writing_contract import text_contains_chinese
from .utils import canonicalize_url, normalize_text, read_json, write_json


MANIFEST_NAME = "publication-manifest.json"


def _urls_from_item(item: dict[str, Any]) -> set[str]:
    values = [item.get("url")]
    values.extend(source.get("url") for source in item.get("sources") or [])
    return {canonicalize_url(value) for value in values if canonicalize_url(value)}


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


def _appendix_urls(service) -> set[str]:
    urls: set[str] = set()
    for items in (getattr(service, "_topic_appendix_cache", {}) or {}).values():
        for item in items:
            values = [item.get("url")]
            values.extend(link.get("url") for link in item.get("links") or [])
            for value in values:
                canonical = canonicalize_url(value)
                if canonical:
                    urls.add(canonical)
    return urls


def filter_current_final_radar_groups(
    service,
    groups: list[dict[str, Any]],
    *,
    issue_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Filter final Radar against the actual current Deep/Appendix publication.

    The old final-reader helper could refill from a named historical reference run.
    The active publication path must not do that: any refill belongs to this run's
    reserve candidate pool and is handled later by ``finalize_radar_groups``.
    """

    forbidden = {
        canonicalize_url(source.get("url"))
        for item in issue_data.get("items") or []
        for source in item.get("sources") or []
        if canonicalize_url(source.get("url"))
    } | _appendix_urls(service)
    forbidden_projects = _github_projects(forbidden)
    filtered: list[dict[str, Any]] = []
    for group in groups or []:
        kept: list[dict[str, Any]] = []
        for item in group.get("items") or []:
            urls = _urls_from_item(item)
            if not urls or urls & forbidden:
                continue
            if _github_projects(urls) & forbidden_projects:
                continue
            if not text_contains_chinese(item.get("summary")):
                # Reader-facing Radar summaries must be Chinese; raw English
                # abstracts from discovery are not briefing copy.
                continue
            kept.append(dict(item))
        if kept:
            filtered.append({**group, "items": kept})
    return filtered


def _radar_policy(service) -> tuple[int, int]:
    policy = dict(getattr(service.config, "scoring", {}).get("radar") or {})
    return (
        max(1, int(policy.get("total_max", 8))),
        max(1, int(policy.get("max_per_category", 2))),
    )


def _candidate_to_item(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(candidate.get("title") or ""),
        "summary": str(candidate.get("summary") or ""),
        "url": str(candidate.get("url") or ""),
        "source_name": str(candidate.get("source_name") or "source"),
        "published_at": str(candidate.get("published_at") or ""),
        "source_level": str(candidate.get("source_level") or ""),
        "reserve_fill": True,
    }


def radar_required_minimum(raw_eligible: int, capacity: int) -> int:
    """Product invariant with category/total capacity respected.

    If at least eight viable signals exist, five must survive; with four to seven,
    at least three must survive. When category caps make that impossible, require the
    maximum legal capacity instead of silently failing forever.
    """

    if raw_eligible >= 8:
        return min(5, capacity)
    if raw_eligible >= 4:
        return min(3, capacity)
    return min(raw_eligible, capacity)


def finalize_radar_groups(
    service,
    groups: list[dict[str, Any]],
    *,
    issue_id: str | None,
    issue_data: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Bound, refill and persist the final Radar using only this run's candidates."""

    total_max, per_category = _radar_policy(service)
    forbidden = {
        canonicalize_url(source.get("url"))
        for item in issue_data.get("items") or []
        for source in item.get("sources") or []
        if canonicalize_url(source.get("url"))
    } | _appendix_urls(service)
    forbidden_projects = _github_projects(forbidden)

    final_groups: list[dict[str, Any]] = []
    by_name: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    counts: defaultdict[str, int] = defaultdict(int)
    total = 0

    def add(name: str, item: dict[str, Any]) -> bool:
        nonlocal total
        if total >= total_max or counts[name] >= per_category:
            return False
        if not text_contains_chinese(item.get("summary")):
            return False
        urls = _urls_from_item(item)
        if not urls or urls & forbidden or urls & seen:
            return False
        if _github_projects(urls) & forbidden_projects:
            return False
        group = by_name.get(name)
        if group is None:
            group = {"name": name, "items": []}
            by_name[name] = group
            final_groups.append(group)
        group["items"].append(item)
        seen.update(urls)
        counts[name] += 1
        total += 1
        return True

    for group in groups or []:
        name = str(group.get("name") or "其他技术前沿")
        for item in group.get("items") or []:
            add(name, dict(item))

    # Build a current-run reserve pool after Deep + Appendix are final. This replaces
    # the historical-reference refill path that could silently import old Radar cards.
    run_id = str(issue_data.get("run_id") or "")
    direct_candidates = direct_copy_reserve_candidates(service, run_id, issue_data)
    if direct_candidates is not None:
        # Direct-copy candidates already carry verbatim public copy and an
        # original-host source name, so they are used as reserve items as-is.
        reserve_iterable = direct_candidates
    else:
        reserve_iterable = build_radar_candidates(service, run_id, issue_data)
    reserve: list[tuple[str, dict[str, Any]]] = []
    available_by_category: defaultdict[str, int] = defaultdict(int)
    viable_unique: set[str] = set(seen)
    for candidate in reserve_iterable:
        if not text_contains_chinese(candidate.get("summary")):
            # English-only discovery abstracts can enter the Radar lane only through
            # the synthesis Agent, which writes Chinese signals; they must not be
            # reserve-filled straight into the reader-facing set.
            continue
        url = canonicalize_url(candidate.get("url"))
        if not url or url in forbidden or url in viable_unique:
            continue
        if _github_projects({url}) & forbidden_projects:
            continue
        name = str(candidate.get("category") or "其他技术前沿")
        if direct_candidates is not None:
            reserve.append((name, dict(candidate)))
        else:
            reserve.append((name, _candidate_to_item(candidate)))
        viable_unique.add(url)
        available_by_category[name] += 1

    # Capacity counts already-kept cards plus legal reserve slots per category.
    category_names = set(counts) | set(available_by_category)
    capacity = min(
        total_max,
        sum(
            min(per_category, counts[name] + available_by_category[name])
            for name in category_names
        ),
    )
    raw_eligible = total + len(reserve)
    required = radar_required_minimum(raw_eligible, capacity)

    for name, item in reserve:
        if total >= required:
            break
        add(name, item)

    contract = {
        "raw_eligible": raw_eligible,
        "legal_capacity": capacity,
        "required_minimum": required,
        "final_count": total,
        "total_max": total_max,
        "max_per_category": per_category,
    }

    if issue_id:
        service.db.execute(
            "DELETE FROM issue_radar_items WHERE issue_id=? AND category NOT LIKE 'TOPIC_APPENDIX:%'",
            (issue_id,),
        )
        position = 0
        for group in final_groups:
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
    final_result = [group for group in final_groups if group.get("items")]
    # The final card set is now immutable: record direct-copy provenance,
    # compat radar_signals and upstream ledger decisions for exactly this set.
    record_direct_publication(
        service,
        issue_id=issue_id,
        run_id=run_id,
        final_groups=final_result,
        contract=contract,
    )
    return final_result, contract


def _rendered_item_urls(item: dict[str, Any]) -> list[str]:
    # The template renders at most the first two source links per detailed/observation card.
    urls: list[str] = []
    for source in (item.get("sources") or [])[:2]:
        url = canonicalize_url(source.get("url"))
        if url and url not in urls:
            urls.append(url)
    return urls


def write_publication_manifest(
    service,
    issue_data: dict[str, Any],
    groups: list[dict[str, Any]],
    radar_contract: dict[str, int],
) -> Path:
    run_id = str(issue_data.get("run_id") or "")
    appendix: list[dict[str, Any]] = []
    for topic_id, items in (getattr(service, "_topic_appendix_cache", {}) or {}).items():
        for item in items:
            urls: list[str] = []
            for value in [item.get("url"), *(link.get("url") for link in item.get("links") or [])]:
                url = canonicalize_url(value)
                if url and url not in urls:
                    urls.append(url)
            appendix.append({"topic_id": str(topic_id), "title": str(item.get("title") or ""), "urls": urls})

    radar: list[dict[str, Any]] = []
    for group in groups:
        for item in group.get("items") or []:
            primary = canonicalize_url(item.get("url"))
            radar.append(
                {
                    "category": str(group.get("name") or "其他技术前沿"),
                    "title": str(item.get("title") or ""),
                    # The template renders only hot.url even when one synthesized
                    # signal was grounded by multiple source URLs.
                    "urls": [primary] if primary else [],
                }
            )

    manifest = {
        "version": 1,
        "issue_id": issue_data.get("id"),
        "run_id": run_id,
        "deep": [
            {
                "brief_item_id": item.get("brief_item_id"),
                "item_role": item.get("item_role", "core"),
                "title": item.get("title", ""),
                "urls": _rendered_item_urls(item),
            }
            for item in issue_data.get("items") or []
        ],
        "appendix": appendix,
        "radar": radar,
        "radar_contract": radar_contract,
    }
    path = service.root / "workspace" / "runs" / run_id / MANIFEST_NAME
    write_json(path, manifest)
    return path


def _html_urls(soup, selector: str) -> set[str]:
    urls: set[str] = set()
    for node in soup.select(selector):
        for link in node.find_all("a", href=True):
            href = str(link.get("href") or "")
            if href.startswith("#"):
                continue
            url = canonicalize_url(href)
            if url:
                urls.add(url)
    return urls


def _radar_records_from_manifest(manifest: dict[str, Any]) -> set[tuple[str, str, str]]:
    records: set[tuple[str, str, str]] = set()
    for item in manifest.get("radar") or []:
        category = normalize_text(item.get("category") or "")
        title = normalize_text(item.get("title") or "")
        for value in item.get("urls") or []:
            url = canonicalize_url(value)
            if url:
                records.add((category, title, url))
    return records


def _radar_records_from_html(soup) -> set[tuple[str, str, str]]:
    records: set[tuple[str, str, str]] = set()
    for card in soup.select('[data-reader-role="radar-card"]'):
        category = normalize_text(card.get("data-radar-category") or "")
        for node in card.select('[data-reader-role="radar-item"]'):
            link = node.find("a", href=True)
            if link is None:
                continue
            url = canonicalize_url(link.get("href"))
            if url:
                records.add((category, normalize_text(link.get_text(" ", strip=True)), url))
    return records


def publication_provenance_errors(root: Path, run_id: str, email_html: str) -> list[str]:
    """Prove that the final DOM is the structured publication, not a hand-edited lookalike."""

    path = root / "workspace" / "runs" / run_id / MANIFEST_NAME
    if not path.is_file():
        return ["Missing publication-manifest.json for final provenance validation"]
    manifest = read_json(path, {})
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(email_html, "html.parser")
    errors: list[str] = []
    expected_deep = {
        url for item in manifest.get("deep") or [] for url in item.get("urls") or [] if url
    }
    expected_appendix = {
        url for item in manifest.get("appendix") or [] for url in item.get("urls") or [] if url
    }
    actual_deep = _html_urls(soup, '[data-reader-role="deep-card"], [data-reader-role="observation-card"]')
    actual_appendix = _html_urls(soup, 'tr[data-topic-appendix="1"]')

    for label, expected, actual in (
        ("Deep/Observation", expected_deep, actual_deep),
        ("Appendix", expected_appendix, actual_appendix),
    ):
        if expected != actual:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            errors.append(f"{label} HTML provenance mismatch: missing={missing[:3]} extra={extra[:3]}")

    expected_radar = _radar_records_from_manifest(manifest)
    actual_radar = _radar_records_from_html(soup)
    if expected_radar != actual_radar:
        missing = sorted(expected_radar - actual_radar)
        extra = sorted(actual_radar - expected_radar)
        errors.append(
            f"Radar HTML provenance mismatch: missing={missing[:3]} extra={extra[:3]}"
        )

    contract = manifest.get("radar_contract") or {}
    required = int(contract.get("required_minimum") or 0)
    final_count = len(soup.select('[data-reader-role="radar-item"]'))
    if final_count < required:
        errors.append(
            f"Final Radar underfilled: {final_count} items, required minimum {required} "
            f"from {contract.get('raw_eligible', 0)} eligible signals"
        )
    return errors


def illustration_provenance_errors(
    root: Path,
    run_id: str,
    email_html: str,
    *,
    required: bool = False,
) -> list[str]:
    """Validate generated illustration identity, multiplicity and spacing.

    Missing illustration state is allowed only for runs that never entered the
    illustration stage. Callers that know an illustration task exists must set
    ``required=True`` so this validator remains a second fail-closed guard even if
    an upstream build-time manifest check regresses.
    """

    path = root / "workspace" / "runs" / run_id / "illustrations" / "manifest.json"
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(email_html, "html.parser")
    rows = soup.select('tr[data-reader-role="explanatory-illustration"]')
    if not path.is_file():
        if required or rows:
            return ["Missing illustrations/manifest.json for final illustration provenance validation"]
        return []

    manifest = read_json(path, {})
    expected = Counter(
        str(item.get("published_asset_url") or item.get("generated_asset_path") or "")
        for item in manifest.get("illustrations") or []
        if item.get("status") == "generated"
        and item.get("persona_used") is True
        and str(item.get("published_asset_url") or item.get("generated_asset_path") or "")
    )
    # The renderer contract currently puts one generated image in each explanatory
    # illustration row. Count rather than set-compare so duplicate DOM insertions cannot
    # hide behind identical src values.
    actual = Counter(
        str(image.get("src") or "")
        for row in rows
        for image in row.find_all("img", src=True)
    )
    errors: list[str] = []
    if expected != actual:
        missing = list((expected - actual).elements())
        extra = list((actual - expected).elements())
        errors.append(
            "Illustration HTML provenance mismatch: rendered generated images do not exactly match manifest "
            f"including multiplicity; missing={missing[:3]} extra={extra[:3]}"
        )
    for row in rows:
        previous = row.find_previous_sibling("tr")
        next_row = row.find_next_sibling("tr")
        if (
            previous is not None
            and previous.get("data-reader-role") == "explanatory-illustration"
        ) or (
            next_row is not None
            and next_row.get("data-reader-role") == "explanatory-illustration"
        ):
            errors.append("Adjacent explanatory illustrations are forbidden")
            break
    return errors
