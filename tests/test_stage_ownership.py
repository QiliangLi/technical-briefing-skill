from __future__ import annotations

from pathlib import Path

from briefing_skill import deep_efficiency


def test_canonical_evidence_builder_spans_required_roles_with_one_budget() -> None:
    text = """
# Abstract
We study KVCache-aware scheduling for distributed inference.
# Method
The scheduler tracks cache placement and routes requests to avoid unnecessary transfer.
# Evaluation
Against the baseline, experiments report lower latency under the stated workload and hardware configuration.
# Limitations
The result depends on the evaluated cluster scale and does not establish a WAN deployment result.
""".strip()
    pack = deep_efficiency.build_evidence_pack(
        text,
        {"current_questions": ["KVCache调度"], "valuable_evidence": ["端到端性能"]},
        {"include_terms": ["KVCache", "scheduling"]},
        max_chars=4000,
    )

    assert len(pack) <= 4000
    assert "# Balanced Evidence Pack" in pack
    assert "Evidence locator: Method" in pack
    assert "Evidence locator: Evaluation" in pack
    assert "Evidence locator: Limitations" in pack
    assert deep_efficiency.EVIDENCE_STRATEGY == "balanced-evidence-v2"


def test_balanced_compatibility_module_no_longer_monkey_patches_builder() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "briefing_skill" / "balanced_evidence.py").read_text(encoding="utf-8")

    assert "deep_efficiency.build_evidence_pack =" not in source
    assert "FulltextService.fetch_candidate =" not in source
    assert "_runtime_extractor_version =" not in source


def test_technology_value_is_signal_not_runtime_selector_owner() -> None:
    root = Path(__file__).resolve().parents[1]
    technology = (root / "briefing_skill" / "technology_value.py").read_text(encoding="utf-8")
    topic_local = (root / "briefing_skill" / "topic_local_deep.py").read_text(encoding="utf-8")

    assert "efficiency.select_deep_budget = select_deep_budget_with_technology_value" not in technology
    assert "efficiency.select_deep_budget = select_topic_local_deep_budget" in topic_local


def test_extractor_version_keeps_balanced_v2_suffix_for_cache_compatibility(tmp_path: Path) -> None:
    class Config:
        settings = {"efficiency": {"fact_extractor_version": "facts-v1"}}

    version = deep_efficiency._runtime_extractor_version(Config(), tmp_path)
    assert version.startswith("facts-v1:")
    assert version.endswith(":balanced-evidence-v2")
