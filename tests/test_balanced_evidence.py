from briefing_skill.balanced_evidence import build_balanced_evidence_pack


def test_balanced_pack_keeps_method_results_and_limitations_within_budget():
    text = """
# Abstract
We introduce a KV-aware scheduler for distributed LLM inference.

# Introduction
The system targets remote KV movement and tail latency.

# Method
Requests are routed using session state, KV location, and network load. The scheduler avoids unnecessary transfers.

# Evaluation
On 8 GPUs over 200 GbE, the method reduces P99 latency from 64 ms to 48 ms and lowers transferred KV bytes by 31% against FIFO.

# Limitations
The gain narrows for compute-bound low-load workloads where network transfer is not on the critical path.
""" * 20

    pack = build_balanced_evidence_pack(
        text,
        {"current_questions": ["KV scheduling"], "valuable_evidence": ["P99 latency"]},
        {"include_terms": ["KV", "network load", "latency"]},
        max_chars=6000,
    )

    assert len(pack) <= 6000
    assert "Evidence locator: Method" in pack
    assert "Evidence locator: Evaluation" in pack
    assert "Evidence locator: Limitations" in pack
    assert "64 ms" in pack and "48 ms" in pack
