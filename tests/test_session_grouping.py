from __future__ import annotations

from pathlib import Path

from briefing_skill.session_grouping import (
    fact_session_instructions,
    plan_fact_session_groups,
)
from briefing_skill.utils import read_json, write_json


def _task(
    root: Path,
    *,
    task_id: str,
    topic_id: str = "tpn",
    direction_id: str = "kv_transfer",
    evidence_chars: int = 18000,
    priority: float = 80,
):
    input_path = root / "workspace" / "runs" / "r1" / "tasks" / "fact_extraction" / f"{task_id}.input.json"
    output_path = input_path.with_name(f"{task_id}.output.json")
    evidence_path = root / "workspace" / "runs" / "r1" / "documents" / f"{task_id}.evidence.md"
    write_json(
        input_path,
        {
            "_task": {
                "id": task_id,
                "type": "fact_extraction",
                "entity_id": f"candidate-{task_id}",
                "input_digest": f"digest-{task_id}",
            },
            "candidate_id": f"candidate-{task_id}",
            "source": {
                "title": f"Paper {task_id}",
                "url": f"https://example.com/{task_id}",
                "source_level": "A",
                "discovery_only": False,
            },
            "topic": {"id": topic_id, "name": topic_id},
            "direction": {"id": direction_id, "name": direction_id},
            "project_context_path": f"config/project-context/{topic_id}.md",
            "document": {
                "document_id": f"doc-{task_id}",
                "fetch_status": "FETCHED",
                "text_path": str(evidence_path.relative_to(root)),
                "chunks": [str(evidence_path.relative_to(root))],
                "evidence_char_count": evidence_chars,
                "fact_cache_hit": False,
            },
        },
    )
    return {
        "id": task_id,
        "run_id": "r1",
        "task_type": "fact_extraction",
        "entity_id": f"candidate-{task_id}",
        "input_path": str(input_path.relative_to(root)),
        "output_path": str(output_path.relative_to(root)),
        "prompt_path": "prompts/fact-extraction.md",
        "schema_path": "schemas/facts.schema.json",
        "priority": priority,
        "created_at": f"2026-08-08T00:00:0{task_id[-1] if task_id[-1].isdigit() else '0'}+00:00",
        "updated_at": "2026-08-08T00:00:00+00:00",
    }


def test_fact_session_grouping_only_shares_same_topic_and_direction(tmp_path):
    tasks = [
        _task(tmp_path, task_id="t1", topic_id="tpn", direction_id="kv_transfer", priority=90),
        _task(tmp_path, task_id="t2", topic_id="tpn", direction_id="kv_transfer", priority=80),
        _task(tmp_path, task_id="t3", topic_id="tpn", direction_id="pd_disaggregation", priority=70),
        _task(tmp_path, task_id="t4", topic_id="cross_region", direction_id="kv_transfer", priority=60),
    ]

    groups = plan_fact_session_groups(tmp_path, tasks, max_size=2, max_evidence_chars=40000)
    ids = [[task["id"] for task in group] for group in groups]

    assert ["t1", "t2"] in ids
    assert ["t3"] in ids
    assert ["t4"] in ids
    assert sorted(task_id for group in ids for task_id in group) == ["t1", "t2", "t3", "t4"]


def test_fact_session_grouping_never_drops_evidence_to_make_a_pair_fit(tmp_path):
    tasks = [
        _task(tmp_path, task_id="t1", evidence_chars=22000, priority=90),
        _task(tmp_path, task_id="t2", evidence_chars=22000, priority=80),
    ]

    groups = plan_fact_session_groups(tmp_path, tasks, max_size=2, max_evidence_chars=40000)

    assert [[task["id"] for task in group] for group in groups] == [["t1"], ["t2"]]
    # The planner changes only session assignment; both standalone task inputs
    # still point at their original full Evidence Packs.
    for task in tasks:
        data = read_json(tmp_path / task["input_path"], {})
        assert data["document"]["evidence_char_count"] == 22000


def test_fact_session_grouping_unknown_evidence_size_fails_closed_to_singletons(tmp_path):
    unknown = _task(tmp_path, task_id="t1", evidence_chars=0, priority=90)
    known = _task(tmp_path, task_id="t2", evidence_chars=18000, priority=80)

    groups = plan_fact_session_groups(tmp_path, [unknown, known], max_size=2, max_evidence_chars=40000)

    assert [[task["id"] for task in group] for group in groups] == [["t1"], ["t2"]]


def test_fact_session_grouping_skips_validated_cache_hits(tmp_path):
    cached = _task(tmp_path, task_id="t1", priority=90)
    live = _task(tmp_path, task_id="t2", priority=80)
    cached_path = tmp_path / cached["input_path"]
    data = read_json(cached_path, {})
    data["document"]["fact_cache_hit"] = True
    write_json(cached_path, data)

    groups = plan_fact_session_groups(tmp_path, [cached, live], max_size=2, max_evidence_chars=40000)

    assert [[task["id"] for task in group] for group in groups] == [["t2"]]


class _InstructionService:
    def __init__(self, root: Path):
        self.root = root

    def instructions(self, task):
        return f"single:{task['id']}"


def test_group_instruction_keeps_outputs_separate_and_shared_context_once(tmp_path):
    tasks = [
        _task(tmp_path, task_id="t1", priority=90),
        _task(tmp_path, task_id="t2", priority=80),
    ]
    text = fact_session_instructions(_InstructionService(tmp_path), tasks)

    assert text.count("prompts/fact-extraction.md") == 1
    assert text.count("schemas/facts.schema.json") == 1
    assert text.count("config/project-context/tpn.md") == 1
    assert tasks[0]["input_path"] in text and tasks[1]["input_path"] in text
    assert tasks[0]["output_path"] in text and tasks[1]["output_path"] in text
    assert "never return a combined array or batch file" in text
    assert "Evidence from an earlier task is inadmissible" in text
    assert text.count("python3 briefing.py advance --run r1") == 1
