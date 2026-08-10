from __future__ import annotations

from briefing_skill.fact_stage import cache_commit_eligible


def test_partial_facts_never_enter_cross_run_cache():
    candidate = {"status": "FACTS_PARTIAL"}
    facts = {
        "primary_source_resolved": True,
        "evidence_gaps": [{"question": "missing baseline"}],
    }

    assert cache_commit_eligible(candidate, facts) is False


def test_repair_tasked_facts_never_enter_cross_run_cache():
    candidate = {"status": "FACT_REPAIR_TASKED"}
    facts = {"primary_source_resolved": True, "evidence_gaps": []}

    assert cache_commit_eligible(candidate, facts) is False


def test_ready_facts_with_unresolved_gap_are_not_cached():
    candidate = {"status": "FACTS_READY"}
    facts = {
        "primary_source_resolved": True,
        "evidence_gaps": [{"question": "still unresolved"}],
    }

    assert cache_commit_eligible(candidate, facts) is False


def test_only_ready_gap_free_facts_reach_v2_commit_point():
    candidate = {"status": "FACTS_READY"}
    facts = {"primary_source_resolved": True, "evidence_gaps": []}

    assert cache_commit_eligible(candidate, facts) is True
