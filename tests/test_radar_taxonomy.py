from briefing_skill.radar_taxonomy import (
    HBF_QUERY,
    augment_hbf_topic_queries,
    classify_radar_category,
)


def _topics_config():
    return {
        "topics": [
            {
                "id": "ai_infra_horizontal",
                "aihot_boost_terms": ["HBM"],
                "directions": [
                    {
                        "id": "accelerator_memory_interconnect",
                        "queries": ["AI accelerator HBM CXL storage interconnect architecture"],
                        "aihot_queries": ["HBM CXL"],
                        "arxiv_query": '(HBM OR CXL) AND AI',
                        "include_terms": ["hbm", "cxl", "storage"],
                    }
                ],
            }
        ]
    }


def test_hbf_is_storage_and_media_signal():
    assert classify_radar_category("HBF standard targets AI inference", "") == "存储与介质"
    assert classify_radar_category("High-Bandwidth Flash memory", "") == "存储与介质"
    assert classify_radar_category("高带宽闪存用于大模型推理", "") == "存储与介质"


def test_hbf_queries_are_added_to_horizontal_memory_direction():
    config = _topics_config()
    augment_hbf_topic_queries(config)
    topic = config["topics"][0]
    direction = topic["directions"][0]

    assert "HBF" in topic["aihot_boost_terms"]
    assert "High Bandwidth Flash" in topic["aihot_boost_terms"]
    assert HBF_QUERY in direction["queries"]
    assert "HBF High Bandwidth Flash" in direction["aihot_queries"]
    assert "hbf" in direction["include_terms"]
    assert "high bandwidth flash" in direction["include_terms"]
    assert "High Bandwidth Flash" in direction["arxiv_query"]


def test_hbf_query_augmentation_is_idempotent():
    config = _topics_config()
    augment_hbf_topic_queries(config)
    augment_hbf_topic_queries(config)
    direction = config["topics"][0]["directions"][0]

    assert direction["queries"].count(HBF_QUERY) == 1
    assert direction["aihot_queries"].count("HBF High Bandwidth Flash") == 1
    assert direction["include_terms"].count("hbf") == 1
