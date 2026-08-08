from __future__ import annotations

import copy
import json
from pathlib import Path

from briefing_skill.golden_eval import run_golden_eval


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "eval/golden/v1/manifest.json").read_text(encoding="utf-8"))
BASELINE = json.loads((ROOT / "eval/golden/v1/baseline-results.json").read_text(encoding="utf-8"))


def test_golden_v1_baseline_passes_all_cases():
    report = run_golden_eval(MANIFEST, BASELINE)

    assert report["cases"] == 4
    assert report["passed"] == 4
    assert report["failed"] == 0
    assert report["pass_rate"] == 1.0
    assert report["all_passed"] is True


def test_golden_eval_catches_missing_numeric_baseline_condition():
    bad = copy.deepcopy(BASELINE)
    evidence = bad["results"]["kv-network-scheduler"]["evidence"][0]
    evidence["baseline"] = "FIFO"
    evidence["condition"] = "32 concurrent requests"

    report = run_golden_eval(MANIFEST, bad)
    case = next(row for row in report["reports"] if row["id"] == "kv-network-scheduler")

    assert report["all_passed"] is False
    assert case["passed"] is False
    assert any("baseline" in failure for failure in case["failures"])
    assert any("condition" in failure for failure in case["failures"])


def test_golden_eval_catches_unsupported_claim_and_missing_boundary():
    bad = copy.deepcopy(BASELINE)
    result = bad["results"]["chip-memory-bottleneck"]
    result["mechanism"] += " The peak TOPS increased because the compute array was upgraded."
    result["limitations"] = "Works broadly."

    report = run_golden_eval(MANIFEST, bad)
    case = next(row for row in report["reports"] if row["id"] == "chip-memory-bottleneck")

    assert case["passed"] is False
    assert any("forbidden" in failure for failure in case["failures"])
    assert any("limitations" in failure for failure in case["failures"])
