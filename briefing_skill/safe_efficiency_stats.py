from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .utils import read_json


def _ratio(saved: int, original: int) -> float | None:
    if original <= 0:
        return None
    return round(saved / original, 4)


def safe_efficiency_metrics(db, root: Path, run_id: str) -> dict[str, Any]:
    duplicate_row = db.fetchone(
        "SELECT COUNT(*) AS n FROM candidates WHERE run_id=? AND status='DUPLICATE_PRIMARY'",
        (run_id,),
    ) or {"n": 0}
    deferred_fetch_row = db.fetchone(
        "SELECT COUNT(*) AS n FROM candidates WHERE run_id=? AND status='DEFERRED_FETCH'",
        (run_id,),
    ) or {"n": 0}

    editorial_deferred = 0
    event_rows = db.fetchall(
        """
        SELECT DISTINCT e.id, e.payload_json
        FROM events e JOIN event_members em ON em.event_id=e.id
        WHERE em.run_id=?
        """,
        (run_id,),
    )
    for row in event_rows:
        try:
            payload = json.loads(row.get("payload_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict) and payload.get("editorial_deferred"):
            editorial_deferred += 1

    raw_cache_hits = 0
    raw_cache_observations = 0
    documents_dir = root / "workspace" / "runs" / run_id / "documents"
    if documents_dir.is_dir():
        for path in documents_dir.glob("*.json"):
            manifest = read_json(path, {})
            if not isinstance(manifest, dict) or "raw_fulltext_cache_hit" not in manifest:
                continue
            raw_cache_observations += 1
            raw_cache_hits += int(bool(manifest.get("raw_fulltext_cache_hit")))

    targeted_repairs = 0
    repair_input_chars = 0
    original_input_chars = 0
    for row in db.fetchall("SELECT metadata_json FROM tasks WHERE run_id=?", (run_id,)):
        try:
            metadata = json.loads(row.get("metadata_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        if not isinstance(metadata, dict) or not metadata.get("targeted_repair_attempts"):
            continue
        targeted_repairs += int(metadata.get("targeted_repair_attempts") or 0)
        repair_input_chars += int(metadata.get("repair_input_chars") or 0)
        original_input_chars += int(metadata.get("original_input_chars") or 0)

    saved_repair_chars = max(0, original_input_chars - repair_input_chars)
    return {
        "exact_primary_candidates_suppressed": int(duplicate_row.get("n") or 0),
        "deferred_fetch_candidates": int(deferred_fetch_row.get("n") or 0),
        "editorial_events_skipped_below_score_floor": editorial_deferred,
        "raw_fulltext_cache_observations": raw_cache_observations,
        "raw_fulltext_cache_hits": raw_cache_hits,
        "raw_fulltext_cache_hit_rate": _ratio(raw_cache_hits, raw_cache_observations),
        "targeted_invalid_repairs": targeted_repairs,
        "targeted_repair_original_input_chars": original_input_chars,
        "targeted_repair_sidecar_chars": repair_input_chars,
        "targeted_repair_input_chars_saved": saved_repair_chars,
        "targeted_repair_input_reduction_ratio": _ratio(saved_repair_chars, original_input_chars),
    }


def install_safe_efficiency_stats() -> None:
    """Append quality-neutral optimization counters to the existing stats command."""

    from . import telemetry

    if getattr(telemetry, "_safe_efficiency_stats_installed", False):
        return
    original_run_stats = telemetry.run_stats

    def run_stats(db, root: Path, run_id: str):
        result = original_run_stats(db, root, run_id)
        result["safe_efficiency"] = safe_efficiency_metrics(db, root, run_id)
        notes = list(result.get("notes") or [])
        notes.append(
            "safe_efficiency counters describe deterministic work avoided or local cache reuse; they are not measured Codex token billing."
        )
        result["notes"] = notes
        return result

    telemetry.run_stats = run_stats
    telemetry._safe_efficiency_stats_installed = True
