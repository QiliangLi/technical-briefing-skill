from __future__ import annotations

from briefing_skill.deep_selection_guard import select_deep_budget_with_complete_technology_value
from briefing_skill.topic_local_deep import (
    pick_topic_local_refill_rows,
    select_topic_local_deep_budget,
)


def _row(index: int, topic: str, score: float, *, technology_value: float | None = 15.0):
    return {
        "id": f"{topic}-{index}",
        "topic_id": topic,
        "direction_id": f"direction-{index}",
        "relevance_score": score,
        "rule_score": score,
        "priority": 20,
        "technology_value_score": technology_value,
    }


def _settings():
    return {
        "efficiency": {
            "max_fact_candidates_total": 32,
            "max_fact_candidates_hard_cap": 32,
            "max_fact_candidates_per_topic": 4,
        }
    }


def test_each_topic_gets_its_own_top_four_without_global_competition():
    rows = [
        *[_row(i, "tpn", 100 - i) for i in range(1, 6)],
        *[_row(i, "dpu_inline", 90 - i) for i in range(1, 6)],
    ]

    selected, deferred = select_topic_local_deep_budget(rows, _settings())

    assert [row["id"] for row in selected if row["topic_id"] == "tpn"] == [
        "tpn-1",
        "tpn-2",
        "tpn-3",
        "tpn-4",
    ]
    assert [row["id"] for row in selected if row["topic_id"] == "dpu_inline"] == [
        "dpu_inline-1",
        "dpu_inline-2",
        "dpu_inline-3",
        "dpu_inline-4",
    ]
    assert {row["id"] for row in deferred} == {"tpn-5", "dpu_inline-5"}


def test_topic_with_fewer_than_four_candidates_is_not_padded():
    selected, deferred = select_topic_local_deep_budget(
        [_row(1, "tpn", 90), _row(2, "tpn", 80), _row(1, "cross_region", 70)],
        _settings(),
    )

    assert len([row for row in selected if row["topic_id"] == "tpn"]) == 2
    assert len([row for row in selected if row["topic_id"] == "cross_region"]) == 1
    assert deferred == []


def test_final_selector_uses_technology_value_without_overwriting_relevance():
    rows = [
        _row(1, "tpn", 99, technology_value=1),
        _row(2, "tpn", 90, technology_value=20),
        _row(3, "tpn", 80, technology_value=20),
        _row(4, "tpn", 70, technology_value=20),
        _row(5, "tpn", 60, technology_value=20),
    ]

    selected, deferred = select_topic_local_deep_budget(rows, _settings())

    # 0.8*relevance + technology score preserves the existing Technology Value rank.
    assert [row["id"] for row in selected] == ["tpn-2", "tpn-1", "tpn-3", "tpn-4"]
    assert [row["id"] for row in deferred] == ["tpn-5"]
    assert next(row for row in selected if row["id"] == "tpn-1")["relevance_score"] == 99


def test_mixed_run_keeps_missing_technology_value_behind_assessed_rows_globally():
    rows = [
        _row(1, "tpn", 99, technology_value=None),
        _row(2, "tpn", 60, technology_value=12),
        _row(3, "tpn", 59, technology_value=12),
        _row(4, "tpn", 58, technology_value=12),
        _row(5, "tpn", 57, technology_value=12),
        _row(1, "cross_region", 95, technology_value=15),
    ]

    selected, deferred = select_topic_local_deep_budget(rows, _settings())

    assert "tpn-1" not in {row["id"] for row in selected}
    assert "tpn-1" in {row["id"] for row in deferred}


def test_legacy_guard_helper_delegates_to_same_final_selector():
    rows = [
        *[_row(i, "tpn", 100 - i, technology_value=15) for i in range(1, 6)],
        *[_row(i, "cross_region", 90 - i, technology_value=14) for i in range(1, 4)],
    ]

    assert select_deep_budget_with_complete_technology_value(rows, _settings()) == select_topic_local_deep_budget(rows, _settings())


def test_fetch_failure_refills_the_same_topic_before_other_topics():
    deferred = [
        _row(5, "tpn", 95, technology_value=19),
        _row(5, "dpu_inline", 99, technology_value=20),
    ]

    selected = pick_topic_local_refill_rows(
        deferred,
        existing_total=7,
        existing_topic_counts={"tpn": 3, "dpu_inline": 4},
        settings=_settings(),
    )

    assert [row["id"] for row in selected] == ["tpn-5"]


def test_refill_preserves_pr20_assessed_before_missing_value_order():
    deferred = [
        _row(5, "tpn", 99, technology_value=None),
        _row(6, "tpn", 80, technology_value=18),
    ]

    selected = pick_topic_local_refill_rows(
        deferred,
        existing_total=3,
        existing_topic_counts={"tpn": 3},
        settings=_settings(),
    )

    assert [row["id"] for row in selected] == ["tpn-6"]
