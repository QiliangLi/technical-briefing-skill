from pathlib import Path

from briefing_skill.config import ConfigBundle
from briefing_skill.frontier_source_lanes import augment_frontier_bundle
from briefing_skill.paths import Paths


def test_topics_and_aihot_priority():
    root = Path(__file__).resolve().parents[1]
    config = ConfigBundle.load(Paths(root))
    topics = {topic["id"]: topic for topic in config.topic_list()}
    assert len(topics) == 10
    assert topics["agent_acceleration"]["aihot_priority"] == "highest"
    assert topics["tpn"]["aihot_priority"] == "high"
    assert topics["ai_chip_accelerator"]["aihot_priority"] == "high"
    assert topics["ai_chip_accelerator"]["max_items_per_issue"] == 4
    assert topics["storage_media"]["aihot_priority"] == "medium"
    assert topics["storage_media"]["max_items_per_issue"] == 2
    assert "code_graph" in {d["id"] for d in topics["agent_acceleration"]["directions"]}
    assert "chiplet_packaging" in {d["id"] for d in topics["ai_chip_accelerator"]["directions"]}
    assert "flash_nand_hbf" in {d["id"] for d in topics["storage_media"]["directions"]}
    assert topics["ai_infra_horizontal"]["aihot_priority"] == "highest"
    frontier = topics["frontier_exploration"]
    assert frontier["name"] == "边界探索"
    assert "不是负面信号" in frontier["description"]
    assert config.settings["timezone"] == "Asia/Shanghai"
    arxiv = next(source for source in config.source_list() if source["id"] == "arxiv")
    assert arxiv["request_interval_seconds"] >= 0


def test_frontier_is_radar_lane_and_fixed_blogs_can_feed_it():
    root = Path(__file__).resolve().parents[1]
    config = ConfigBundle.load(Paths(root))
    augment_frontier_bundle(config)

    assert "frontier_exploration" in config.settings["efficiency"]["radar_topics"]
    assert "frontier_exploration" not in config.settings["efficiency"]["deep_topics"]
    sources = {source["id"]: source for source in config.source_list()}
    for source_id in ("simon_willison", "latent_space", "interconnects", "semianalysis"):
        assert "frontier_exploration" in sources[source_id]["topic_allowlist"]
