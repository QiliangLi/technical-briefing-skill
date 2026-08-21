from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .radar_direct import direct_copy_reserve_candidates, record_direct_publication
from .radar_signal_synthesis import build_radar_candidates
from .reader_writing_contract import text_contains_chinese
from .utils import canonicalize_url, content_hash, normalize_text, read_json, stable_hash, write_json


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
                      summary,source_name,published_at,position,upstream_item_id,story_id
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
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
                        item.get("upstream_item_id") or None,
                        item.get("story_id") or None,
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
            summary = str(item.get("summary") or "")
            radar.append(
                {
                    # Deterministic identity shared with the internal ledger;
                    # original URLs only, never an upstream discovery URL.
                    "radar_id": stable_hash("radar", run_id, primary) if primary else None,
                    "category": str(group.get("name") or "其他技术前沿"),
                    "title": str(item.get("title") or ""),
                    "source_name": str(item.get("source_name") or "") or None,
                    # The template renders only hot.url even when one synthesized
                    # signal was grounded by multiple source URLs.
                    "urls": [primary] if primary else [],
                    "summary_sha256": f"sha256:{content_hash(summary)}" if summary else None,
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


def _radar_records_from_manifest(manifest: dict[str, Any]) -> Counter:
    records: Counter = Counter()
    for item in manifest.get("radar") or []:
        category = normalize_text(item.get("category") or "")
        title = normalize_text(item.get("title") or "")
        for value in item.get("urls") or []:
            url = canonicalize_url(value)
            if url:
                records[(category, title, url)] += 1
    return records


def _radar_records_from_html(soup) -> Counter:
    records: Counter = Counter()
    for card in soup.select('[data-reader-role="radar-card"]'):
        category = normalize_text(card.get("data-radar-category") or "")
        for node in card.select('[data-reader-role="radar-item"]'):
            link = node.find("a", href=True)
            if link is None:
                continue
            url = canonicalize_url(link.get("href"))
            if url:
                records[(category, normalize_text(link.get_text(" ", strip=True)), url)] += 1
    return records


def _radar_dom_items(soup) -> list[dict[str, str]]:
    """Ordered DOM radar records: {url, title, summary, category, date}.

    A list (not a dict) so duplicated cards keep their multiplicity; the
    category comes from the owning card and the date from the meta line.
    """
    result: list[dict[str, str]] = []
    for card in soup.select('[data-reader-role="radar-card"]'):
        category = normalize_text(card.get("data-radar-category") or "")
        for node in card.select('[data-reader-role="radar-item"]'):
            link = node.find("a", href=True)
            if link is None:
                continue
            url = canonicalize_url(link.get("href"))
            if not url:
                continue
            summary_node = node.select_one('[data-reader-role="radar-summary"]')
            if summary_node is None:
                # Structural fallback for DOM produced before the marker existed:
                # the summary is the first inner div that is not the meta line.
                for div in node.find_all("div"):
                    text_value = div.get_text(" ", strip=True)
                    if text_value and "阅读原文" not in text_value:
                        summary_node = div
                        break
            date = ""
            source_name = ""
            for div in node.find_all("div"):
                meta_text = " ".join(div.get_text(" ", strip=True).split())
                if "阅读原文" in div.get_text(" ", strip=True):
                    head = meta_text.split("·", 1)[0].strip()
                    if head and "阅读原文" not in head:
                        date = head
                    source_link = div.find_all("a", href=True)
                    if source_link:
                        source_name = " ".join(source_link[-1].get_text(" ", strip=True).split())
                    break
            result.append(
                {
                    "url": url,
                    "title": " ".join(link.get_text(" ", strip=True).split()),
                    "summary": " ".join(summary_node.get_text(" ", strip=True).split()) if summary_node else "",
                    "category": category,
                    "date": date,
                    "source_name": source_name,
                }
            )
    return result


def _direct_copy_provenance_errors(
    root: Path,
    run_id: str,
    soup,
    manifest: dict[str, Any],
    *,
    active_issue: dict[str, Any] | None = None,
) -> list[str]:
    """Fail closed on the full chain: freeze -> radar-direct -> manifest -> DOM.

    In direct-copy mode every layer is mandatory and cross-checked: the
    stored freeze/selection hashes must exist and recompute, every AI Hot
    card must be locatable in the frozen lanes (including daily nesting and
    cross-lane copy fallbacks), direct/manifest/DOM must agree on count,
    uniqueness, category and published date, and the manifest must carry the
    same selection hash as radar-direct.
    """
    from .radar_direct import (
        direct_copy_mode,
        freeze_file_sha256,
        locate_frozen_source,
        recompute_selection_hash,
        verify_copy_integrity,
    )

    mode = direct_copy_mode(root)
    path = root / "workspace" / "runs" / run_id / "issue" / "radar-direct.json"
    if mode is False:
        return []
    if mode is None and not path.is_file():
        # No readable config and no direct records: a legacy-synthesis run.
        return []
    if not path.is_file():
        return ["Direct-copy radar provenance record is missing for final validation"]
    document = read_json(path, {}) or {}
    errors: list[str] = []
    direct_items = list(document.get("items") or [])

    # External anchors: the provenance must belong to THIS active run, its
    # report date and the currently configured timezone. Internal
    # self-consistency of a copied sidecar from another run is not enough.
    if str(document.get("run_id") or "") != run_id:
        errors.append(
            "radar-direct provenance belongs to another run "
            f"({document.get('run_id')!r} != active {run_id!r})"
        )
    issue_document = read_json(root / "workspace" / "runs" / run_id / "issue" / "issue.json", {}) or {}
    active_date = str(issue_document.get("date_to") or "")
    if not active_date:
        errors.append("active issue is missing its date_to report date")
    if str(document.get("reference_date") or "") != active_date:
        errors.append(
            f"radar-direct reference date {document.get('reference_date')!r} does not match the active issue date {active_date!r}"
        )
    from .radar_direct import configured_timezone

    expected_timezone = configured_timezone(root)
    if expected_timezone is None:
        errors.append("configured timezone cannot be read for radar provenance validation")
    elif str(document.get("timezone") or "") != expected_timezone:
        errors.append(
            f"radar-direct timezone {document.get('timezone')!r} does not match the configured {expected_timezone!r}"
        )
    manifest_run_id = str(manifest.get("run_id") or "")
    if not manifest_run_id:
        errors.append("publication manifest is missing its run_id")
    elif manifest_run_id != run_id:
        errors.append(f"publication manifest belongs to another run ({manifest_run_id!r})")
    if active_issue is not None:
        db_run = str(active_issue.get("run_id") or "")
        db_date = str(active_issue.get("date_to") or "")
        if db_run and db_run != run_id:
            errors.append(f"database active issue belongs to another run ({db_run!r})")
        if not db_date:
            errors.append("database active issue is missing its date_to")
        elif db_date != active_date:
            errors.append(
                f"issue.json date_to {active_date!r} does not match the database active issue {db_date!r}"
            )

    for item in direct_items:
        errors.extend(
            f"radar-direct record {item.get('radar_id')}: {error}"
            for error in verify_copy_integrity(item)
        )

    # Mandatory binding fields: absence is a failure, never "nothing to check".
    for field in ("selection_hash", "reference_date", "timezone", "selection_contract"):
        if not document.get(field):
            errors.append(f"radar-direct provenance is missing required field '{field}'")
    freeze_path = root / "workspace" / "runs" / run_id / "source-cache" / "aihot" / "freeze.json"
    freeze_exists = freeze_path.is_file()
    has_aihot_items = any(item.get("upstream_lanes") for item in direct_items)
    if (has_aihot_items or freeze_exists) and not document.get("frozen_input_sha256"):
        errors.append("radar-direct provenance is missing required field 'frozen_input_sha256'")

    # Anchor to the real frozen input.
    actual_freeze_hash = freeze_file_sha256(root, run_id)
    stored_freeze_hash = document.get("frozen_input_sha256")
    if stored_freeze_hash is not None and stored_freeze_hash != actual_freeze_hash:
        errors.append("radar-direct provenance is not anchored to the current frozen AI Hot input")
    freeze_document = read_json(freeze_path, {}) if freeze_exists else {}
    if freeze_exists and str(freeze_document.get("run_id") or "") != run_id:
        errors.append("frozen AI Hot input belongs to another run")
    for item in direct_items:
        if not (item.get("upstream_lanes") or []):
            continue  # non-AI-Hot discovery rows have no freeze anchor
        if not freeze_exists:
            errors.append(
                f"radar-direct record {item.get('radar_id')} requires the run's frozen responses for verification"
            )
            continue
        anchor = locate_frozen_source(freeze_document, item)
        if anchor is None:
            errors.append(
                f"radar-direct record {item.get('radar_id')} cannot be located in the frozen AI Hot responses"
            )
        else:
            if anchor["summary"] is None:
                errors.append(
                    f"radar-direct record {item.get('radar_id')} summary source text differs from every frozen field"
                )
            if anchor["title"] is None:
                errors.append(
                    f"radar-direct record {item.get('radar_id')} title source text differs from every frozen field"
                )

    # Recompute the selection hash over the recorded public fields.
    if document.get("selection_hash") and recompute_selection_hash(document) != document.get("selection_hash"):
        errors.append("radar-direct selection hash does not match its recorded public fields")

    manifest_records = [
        {
            "url": canonicalize_url((record.get("urls") or [None])[0]),
            "category": normalize_text(record.get("category") or ""),
            "title": normalize_text(record.get("title") or ""),
            "summary_sha256": record.get("summary_sha256"),
            "radar_id": record.get("radar_id"),
            "source_name": record.get("source_name"),
        }
        for record in manifest.get("radar") or []
    ]

    # Persisted rule versions must stay within the supported range: a value
    # from the future is rejected rather than silently re-bound.
    from .adapters.aihot import AIHOT_CONNECTOR_VERSION
    from .radar_direct import (
        RADAR_DIRECT_COPY_VERSION,
        RADAR_SELECTION_POLICY_VERSION,
        RADAR_TAXONOMY_VERSION,
    )

    # Explicitly supported version values: 0 (deleted history) and future
    # values are both rejected, and the top-level `version` field is the
    # direct-copy schema version and must agree with direct_copy_version.
    supported_versions = {
        "connector_version": {AIHOT_CONNECTOR_VERSION},
        "direct_copy_version": {RADAR_DIRECT_COPY_VERSION},
        "radar_taxonomy_version": {RADAR_TAXONOMY_VERSION},
        "radar_selection_policy_version": {RADAR_SELECTION_POLICY_VERSION},
        "version": {RADAR_DIRECT_COPY_VERSION},
    }
    for field, supported in supported_versions.items():
        value = document.get(field)
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            errors.append(f"radar-direct provenance field '{field}' is not a version number")
            continue
        if numeric not in supported:
            errors.append(
                f"radar-direct provenance field '{field}' ({numeric}) is not in the supported set {sorted(supported)}"
            )

    # The manifest must link back to the exact provenance document; a missing
    # link is a failure, not an acceptable value.
    manifest_contract = manifest.get("radar_contract") or {}
    if document.get("selection_hash") and manifest_contract.get("selection_hash") != document["selection_hash"]:
        errors.append("publication manifest selection hash is missing or does not match radar-direct")

    # Layer counts and uniqueness: direct == manifest == DOM == final_count,
    # unconditionally — an empty layer must still agree with the others.
    contract = document.get("selection_contract") or {}
    try:
        final_count = int(contract.get("final_count"))
    except (TypeError, ValueError):
        final_count = None
    if final_count is None:
        errors.append("radar-direct selection contract is missing a numeric final_count")
        final_count = -1
    dom_items = _radar_dom_items(soup)
    direct_urls = Counter(canonicalize_url((item.get("source_urls") or [None])[0]) for item in direct_items)
    manifest_urls = Counter(record["url"] for record in manifest_records)
    dom_urls = Counter(item["url"] for item in dom_items)
    direct_ids = Counter(str(item.get("radar_id") or "") for item in direct_items)
    if any(count > 1 for count in direct_ids.values()):
        errors.append("radar-direct records contain duplicate radar_id values")
    if any(count > 1 for count in direct_urls.values()):
        errors.append("radar-direct records contain duplicate canonical URLs")
    if direct_urls != manifest_urls or direct_urls != dom_urls:
        errors.append(
            "Radar layers disagree on records (count/multiplicity): "
            f"direct={len(direct_items)} manifest={len(manifest_records)} dom={len(dom_items)}"
        )
    if len(dom_items) != final_count:
        errors.append(f"Radar DOM count {len(dom_items)} does not equal the contract final_count {final_count}")

    # Field-level chain: direct -> manifest -> DOM for category, title and date.
    direct_by_url = {}
    for item in direct_items:
        url = canonicalize_url((item.get("source_urls") or [None])[0])
        if url:
            direct_by_url[url] = item
    manifest_by_url = {record["url"]: record for record in manifest_records if record["url"]}
    for rendered in dom_items:
        url = rendered["url"]
        direct_item = direct_by_url.get(url)
        manifest_record = manifest_by_url.get(url)
        if direct_item is None or manifest_record is None:
            continue
        if normalize_text(direct_item.get("category") or "") != rendered["category"]:
            errors.append(f"Radar category in HTML does not match radar-direct for {url}")
        if manifest_record["category"] != rendered["category"]:
            errors.append(f"Radar category in HTML does not match the manifest for {url}")
        if manifest_record["title"] != normalize_text(direct_item.get("title") or ""):
            errors.append(f"Radar title in manifest does not match radar-direct for {url}")
        if manifest_record["summary_sha256"] != (direct_item.get("copy_provenance") or {}).get("public_text_hash"):
            errors.append(f"publication manifest summary hash disagrees with radar-direct for {url}")
        if str(direct_item.get("radar_id") or "") != str(manifest_record.get("radar_id") or ""):
            errors.append(f"publication manifest radar_id disagrees with radar-direct for {url}")
        if str(direct_item.get("published_at") or "") != rendered["date"]:
            errors.append(f"Radar published date in HTML does not match radar-direct for {url}")
        if normalize_text(direct_item.get("source_name") or "") != normalize_text(rendered.get("source_name") or ""):
            errors.append(f"Radar source name in HTML does not match radar-direct for {url}")
        if manifest_record.get("source_name") is None:
            errors.append(f"publication manifest is missing source_name for {url}")
        elif normalize_text(manifest_record.get("source_name") or "") != normalize_text(
            direct_item.get("source_name") or ""
        ):
            errors.append(f"publication manifest source name disagrees with radar-direct for {url}")
        # The public source name is derived from the canonical original URL;
        # a name forged across every layer still breaks this recompute.
        from .radar_direct import public_source_name

        derived = public_source_name(str((direct_item.get("source_urls") or [""])[0] or ""))
        if derived != str(direct_item.get("source_name") or ""):
            errors.append(f"radar-direct source name is not derived from the original URL for {url}")

        provenance = direct_item.get("copy_provenance") or {}
        title_provenance = direct_item.get("title_provenance") or {}
        if provenance.get("public_text_hash") != f"sha256:{content_hash(rendered['summary'])}":
            errors.append(
                f"Radar summary in HTML does not match the frozen copy provenance for {url}"
            )
        if title_provenance.get("public_text_hash") != f"sha256:{content_hash(rendered['title'])}":
            errors.append(
                f"Radar title in HTML does not match the frozen title provenance for {url}"
            )
    return errors


def publication_provenance_errors(
    root: Path,
    run_id: str,
    email_html: str,
    *,
    active_issue: dict[str, Any] | None = None,
) -> list[str]:
    """Prove that the final DOM is the structured publication, not a hand-edited lookalike.

    ``active_issue`` optionally supplies the database-backed active issue
    row (``run_id``/``date_to``); when present it is the external anchor the
    filesystem artifacts must match.
    """

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
    errors.extend(_direct_copy_provenance_errors(root, run_id, soup, manifest, active_issue=active_issue))

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
