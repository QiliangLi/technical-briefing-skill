from briefing_skill.evidence_repair import build_supplement_pack


def test_supplement_reads_only_omitted_sections_matching_explicit_gap_terms():
    raw = """# Abstract
A KV cache transfer system.

# Architecture
The design coalesces remote block transfers.

# Evaluation Setup
Experiments use 8 NVIDIA A100 GPUs with batch size 16 and compare against Baseline-X.
The workload uses long-context decode requests under a fixed arrival rate.

# Results
Baseline-X is slower in the reported workload.

# Limitations
The study evaluates a single cluster and does not test cross-region failures.
""" + ("background filler without requested terms.\n" * 100)
    existing = """# Deterministic Evidence Pack

## Evidence locator: Abstract
A KV cache transfer system.

## Evidence locator: Architecture
The design coalesces remote block transfers.

## Evidence locator: Results
Baseline-X is slower in the reported workload.
"""
    gaps = [
        {
            "question": "What hardware, batch size and baseline were used?",
            "terms": ["A100", "batch size", "Baseline-X"],
        }
    ]
    supplement = build_supplement_pack(raw, existing, gaps, max_chars=2200)
    assert "Evaluation Setup" in supplement
    assert "8 NVIDIA A100 GPUs" in supplement
    assert "batch size 16" in supplement
    assert "Supplemental locator: Results" not in supplement
    assert len(supplement) <= 2200


def test_supplement_does_not_fall_back_to_generic_fulltext_when_terms_miss():
    raw = """# Abstract
A storage system.

# Evaluation
Throughput is reported for a local SSD workload.

# Limitations
Only one machine is tested.
""" + ("generic filler text.\n" * 50)
    existing = "# Deterministic Evidence Pack\n\n## Evidence locator: Abstract\nA storage system.\n"
    gaps = [{"question": "Which accelerator was used?", "terms": ["H100", "TPU v7"]}]
    assert build_supplement_pack(raw, existing, gaps, max_chars=2000) == ""
