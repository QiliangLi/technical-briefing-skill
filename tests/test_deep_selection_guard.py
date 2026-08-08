from briefing_skill.deep_selection_guard import (
    require_technology_review_for_deep,
    select_deep_budget_with_complete_technology_value,
)
from briefing_skill.efficiency import RelevancePlan


def test_high_rule_deep_candidate_cannot_bypass_technology_review():
    high_rule = {
        "id": "release-high-rule",
        "topic_id": "tpn",
        "direction_id": "kv-scheduling",
        "rule_score": 130,
    }
    already_reviewed = {
        "id": "paper-reviewed",
        "topic_id": "tpn",
        "direction_id": "kv-scheduling",
        "rule_score": 70,
    }
    plan = RelevancePlan(
        accepted=(high_rule,),
        rejected=(),
        radar=(),
        batches=((already_reviewed,),),
    )

    guarded = require_technology_review_for_deep(
        plan,
        {"efficiency": {"deep_topics": ["tpn"]}, "max_relevance_batch": 24},
    )

    assert guarded.accepted == ()
    assert {row["id"] for batch in guarded.batches for row in batch} == {
        "release-high-rule",
        "paper-reviewed",
    }


def test_assessed_high_value_candidate_beats_missing_legacy_score():
    assessed = {
        "id": "paper-83",
        "topic_id": "tpn",
        "direction_id": "kv-scheduling",
        "relevance_score": 83,
        "rule_score": 60,
        "technology_value_score": 18,
        "identity_key": "paper-83",
    }
    legacy = {
        "id": "release-130",
        "topic_id": "tpn",
        "direction_id": "release-noise",
        "relevance_score": 130,
        "rule_score": 130,
        "technology_value_score": None,
        "identity_key": "release-130",
    }

    selected, deferred = select_deep_budget_with_complete_technology_value(
        [legacy, assessed],
        {
            "efficiency": {
                "max_fact_candidates_total": 1,
                "max_fact_candidates_per_topic": 1,
                "max_fact_candidates_per_direction": 1,
                "max_fact_candidates_per_project": 1,
            }
        },
    )

    assert [row["id"] for row in selected] == ["paper-83"]
    assert [row["id"] for row in deferred] == ["release-130"]
    assert selected[0]["technology_selection_score"] > deferred[0]["technology_selection_score"]
