from __future__ import annotations

import json
import re
from typing import Any

from .utils import stable_hash


NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])\d+(?:\.\d+)?")
STRONG_CLAIM_TERMS = (
    "首次",
    "首个",
    "最高",
    "最优",
    "最快",
    "领先",
    "优于",
    "超过",
    "全面超过",
    "生产级",
    "production",
    "state-of-the-art",
    "sota",
)
SIMULATION_TERMS = ("仿真", "模拟", "simulation", "simulated", "prototype", "原型")
PRODUCTION_TERMS = ("生产", "production", "现网", "线上部署", "大规模部署")


def _machine_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "")
        for field in (
            "title",
            "core_conclusion",
            "mechanism",
            "result",
            "boundary",
            "project_relevance",
        )
    )


def _facts_text(facts: list[dict[str, Any]]) -> str:
    return json.dumps(facts, ensure_ascii=False, sort_keys=True)


def evidence_gate(item: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a deterministic grounding decision for a machine item.

    PASS means the item is low-risk enough to skip the extra LLM verifier. REVIEW
    means one or more conditions deserve semantic verification. The gate never
    rewrites facts or prose.
    """

    text = _machine_text(item)
    fact_text = _facts_text(facts)
    reasons: list[str] = []

    item_numbers = sorted(set(NUMBER_RE.findall(text)))
    fact_numbers = set(NUMBER_RE.findall(fact_text))
    missing_numbers = [number for number in item_numbers if number not in fact_numbers]
    if missing_numbers:
        reasons.append("number_not_grounded:" + ",".join(missing_numbers))

    if len(item_numbers) >= 3:
        reasons.append("many_numeric_claims")

    lowered = text.lower()
    if any(term.lower() in lowered for term in STRONG_CLAIM_TERMS):
        reasons.append("strong_comparative_or_superlative_claim")

    sources = list(item.get("sources") or [])
    primary_sources = [source for source in sources if source.get("primary")]
    if len(primary_sources) > 1 or len(facts) > 1:
        reasons.append("multi_source_synthesis")

    if any(str(source.get("source_level") or "").upper() != "A" for source in sources):
        reasons.append("non_a_level_source")

    boundary = str(item.get("boundary") or "").lower()
    result = str(item.get("result") or "").lower()
    if any(term.lower() in boundary for term in SIMULATION_TERMS) and any(
        term.lower() in result for term in PRODUCTION_TERMS
    ):
        reasons.append("simulation_to_production_risk")

    decision = "REVIEW" if reasons else "PASS"
    return {
        "decision": decision,
        "reasons": reasons,
        "numbers_checked": item_numbers,
        "gate_version": 1,
        "gate_id": stable_hash("evidence-gate-v1", decision, *reasons, length=20),
    }
