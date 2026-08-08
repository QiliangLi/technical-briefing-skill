from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import read_json, write_json


INTRO_TERMS = ("abstract", "introduction", "overview", "motivation", "background", "摘要", "引言", "背景")
METHOD_TERMS = ("method", "design", "architecture", "implementation", "algorithm", "system", "方法", "设计", "架构", "实现", "算法")
EVAL_TERMS = ("evaluation", "experiment", "results", "benchmark", "performance", "latency", "throughput", "实验", "评估", "结果", "性能", "时延", "吞吐")
BOUNDARY_TERMS = ("limitation", "limitations", "discussion", "conclusion", "threat", "限制", "局限", "讨论", "结论")


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def _normalised_heading(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _role_candidates(
    scored: list[dict[str, Any]],
    used: set[int],
    keywords: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Prefer explicit section headings; use body keywords only as a fallback.

    Body-level terms such as ``system`` or ``performance`` commonly appear in an
    Abstract/Introduction. Letting those mentions compete directly with a real Method
    or Evaluation heading can starve the evidence role we are trying to reserve budget
    for. Duplicate headings are collapsed so repeated/merged source text cannot consume
    both slots for the same role.
    """

    available = [row for row in scored if int(row["index"]) not in used]
    heading_matches = [row for row in available if _contains(str(row["title"]), keywords)]
    matches = heading_matches or [
        row for row in available if _contains(str(row["body"])[:1200], keywords)
    ]
    matches.sort(key=lambda row: (-float(row["score"]), int(row["index"])))

    deduped: list[dict[str, Any]] = []
    seen_headings: set[str] = set()
    for row in matches:
        heading = _normalised_heading(row["title"])
        if heading in seen_headings:
            continue
        seen_headings.add(heading)
        deduped.append(row)
    return deduped


def build_balanced_evidence_pack(
    text: str,
    topic: dict[str, Any],
    direction: dict[str, Any],
    *,
    max_chars: int = 18000,
) -> str:
    """Build one bounded first read spanning context, mechanism, results, and boundaries.

    The previous front-prefix policy made Abstract/Introduction cheap to obtain but pushed
    Evaluation/Results into the repair path. This pack keeps the same total character
    budget while deliberately reserving space for the evidence needed to judge a paper.
    """

    from . import deep_efficiency

    max_chars = max(4000, int(max_chars))
    sections = deep_efficiency._sections(text)
    if not sections:
        return deep_efficiency._safe_excerpt(text, max_chars)

    terms = deep_efficiency._evidence_terms(topic, direction)
    scored = [
        {
            "index": index,
            "title": title,
            "body": body,
            "score": deep_efficiency._section_score(index, title, body, terms),
        }
        for index, title, body in sections
        if str(body or "").strip()
    ]

    groups: list[tuple[str, tuple[str, ...], float]] = [
        ("context", INTRO_TERMS, 0.18),
        ("mechanism", METHOD_TERMS, 0.30),
        ("results", EVAL_TERMS, 0.38),
        ("boundary", BOUNDARY_TERMS, 0.14),
    ]
    selected: list[dict[str, Any]] = []
    used: set[int] = set()
    header = (
        "# Balanced Evidence Pack\n\n"
        "This first read intentionally spans problem context, mechanism, evaluation/results, "
        "and limitations. Evidence locators preserve the source section names.\n\n"
    )
    remaining = max_chars - len(header)

    for label, keywords, ratio in groups:
        budget = max(500, int((max_chars - len(header)) * ratio))
        candidates = _role_candidates(scored, used, keywords)
        if label == "context" and not candidates:
            candidates = [row for row in scored if row["index"] <= 1 and row["index"] not in used]
        group_used = 0
        for row in candidates[:2]:
            locator = f"## Evidence locator: {row['title']}\n\n"
            allowance = min(budget - group_used, remaining - len(locator) - 2, 5200)
            if allowance <= 180:
                break
            excerpt = deep_efficiency._safe_excerpt(str(row["body"]), allowance)
            if not excerpt:
                continue
            selected.append({**row, "excerpt": excerpt, "group": label})
            used.add(int(row["index"]))
            consumed = len(locator) + len(excerpt) + 2
            group_used += consumed
            remaining -= consumed
            if group_used >= budget or remaining <= 300:
                break

    # Spend any unused budget on the strongest still-unseen sections. This handles
    # sources with unconventional headings while keeping the first read bounded.
    if remaining > 500:
        supplemental_headings: set[str] = {
            _normalised_heading(row["title"]) for row in selected
        }
        for row in sorted(scored, key=lambda value: (-float(value["score"]), int(value["index"]))):
            if row["index"] in used:
                continue
            heading = _normalised_heading(row["title"])
            if heading in supplemental_headings:
                continue
            locator = f"## Evidence locator: {row['title']}\n\n"
            allowance = min(remaining - len(locator) - 2, 4200)
            if allowance <= 180:
                break
            excerpt = deep_efficiency._safe_excerpt(str(row["body"]), allowance)
            if not excerpt:
                continue
            selected.append({**row, "excerpt": excerpt, "group": "supplemental"})
            used.add(int(row["index"]))
            supplemental_headings.add(heading)
            remaining -= len(locator) + len(excerpt) + 2
            if remaining <= 300:
                break

    if not selected:
        return deep_efficiency._safe_excerpt(text, max_chars)

    # Present by evidence role instead of raw source position so the Fact Agent sees
    # the causal chain directly: context -> mechanism -> results -> boundary.
    group_order = {"context": 0, "mechanism": 1, "results": 2, "boundary": 3, "supplemental": 4}
    selected.sort(key=lambda row: (group_order.get(str(row["group"]), 9), int(row["index"])))
    blocks = [header.rstrip()]
    for row in selected:
        blocks.append(f"## Evidence locator: {row['title']}\n\n{str(row['excerpt']).strip()}")
    pack = "\n\n".join(blocks).strip()
    return pack[:max_chars].rstrip()


def _repair_health(db, run_id: str) -> dict[str, Any]:
    fact = db.fetchone(
        "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='fact_extraction'",
        (run_id,),
    )
    repair = db.fetchone(
        "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='fact_evidence_repair'",
        (run_id,),
    )
    fact_count = int((fact or {}).get("n") or 0)
    repair_count = int((repair or {}).get("n") or 0)
    rate = round(repair_count / fact_count, 4) if fact_count else 0.0
    return {
        "fact_tasks": fact_count,
        "repair_tasks": repair_count,
        "repair_rate": rate,
        "status": "warning" if fact_count and rate > 0.25 else "healthy",
        "warning_threshold": 0.25,
        "note": "Repair is an exception path; >25% indicates the first-read evidence policy needs attention.",
    }


def install_balanced_evidence() -> None:
    """Replace front-prefix evidence with a balanced pack and expose repair amplification."""

    from . import deep_efficiency, telemetry
    from .fulltext import FulltextService
    from .pipeline import Pipeline

    if getattr(Pipeline, "_balanced_evidence_installed", False):
        return

    deep_efficiency.build_evidence_pack = build_balanced_evidence_pack

    original_version = deep_efficiency._runtime_extractor_version

    def runtime_extractor_version(config, root: Path, topic_id=None, direction_id=None):
        return f"{original_version(config, root, topic_id, direction_id)}:balanced-evidence-v2"

    deep_efficiency._runtime_extractor_version = runtime_extractor_version

    original_fetch = FulltextService.fetch_candidate

    def fetch_candidate(self, run_id: str, candidate: dict):
        manifest = original_fetch(self, run_id, candidate)
        if manifest.get("evidence_strategy") in {"front-evidence-v2", "balanced-evidence-v1"}:
            manifest["evidence_strategy"] = "balanced-evidence-v2"
            document_id = str(manifest.get("document_id") or "")
            manifest_path = self.run_dir / "documents" / f"{document_id}.json"
            if document_id and manifest_path.is_file():
                stored = read_json(manifest_path, {})
                stored["evidence_strategy"] = "balanced-evidence-v2"
                write_json(manifest_path, stored)
        return manifest

    FulltextService.fetch_candidate = fetch_candidate

    original_stats = telemetry.run_stats

    def run_stats(db, root, run_id: str):
        payload = original_stats(db, root, run_id)
        payload["evidence_repair_health"] = _repair_health(db, run_id)
        return payload

    telemetry.run_stats = run_stats
    Pipeline._balanced_evidence_installed = True
