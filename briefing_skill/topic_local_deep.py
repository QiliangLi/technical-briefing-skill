from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .technology_value import technology_selection_score


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rank_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank a topic-local pool consistently with the Technology Value guard.

    New runs should have Technology Value on every deep-topic candidate. For legacy
    mixed pools, assessed rows stay ahead of missing-value rows just like PR20's
    deep-selection guard. If the whole pool predates Technology Value, relevance
    remains the compatibility fallback.
    """

    source = [dict(row) for row in rows]
    any_assessed = any(row.get("technology_value_score") is not None for row in source)

    def rank(row: dict[str, Any]) -> tuple[float, float, float, str]:
        if row.get("technology_value_score") is not None:
            primary = technology_selection_score(row)
        elif any_assessed:
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
    """Select the top N deep candidates independently inside every deep topic.

    Topic ranking is the product contract: a hot topic may not consume another
    topic's detailed-reading slots. The configured hard cap is only a safety fuse;
    it must be large enough for all active topic-local quotas and never silently
    reintroduces cross-topic competition.
    """

    policy = dict(settings.get("efficiency") or {})
    per_topic_max = max(1, int(policy.get("max_fact_candidates_per_topic", 4)))
    hard_cap = max(
        per_topic_max,
        int(policy.get("max_fact_candidates_hard_cap", policy.get("max_fact_candidates_total", 32))),
    )

    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_topic[str(row.get("topic_id") or "unknown")].append(dict(row))

    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for topic_id in sorted(by_topic):
        ordered = sorted(
            by_topic[topic_id],
            key=lambda row: (
                -_number(row.get("relevance_score")),
                -_number(row.get("rule_score")),
                -_number(row.get("priority")),
                str(row.get("id") or ""),
            ),
        )
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
    """Refill failed deep work from the same topic before any slot can disappear.

    With topic-local Top4 selection, a topic has deferred rows only after its first
    four ranked candidates were selected. Therefore a topic that now has fewer than
    four occupied Fact slots and still has deferred candidates has lost executable
    work and should refill locally. Topics that never had enough candidates have no
    deferred tail and are not padded with weak material.
    """

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
    """Replace global deep-slot competition with per-topic Top4 semantics."""

    from . import coverage_policy, safe_efficiency
    from .pipeline import Pipeline

    if getattr(Pipeline, "_topic_local_deep_policy_installed", False):
        return

    # PR20's final selector calls coverage_policy.select_diverse_deep_budget at
    # runtime after it has converted relevance_score to Technology Value ranking.
    # Replacing this function therefore preserves PR20 ranking while changing only
    # the budget semantics from global competition to topic-local Top4.
    coverage_policy.select_diverse_deep_budget = select_topic_local_deep_budget

    # safe_efficiency's nested fetch-failure loop resolves this module global at
    # runtime, so replacing it makes every vacated slot refill from its own topic.
    safe_efficiency.pick_deep_refill_rows = pick_topic_local_refill_rows

    Pipeline._topic_local_deep_policy_installed = True
