from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .technology_value import technology_selection_score


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rank_rows(
    rows: Iterable[dict[str, Any]],
    *,
    any_assessed: bool | None = None,
) -> list[dict[str, Any]]:
    """Rank candidates with the canonical assessed-before-legacy compatibility rule."""

    source = [dict(row) for row in rows]
    assessed_exists = (
        any(row.get("technology_value_score") is not None for row in source)
        if any_assessed is None
        else bool(any_assessed)
    )

    def rank(row: dict[str, Any]) -> tuple[float, float, float, str]:
        if row.get("technology_value_score") is not None:
            primary = technology_selection_score(row)
        elif assessed_exists:
            primary = -1.0
        else:
            primary = _number(row.get("relevance_score"))
        return (
            -primary,
            -_number(row.get("rule_score")),
            -_number(row.get("priority")),
            str(row.get("id") or ""),
        )

    return sorted(source, key=rank)


def select_topic_local_deep_budget(
    rows: Iterable[dict[str, Any]],
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select the Technology-Value-ranked Top N independently inside each topic.

    This is the final Deep selector. It owns both ranking and budget semantics instead
    of relying on a wrapper to temporarily overwrite relevance_score before calling a
    separately monkey-patched coverage selector. Product behavior remains identical:
    assessed candidates rank by 0.8*relevance + Technology Value, missing legacy rows
    fall behind assessed rows in a mixed run, and every topic receives its own Top4.
    """

    policy = dict(settings.get("efficiency") or {})
    per_topic_max = max(1, int(policy.get("max_fact_candidates_per_topic", 4)))
    hard_cap = max(
        per_topic_max,
        int(policy.get("max_fact_candidates_hard_cap", policy.get("max_fact_candidates_total", 32))),
    )

    source_rows = [dict(row) for row in rows]
    any_assessed = any(row.get("technology_value_score") is not None for row in source_rows)
    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        by_topic[str(row.get("topic_id") or "unknown")].append(row)

    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for topic_id in sorted(by_topic):
        ordered = _rank_rows(by_topic[topic_id], any_assessed=any_assessed)
        for row in ordered:
            if row.get("technology_value_score") is not None:
                row["technology_selection_score"] = technology_selection_score(row)
            elif any_assessed:
                row["technology_selection_score"] = -1.0
            else:
                row["technology_selection_score"] = _number(row.get("relevance_score"))
            row["technology_value_missing"] = row.get("technology_value_score") is None
        selected.extend(ordered[:per_topic_max])
        deferred.extend(ordered[per_topic_max:])

    if len(selected) > hard_cap:
        raise RuntimeError(
            "topic-local deep selection exceeds max_fact_candidates_hard_cap; "
            "increase the safety cap instead of silently starving a topic"
        )
    return selected, deferred


def pick_topic_local_refill_rows(
    deferred_rows: Iterable[dict[str, Any]],
    *,
    existing_total: int,
    existing_topic_counts: dict[str, int],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    """Refill failed Deep work from the same topic before any slot can disappear."""

    policy = dict(settings.get("efficiency") or {})
    per_topic_max = max(1, int(policy.get("max_fact_candidates_per_topic", 4)))
    hard_cap = max(
        per_topic_max,
        int(policy.get("max_fact_candidates_hard_cap", policy.get("max_fact_candidates_total", 32))),
    )
    remaining_total = max(0, hard_cap - max(0, int(existing_total)))
    if not remaining_total:
        return []

    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in deferred_rows:
        by_topic[str(row.get("topic_id") or "unknown")].append(dict(row))

    selected: list[dict[str, Any]] = []
    for topic_id in sorted(by_topic):
        current = max(0, int(existing_topic_counts.get(topic_id, 0)))
        deficit = max(0, per_topic_max - current)
        if not deficit:
            continue
        ordered = _rank_rows(by_topic[topic_id])
        take = min(deficit, remaining_total - len(selected))
        if take <= 0:
            break
        selected.extend(ordered[:take])
    return selected


def install_topic_local_deep_policy() -> None:
    """Install one explicit final Deep selector plus topic-local refill semantics."""

    from . import efficiency, safe_efficiency
    from .pipeline import Pipeline

    if getattr(Pipeline, "_topic_local_deep_policy_installed", False):
        return

    # Direct ownership removes the previous three-layer selector chain:
    # Technology Value -> Deep Guard -> monkey-patched coverage selector.
    efficiency.select_deep_budget = select_topic_local_deep_budget

    # Fetch-failure refill remains topic-local and resolves this function at runtime.
    safe_efficiency.pick_deep_refill_rows = pick_topic_local_refill_rows

    Pipeline._topic_local_deep_policy_installed = True
