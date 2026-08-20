from types import SimpleNamespace

from briefing_skill.frontier_source_lanes import (
    FRONTIER_CATEGORY,
    _extra_observation_candidates,
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


def test_extra_observations_do_not_reintroduce_core_or_historical_radar_urls(monkeypatch):
    monkeypatch.setattr(
        "briefing_skill.frontier_source_lanes.published_age_days",
        lambda value: 0,
    )

    class FakeDB:
        def fetchall(self, sql, params=()):
            if "FROM radar_history" in sql:
                return [
                    {
                        "canonical_url": "https://blog.example/already-sent",
                        "normalized_title": "already sent signal",
                    }
                ]
            return [
                {
                    "id": "core",
                    "title": "Current core source",
                    "summary": "这是本期核心条目对应的来源，不应再次进入最下面的雷达部分。",
                    "original_url": "https://blog.example/current-core",
                    "canonical_url": "https://blog.example/current-core",
                    "published_at": "2026-08-20",
                    "priority": 20,
                    "discovery_source": "builder",
                    "source_id": "follow_builders",
                    "source_level": "B",
                    "discovery_only": 1,
                    "topic_id": FRONTIER_CATEGORY,
                    "relevance_reason": "",
                    "relevant": 1,
                },
                {
                    "id": "history",
                    "title": "Already sent signal",
                    "summary": "这是已经在早期雷达中发送过的内容，不应因为重新采集而再次出现。",
                    "original_url": "https://blog.example/already-sent",
                    "canonical_url": "https://blog.example/already-sent",
                    "published_at": "2026-08-20",
                    "priority": 19,
                    "discovery_source": "builder",
                    "source_id": "follow_builders",
                    "source_level": "B",
                    "discovery_only": 1,
                    "topic_id": FRONTIER_CATEGORY,
                    "relevance_reason": "",
                    "relevant": 1,
                },
                {
                    "id": "fresh",
                    "title": "Fresh signal",
                    "summary": "这是本期新发现且尚未发送的技术内容，应该保留在候选集合中。",
                    "original_url": "https://blog.example/fresh",
                    "canonical_url": "https://blog.example/fresh",
                    "published_at": "2026-08-20",
                    "priority": 18,
                    "discovery_source": "builder",
                    "source_id": "follow_builders",
                    "source_level": "B",
                    "discovery_only": 1,
                    "topic_id": FRONTIER_CATEGORY,
                    "relevance_reason": "",
                    "relevant": 1,
                },
            ]

    radar = SimpleNamespace(
        RADAR_SUMMARY_MAX_CHARS=420,
        _clean=lambda value, limit: str(value or "")[:limit],
        _category=lambda title, summary: "AI Infra",
        _normalise_title=lambda value: "".join(ch.lower() for ch in str(value) if ch.isalnum()),
        summary_is_reader_chinese=lambda value: False,
    )
    service = SimpleNamespace(db=FakeDB())
    issue_input = {
        "items": [
            {"sources": [{"url": "https://blog.example/current-core"}]},
        ]
    }

    result = _extra_observation_candidates(radar, service, "run-current", issue_input)

    assert [row["candidate_id"] for row in result] == ["fresh"]
