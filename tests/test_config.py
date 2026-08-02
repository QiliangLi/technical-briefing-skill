from pathlib import Path

from briefing_skill.config import ConfigBundle
from briefing_skill.paths import Paths


def test_topics_and_aihot_priority():
    root = Path(__file__).resolve().parents[1]
    config = ConfigBundle.load(Paths(root))
    topics = {topic["id"]: topic for topic in config.topic_list()}
    assert len(topics) == 6
    assert topics["agent_acceleration"]["aihot_priority"] == "highest"
    assert topics["tpn"]["aihot_priority"] == "high"
    assert "code_graph" in {d["id"] for d in topics["agent_acceleration"]["directions"]}
    assert config.settings["timezone"] == "Asia/Shanghai"
    arxiv = next(source for source in config.source_list() if source["id"] == "arxiv")
    assert arxiv["request_interval_seconds"] >= 0
