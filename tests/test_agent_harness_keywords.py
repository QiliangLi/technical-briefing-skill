from pathlib import Path

import yaml

from briefing_skill.deep_eligibility import DEEP_ENTRY_CONTRACTS
from briefing_skill.radar_taxonomy import classify_radar_category


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "harness",
    "agent harness",
    "coding harness",
    "agentic coding",
    "agentic workflow",
    "agentic system",
}


def test_agent_harness_has_discovery_boost_and_dedicated_direction() -> None:
    config = yaml.safe_load((ROOT / "config" / "topics.yaml").read_text(encoding="utf-8"))
    topic = next(row for row in config["topics"] if row["id"] == "agent_acceleration")
    assert REQUIRED <= {str(value).lower() for value in topic["aihot_boost_terms"]}
    direction = next(row for row in topic["directions"] if row["id"] == "agent_harness")
    searchable = " ".join(
        [
            *direction["queries"],
            *direction["aihot_queries"],
            direction["arxiv_query"],
            *direction["include_terms"],
        ]
    ).lower()
    assert all(term in searchable for term in REQUIRED)
    assert "biomedical" in {value.lower() for value in direction["exclude_terms"]}
    assert "agent_harness" in DEEP_ENTRY_CONTRACTS["agent_acceleration"]["allowed_core_contributions"]


def test_frontier_and_radar_recognize_harness_without_weakening_deep_boundary() -> None:
    frontier = yaml.safe_load((ROOT / "config" / "topics-frontier.yaml").read_text(encoding="utf-8"))["topic"]
    direction = next(row for row in frontier["directions"] if row["id"] == "agent_tooling_frontier")
    searchable = " ".join([*direction["queries"], *direction["aihot_queries"], *direction["include_terms"]]).lower()
    assert all(term in searchable for term in REQUIRED)
    assert classify_radar_category("Coding Harness更新", "新增长任务状态恢复和接受门") == "Agent生态"
    assert "generic 'agentic' applications do not qualify" in DEEP_ENTRY_CONTRACTS["agent_acceleration"]["boundary"]
