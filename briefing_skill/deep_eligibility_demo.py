from __future__ import annotations


def install_deep_eligibility_demo() -> None:
    """Teach deterministic demo relevance output the new structured audit fields."""

    from . import demo as demo_module

    if getattr(demo_module, "_deep_eligibility_demo_installed", False):
        return
    original_demo = demo_module._demo_output

    def demo_output(task_type: str, data: dict):
        output = original_demo(task_type, data)
        if task_type != "relevance_batch" or not isinstance(output, dict):
            return output
        contract = data.get("deep_entry_contract") or {}
        allowed = list(contract.get("allowed_core_contributions") or [])
        if not allowed:
            return output
        candidates = {
            str(row.get("candidate_id") or ""): row
            for row in data.get("candidates") or []
        }
        for result in output.get("results") or []:
            candidate = candidates.get(str(result.get("candidate_id") or "")) or {}
            result.setdefault("topic_fit", "direct")
            result.setdefault("core_contribution", str(allowed[0]))
            result.setdefault("matched_direction_id", str(candidate.get("direction_id") or "demo-direction"))
            result.setdefault("boundary_conflict", False)
        return output

    demo_module._demo_output = demo_output
    demo_module._deep_eligibility_demo_installed = True
