from __future__ import annotations

import json
from pathlib import Path

from briefing_skill.session_grouping import plan_fact_session_groups


def _write_task(
    root: Path,
    *,
    task_id: str,
    topic_id: str = "tpn",
    direction_id: str = "dir-a",
    evidence_chars: int = 18000,
    cache_hit: bool = False,
    priority: float = 100,
) -> dict:
    input_path = Path("workspace") / f"{task_id}.input.json"
    full_path = root / input_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(
        json.dumps(
            {
                "topic": {"id": topic_id, "name": topic_id},
                "direction": {"id": direction_id, "name": direction_id},
                "project_context_path": "config/project-context.yaml",
                "document": {
                    "evidence_char_count": evidence_chars,
                    "fact_cache_hit": cache_hit,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {
        "id": task_id,
        "run_id": "run-1",
        "task_type": "fact_extraction",
        "entity_id": task_id,
        "input_path": str(input_path),
        "output_path": str(Path("workspace") / f"{task_id}.output.json"),
        "prompt_path": "prompts/fact-extraction.md",
        "schema_path": "schemas/fact-result.schema.json",
        "priority": priority,
        "created_at": f"2026-08-10T00:00:{task_id[-1] if task_id[-1].isdigit() else '0'}Z",
    }


def test_same_topic_different_directions_share_one_top4_invocation(tmp_path: Path) -> None:
    tasks = [
        _write_task(tmp_path, task_id=f"fact-{index}", direction_id=f"dir-{index}")
        for index in range(1, 5)
    ]

    groups = plan_fact_session_groups(
        tmp_path,
        tasks,
        max_size=4,
        max_evidence_chars=72000,
    )

    assert len(groups) == 1
    assert {task["id"] for task in groups[0]} == {f"fact-{index}" for index in range(1, 5)}


def test_fifth_same_topic_task_spills_to_second_invocation(tmp_path: Path) -> None:
    tasks = [
        _write_task(tmp_path, task_id=f"fact-{index}", direction_id=f"dir-{index}")
        for index in range(1, 6)
    ]

    groups = plan_fact_session_groups(
        tmp_path,
        tasks,
        max_size=4,
        max_evidence_chars=90000,
    )

    assert sorted(len(group) for group in groups) == [1, 4]


def test_topics_never_share_fact_invocation(tmp_path: Path) -> None:
    tasks = [
        _write_task(tmp_path, task_id="fact-1", topic_id="tpn", direction_id="dir-a"),
        _write_task(tmp_path, task_id="fact-2", topic_id="dpu_inline", direction_id="dir-a"),
    ]

    groups = plan_fact_session_groups(
        tmp_path,
        tasks,
        max_size=4,
        max_evidence_chars=72000,
    )

    assert len(groups) == 2
    assert all(len(group) == 1 for group in groups)


def test_evidence_budget_still_splits_batches(tmp_path: Path) -> None:
    tasks = [
        _write_task(tmp_path, task_id=f"fact-{index}", direction_id=f"dir-{index}", evidence_chars=18000)
        for index in range(1, 5)
    ]

    groups = plan_fact_session_groups(
        tmp_path,
        tasks,
        max_size=4,
        max_evidence_chars=40000,
    )

    assert sorted(len(group) for group in groups) == [2, 2]


def test_cache_hits_do_not_consume_agent_batch_slots(tmp_path: Path) -> None:
    tasks = [
        _write_task(tmp_path, task_id="fact-1", cache_hit=True),
        _write_task(tmp_path, task_id="fact-2", direction_id="dir-b"),
    ]

    groups = plan_fact_session_groups(
        tmp_path,
        tasks,
        max_size=4,
        max_evidence_chars=72000,
    )

    assert [[task["id"] for task in group] for group in groups] == [["fact-2"]]
