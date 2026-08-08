from __future__ import annotations

import json

from briefing_skill.db import Database
from briefing_skill.safe_efficiency_stats import safe_efficiency_metrics
from briefing_skill.utils import now_iso, write_json


def test_safe_efficiency_metrics_report_avoided_work_and_local_cache_hits(tmp_path):
    root = tmp_path
    run_id = "safe-stats"
    db = Database(root / "workspace" / "briefing.sqlite")
    db.init()
    db.create_run(run_id)
    created = now_iso()

    # Candidate counters.
    for index, status in enumerate(("DUPLICATE_PRIMARY", "DEFERRED_FETCH")):
        raw_id = f"raw-{index}"
        candidate_id = f"candidate-{index}"
        db.execute(
            """
            INSERT INTO raw_items(
                id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
                original_url,aihot_url,canonical_url,identity_key,published_at,discovered_at,
                authors_json,external_id,topic_hint,direction_hint,priority,content_hash,payload_json,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                raw_id, run_id, "arxiv", "arXiv", "A", 0, f"paper {index}", "summary",
                f"https://arxiv.org/abs/2608.1000{index}v1", "",
                f"https://arxiv.org/abs/2608.1000{index}v1", f"arxiv:2608.1000{index}",
                created, created, "[]", f"2608.1000{index}v1", "tpn", "kv_transfer",
                10, f"hash-{index}", "{}", created,
            ),
        )
        db.execute(
            """
            INSERT INTO candidates(id,run_id,raw_item_id,topic_id,direction_id,rule_score,status,created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (candidate_id, run_id, raw_id, "tpn", "kv_transfer", 80, status, created),
        )

    # An event skipped before writing.
    db.execute(
        """
        INSERT INTO events(id,topic_id,direction_id,canonical_title,fingerprint,event_key,score,
                           first_seen_at,last_updated_at,last_pushed_at,payload_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "event-1", "tpn", "kv_transfer", "low score", "fp", "event-key", 55,
            created, created, None, json.dumps({"editorial_deferred": True}),
        ),
    )
    db.execute(
        "INSERT INTO event_members(event_id,candidate_id,run_id) VALUES (?,?,?)",
        ("event-1", "candidate-0", run_id),
    )

    # One raw fulltext cache hit manifest.
    documents = root / "workspace" / "runs" / run_id / "documents"
    write_json(documents / "doc-1.json", {"raw_fulltext_cache_hit": True})
    write_json(documents / "doc-2.json", {"raw_fulltext_cache_hit": False})

    # A task that took the targeted repair path.
    tasks_dir = root / "workspace" / "runs" / run_id / "tasks"
    input_path = tasks_dir / "inputs" / "task-1.json"
    output_path = tasks_dir / "outputs" / "task-1.json"
    write_json(input_path, {"x": 1})
    write_json(output_path, {"x": 1})
    db.execute(
        """
        INSERT INTO tasks(id,run_id,task_type,entity_id,input_path,output_path,prompt_path,schema_path,
                          status,priority,metadata_json,error,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "task-1", run_id, "item_writing", "event-1",
            str(input_path.relative_to(root)), str(output_path.relative_to(root)),
            "prompts/item-writing.md", "schemas/brief-item.schema.json", "PENDING", 1,
            json.dumps({
                "targeted_repair_attempts": 1,
                "original_input_chars": 12000,
                "repair_input_chars": 1500,
            }),
            None, created, created,
        ),
    )

    metrics = safe_efficiency_metrics(db, root, run_id)
    assert metrics["exact_primary_candidates_suppressed"] == 1
    assert metrics["deferred_fetch_candidates"] == 1
    assert metrics["editorial_events_skipped_below_score_floor"] == 1
    assert metrics["raw_fulltext_cache_observations"] == 2
    assert metrics["raw_fulltext_cache_hits"] == 1
    assert metrics["raw_fulltext_cache_hit_rate"] == 0.5
    assert metrics["targeted_invalid_repairs"] == 1
    assert metrics["targeted_repair_input_chars_saved"] == 10500
    assert metrics["targeted_repair_input_reduction_ratio"] == 0.875
