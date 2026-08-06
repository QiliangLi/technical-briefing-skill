from __future__ import annotations

from pathlib import Path

from briefing_skill.adapters.base import CollectedItem
from briefing_skill.collection import CollectionService
from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database
from briefing_skill.pipeline import Pipeline
from briefing_skill.utils import now_iso, read_json, write_json


def _config() -> ConfigBundle:
    return ConfigBundle(
        topics={
            "topics": [
                {
                    "id": "tpn",
                    "name": "状态感知网络、TPN",
                    "directions": [{"id": "d", "name": "传输调度"}],
                }
            ]
        },
        sources={},
        scoring={"weights": {}},
        settings={},
        email={},
    )


def _seed_fact_run(tmp_path: Path, *, source_level: str, url: str, primary_resolved: bool) -> Database:
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    db.create_run("run-1")
    run_dir = tmp_path / "workspace" / "runs" / "run-1"
    service = CollectionService(_config(), db, run_dir)
    try:
        raw = service.persist(
            "run-1",
            [
                CollectedItem(
                    source_id="fixture",
                    discovery_source="Fixture",
                    source_level=source_level,
                    discovery_only=source_level != "A",
                    title="分阶段传输降低拥塞",
                    summary="测试摘要",
                    original_url=url,
                    published_at=now_iso(),
                    topic_hint="tpn",
                    direction_hint="d",
                )
            ],
        )[0]
    finally:
        service.close()
    candidate_id = "candidate-1"
    db.execute(
        """
        INSERT INTO candidates(
            id, run_id, raw_item_id, topic_id, direction_id, rule_score,
            relevance_score, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (candidate_id, "run-1", raw["id"], "tpn", "d", 80, 80, "FACTS_READY", now_iso()),
    )
    facts_path = run_dir / "facts" / f"{candidate_id}.json"
    write_json(
        facts_path,
        {
            "title": "分阶段传输降低拥塞",
            "event_hint": "分阶段传输降低拥塞",
            "problem": "具体问题。",
            "mechanism": "具体机制。",
            "evidence": [],
            "evaluation_context": "测试环境。",
            "limitations": "适用范围有限。",
            "project_relevance": "项目侧需要进一步验证。",
            "primary_source_resolved": primary_resolved,
            "quality_score": 80,
        },
    )
    db.execute(
        """
        INSERT INTO facts(id, run_id, candidate_id, json_path, quality_score, event_hint, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("fact-1", "run-1", candidate_id, str(facts_path.relative_to(tmp_path)), 80, "分阶段传输降低拥塞", now_iso()),
    )
    return db


def test_item_writing_skips_event_without_a_level_source(tmp_path: Path) -> None:
    db = _seed_fact_run(
        tmp_path,
        source_level="B",
        url="https://example.com/analysis/transport",
        primary_resolved=True,
    )

    Pipeline(tmp_path, _config(), db, "run-1")._maybe_prepare_items()

    assert db.fetchone("SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='item_writing'", ("run-1",))["n"] == 0


def test_item_writing_created_for_resolved_a_level_source(tmp_path: Path) -> None:
    db = _seed_fact_run(
        tmp_path,
        source_level="A",
        url="https://example.com/paper/transport",
        primary_resolved=True,
    )

    Pipeline(tmp_path, _config(), db, "run-1")._maybe_prepare_items()

    task = db.fetchone("SELECT * FROM tasks WHERE run_id=? AND task_type='item_writing'", ("run-1",))
    assert task is not None
    task_input = read_json(tmp_path / task["input_path"])
    assert task_input["sources"][0]["source_level"] == "A"
    assert task_input["sources"][0]["url"] == "https://example.com/paper/transport"
