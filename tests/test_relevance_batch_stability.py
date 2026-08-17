from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from briefing_skill.config import ConfigBundle
from briefing_skill.cost_schema import ensure_cost_schema
from briefing_skill.db import Database
from briefing_skill.efficiency import (
    install_pipeline_optimizations,
    reset_orphaned_relevance_candidates,
)
from briefing_skill.paths import Paths
from briefing_skill.pipeline import Pipeline
from briefing_skill.relevance_efficiency import install_relevance_efficiency
from briefing_skill.utils import write_json


ROOT = Path(__file__).resolve().parents[1]


def _config() -> ConfigBundle:
    return ConfigBundle.load(Paths(ROOT))


def _db(tmp_path) -> Database:
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    ensure_cost_schema(db)
    return db


def _insert_raw(db: Database, *, raw_id: str, run_id: str, title: str) -> None:
    db.execute(
        """
        INSERT INTO raw_items(
            id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
            original_url,canonical_url,identity_key,published_at,authors_json,external_id,
            priority,content_hash,payload_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            raw_id, run_id, "agent_web", "Agent Web Search", "A", 0, title,
            "summary text", f"https://arxiv.org/abs/2608.{uuid.uuid4().hex[:5]}v1",
            f"https://arxiv.org/abs/2608.{uuid.uuid4().hex[:5]}v1",
            f"arxiv:2608.{uuid.uuid4().hex[:5]}",
            "2026-08-10T00:00:00Z", "[]", "", 20, "hash", "{}", "2026-08-10T00:00:00Z",
        ),
    )


def _insert_candidate(
    db: Database, *, candidate_id: str, raw_id: str, run_id: str, status="PENDING_RELEVANCE"
) -> None:
    db.execute(
        """
        INSERT INTO candidates(
            id,run_id,raw_item_id,topic_id,direction_id,rule_score,status,created_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (candidate_id, run_id, raw_id, "agent_acceleration", "tool_chain", 60.0, status, "2026-08-10T00:00:00Z"),
    )


def test_orphaned_tasked_candidates_return_to_pool(tmp_path):
    db = _db(tmp_path)
    _insert_raw(db, raw_id="r1", run_id="run1", title="member paper")
    _insert_raw(db, raw_id="r2", run_id="run1", title="orphan paper")
    _insert_candidate(db, candidate_id="c-member", raw_id="r1", run_id="run1", status="RELEVANCE_TASKED")
    _insert_candidate(db, candidate_id="c-orphan", raw_id="r2", run_id="run1", status="RELEVANCE_TASKED")
    write_json(
        tmp_path / "tasks" / "batch.input.json",
        {"candidates": [{"candidate_id": "c-member"}]},
    )
    db.execute(
        """
        INSERT INTO tasks(id,run_id,task_type,entity_id,input_path,output_path,prompt_path,
                          schema_path,status,priority,created_at,updated_at)
        VALUES ('t1','run1','relevance_batch','e1','tasks/batch.input.json','tasks/batch.output.json',
                'prompts/relevance-batch.md','schemas/relevance-batch.schema.json','PENDING',0,
                '2026-08-10T00:00:00Z','2026-08-10T00:00:00Z')
        """
    )

    assert reset_orphaned_relevance_candidates(db, tmp_path, "run1") == 1
    assert db.fetchone("SELECT status FROM candidates WHERE id='c-member'")["status"] == "RELEVANCE_TASKED"
    assert db.fetchone("SELECT status FROM candidates WHERE id='c-orphan'")["status"] == "PENDING_RELEVANCE"


def test_second_prepare_wave_never_overwrites_first_batch(tmp_path):
    config = _config()
    db = _db(tmp_path)
    install_pipeline_optimizations()
    install_relevance_efficiency()
    run_id = "pytest-wave-stability"
    db.execute(
        "INSERT INTO runs(id,created_at,updated_at,status,stage,note) VALUES (?,datetime('now'),datetime('now'),'ACTIVE','AWAITING_RELEVANCE','test')",
        (run_id,),
    )
    _insert_raw(db, raw_id="r1", run_id=run_id, title="wave one paper")
    _insert_candidate(db, candidate_id="c1", raw_id="r1", run_id=run_id)
    pipeline = Pipeline(ROOT, config, db, run_id)
    pipeline.prepare_relevance()
    first_tasks = db.fetchall(
        "SELECT id,input_path FROM tasks WHERE run_id=? AND task_type='relevance_batch'", (run_id,)
    )
    assert len(first_tasks) == 1
    first_input = first_tasks[0]["input_path"]

    _insert_raw(db, raw_id="r2", run_id=run_id, title="wave two paper")
    _insert_candidate(db, candidate_id="c2", raw_id="r2", run_id=run_id)
    pipeline.prepare_relevance()
    tasks = db.fetchall(
        "SELECT id,input_path FROM tasks WHERE run_id=? AND task_type='relevance_batch' ORDER BY created_at, id",
        (run_id,),
    )
    assert len(tasks) == 2
    import json as _json

    wave_one_ids = {
        row["candidate_id"]
        for row in _json.loads((Path(first_input)).read_text())["candidates"]
    }
    assert wave_one_ids == {"c1"}
    statuses = {
        row["id"]: row["status"]
        for row in db.fetchall("SELECT id,status FROM candidates WHERE run_id=?", (run_id,))
    }
    assert statuses["c1"] == "RELEVANCE_TASKED"
    assert statuses["c2"] == "RELEVANCE_TASKED"
