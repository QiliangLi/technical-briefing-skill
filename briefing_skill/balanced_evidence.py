from __future__ import annotations

from typing import Any


def build_balanced_evidence_pack(
    text: str,
    topic: dict[str, Any],
    direction: dict[str, Any],
    *,
    max_chars: int = 18000,
) -> str:
    """Compatibility alias for callers predating the canonical EvidenceBuilder."""

    from .deep_efficiency import build_evidence_pack

    return build_evidence_pack(text, topic, direction, max_chars=max_chars)


def _repair_health(db, run_id: str) -> dict[str, Any]:
    fact = db.fetchone(
        "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='fact_extraction'",
        (run_id,),
    )
    repair = db.fetchone(
        "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='fact_evidence_repair'",
        (run_id,),
    )
    fact_count = int((fact or {}).get("n") or 0)
    repair_count = int((repair or {}).get("n") or 0)
    rate = round(repair_count / fact_count, 4) if fact_count else 0.0
    return {
        "fact_tasks": fact_count,
        "repair_tasks": repair_count,
        "repair_rate": rate,
        "status": "warning" if fact_count and rate > 0.25 else "healthy",
        "warning_threshold": 0.25,
        "note": "Repair is an exception path; >25% indicates the first-read evidence policy needs attention.",
    }


def install_balanced_evidence() -> None:
    """Expose Evidence Repair health without replacing the canonical builder."""

    from . import telemetry
    from .pipeline import Pipeline

    if getattr(Pipeline, "_balanced_evidence_installed", False):
        return

    original_stats = telemetry.run_stats

    def run_stats(db, root, run_id: str):
        payload = original_stats(db, root, run_id)
        payload["evidence_repair_health"] = _repair_health(db, run_id)
        return payload

    telemetry.run_stats = run_stats
    Pipeline._balanced_evidence_installed = True
