from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from briefing_skill.cache_fastpath import install_fact_cache_fastpath
from briefing_skill.cost_schema import ensure_cost_schema
from briefing_skill.db import Database
from briefing_skill.deep_efficiency import _source_fingerprint, install_deep_efficiency
from briefing_skill.pipeline import Pipeline
from briefing_skill.telemetry import install_task_telemetry
from briefing_skill.utils import now_iso, write_json


def test_fact_cache_fastpath_materializes_facts_without_pending_agent_task(tmp_path):
    root = tmp_path
    run_id = "cached-run"
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
    raw = db.fetchone("SELECT * FROM raw_items WHERE id=?", (raw_id,))
    fingerprint = _source_fingerprint(raw)
    cache_key = "fast-cache-key"
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
    }
    cache_path = root / "workspace" / "cache" / "facts" / f"{cache_key}.json"
    write_json(cache_path, cached)
    db.execute(
        """
        INSERT INTO fact_cache(
            cache_key,source_fingerprint,extractor_version,source_url,source_identity,external_id,
            source_content_hash,json_path,quality_score,event_hint,raw_char_count,evidence_char_count,
            created_at,last_used_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            cache_key, fingerprint, "evidence-pack-v1", url, raw["identity_key"], raw["external_id"],
            raw["content_hash"], str(cache_path.relative_to(root)), 91, "fastpath-event",
            120000, 18000, created, created,
        ),
    )
    (root / "context.md").write_text("topic context", encoding="utf-8")
    config = SimpleNamespace(
        settings={
            "efficiency": {
                "fact_cache_enabled": True,
                "fact_extractor_version": "evidence-pack-v1",
                "max_fact_candidates_total": 4,
                "max_fact_candidates_per_topic": 4,
            }
        },
        scoring={"weights": {}},
        topic=lambda topic_id: {"id": topic_id, "name": "TPN", "current_questions": [], "valuable_evidence": []},
        direction=lambda topic_id, direction_id: {"id": direction_id, "name": "KV transfer"},
        context_path=lambda paths, topic_id: root / "context.md",
    )

    # This unit test intentionally uses the base pipeline so it does not leak the
    # global efficiency EmailService patch into unrelated Radar tests. Production
    # bootstrap installs efficiency first; the cache fastpath is agnostic to which
    # _maybe_prepare_facts implementation it wraps.
    install_deep_efficiency()
    install_task_telemetry()
    install_fact_cache_fastpath()
    pipeline = Pipeline(root, config, db, run_id)
    pipeline._maybe_prepare_facts()

    fact = db.fetchone("SELECT * FROM facts WHERE run_id=? AND candidate_id=?", (run_id, candidate_id))
    assert fact is not None
    assert fact["quality_score"] == 91
    candidate = db.fetchone("SELECT status FROM candidates WHERE id=?", (candidate_id,))
    assert candidate["status"] == "FACTS_READY"
    task = db.fetchone("SELECT status FROM tasks WHERE run_id=? AND task_type='fact_extraction'", (run_id,))
    assert task["status"] == "APPLIED"
    pending = db.fetchone("SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND status='PENDING'", (run_id,))
    assert pending["n"] == 0
    metric = db.fetchone("SELECT cache_hit,attempts,completed_at FROM task_metrics WHERE run_id=?", (run_id,))
    assert metric["cache_hit"] == 1
    assert metric["attempts"] == 0
    assert metric["completed_at"] is not None
