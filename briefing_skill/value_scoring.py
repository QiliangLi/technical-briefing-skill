from __future__ import annotations

from typing import Any


def value_aware_event_score(scorer, facts: list[dict[str, Any]], candidates: list[dict[str, Any]], raw_items: list[dict[str, Any]]) -> float:
    """Rank events primarily by the semantic value review, not field counts.

    relevance_score is produced by the batch rubric (project relevance, technical
    substance, evidence, actionability, freshness). Fact extraction then adjusts
    confidence using source-level evidence quality without re-inventing novelty
    from the number of populated JSON fields.
    """

    if not facts or not candidates:
        return 0.0
    relevance = max(float(candidate.get("relevance_score") or 0) for candidate in candidates)
    fact_quality = max(float(fact.get("quality_score") or 0) for fact in facts)
    evidence = [entry for fact in facts for entry in (fact.get("evidence") or []) if isinstance(entry, dict)]
    quantitative = sum(1 for entry in evidence if entry.get("value") not in (None, ""))
    conditioned = sum(1 for entry in evidence if entry.get("baseline") or entry.get("condition"))
    evidence_bonus = min(8.0, len(evidence) * 1.0 + quantitative * 1.5 + conditioned * 0.5)
    multi_source_bonus = 3.0 if len({item.get("canonical_url") for item in raw_items if item.get("canonical_url")}) >= 2 else 0.0
    freshness_bonus = scorer._freshness(raw_items) * 4.0
    score = relevance * 0.65 + fact_quality * 0.20 + evidence_bonus + multi_source_bonus + freshness_bonus
    return round(min(100.0, score), 2)


def install_value_scoring() -> None:
    """Install value-aware final scoring and a hard full-text score floor."""

    from .pipeline import Pipeline
    from .scoring import Scorer

    if getattr(Scorer, "_value_scoring_installed", False):
        return

    original_apply = Pipeline._apply_task

    def apply_task(self, task: dict[str, Any]) -> None:
        original_apply(self, task)
        if task.get("task_type") != "relevance_batch":
            return
        threshold = float(
            (self.config.scoring.get("thresholds") or {}).get("relevance_fulltext", 65)
        )
        self.db.execute(
            """
            UPDATE candidates
            SET fulltext_required=0, status='RADAR'
            WHERE run_id=? AND status='RELEVANT'
              AND COALESCE(relevance_score, 0) < ?
            """,
            (self.run_id, threshold),
        )

    Scorer.event_score = value_aware_event_score
    Scorer._value_scoring_installed = True
    Pipeline._apply_task = apply_task
