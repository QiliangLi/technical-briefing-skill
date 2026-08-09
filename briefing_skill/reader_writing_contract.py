from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from .utils import normalize_text


GENERIC_READER_PHRASES = (
    "与指定方向直接相关，并包含可验证机制",
    "与指定方向直接相关",
    "包含可验证机制",
    "值得进一步关注",
    "值得持续关注",
)


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", normalize_text(str(value or "")))


def text_is_generic_boilerplate(value: Any) -> bool:
    compact = _compact(value)
    if not compact:
        return True
    return any(_compact(phrase) == compact for phrase in GENERIC_READER_PHRASES)


def title_conclusion_too_similar(title: Any, conclusion: Any) -> bool:
    left = _compact(title)
    right = _compact(conclusion)
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    if len(shorter) >= 14 and shorter in longer:
        return True
    return SequenceMatcher(None, left, right).ratio() >= 0.82


def _sentence_count(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    endings = re.findall(r"[。！？!?]+|(?<!\d)\.(?=\s|$)", text)
    return max(1, len(endings))


def _numeric_mentions(value: Any) -> int:
    text = str(value or "")
    # Count user-visible quantities, including bare integers. Decimal points remain
    # inside one match. This intentionally treats dense benchmark enumeration as a
    # writing-contract violation regardless of whether every number is factual.
    return len(re.findall(r"(?<![A-Za-z0-9_])\d+(?:\.\d+)?(?:\s*(?:%|倍|x|×|ms|us|µs|s|GB|TB|MB|Gbps|Mbps|GB/s|TPS|QPS|K|M|B))?", text, flags=re.IGNORECASE))


def item_writing_contract_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    title = str(data.get("title") or "").strip()
    conclusion = str(data.get("core_conclusion") or "").strip()
    if len(title) > 48:
        errors.append("item title must be <=48 characters")
    if title_conclusion_too_similar(title, conclusion):
        errors.append("item title and core_conclusion must add distinct information rather than repeat each other")
    for field in ("title", "core_conclusion", "mechanism", "result", "boundary", "project_relevance"):
        if text_is_generic_boilerplate(data.get(field)):
            errors.append(f"{field} contains generic reader-facing boilerplate")
    return errors


def issue_writing_contract_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for index, judgement in enumerate(data.get("judgements") or []):
        if not isinstance(judgement, dict):
            continue
        title = str(judgement.get("title") or "").strip()
        body = str(judgement.get("body") or "").strip()
        if len(title) > 32:
            errors.append(f"judgement {index} title must be <=32 characters")
        if len(body) > 180:
            errors.append(f"judgement {index} body must be <=180 characters")
        if _sentence_count(body) > 3:
            errors.append(f"judgement {index} body must contain no more than 3 sentences")
        if _numeric_mentions(body) > 2:
            errors.append(f"judgement {index} body may contain at most 2 numeric mentions")
        if text_is_generic_boilerplate(title) or text_is_generic_boilerplate(body):
            errors.append(f"judgement {index} contains generic reader-facing boilerplate")
    return errors


def _clean_appendix_boilerplate(service, original_collect, run_id: str, issue_data: dict[str, Any]):
    appendix = original_collect(service, run_id, issue_data)
    cleaned: dict[str, list[dict[str, Any]]] = {}
    for topic_id, items in appendix.items():
        kept: list[dict[str, Any]] = []
        for item in items:
            summary = str(item.get("summary") or "").strip()
            if text_is_generic_boilerplate(summary):
                # Do not replace one vague sentence with another generated sentence.
                # Prefer the source summary already captured in raw_items.
                url = str(item.get("url") or "")
                raw = service.db.fetchone(
                    """
                    SELECT summary FROM raw_items
                    WHERE canonical_url=? OR original_url=?
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (url, url),
                )
                summary = service.__class__._clean_text((raw or {}).get("summary")) if raw else ""
            if not summary or text_is_generic_boilerplate(summary):
                continue
            kept.append({**item, "summary": summary})
        if kept:
            cleaned[str(topic_id)] = kept
    return cleaned


def install_reader_writing_contract() -> None:
    """Reject verbose/repetitive reader copy before it can become a valid issue."""

    from . import coverage_policy
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_reader_writing_contract_installed", False):
        return

    original_semantic_errors = TaskService._semantic_errors

    def semantic_errors(self, task, input_data, data):
        errors = list(original_semantic_errors(self, task, input_data, data))
        if task.get("task_type") == "item_writing":
            errors.extend(item_writing_contract_errors(data))
        elif task.get("task_type") == "issue_synthesis":
            errors.extend(issue_writing_contract_errors(data))
        return errors

    TaskService._semantic_errors = semantic_errors

    original_collect = coverage_policy.collect_topic_appendix

    def collect_topic_appendix(service, run_id: str, issue_data: dict[str, Any]):
        return _clean_appendix_boilerplate(service, original_collect, run_id, issue_data)

    coverage_policy.collect_topic_appendix = collect_topic_appendix
    Pipeline._reader_writing_contract_installed = True
