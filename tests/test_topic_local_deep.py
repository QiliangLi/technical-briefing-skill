from __future__ import annotations

from briefing_skill.topic_local_deep import (
    pick_topic_local_refill_rows,
    select_topic_local_deep_budget,
)


def _row(index: int, topic: str, score: float, *, technology_value: float = 15.0):
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


def test_fetch_failure_refills_the_same_topic_before_other_topics():
    deferred = [
        _row(5, "tpn", 95, technology_value=19),
        _row(5, "dpu_inline", 99, technology_value=20),
    ]

    # TPN lost one of its four selected candidates. DPU still has all four. Even
    # though DPU's deferred candidate scores higher, it cannot steal TPN's refill.
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
