from __future__ import annotations

from typing import Any


MAX_CARD_TEXT_CHARS = 720
MAX_JUDGEMENT_TITLE_CHARS = 48
MAX_JUDGEMENT_BODY_CHARS = 300
MAX_JUDGEMENT_SENTENCES = 4
MAX_JUDGEMENT_NUMERIC_MENTIONS = 4


def reader_projection_quality_errors(data: dict[str, Any]) -> list[str]:
    """Catch issue-wide rhythm collapse without prescribing a title style up front."""

    from .editorial_intent import reader_projection_repetition_errors
    from .reader_projection_v2 import normalise_blocks

    errors = list(reader_projection_repetition_errors(data))
    for index, result in enumerate(data.get("results") or []):
        if not isinstance(result, dict):
            continue
        blocks = normalise_blocks(result.get("blocks"))
        total_chars = sum(len(str(block.get("text") or "")) for block in blocks)
        if total_chars > MAX_CARD_TEXT_CHARS:
            errors.append(
                f"reader_projection result {index} is too long: "
                f"block text must total <={MAX_CARD_TEXT_CHARS} characters"
            )
    return errors


def issue_synthesis_readability_errors(data: dict[str, Any]) -> list[str]:
    """Keep a broad readability fuse without restoring the old slogan-sized limits."""

    from .reader_writing_contract import _numeric_mentions, _sentence_count

    errors: list[str] = []
    for index, judgement in enumerate(data.get("judgements") or []):
        if not isinstance(judgement, dict):
            continue
        title = str(judgement.get("title") or "").strip()
        body = str(judgement.get("body") or "").strip()
        if len(title) > MAX_JUDGEMENT_TITLE_CHARS:
            errors.append(
                f"judgement {index} title must be <={MAX_JUDGEMENT_TITLE_CHARS} characters"
            )
        if len(body) > MAX_JUDGEMENT_BODY_CHARS:
            errors.append(
                f"judgement {index} body must be <={MAX_JUDGEMENT_BODY_CHARS} characters"
            )
        if _sentence_count(body) > MAX_JUDGEMENT_SENTENCES:
            errors.append(
                f"judgement {index} body must contain no more than "
                f"{MAX_JUDGEMENT_SENTENCES} sentences"
            )
        if _numeric_mentions(body) > MAX_JUDGEMENT_NUMERIC_MENTIONS:
            errors.append(
                f"judgement {index} body may contain at most "
                f"{MAX_JUDGEMENT_NUMERIC_MENTIONS} numeric mentions"
            )
    return errors


def install_reader_quality_guard_v2() -> None:
    """Install post-generation guards while leaving Reader v2 structure model-owned."""

    from . import reader_projection
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_reader_quality_guard_v2_installed", False):
        return

    original_semantic_errors = TaskService._semantic_errors

    def semantic_errors(self, task, input_data, data):
        errors = list(original_semantic_errors(self, task, input_data, data))
        if task.get("task_type") == reader_projection.TASK_TYPE:
            errors.extend(reader_projection_quality_errors(data))
        elif task.get("task_type") == "issue_synthesis":
            errors.extend(issue_synthesis_readability_errors(data))
        return list(dict.fromkeys(errors))

    TaskService._semantic_errors = semantic_errors
    Pipeline._reader_quality_guard_v2_installed = True
