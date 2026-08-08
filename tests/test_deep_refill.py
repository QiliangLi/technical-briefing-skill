from __future__ import annotations

from briefing_skill.safe_efficiency import pick_deep_refill_rows


def test_deep_refill_only_fills_vacated_slots_and_respects_topic_cap():
    deferred = [
        {"id": "tpn-high", "topic_id": "tpn", "relevance_score": 95, "rule_score": 90, "priority": 20},
        {"id": "agent-high", "topic_id": "agent_acceleration", "relevance_score": 93, "rule_score": 89, "priority": 18},
        {"id": "cross-next", "topic_id": "cross_region", "relevance_score": 91, "rule_score": 88, "priority": 17},
    ]
    settings = {
        "efficiency": {
            "max_fact_candidates_total": 4,
            "max_fact_candidates_per_topic": 2,
        }
    }

    # Three real fact tasks already occupy the budget: TPN has reached its per-topic
    # cap, so the one vacated slot must be filled by the best candidate from another
    # topic rather than silently shrinking the deep-analysis set.
    selected = pick_deep_refill_rows(
        deferred,
        existing_total=3,
        existing_topic_counts={"tpn": 2, "cross_region": 1},
        settings=settings,
    )
    assert [row["id"] for row in selected] == ["agent-high"]


def test_deep_refill_never_expands_configured_budget():
    selected = pick_deep_refill_rows(
        [{"id": "extra", "topic_id": "tpn", "relevance_score": 99}],
        existing_total=4,
        existing_topic_counts={"tpn": 1},
        settings={
            "efficiency": {
                "max_fact_candidates_total": 4,
                "max_fact_candidates_per_topic": 4,
            }
        },
    )
    assert selected == []
