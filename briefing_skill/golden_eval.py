from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _contains_all(value: Any, terms: list[str]) -> bool:
    haystack = _text(value).casefold()
    return all(str(term).casefold() in haystack for term in terms)


def _check_evidence(result: dict[str, Any], rule: dict[str, Any]) -> str | None:
    rows = result.get("evidence") or []
    if not isinstance(rows, list):
        return "evidence must be a list"
    claim_terms = [str(value) for value in rule.get("claim_contains") or []]
    match = next(
        (
            row
            for row in rows
            if isinstance(row, dict) and _contains_all(row.get("claim"), claim_terms)
        ),
        None,
    )
    if match is None:
        return f"missing evidence claim containing {claim_terms}"

    if "value" in rule and str(match.get("value")) != str(rule.get("value")):
        return f"evidence value mismatch for {claim_terms}: expected {rule.get('value')!r}, got {match.get('value')!r}"
    for field in ("baseline", "condition", "source_locator"):
        required = [str(value) for value in rule.get(f"{field}_contains") or []]
        if required and not _contains_all(match.get(field), required):
            return f"evidence {field} missing terms {required} for {claim_terms}"
    return None


def evaluate_case(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    expected = dict(case.get("expected") or {})

    for path in expected.get("required_fields") or []:
        value = _read_path(result, str(path))
        if value in (None, "", [], {}):
            failures.append(f"required field is empty: {path}")

    for path, wanted in (expected.get("equals") or {}).items():
        actual = _read_path(result, str(path))
        if actual != wanted:
            failures.append(f"{path} expected {wanted!r}, got {actual!r}")

    for path, terms in (expected.get("contains") or {}).items():
        actual = _read_path(result, str(path))
        required = [str(term) for term in terms]
        if not _contains_all(actual, required):
            failures.append(f"{path} missing terms {required}")

    flattened = _text(result)
    for term in expected.get("forbidden_terms") or []:
        if str(term).casefold() in flattened.casefold():
            failures.append(f"forbidden unsupported term present: {term}")

    for rule in expected.get("evidence") or []:
        error = _check_evidence(result, dict(rule))
        if error:
            failures.append(error)

    return {
        "id": case.get("id"),
        "passed": not failures,
        "failures": failures,
    }


def run_golden_eval(manifest: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
    cases = list(manifest.get("cases") or [])
    result_map = dict(results.get("results") or results)
    reports: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get("id") or "")
        value = result_map.get(case_id)
        if not isinstance(value, dict):
            reports.append(
                {
                    "id": case_id,
                    "passed": False,
                    "failures": ["missing result object"],
                }
            )
            continue
        reports.append(evaluate_case(case, value))

    passed = sum(1 for report in reports if report["passed"])
    return {
        "manifest_version": manifest.get("version"),
        "cases": len(reports),
        "passed": passed,
        "failed": len(reports) - passed,
        "pass_rate": round(passed / len(reports), 4) if reports else None,
        "all_passed": bool(reports) and passed == len(reports),
        "reports": reports,
        "notes": [
            "Golden Eval is a deterministic regression gate over structured outputs; it does not score prose style subjectively.",
            "The bundled v1 corpus is synthetic and versioned. Production-source cases should be added before changing evidence budgets or ranking thresholds.",
        ],
    }


def load_and_run(manifest_path: Path, results_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = json.loads(results_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(results, dict):
        raise ValueError("golden eval manifest and results must be JSON objects")
    return run_golden_eval(manifest, results)
