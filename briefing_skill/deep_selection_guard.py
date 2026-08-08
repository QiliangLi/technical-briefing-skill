from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .efficiency import DEFAULT_DEEP_TOPICS, RelevancePlan
from .technology_value import technology_selection_score


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _deep_topics(settings: dict[str, Any]) -> set[str]:
    policy = dict(settings.get("efficiency") or {})
    return set(policy.get("deep_topics") or DEFAULT_DEEP_TOPICS)


def require_technology_review_for_deep(
    plan: RelevancePlan,
    settings: dict[str, Any],
) -> RelevancePlan:
    """Prevent deterministic rule-score acceptance from bypassing Technology Value.

    Deep-topic A-level candidates may still be rejected deterministically at the low
    rule-score floor, but candidates strong enough to compete for Deep analysis must
    pass the relevance/Technology Value batch. Horizontal/Radar behavior is unchanged.
    """

    deep_topics = _deep_topics(settings)
    moved = [row for row in plan.accepted if str(row.get("topic_id") or "") in deep_topics]
    if not moved:
        return plan

    accepted = tuple(
        row for row in plan.accepted if str(row.get("topic_id") or "") not in deep_topics
    )
    passthrough_batches: list[tuple[dict[str, Any], ...]] = []
    deep_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for batch in plan.batches:
        if not batch:
            continue
        topic_id = str(batch[0].get("topic_id") or "")
        if topic_id in deep_topics:
            deep_rows[topic_id].extend(batch)
        else:
            passthrough_batches.append(batch)
    for row in moved:
        deep_rows[str(row.get("topic_id") or "")].append(row)

    batch_size = max(1, int(settings.get("max_relevance_batch", 12)))
    rebuilt: list[tuple[dict[str, Any], ...]] = []
    for topic_id in sorted(deep_rows):
        deduped: dict[str, dict[str, Any]] = {}
        for row in deep_rows[topic_id]:
            deduped[str(row.get("id") or id(row))] = row
        ordered = sorted(
            deduped.values(),
            key=lambda row: (-_number(row.get("rule_score")), str(row.get("id") or "")),
        )
        rebuilt.extend(tuple(ordered[i : i + batch_size]) for i in range(0, len(ordered), batch_size))

    return RelevancePlan(
        accepted=accepted,
        rejected=plan.rejected,
        radar=plan.radar,
        batches=tuple(passthrough_batches + rebuilt),
    )


def select_deep_budget_with_complete_technology_value(
    rows: Iterable[dict[str, Any]],
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rank assessed candidates ahead of legacy/missing Technology Value rows.

    A partially evaluated pool is the dangerous case: a legacy deterministic accept can
    otherwise keep a very large rule/relevance score and outrank candidates that actually
    received Technology Value assessment. Missing-value rows remain eligible only after
    assessed rows, so unfinished legacy runs can still make progress without letting the
    bypass dominate a mixed pool.
    """

    from . import coverage_policy

    source_rows = [dict(row) for row in rows]
    if not source_rows:
        return [], []
    any_assessed = any(row.get("technology_value_score") is not None for row in source_rows)

    originals: dict[str, float] = {}
    prepared: list[dict[str, Any]] = []
    for row in source_rows:
        row_id = str(row.get("id") or "")
        originals[row_id] = _number(row.get("relevance_score"))
        if row.get("technology_value_score") is not None:
            rank = technology_selection_score(row)
        elif any_assessed:
            rank = -1.0
        else:
            rank = originals[row_id]
        row["relevance_score"] = rank
        row["technology_selection_score"] = rank
        row["technology_value_missing"] = row.get("technology_value_score") is None
        prepared.append(row)

    selected, deferred = coverage_policy.select_diverse_deep_budget(prepared, settings)
    for row in [*selected, *deferred]:
        row["relevance_score"] = originals.get(str(row.get("id") or ""), _number(row.get("relevance_score")))
    return selected, deferred


def install_deep_selection_guard() -> None:
    """Close the rule-score bypass after Technology Value has been installed."""

    from . import efficiency
    from .pipeline import Pipeline

    if getattr(Pipeline, "_deep_selection_guard_installed", False):
        return

    original_plan = efficiency.plan_relevance_rows

    def plan_relevance_rows(rows, settings):
        return require_technology_review_for_deep(original_plan(rows, settings), settings)

    efficiency.plan_relevance_rows = plan_relevance_rows
    efficiency.select_deep_budget = select_deep_budget_with_complete_technology_value
    Pipeline._deep_selection_guard_installed = True
