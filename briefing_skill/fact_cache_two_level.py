from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import now_iso, stable_hash


L0_LEVEL = "l0_immutable"
L1_PRE_LEVEL = "l1_hash_pre_fetch"
L1_POST_LEVEL = "l1_hash_post_fetch"


def immutable_source_key(raw: dict[str, Any]) -> str | None:
    """Return a key only for sources whose exact version is provably immutable."""

    from .safe_efficiency import exact_primary_version_key

    return exact_primary_version_key(raw)


def lookup_immutable_fact_cache(
    db,
    root: Path,
    *,
    mode: str,
    source_fingerprint: str,
    extractor_version: str,
    source_content_hash: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Reuse V2 facts without source I/O only after immutable identity is proven.

    The caller is responsible for proving an exact immutable source version. Once that
    is true, the source fingerprint already binds that version while extractor_version
    binds topic, direction, project context, prompts, schema and evidence policy.
    Stored source/evidence hashes remain part of the cache payload and are still
    validated for tamper detection; they simply do not need to be recomputed.
    """

    from .fact_cache_provenance import (
        _cache_payload_is_valid,
        ensure_fact_cache_provenance_schema,
        readable_namespaces,
    )

    ensure_fact_cache_provenance_schema(db)
    for namespace in readable_namespaces(mode):
        rows = db.fetchall(
            """
            SELECT * FROM fact_cache_v2
            WHERE cache_namespace=? AND source_fingerprint=? AND extractor_version=?
              AND source_content_hash=?
            ORDER BY last_used_at DESC, created_at DESC
            """,
            (namespace, source_fingerprint, extractor_version, source_content_hash),
        )
        for row in rows:
            facts = _cache_payload_is_valid(row, root)
            if facts is None:
                continue
            db.execute(
                "UPDATE fact_cache_v2 SET last_used_at=? WHERE cache_key=?",
                (now_iso(), row["cache_key"]),
            )
            return dict(row), facts
    return None


def _cache_hit_manifest(
    service,
    run_id: str,
    candidate: dict[str, Any],
    raw: dict[str, Any],
    row: dict[str, Any],
    *,
    mode: str,
    source_fingerprint: str,
    extractor_version: str,
    source_content_hash: str,
    level: str,
    base_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert either a zero-I/O hit or a post-fetch hit into one cache-fastpath manifest."""

    manifest = dict(base_manifest or {})
    url = raw.get("original_url") or raw.get("canonical_url") or raw.get("aihot_url")
    document_id = str(manifest.get("document_id") or stable_hash(run_id, candidate["id"], url))
    if not manifest.get("text_path"):
        stub = service.run_dir / "documents" / f"{document_id}.evidence.md"
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text(
            "# Fact cache v2 hit\n\nValidated facts were reused from an exact immutable source/version and extractor context.\n",
            encoding="utf-8",
        )
        manifest.update(
            {
                "text_path": str(stub),
                "chunks": [str(stub)],
                "media_type": "application/x-fact-cache-v2",
                "fetch_status": "FETCHED",
                "char_count": int(row.get("evidence_char_count") or 0),
                "raw_char_count": int(row.get("raw_char_count") or 0),
                "evidence_char_count": int(row.get("evidence_char_count") or 0),
            }
        )
    manifest.update(
        {
            "document_id": document_id,
            "candidate_id": candidate["id"],
            "url": url,
            "fact_cache_hit": True,
            "fact_cache_v2_hit": True,
            "fact_cache_key": row["cache_key"],
            "fact_cache_v2_key": row["cache_key"],
            "fact_cache_v2_namespace": row["cache_namespace"],
            "fact_cache_v2_mode": mode,
            "fact_cache_lookup_level": level,
            "source_fingerprint": source_fingerprint,
            "extractor_version": extractor_version,
            "source_content_hash": source_content_hash,
            "source_text_hash": row.get("source_text_hash") or manifest.get("source_text_hash") or "",
            "evidence_hash": row.get("evidence_hash") or manifest.get("evidence_hash") or "",
            "fact_cache_v2_eligible": True,
        }
    )
    return manifest


def _post_fetch_l1_hit(
    db,
    root: Path,
    *,
    mode: str,
    source_fingerprint: str,
    extractor_version: str,
    source_content_hash: str,
    manifest: dict[str, Any],
):
    """Re-check V2 immediately after source/evidence hashes become available."""

    if manifest.get("fact_cache_v2_hit"):
        return None
    source_text_hash = str(manifest.get("source_text_hash") or "")
    evidence_hash = str(manifest.get("evidence_hash") or "")
    if not source_text_hash or not evidence_hash:
        return None
    if str(manifest.get("fetch_status") or "").upper() == "FALLBACK":
        return None
    from .fact_cache_provenance import lookup_fact_cache_v2

    return lookup_fact_cache_v2(
        db,
        root,
        mode=mode,
        source_fingerprint=source_fingerprint,
        extractor_version=extractor_version,
        source_content_hash=source_content_hash,
        source_text_hash=source_text_hash,
        evidence_hash=evidence_hash,
    )


def install_two_level_fact_cache() -> None:
    """Add L0 immutable reuse and a post-fetch L1 lookup to authoritative Fact Cache V2."""

    from .deep_efficiency import _cache_eligible, _runtime_extractor_version, _source_fingerprint
    from .fact_cache_provenance import _source_content_hash, execution_mode
    from .fulltext import FulltextService
    from .pipeline import Pipeline

    if getattr(Pipeline, "_two_level_fact_cache_installed", False):
        return

    original_fetch = FulltextService.fetch_candidate

    def fetch_candidate(self, run_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
        effective = dict(candidate)
        if not effective.get("topic_id") or not effective.get("direction_id"):
            lane = self.db.fetchone(
                "SELECT topic_id,direction_id FROM candidates WHERE id=?",
                (effective["id"],),
            )
            if lane:
                effective.setdefault("topic_id", lane.get("topic_id"))
                effective.setdefault("direction_id", lane.get("direction_id"))

        raw = self.db.fetchone("SELECT * FROM raw_items WHERE id=?", (effective["raw_item_id"],))
        if not raw:
            raise KeyError(effective["raw_item_id"])
        root = self.run_dir.parents[2]
        topic_id = str(effective.get("topic_id") or "")
        direction_id = str(effective.get("direction_id") or "")
        fingerprint = _source_fingerprint(raw)
        version = _runtime_extractor_version(self.config, root, topic_id, direction_id)
        mode = execution_mode(self.db, run_id, raw)
        content_hash = _source_content_hash(raw)
        enabled = bool((self.config.settings.get("efficiency") or {}).get("fact_cache_enabled", True))
        eligible = enabled and _cache_eligible(raw) and bool(topic_id and direction_id)

        # L0: only a provably immutable exact source version may bypass source I/O.
        immutable_key = immutable_source_key(raw) if eligible else None
        if immutable_key:
            hit = lookup_immutable_fact_cache(
                self.db,
                root,
                mode=mode,
                source_fingerprint=fingerprint,
                extractor_version=version,
                source_content_hash=content_hash,
            )
            if hit:
                row, _facts = hit
                return _cache_hit_manifest(
                    self,
                    run_id,
                    effective,
                    raw,
                    row,
                    mode=mode,
                    source_fingerprint=fingerprint,
                    extractor_version=version,
                    source_content_hash=content_hash,
                    level=L0_LEVEL,
                )

        manifest = original_fetch(self, run_id, effective)
        if manifest.get("fact_cache_v2_hit"):
            manifest = dict(manifest)
            manifest.setdefault("fact_cache_lookup_level", L1_PRE_LEVEL)
            return manifest

        # L1 post-fetch: if no local source was available for the pre-fetch lookup,
        # do not waste the hashes just computed by network fetch + EvidenceBuilder.
        if eligible:
            hit = _post_fetch_l1_hit(
                self.db,
                root,
                mode=mode,
                source_fingerprint=fingerprint,
                extractor_version=version,
                source_content_hash=content_hash,
                manifest=manifest,
            )
            if hit:
                row, _facts = hit
                return _cache_hit_manifest(
                    self,
                    run_id,
                    effective,
                    raw,
                    row,
                    mode=mode,
                    source_fingerprint=fingerprint,
                    extractor_version=version,
                    source_content_hash=content_hash,
                    level=L1_POST_LEVEL,
                    base_manifest=manifest,
                )
        return manifest

    FulltextService.fetch_candidate = fetch_candidate
    Pipeline._two_level_fact_cache_installed = True
