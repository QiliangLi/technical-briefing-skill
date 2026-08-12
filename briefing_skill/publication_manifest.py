from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .radar_signal_synthesis import build_radar_candidates
from .utils import canonicalize_url, read_json, write_json


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

    # Keep synthesis-selected signals first, but apply the final category/total limits
    # deterministically before considering reserve candidates.
    final_groups: list[dict[str, Any]] = []
    by_name: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    counts: defaultdict[str, int] = defaultdict(int)
    total = 0

    def add(name: str, item: dict[str, Any]) -> bool:
        nonlocal total
        if total >= total_max or counts[name] >= per_category:
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
    candidates = build_radar_candidates(service, str(issue_data.get("run_id") or ""), issue_data)
    reserve: list[tuple[str, dict[str, Any]]] = []
    available_by_category: defaultdict[str, int] = defaultdict(int)
    viable_unique: set[str] = set(seen)
    for candidate in candidates:
        url = canonicalize_url(candidate.get("url"))
        if not url or url in forbidden or url in viable_unique:
            continue
        if _github_projects({url}) & forbidden_projects:
            continue
        name = str(candidate.get("category") or "其他技术前沿")
        reserve.append((name, candidate))
        viable_unique.add(url)
        available_by_category[name] += 1

    # Capacity counts already-kept signals plus legal reserve slots per category.
    category_names = set(counts) | set(available_by_category)
    capacity = min(
        total_max,
        sum(
            min(per_category, counts[name] + available_by_category[name])
            for name in category_names
        ),
    )
    raw_eligible = len(seen) + len(reserve)
    required = radar_required_minimum(raw_eligible, capacity)

    for name, candidate in reserve:
        if total >= required:
            break
        add(name, _candidate_to_item(candidate))

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
    return [group for group in final_groups if group.get("items")], contract


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
            radar.append(
                {
                    "category": str(group.get("name") or "其他技术前沿"),
                    "title": str(item.get("title") or ""),
                    "urls": sorted(_urls_from_item(item)),
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
    expected_radar = {
        url for item in manifest.get("radar") or [] for url in item.get("urls") or [] if url
    }
    actual_deep = _html_urls(soup, '[data-reader-role="deep-card"], [data-reader-role="observation-card"]')
    actual_appendix = _html_urls(soup, 'tr[data-topic-appendix="1"]')
    actual_radar = _html_urls(soup, '[data-reader-role="radar-item"]')

    for label, expected, actual in (
        ("Deep/Observation", expected_deep, actual_deep),
        ("Appendix", expected_appendix, actual_appendix),
        ("Radar", expected_radar, actual_radar),
    ):
        if expected != actual:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            errors.append(f"{label} HTML provenance mismatch: missing={missing[:3]} extra={extra[:3]}")

    contract = manifest.get("radar_contract") or {}
    required = int(contract.get("required_minimum") or 0)
    final_count = len(soup.select('[data-reader-role="radar-item"]'))
    if final_count < required:
        errors.append(
            f"Final Radar underfilled: {final_count} items, required minimum {required} "
            f"from {contract.get('raw_eligible', 0)} eligible signals"
        )
    return errors


def illustration_provenance_errors(root: Path, run_id: str, email_html: str) -> list[str]:
    path = root / "workspace" / "runs" / run_id / "illustrations" / "manifest.json"
    if not path.is_file():
        return []
    manifest = read_json(path, {})
    expected = {
        str(item.get("published_asset_url") or item.get("generated_asset_path") or "")
        for item in manifest.get("illustrations") or []
        if item.get("status") == "generated" and item.get("persona_used") is True
    }
    expected.discard("")
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(email_html, "html.parser")
    rows = soup.select('tr[data-reader-role="explanatory-illustration"]')
    actual = {
        str(image.get("src") or "")
        for row in rows
        for image in row.find_all("img", src=True)
    }
    errors: list[str] = []
    if expected != actual:
        errors.append(
            "Illustration HTML provenance mismatch: rendered generated images do not exactly match manifest"
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
