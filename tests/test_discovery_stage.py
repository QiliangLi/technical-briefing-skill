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


def test_planner_topic_scopes_gap_lanes_against_cross_topic_generic_words(tmp_path) -> None:
    """Regression for docs/designs/2026-09-03-topic-scoped-gap-coverage.md.

    Cross-topic A-level records whose abstracts merely contain generic words
    (accelerator + storage / fine-grained + queue) must not mark the
    accelerator_io_datapath directions as covered, and the planner must spend
    its lanes on the real gaps first.
    """

    import json
    from types import SimpleNamespace

    from briefing_skill.config import ConfigBundle
    from briefing_skill.coverage_policy import install_coverage_policy
    from briefing_skill.db import Database
    from briefing_skill.discovery_stage import plan_coverage_gap_searches
    from briefing_skill.paths import Paths

    install_coverage_policy()
    config = ConfigBundle.load(Paths(ROOT))
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    db.create_run("run")

    def insert(row_id: str, *, level: str, hint_topic: str | None, hint_dir: str | None, title: str, summary: str):
        columns = [
            "id", "run_id", "source_id", "discovery_source", "source_level", "discovery_only",
            "title", "summary", "original_url", "canonical_url", "identity_key",
            "topic_hint", "direction_hint", "priority", "content_hash", "payload_json", "created_at",
        ]
        values = [
            row_id, "run", "src", "arxiv", level, 0,
            title, summary, f"https://arxiv.org/abs/{row_id}", f"https://arxiv.org/abs/{row_id}",
            f"id:{row_id}", hint_topic, hint_dir, 0, f"hash:{row_id}", "{}", "2026-09-01T00:00:00Z",
        ]
        placeholders = ", ".join("?" for _ in columns)
        db.execute(
            f"INSERT INTO raw_items({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )

    # The run-2026-09-03-003948 false positive: A-level TPN abstract carrying
    # accelerator + storage (+ fine-grained + queue) generic vocabulary.
    insert(
        "ainfer-pd",
        level="A",
        hint_topic="tpn",
        hint_dir="kv_network_scheduling",
        title="AInfer-PD: Communication-Safe In-Place Prefill-Decode Multiplexing",
        summary="Distributed MoE rollouts keep accelerator storage and fine-grained queue state safe while prefill and decode share one device.",
    )
    insert(
        "gpu-storage-noise",
        level="A",
        hint_topic="ai_infra_horizontal",
        hint_dir=None,
        title="GPU cluster storage refresh",
        summary="A gpu and storage refresh note from another topic.",
    )
    # The new topic itself only ever produced B-level discovery leads.
    insert(
        "io-lead-b",
        level="B",
        hint_topic="accelerator_io_datapath",
        hint_dir="direct_storage_path",
        title="GDS storage lead from an aggregator",
        summary="Aggregated lead about gpu direct storage.",
    )

    # Mirror the real run: every other configured direction is covered by its own
    # topic's A-level sources, except the two genuine gaps observed that day
    # (storage_media:magnetic_recording, optical_network:hybrid_network).
    io_gap_directions = {
        "accelerator_io_datapath:accelerator_initiated_io",
        "accelerator_io_datapath:accelerator_storage_controller",
        "accelerator_io_datapath:accelerator_storage_stack",
        "accelerator_io_datapath:direct_storage_path",
    }
    real_gaps = {"storage_media:magnetic_recording", "optical_network:hybrid_network"}
    for topic, direction in config.iter_directions():
        key = f"{topic['id']}:{direction['id']}"
        if key in io_gap_directions or key in real_gaps:
            continue
        insert(
            f"cover-{len(key)}-{abs(hash(key)) % 10_000}",
            level="A",
            hint_topic=topic["id"],
            hint_dir=direction["id"],
            title=f"Primary source for {topic['id']} {direction['id']}",
            summary=f"Resolved primary coverage for {key}.",
        )

    pipeline = SimpleNamespace(config=config, db=db, run_id="run")
    searches = plan_coverage_gap_searches(pipeline, max_queries=4)

    search_ids = [s["search_id"] for s in searches]
    assert search_ids == [
        "accelerator_io_datapath:accelerator_initiated_io",
        "accelerator_io_datapath:accelerator_storage_controller",
        "accelerator_io_datapath:accelerator_storage_stack",
        "accelerator_io_datapath:direct_storage_path",
    ]
    assert len({s["search_id"] for s in searches}) == len(searches)
