from __future__ import annotations

from pathlib import Path

from briefing_skill.config import ConfigBundle
from briefing_skill.matching import RuleMatcher
from briefing_skill.paths import Paths


ROOT = Path(__file__).resolve().parents[1]


def test_accelerator_io_topic_has_focused_directions_context_and_capacity() -> None:
    paths = Paths(ROOT)
    config = ConfigBundle.load(paths)
    topic = config.topic("accelerator_io_datapath")

    assert topic["name"] == "加速器直连I/O与存储数据路径"
    assert {direction["id"] for direction in topic["directions"]} == {
        "direct_storage_path",
        "accelerator_initiated_io",
        "accelerator_storage_stack",
        "accelerator_storage_controller",
    }
    assert len(topic["current_questions"]) == 5
    assert config.context_path(paths, topic["id"]).is_file()

    efficiency = config.settings["efficiency"]
    assert topic["id"] in efficiency["deep_topics"]
    assert efficiency["max_fact_candidates_total"] == 36
    assert efficiency["max_fact_candidates_hard_cap"] == 36
    assert efficiency["max_fact_candidates_per_topic"] == 4
    expanded = config.scoring["expanded_v2"]
    assert expanded["core_max"] == 36
    assert expanded["observation_max"] == 36
    assert expanded["total_max"] == 36
    assert expanded["max_per_topic"] == 4
    assert expanded["topic_target"] == 4

    ordered_ids = [item["id"] for item in config.topic_list()]
    assert ordered_ids.index("storage_media") < ordered_ids.index(topic["id"])
    assert ordered_ids.index(topic["id"]) < ordered_ids.index("frontier_exploration")


def test_accelerator_io_source_routing_is_prioritised_but_not_allowlisted_globally() -> None:
    config = ConfigBundle.load(Paths(ROOT))
    sources = {source["id"]: source for source in config.source_list()}
    topic_id = "accelerator_io_datapath"

    assert sources["aihot"]["topic_boosts"][topic_id] == 1.35
    assert topic_id in sources["semianalysis"]["topic_allowlist"]
    assert topic_id in sources["ai_news"]["topic_allowlist"]
    assert sources["follow_builders"]["topic_boosts"][topic_id] == 1.10
    assert sources["yeekal_daily"]["topic_boosts"][topic_id] == 1.15
    assert topic_id not in sources["simon_willison"]["topic_allowlist"]


def test_accelerator_io_rule_routing_separates_direct_storage_from_generic_io() -> None:
    config = ConfigBundle.load(Paths(ROOT))
    matcher = RuleMatcher(config, None)

    direct_matches = matcher._matches(
        {
            "title": "GPU-initiated NVMe storage removes the host bounce buffer",
            "summary": "The accelerator controls a direct data path into GPU memory.",
            "priority": 20,
            "payload_json": "{}",
        }
    )
    generic_matches = matcher._matches(
        {
            "title": "Generic io_uring filesystem benchmark",
            "summary": "CPU-only async I/O throughput improves for a database.",
            "priority": 20,
            "payload_json": "{}",
        }
    )

    assert any(
        topic_id == "accelerator_io_datapath" and score >= 15
        for topic_id, _, score in direct_matches
    )
    assert all(
        score < 15
        for topic_id, _, score in generic_matches
        if topic_id == "accelerator_io_datapath"
    )
