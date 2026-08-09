from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from briefing_skill.db import Database
from briefing_skill.executor_usage import (
    executor_usage_stats,
    import_executor_usage,
    parse_claude_code_usage_file,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _assistant(
    *,
    uuid: str,
    parent: str,
    timestamp: str,
    request: str,
    model: str = "claude-sonnet-test",
    input_tokens: int,
    cache_create: int,
    cache_read: int,
    output_tokens: int,
    agent_id: str = "",
):
    return {
        "uuid": uuid,
        "parentUuid": parent,
        "type": "assistant",
        "timestamp": timestamp,
        "sessionId": "session-1",
        "agentId": agent_id,
        "requestId": request,
        "message": {
            "id": f"msg-{request}",
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "cache_creation_input_tokens": cache_create,
                "cache_read_input_tokens": cache_read,
                "output_tokens": output_tokens,
            },
            "content": [{"type": "text", "text": "done"}],
        },
    }


def test_parser_keeps_cache_components_separate_and_deduplicates_requests(tmp_path):
    task_id = "a" * 24
    path = tmp_path / "agent.jsonl"
    user = {
        "uuid": "u1",
        "parentUuid": None,
        "type": "user",
        "timestamp": "2026-08-09T02:00:00+00:00",
        "message": {
            "role": "user",
            "content": (
                "TASK ID: " + task_id + "\n"
                "workspace/runs/run-x/tasks/fact_extraction/" + task_id + ".input.json"
            ),
        },
    }
    first = _assistant(
        uuid="a1",
        parent="u1",
        timestamp="2026-08-09T02:00:01+00:00",
        request="req-1",
        input_tokens=11,
        cache_create=22,
        cache_read=33,
        output_tokens=44,
        agent_id="agent-1",
    )
    # Same request appears again with smaller partial counters. It must not be summed.
    partial = _assistant(
        uuid="a2",
        parent="u1",
        timestamp="2026-08-09T02:00:02+00:00",
        request="req-1",
        input_tokens=5,
        cache_create=10,
        cache_read=20,
        output_tokens=30,
        agent_id="agent-1",
    )
    _write_jsonl(path, [user, first, partial])

    rows = parse_claude_code_usage_file(path, run_id="run-x")

    assert len(rows) == 1
    row = rows[0]
    assert row["stage"] == "fact_extraction"
    assert row["task_ids"] == [task_id]
    assert row["input_tokens"] == 11
    assert row["cache_creation_input_tokens"] == 22
    assert row["cache_read_input_tokens"] == 33
    assert row["output_tokens"] == 44


def test_host_parser_respects_explicit_time_window(tmp_path):
    path = tmp_path / "host.jsonl"
    rows = [
        {
            "uuid": "u0",
            "parentUuid": None,
            "type": "user",
            "timestamp": "2026-08-09T01:00:00+00:00",
            "message": {"role": "user", "content": "unrelated coding"},
        },
        _assistant(
            uuid="old",
            parent="u0",
            timestamp="2026-08-09T01:00:01+00:00",
            request="old",
            input_tokens=100,
            cache_create=100,
            cache_read=100,
            output_tokens=100,
        ),
        {
            "uuid": "u1",
            "parentUuid": None,
            "type": "user",
            "timestamp": "2026-08-09T02:00:00+00:00",
            "message": {"role": "user", "content": "python briefing.py advance --run run-x"},
        },
        _assistant(
            uuid="inside",
            parent="u1",
            timestamp="2026-08-09T02:00:01+00:00",
            request="inside",
            input_tokens=10,
            cache_create=20,
            cache_read=30,
            output_tokens=40,
        ),
    ]
    _write_jsonl(path, rows)

    parsed = parse_claude_code_usage_file(
        path,
        run_id="run-x",
        source_kind="host",
        host_start=datetime(2026, 8, 9, 1, 59, tzinfo=timezone.utc),
        host_end=datetime(2026, 8, 9, 2, 1, tzinfo=timezone.utc),
    )

    assert len(parsed) == 1
    assert parsed[0]["request_id"] == "inside"
    assert parsed[0]["stage"] == "host_orchestration"


def test_import_and_stats_attribute_host_agents_stages_and_retry(tmp_path):
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    db.create_run("run-x")

    host = tmp_path / "host.jsonl"
    _write_jsonl(
        host,
        [
            {
                "uuid": "hu",
                "parentUuid": None,
                "type": "user",
                "timestamp": "2026-08-09T02:00:00+00:00",
                "message": {"role": "user", "content": "python briefing.py stats --run run-x"},
            },
            _assistant(
                uuid="ha",
                parent="hu",
                timestamp="2026-08-09T02:00:01+00:00",
                request="host-1",
                input_tokens=10,
                cache_create=20,
                cache_read=30,
                output_tokens=40,
            ),
        ],
    )

    task_id = "b" * 24
    prompt = (
        "TASK ID: " + task_id + "\n"
        "workspace/runs/run-x/tasks/item_writing_batch/" + task_id + ".input.json"
    )
    agent1 = tmp_path / "agent-1.jsonl"
    agent2 = tmp_path / "agent-2.jsonl"
    for path, suffix, values in (
        (agent1, "1", (1, 2, 3, 4)),
        (agent2, "2", (5, 6, 7, 8)),
    ):
        _write_jsonl(
            path,
            [
                {
                    "uuid": f"u{suffix}",
                    "parentUuid": None,
                    "type": "user",
                    "timestamp": f"2026-08-09T02:00:1{suffix}+00:00",
                    "message": {"role": "user", "content": prompt},
                },
                _assistant(
                    uuid=f"a{suffix}",
                    parent=f"u{suffix}",
                    timestamp=f"2026-08-09T02:00:2{suffix}+00:00",
                    request=f"agent-{suffix}",
                    input_tokens=values[0],
                    cache_create=values[1],
                    cache_read=values[2],
                    output_tokens=values[3],
                    agent_id=f"agent-{suffix}",
                ),
            ],
        )

    imported = import_executor_usage(
        db,
        tmp_path,
        "run-x",
        host_logs=[host],
        agent_logs=[agent1, agent2],
        host_start=datetime(2026, 8, 9, 1, 59, tzinfo=timezone.utc),
        host_end=datetime(2026, 8, 9, 2, 2, tzinfo=timezone.utc),
        replace=True,
    )
    assert imported["records_imported"] == 3

    stats = executor_usage_stats(db, "run-x")
    assert stats["available"] is True
    assert stats["totals"]["input_tokens"] == 16
    assert stats["totals"]["cache_creation_input_tokens"] == 28
    assert stats["totals"]["cache_read_input_tokens"] == 40
    assert stats["totals"]["output_tokens"] == 52
    assert stats["totals"]["total_tokens"] == 136
    assert stats["by_scope"]["host"]["total_tokens"] == 100
    assert stats["by_scope"]["agent"]["total_tokens"] == 36
    assert stats["by_stage"]["item_writing_batch"]["total_tokens"] == 36
    assert stats["agent_sessions"] == 2
    assert stats["retry"]["sessions"] == 1
    assert stats["retry"]["tokens"]["total_tokens"] == 26
