from __future__ import annotations

from types import SimpleNamespace

from briefing_skill import cli
from briefing_skill.cache_fastpath import install_fact_cache_fastpath
from briefing_skill.cost_schema import ensure_cost_schema
from briefing_skill.db import Database
from briefing_skill.pipeline import Pipeline
from briefing_skill.tasks import TASK_BINDING_KEY, TaskService
from briefing_skill.telemetry import install_task_telemetry
from briefing_skill.utils import now_iso, read_json, write_json


def _restore_attr(obj, name: str, value, existed: bool) -> None:
    if existed:
        setattr(obj, name, value)
    elif hasattr(obj, name):
        delattr(obj, name)


def test_fact_cache_fastpath_materializes_prefilled_v2_output_without_agent_task(tmp_path):
    root = tmp_path
    run_id = "cached-run"
    run_dir = root / "workspace" / "runs" / run_id
    run_dir.mkdir(parents=True)
    db = Database(root / "workspace" / "briefing.sqlite")
    db.init()
    ensure_cost_schema(db)
    db.create_run(run_id)
    created = now_iso()
    raw_id = "raw-cached"
    candidate_id = "candidate-cached"
    url = "https://arxiv.org/abs/2608.55555"
    db.execute(
        """
        INSERT INTO raw_items(
            id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
            original_url,aihot_url,canonical_url,identity_key,published_at,discovered_at,
            authors_json,external_id,topic_hint,direction_hint,priority,content_hash,payload_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            raw_id, run_id, "arxiv", "arXiv", "A", 0, "Cached fastpath paper", "abstract",
            url, "", url, "arxiv:2608.55555", created, created, "[]",
            "http://arxiv.org/abs/2608.55555v1", "tpn", "kv_transfer", 18,
            "content-hash", "{}", created,
        ),
    )
    db.execute(
        """
        INSERT INTO candidates(
            id,run_id,raw_item_id,topic_id,direction_id,rule_score,relevant,relevance_score,
            relevance_reason,fulltext_required,status,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (candidate_id, run_id, raw_id, "tpn", "kv_transfer", 90, 1, 90, "valuable", 1, "RELEVANT", created),
    )
    config = SimpleNamespace(
        settings={"efficiency": {"max_fact_candidates_total": 4, "max_fact_candidates_per_topic": 4}},
        scoring={"weights": {}},
        topic=lambda topic_id: {"id": topic_id, "name": "TPN"},
        direction=lambda topic_id, direction_id: {"id": direction_id, "name": "KV transfer"},
    )

    snapshots = {
        "task_next": (TaskService.next, hasattr(TaskService, "next")),
        "task_sync": (TaskService.sync, hasattr(TaskService, "sync")),
        "task_reopen": (TaskService.reopen_invalid, hasattr(TaskService, "reopen_invalid")),
        "pipeline_apply": (Pipeline._apply_task, hasattr(Pipeline, "_apply_task")),
        "pipeline_facts": (Pipeline._maybe_prepare_facts, hasattr(Pipeline, "_maybe_prepare_facts")),
        "cli_parser": (cli.build_parser, hasattr(cli, "build_parser")),
        "task_telemetry_flag": (getattr(TaskService, "_telemetry_installed", None), hasattr(TaskService, "_telemetry_installed")),
        "pipeline_fast_flag": (getattr(Pipeline, "_fact_cache_fastpath_installed", None), hasattr(Pipeline, "_fact_cache_fastpath_installed")),
        "cli_stats_flag": (getattr(cli, "_stats_command_installed", None), hasattr(cli, "_stats_command_installed")),
    }
    try:
        install_task_telemetry()
        install_fact_cache_fastpath()

        tasks = TaskService(db, root, run_dir)
        task = tasks.create(
            run_id,
            "fact_extraction",
            candidate_id,
            {
                "candidate_id": candidate_id,
                "source": {"title": "Cached fastpath paper", "url": url},
                "topic": {"id": "tpn", "name": "TPN"},
                "direction": {"id": "kv_transfer", "name": "KV transfer"},
                "document": {
                    "document_id": "cached-document",
                    "fetch_status": "FETCHED",
                    "fact_cache_hit": True,
                    "fact_cache_v2_hit": True,
                    "fact_cache_v2_key": "v2-cache-key",
                    "text_path": "workspace/cache/facts-v2/production/v2-cache-key.json",
                    "chunks": [],
                },
            },
            prompt="fact-extraction.md",
            schema="facts.schema.json",
        )
        task_input = read_json(root / task["input_path"], {})
        cached = {
            "title": "Cached fastpath paper",
            "event_hint": "fastpath-event",
            "problem": "problem",
            "mechanism": "mechanism",
            "evidence": [],
            "evaluation_context": "context",
            "limitations": "limits",
            "project_relevance": "relevance",
            "primary_source_resolved": True,
            "quality_score": 91,
            "evidence_gaps": [],
        }
        write_json(
            root / task["output_path"],
            {TASK_BINDING_KEY: task_input[TASK_BINDING_KEY], **cached},
        )

        pipeline = Pipeline(root, config, db, run_id)
        pipeline._maybe_prepare_facts()

        fact = db.fetchone("SELECT * FROM facts WHERE run_id=? AND candidate_id=?", (run_id, candidate_id))
        assert fact is not None
        assert fact["quality_score"] == 91
        candidate = db.fetchone("SELECT status FROM candidates WHERE id=?", (candidate_id,))
        assert candidate["status"] == "FACTS_READY"
        applied = db.fetchone("SELECT status FROM tasks WHERE id=?", (task["id"],))
        assert applied["status"] == "APPLIED"
        pending = db.fetchone("SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND status='PENDING'", (run_id,))
        assert pending["n"] == 0
        metric = db.fetchone("SELECT cache_hit,attempts,completed_at FROM task_metrics WHERE task_id=?", (task["id"],))
        assert metric["cache_hit"] == 1
        assert metric["attempts"] == 0
        assert metric["completed_at"] is not None
    finally:
        _restore_attr(TaskService, "next", *snapshots["task_next"])
        _restore_attr(TaskService, "sync", *snapshots["task_sync"])
        _restore_attr(TaskService, "reopen_invalid", *snapshots["task_reopen"])
        _restore_attr(Pipeline, "_apply_task", *snapshots["pipeline_apply"])
        _restore_attr(Pipeline, "_maybe_prepare_facts", *snapshots["pipeline_facts"])
        _restore_attr(cli, "build_parser", *snapshots["cli_parser"])
        _restore_attr(TaskService, "_telemetry_installed", *snapshots["task_telemetry_flag"])
        _restore_attr(Pipeline, "_fact_cache_fastpath_installed", *snapshots["pipeline_fast_flag"])
        _restore_attr(cli, "_stats_command_installed", *snapshots["cli_stats_flag"])
