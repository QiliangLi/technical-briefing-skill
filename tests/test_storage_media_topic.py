from pathlib import Path

from briefing_skill.config import ConfigBundle
from briefing_skill.paths import Paths


ROOT = Path(__file__).resolve().parents[1]


def test_storage_media_is_loaded_as_deep_topic_with_topic_local_top4_capacity():
    paths = Paths(ROOT)
    config = ConfigBundle.load(paths)

    topic = config.topic("storage_media")
    assert topic["name"] == "存储介质与器件"
    assert {direction["id"] for direction in topic["directions"]} == {
        "flash_nand_hbf",
        "emerging_nvm",
        "magnetic_recording",
        "media_controller_codesign",
    }

    efficiency = config.settings["efficiency"]
    deep_topics = efficiency["deep_topics"]
    assert "storage_media" in deep_topics
    assert efficiency["max_fact_candidates_per_topic"] == 4
    assert efficiency["max_fact_candidates_hard_cap"] == 32
    assert efficiency["max_fact_candidates_total"] == 32
    assert config.scoring["expanded_v2"]["max_per_topic"] == 4
    assert config.scoring["expanded_v2"]["total_max"] == 32
    assert config.context_path(paths, "storage_media").is_file()

    ordered_ids = [item["id"] for item in config.topic_list()]
    assert ordered_ids.index("storage_media") < ordered_ids.index("ai_infra_horizontal")