import json

from briefing_skill.technology_value import (
    normalise_technology_value,
    select_deep_budget_with_technology_value,
    technology_selection_score,
    technology_value_semantic_errors,
)


def _row(candidate_id, relevance, technology, *, repo, direction="d1"):
    return {
        "id": candidate_id,
        "topic_id": "tpn",
        "direction_id": direction,
        "relevance_score": relevance,
        "technology_value_score": technology,
        "rule_score": 50,
        "priority": 10,
        "payload_json": json.dumps({"repo": repo}),
        "original_url": f"https://github.com/{repo}",
    }


def test_normalise_technology_value_clamps_dimensions_and_recomputes_total():
    value = normalise_technology_value(
        {
            "novelty": {"score": 7, "reason": "new mechanism"},
            "architecture_impact": {"score": 4, "reason": "changes data path"},
            "industry_signal": {"score": -2, "reason": "isolated"},
            "project_alignment": {"score": 5, "reason": "directly relevant"},
            "total_score": 999,
        }
    )
    assert value["novelty"]["score"] == 5
    assert value["industry_signal"]["score"] == 0
    assert value["total_score"] == 14


def test_technology_value_is_separate_from_relevance_but_can_change_deep_order():
    routine = _row("routine", 92, 3, repo="org/routine")
    architecture = _row("architecture", 82, 19, repo="org/architecture")

    assert technology_selection_score(routine) == 76.6
    assert technology_selection_score(architecture) == 84.6

    selected, deferred = select_deep_budget_with_technology_value(
        [routine, architecture],
        {
            "efficiency": {
                "max_fact_candidates_total": 1,
                "max_fact_candidates_per_topic": 1,
                "max_fact_candidates_per_direction": 2,
                "max_fact_candidates_per_project": 1,
            }
        },
    )
    assert [row["id"] for row in selected] == ["architecture"]
    assert [row["id"] for row in deferred] == ["routine"]
    assert selected[0]["relevance_score"] == 82


def test_existing_same_project_diversity_constraint_is_preserved():
    release_a = _row("release-a", 90, 18, repo="org/shared", direction="d1")
    release_b = _row("release-b", 88, 17, repo="org/shared", direction="d2")
    alternative = _row("alternative", 80, 15, repo="org/other", direction="d2")

    selected, _ = select_deep_budget_with_technology_value(
        [release_a, release_b, alternative],
        {
            "efficiency": {
                "max_fact_candidates_total": 2,
                "max_fact_candidates_per_topic": 2,
                "max_fact_candidates_per_direction": 2,
                "max_fact_candidates_per_project": 1,
            }
        },
    )
    assert {row["id"] for row in selected} == {"release-a", "alternative"}


def test_missing_technology_value_never_penalises_existing_relevance_path():
    row = {"relevance_score": 83, "technology_value_score": None}
    assert technology_selection_score(row) == 83


def test_new_relevance_task_requires_technology_value():
    task = {
        "task_type": "relevance_batch",
        "metadata_json": json.dumps({"technology_value_required": True}),
    }
    errors = technology_value_semantic_errors(task, {"results": [{"candidate_id": "c1"}]})
    assert errors == ["relevance result 0 requires technology_value"]


def test_legacy_relevance_task_without_policy_marker_remains_compatible():
    task = {"task_type": "relevance_batch", "metadata_json": "{}"}
    assert technology_value_semantic_errors(task, {"results": [{"candidate_id": "c1"}]}) == []
