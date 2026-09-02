from __future__ import annotations

import json

from briefing_skill.deep_eligibility import (
    DEEP_ENTRY_CONTRACTS,
    deep_eligibility_semantic_errors,
    derive_deep_eligibility,
)
from briefing_skill.deep_eligibility_version import contract_fingerprint


def _technology_value(score: int = 4):
    return {
        name: {"score": score, "reason": "concrete technical evidence"}
        for name in ("novelty", "architecture_impact", "industry_signal", "project_alignment")
    }


def _candidate(direction_id: str = "kv_cross_region"):
    return {
        "candidate_id": "candidate-1",
        "direction_id": direction_id,
        "source": {"source_level": "A", "discovery_only": False},
    }


def _result(**overrides):
    result = {
        "candidate_id": "candidate-1",
        "relevant": True,
        "score": 90,
        "reason": "direct transport mechanism",
        # Deliberately false: Python, not this legacy Agent field, owns Deep admission.
        "fulltext_required": False,
        "topic_fit": "direct",
        "core_contribution": "wan_transfer",
        "matched_direction_id": "kv_cross_region",
        "boundary_conflict": False,
        "technology_value": _technology_value(),
    }
    result.update(overrides)
    return result


def test_python_can_admit_direct_candidate_even_when_agent_fulltext_boolean_is_false():
    deep, reason = derive_deep_eligibility(
        _result(fulltext_required=False),
        _candidate(),
        DEEP_ENTRY_CONTRACTS["cross_region"],
    )

    assert deep is True
    assert "passes structured" in reason


def test_agent_cannot_force_adjacent_candidate_into_deep():
    deep, reason = derive_deep_eligibility(
        _result(fulltext_required=True, topic_fit="adjacent"),
        _candidate(),
        DEEP_ENTRY_CONTRACTS["cross_region"],
    )

    assert deep is False
    assert "topic_fit is not direct" in reason


def test_boundary_conflict_blocks_deep_even_with_high_scores():
    deep, reason = derive_deep_eligibility(
        _result(boundary_conflict=True, score=100, technology_value=_technology_value(5)),
        _candidate(),
        DEEP_ENTRY_CONTRACTS["cross_region"],
    )

    assert deep is False
    assert "topic boundary conflict" in reason


def test_algorithm_on_gpu_cannot_claim_direct_chip_slot_without_hardware_contribution():
    candidate = _candidate("accelerator_runtime")
    result = _result(
        matched_direction_id="accelerator_runtime",
        core_contribution="other",
        fulltext_required=True,
    )

    deep, reason = derive_deep_eligibility(
        result,
        candidate,
        DEEP_ENTRY_CONTRACTS["ai_chip_accelerator"],
    )

    assert deep is False
    assert "core contribution is outside" in reason


def test_low_technology_value_blocks_deep():
    deep, reason = derive_deep_eligibility(
        _result(technology_value=_technology_value(2)),
        _candidate(),
        DEEP_ENTRY_CONTRACTS["cross_region"],
    )

    assert deep is False
    assert "Technology Value below Deep threshold" in reason


def test_new_relevance_task_requires_structured_fields_and_direction_binding():
    task = {
        "task_type": "relevance_batch",
        "metadata_json": json.dumps({"deep_entry_contract_required": True}),
    }
    input_data = {
        "deep_entry_contract": DEEP_ENTRY_CONTRACTS["cross_region"],
        "candidates": [_candidate()],
    }
    invalid = _result(matched_direction_id="wrong-direction")

    errors = deep_eligibility_semantic_errors(task, input_data, {"results": [invalid]})

    assert any("matched_direction_id" in error for error in errors)


def test_all_configured_deep_topics_have_machine_readable_entry_contracts():
    assert set(DEEP_ENTRY_CONTRACTS) == {
        "tpn",
        "memory_dsa",
        "dpu_inline",
        "agent_acceleration",
        "cross_region",
        "optical_network",
        "ai_chip_accelerator",
        "storage_media",
        "accelerator_io_datapath",
    }
    assert all(contract["allowed_core_contributions"] for contract in DEEP_ENTRY_CONTRACTS.values())


def test_accelerator_storage_path_requires_an_allowed_core_contribution():
    candidate = _candidate("direct_storage_path")
    direct = _result(
        matched_direction_id="direct_storage_path",
        core_contribution="accelerator_storage_direct_path",
    )
    generic = _result(
        matched_direction_id="direct_storage_path",
        core_contribution="other",
    )

    admitted, _ = derive_deep_eligibility(
        direct,
        candidate,
        DEEP_ENTRY_CONTRACTS["accelerator_io_datapath"],
    )
    rejected, reason = derive_deep_eligibility(
        generic,
        candidate,
        DEEP_ENTRY_CONTRACTS["accelerator_io_datapath"],
    )

    assert admitted is True
    assert rejected is False
    assert "core contribution is outside" in reason


def test_contract_fingerprint_changes_when_machine_rule_changes(monkeypatch):
    before = contract_fingerprint("cross_region")
    changed = dict(DEEP_ENTRY_CONTRACTS["cross_region"])
    changed["min_technology_value_score"] = 19
    monkeypatch.setitem(DEEP_ENTRY_CONTRACTS, "cross_region", changed)

    assert contract_fingerprint("cross_region") != before
