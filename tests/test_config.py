from pathlib import Path

from briefing_skill.config import ConfigBundle
from briefing_skill.paths import Paths


def test_topics_and_aihot_priority():
    root = Path(__file__).resolve().parents[1]
    config = ConfigBundle.load(Paths(root))
    topics = {topic["id"]: topic for topic in config.topic_list()}
    assert len(topics) == 9
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
    assert config.settings["timezone"] == "Asia/Shanghai"
    arxiv = next(source for source in config.source_list() if source["id"] == "arxiv")
    assert arxiv["request_interval_seconds"] >= 0
