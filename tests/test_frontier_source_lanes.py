from types import SimpleNamespace

from briefing_skill.frontier_source_lanes import (
    FRONTIER_CATEGORY,
    _rebalance_candidates,
)


def _row(url: str, category: str, level: str, lane: str):
    return {
        "candidate_id": url,
        "category": category,
        "title": url,
        "summary": "这是一个足够长的技术摘要，用于测试来源赛道混排。",
        "url": url,
        "source_level": level,
        "source_lane": lane,
    }


def test_observation_category_reserves_room_for_builder_sources():
    radar = SimpleNamespace(
        RADAR_CATEGORIES=("AI Infra", FRONTIER_CATEGORY),
        MAX_CANDIDATES_PER_CATEGORY=6,
        MAX_RADAR_CANDIDATES=30,
    )
    academic = [
        _row(f"https://arxiv.org/abs/{index}", "AI Infra", "A", "academic_primary")
        for index in range(6)
    ]
    builders = [
        _row(f"https://blog.example/{index}", "AI Infra", "B", "industry_builder")
        for index in range(3)
    ]

    result = _rebalance_candidates(radar, academic, builders)
    infra = [row for row in result if row["category"] == "AI Infra"]

    assert len(infra) == 6
    assert sum(row["source_lane"] == "industry_builder" for row in infra) >= 2
    assert any(row["source_lane"] == "academic_primary" for row in infra)


def test_frontier_category_prefers_builder_signals_without_requiring_project_alignment():
    radar = SimpleNamespace(
        RADAR_CATEGORIES=(FRONTIER_CATEGORY,),
        MAX_CANDIDATES_PER_CATEGORY=6,
        MAX_RADAR_CANDIDATES=30,
    )
    rows = [
        _row("https://blog.example/frontier", FRONTIER_CATEGORY, "B", "industry_builder"),
        _row("https://arxiv.org/abs/frontier", FRONTIER_CATEGORY, "A", "academic_primary"),
    ]

    result = _rebalance_candidates(radar, [], rows)

    assert [row["source_lane"] for row in result] == ["industry_builder", "academic_primary"]
