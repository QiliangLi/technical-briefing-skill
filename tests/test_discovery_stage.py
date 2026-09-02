from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from briefing_skill.discovery_stage import _preferred_domains, discovery_batch_semantic_errors


ROOT = Path(__file__).resolve().parents[1]


def _input() -> dict:
    return {
        "searches": [
            {
                "search_id": "tpn:kv_transfer",
                "topic_id": "tpn",
                "direction_id": "kv_transfer",
            },
            {
                "search_id": "agent_acceleration:code_graph",
                "topic_id": "agent_acceleration",
                "direction_id": "code_graph",
            },
        ]
    }


def test_batch_semantics_require_exact_lane_identity() -> None:
    valid = {
        "results": [
            {
                "search_id": "tpn:kv_transfer",
                "topic_id": "tpn",
                "direction_id": "kv_transfer",
                "items": [],
            },
            {
                "search_id": "agent_acceleration:code_graph",
                "topic_id": "agent_acceleration",
                "direction_id": "code_graph",
                "items": [],
            },
        ]
    }
    assert discovery_batch_semantic_errors(_input(), valid) == []

    invalid = {
        "results": [
            {
                "search_id": "tpn:kv_transfer",
                "topic_id": "wrong",
                "direction_id": "kv_transfer",
                "items": [],
            },
            {
                "search_id": "tpn:kv_transfer",
                "topic_id": "tpn",
                "direction_id": "kv_transfer",
                "items": [],
            },
        ]
    }
    errors = discovery_batch_semantic_errors(_input(), invalid)
    assert any("duplicate" in error for error in errors)
    assert any("omits" in error for error in errors)
    assert any("changed topic_id" in error for error in errors)


def test_batch_schema_accepts_grouped_results_and_rejects_cross_lane_shape() -> None:
    schema = json.loads((ROOT / "schemas" / "web-search-batch.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    valid = {
        "results": [
            {
                "search_id": "tpn:kv_transfer",
                "topic_id": "tpn",
                "direction_id": "kv_transfer",
                "items": [
                    {
                        "title": "Paper",
                        "url": "https://arxiv.org/abs/2608.12345",
                        "publisher": "arXiv",
                        "published_at": "2026-08-11",
                        "source_level": "A",
                        "summary": "Primary source.",
                        "primary": True,
                    }
                ],
            }
        ]
    }
    assert list(validator.iter_errors(valid)) == []
    invalid = {"results": [{"title": "flat legacy result"}]}
    assert list(validator.iter_errors(invalid))


def test_discovery_stage_creates_one_task_for_multiple_lanes() -> None:
    source = (ROOT / "briefing_skill" / "discovery_stage.py").read_text(encoding="utf-8")
    prepare = source.split("def prepare_agent_search", 1)[1].split("Pipeline.prepare_agent_search", 1)[0]

    assert prepare.count("self.tasks.create(") == 1
    assert '"searches"' in prepare
    assert 'prompt="agent-web-search-batch.md"' in prepare
    assert 'schema="web-search-batch.schema.json"' in prepare
    assert "return 1" in prepare


def test_accelerator_io_gap_search_prefers_vendor_and_primary_domains() -> None:
    domains = _preferred_domains("accelerator_io_datapath")

    assert {"nvidia.com", "marvell.com", "micron.com"}.issubset(domains)
    assert {"arxiv.org", "dl.acm.org", "usenix.org"}.issubset(domains)


def test_batch_prompt_explicitly_forbids_cross_lane_transfer() -> None:
    prompt = (ROOT / "prompts" / "agent-web-search-batch.md").read_text(encoding="utf-8")
    assert "single Agent invocation" in prompt
    assert "Do not transfer results" in prompt
    assert "one result group for every input `search_id`" in prompt


def test_bootstrap_installs_discovery_after_coverage_policy() -> None:
    source = (ROOT / "briefing_skill" / "bootstrap.py").read_text(encoding="utf-8")
    assert "install_discovery_stage()" in source
    assert source.index("install_coverage_policy()") < source.index("install_discovery_stage()")
