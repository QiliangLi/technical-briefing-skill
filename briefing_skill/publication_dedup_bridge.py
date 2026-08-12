from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from .utils import canonicalize_url, normalize_text, source_identity_key


def exact_version_identity(url: str | None) -> str:
    """Normalize URL aliases that identify the same immutable source version.

    In particular, arXiv `/abs/<id>vN` and `/pdf/<id>vN.pdf` are one exact version.
    Unversioned arXiv URLs remain URL-specific because they can move to a newer version.
    """

    canonical = canonicalize_url(url)
    if not canonical:
        return ""
    parts = urlsplit(canonical)
    host = (parts.hostname or "").lower()
    path = unquote(parts.path or "").strip("/")
    if host in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        match = re.search(r"(?:abs|pdf)/([^/?#]+)", f"/{path}", flags=re.I)
        if match:
            value = re.sub(r"\.pdf$", "", match.group(1), flags=re.I)
            version = re.search(r"v(\d+)$", value, flags=re.I)
            if version:
                base = re.sub(r"v\d+$", "", value, flags=re.I).lower()
                return f"arxiv:{base}@v{version.group(1)}"
        return canonical
    identity = source_identity_key(canonical)
    if identity.startswith(("github-release:", "github-commit:", "doi:")):
        return identity
    return canonical


def project_exact_version_aliases(db, run_id: str | None = None) -> int:
    """Teach legacy URL-history readers every known alias of an already sent version."""

    try:
        published = db.fetchall(
            "SELECT canonical_url,normalized_title,sent_at,issue_id FROM published_sources"
        )
    except Exception:
        return 0
    by_version: dict[str, dict] = {}
    for row in published:
        key = exact_version_identity(row.get("canonical_url"))
        if key and (key not in by_version or str(row.get("sent_at") or "") > str(by_version[key].get("sent_at") or "")):
            by_version[key] = row
    if not by_version:
        return 0

    if run_id:
        raw_rows = db.fetchall(
            "SELECT original_url,canonical_url,title FROM raw_items WHERE run_id=?",
            (run_id,),
        )
    else:
        raw_rows = db.fetchall("SELECT original_url,canonical_url,title FROM raw_items")

    inserted = 0
    for raw in raw_rows:
        url = canonicalize_url(raw.get("original_url") or raw.get("canonical_url"))
        if not url:
            continue
        historical = by_version.get(exact_version_identity(url))
        if not historical:
            continue
        if db.fetchone("SELECT 1 AS ok FROM radar_history WHERE canonical_url=?", (url,)):
            continue
        db.execute(
            """
            INSERT OR REPLACE INTO radar_history(
              canonical_url,normalized_title,last_pushed_at,issue_id
            ) VALUES (?,?,?,?)
            """,
            (
                url,
                normalize_text(raw.get("title") or historical.get("normalized_title") or ""),
                historical["sent_at"],
                historical["issue_id"],
            ),
        )
        inserted += 1
    return inserted


def install_publication_dedup_bridge() -> None:
    """Bridge the canonical history into legacy selectors until they are retired."""

    from . import coverage_policy, radar_signal_synthesis

    if getattr(coverage_policy, "_publication_dedup_bridge_installed", False):
        return

    original_backlog = coverage_policy.materialize_deep_backlog
    original_appendix = coverage_policy.collect_topic_appendix
    original_radar = radar_signal_synthesis.build_radar_candidates

    def materialize_deep_backlog(config, db, run_id: str):
        project_exact_version_aliases(db)
        return original_backlog(config, db, run_id)

    def collect_topic_appendix(service, run_id: str, issue_data):
        project_exact_version_aliases(service.db, run_id)
        return original_appendix(service, run_id, issue_data)

    def build_radar_candidates(task_service, run_id: str, issue_input):
        project_exact_version_aliases(task_service.db, run_id)
        return original_radar(task_service, run_id, issue_input)

    coverage_policy.materialize_deep_backlog = materialize_deep_backlog
    coverage_policy.collect_topic_appendix = collect_topic_appendix
    radar_signal_synthesis.build_radar_candidates = build_radar_candidates
    coverage_policy._publication_dedup_bridge_installed = True
