from __future__ import annotations

import json
from pathlib import Path

from briefing_skill.config import ConfigBundle
from briefing_skill.paths import Paths
from briefing_skill.tasks import brief_item_validation_errors


ROOT = Path(__file__).resolve().parents[1]


def test_config_loads_seven_deep_topics_plus_horizontal_topic():
    config = ConfigBundle.load(Paths(ROOT))
    topic_ids = [topic["id"] for topic in config.topic_list()]
    assert len(topic_ids) == 8
    assert topic_ids[-1] == "ai_chip_accelerator"
    assert "ai_infra_horizontal" in topic_ids
    assert len(config.settings["efficiency"]["deep_topics"]) == 7


def test_chip_topic_has_focused_directions_and_context():
    config = ConfigBundle.load(Paths(ROOT))
    topic = config.topic("ai_chip_accelerator")
    assert topic["name"] == "AI芯片与加速器"
    assert {direction["id"] for direction in topic["directions"]} == {
        "accelerator_architecture",
        "chiplet_packaging",
        "memory_io_codesign",
    }
    assert "HBF" in topic["directions"][2]["arxiv_query"]
    assert config.context_path(Paths(ROOT), topic["id"]).is_file()


def test_compact_item_character_budget_accepts_180_to_260_chars():
    item = {
        "core_conclusion": "甲" * 49 + "。",
        "mechanism": "乙" * 39 + "。",
        "result": "丙" * 39 + "。",
        "boundary": "丁" * 24 + "。",
        "project_relevance": "戊" * 34 + "。",
    }
    assert sum(len(item[field]) for field in item) == 190
    assert brief_item_validation_errors(item, min_chars=180, max_chars=260) == []
    assert brief_item_validation_errors(item, min_chars=200, max_chars=260)


def test_compact_schema_and_issue_capacity_match_settings():
    config = ConfigBundle.load(Paths(ROOT))
    schema = json.loads((ROOT / "schemas" / "brief-item.schema.json").read_text(encoding="utf-8"))
    assert config.settings["brief_item_min_chars"] == 180
    assert config.settings["brief_item_max_chars"] == 260
    assert schema["properties"]["core_conclusion"]["maxLength"] == 75
    assert schema["properties"]["boundary"]["maxLength"] == 35
    assert config.scoring["expanded_v2"]["core_max"] == 16
    assert config.scoring["expanded_v2"]["total_max"] == 20
    assert config.scoring["expanded_v2"]["max_per_topic"] == 4
    assert config.settings["efficiency"]["max_fact_candidates_total"] == 16
    assert config.settings["efficiency"]["max_fact_candidates_per_topic"] == 4
