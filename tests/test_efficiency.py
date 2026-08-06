from briefing_skill.efficiency import (
    direction_is_covered,
    estimate_task_reduction,
    plan_relevance_rows,
    radar_category,
    select_deep_budget,
)


def settings():
    return {
        "max_relevance_batch": 12,
        "efficiency": {
            "auto_accept_rule_score": 85,
            "auto_reject_rule_score": 15,
            "radar_promotion_rule_score": 88,
            "radar_topics": ["ai_infra_horizontal"],
            "max_fact_candidates_total": 4,
            "max_fact_candidates_per_topic": 2,
        },
    }


def row(index, *, score=50, level="A", discovery=False, topic="tpn"):
    return {
        "id": f"c{index}",
        "rule_score": score,
        "source_level": level,
        "discovery_only": discovery,
        "topic_id": topic,
        "relevance_score": score,
        "priority": score,
    }


def test_relevance_plan_uses_rules_radar_and_topic_batches():
    rows = [row(1, score=90), row(2, score=10), row(3, level="B"), row(4, score=50), row(5, score=60)]
    plan = plan_relevance_rows(rows, settings())
    assert [item["id"] for item in plan.accepted] == ["c1"]
    assert [item["id"] for item in plan.rejected] == ["c2"]
    assert [item["id"] for item in plan.radar] == ["c3"]
    assert [[item["id"] for item in batch] for batch in plan.batches] == [["c5", "c4"]]
    assert plan.agent_task_count == 1


def test_horizontal_primary_requires_promotion_score():
    plan = plan_relevance_rows(
        [row(1, score=87, topic="ai_infra_horizontal"), row(2, score=90, topic="ai_infra_horizontal")],
        settings(),
    )
    assert [item["id"] for item in plan.radar] == ["c1"]
    assert [item["id"] for item in plan.accepted] == ["c2"]


def test_deep_budget_preserves_topic_diversity():
    rows = [
        row(1, score=99, topic="tpn"), row(2, score=98, topic="tpn"), row(3, score=97, topic="tpn"),
        row(4, score=96, topic="dpu_inline"), row(5, score=95, topic="agent_acceleration"),
    ]
    selected, deferred = select_deep_budget(rows, settings())
    assert [item["id"] for item in selected] == ["c1", "c2", "c4", "c5"]
    assert [item["id"] for item in deferred] == ["c3"]


def test_direction_coverage_uses_hints_or_multiple_terms():
    direction = {"id": "kv_transfer", "include_terms": ["kv cache", "network", "transfer"]}
    assert direction_is_covered([{"topic_hint": "tpn", "direction_hint": "kv_transfer"}], "tpn", direction)
    assert direction_is_covered([{"title": "KV cache transfer over network", "summary": ""}], "tpn", direction)
    assert not direction_is_covered([{"title": "CPU cache tutorial", "summary": ""}], "tpn", direction)


def test_radar_categories_cover_requested_horizontal_scope():
    assert radar_category("MCP agent runtime released", "") == "Agent生态"
    assert radar_category("LMCache prefix cache routing", "") == "KVCache生态"
    assert radar_category("QLC NVMe SSD for AI storage", "") == "存储与介质"
    assert radar_category("New inference compiler runtime", "") == "AI Infra"
    assert radar_category("New foundation model benchmark", "") == "其他"


def test_representative_workload_reduces_agent_tasks_over_70_percent():
    estimate = estimate_task_reduction(
        candidates=100,
        ambiguous_candidates=36,
        batch_size=12,
        fact_candidates_before=17,
        fact_budget=12,
        item_candidates_before=17,
        item_budget=10,
        search_before=18,
        search_after=4,
    )
    assert estimate["relevance_tasks_after"] == 3
    assert estimate["task_reduction_ratio"] >= 0.70
