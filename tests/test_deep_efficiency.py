from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from briefing_skill.cost_schema import ensure_cost_schema
from briefing_skill.db import Database
from briefing_skill.deep_efficiency import build_evidence_pack, install_deep_efficiency
from briefing_skill.fulltext import FulltextService
from briefing_skill.tasks import TASK_BINDING_KEY, TaskService
from briefing_skill.utils import now_iso, read_json, write_json


def test_evidence_pack_keeps_method_evaluation_and_limitations_with_large_reduction():
    filler = "generic background sentence " * 250
    text = (
        "# Abstract\nA network-aware KV cache system.\n\n"
        f"# Related Work\n{filler}\n\n"
        "# Architecture\nThe design places cache blocks by network cost and coalesces remote transfers.\n\n"
        "# Evaluation\nOn 8 GPUs, P99 latency falls by 31% versus baseline A at the same workload. "
        "Throughput reaches 420 GB/s.\n\n"
        "# Limitations\nThe evaluation covers one cluster and does not validate cross-region failures.\n"
    )
    topic = {
        "current_questions": ["KVCache跨域传输如何减少带宽和P99时延？"],
        "valuable_evidence": ["端到端P99、吞吐、网络开销"],
    }
    direction = {"include_terms": ["kv cache", "network", "transfer", "p99"]}
    pack = build_evidence_pack(text, topic, direction, max_chars=2200)
    assert len(pack) <= 2200
    assert len(pack) < len(text) * 0.35
    assert "Architecture" in pack
    assert "P99 latency falls by 31%" in pack
    assert "Limitations" in pack
    assert "cross-region failures" in pack


def _insert_raw_and_candidate(db: Database, run_id: str) -> dict:
    created = now_iso()
    raw_id = f"raw-{run_id}"
    candidate_id = f"candidate-{run_id}"
    db.execute(
        """
        INSERT INTO raw_items(
            id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
            original_url,aihot_url,canonical_url,identity_key,published_at,discovered_at,
            authors_json,external_id,topic_hint,direction_hint,priority,content_hash,payload_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            raw_id, run_id, "arxiv", "arXiv", "A", 0, "Cached paper", "same abstract",
            "https://arxiv.org/abs/2608.12345", "", "https://arxiv.org/abs/2608.12345",
            "arxiv:2608.12345", created, created, "[]", "http://arxiv.org/abs/2608.12345v1",
            "tpn", "kv_transfer", 18, "same-content-hash", "{}", created,
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
    return {"id": candidate_id, "raw_item_id": raw_id, "topic_id": "tpn", "direction_id": "kv_transfer"}


def test_fact_cache_hit_avoids_fetch_and_prefills_task_output(tmp_path):
    root = tmp_path
    run_id = "run-new"
    run_dir = root / "workspace" / "runs" / run_id
    run_dir.mkdir(parents=True)
    db = Database(root / "workspace" / "briefing.sqlite")
    db.init()
    ensure_cost_schema(db)
    db.create_run(run_id)
    candidate = _insert_raw_and_candidate(db, run_id)

    config = SimpleNamespace(
        settings={"efficiency": {"fact_cache_enabled": True, "fact_extractor_version": "evidence-pack-v1"}},
        topic=lambda topic_id: {"id": topic_id},
        direction=lambda topic_id, direction_id: {"id": direction_id},
    )

    # Compute the exact fingerprint through the public fetch path once the cache is present.
    from briefing_skill.deep_efficiency import _source_fingerprint
    raw = db.fetchone("SELECT * FROM raw_items WHERE id=?", (candidate["raw_item_id"],))
    fingerprint = _source_fingerprint(raw)
    cache_key = "cache-key"
    cached_result = {
        "title": "Cached paper",
        "event_hint": "cached-event",
        "problem": "problem",
        "mechanism": "mechanism",
        "evidence": [],
        "evaluation_context": "context",
        "limitations": "limits",
        "project_relevance": "relevance",
        "primary_source_resolved": True,
        "quality_score": 88,
    }
    cache_path = root / "workspace" / "cache" / "facts" / f"{cache_key}.json"
    write_json(cache_path, cached_result)
    db.execute(
        """
        INSERT INTO fact_cache(
            cache_key,source_fingerprint,extractor_version,source_url,source_identity,external_id,
            source_content_hash,json_path,quality_score,event_hint,raw_char_count,evidence_char_count,
            created_at,last_used_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            cache_key, fingerprint, "evidence-pack-v1", raw["original_url"], raw["identity_key"],
            raw["external_id"], raw["content_hash"], str(cache_path.relative_to(root)), 88, "cached-event",
            90000, 17000, now_iso(), now_iso(),
        ),
    )

    install_deep_efficiency()
    service = FulltextService(config, db, run_dir)
    manifest = service.fetch_candidate(run_id, candidate)
    service.close()
    assert manifest["fact_cache_hit"] is True
    assert manifest["raw_char_count"] == 90000
    assert manifest["evidence_char_count"] == 17000

    tasks = TaskService(db, root, run_dir)
    task = tasks.create(
        run_id,
        "fact_extraction",
        candidate["id"],
        {
            "candidate_id": candidate["id"],
            "source": {"title": "Cached paper", "url": raw["original_url"]},
            "document": manifest,
        },
        prompt="fact-extraction.md",
        schema="facts.schema.json",
    )
    output = read_json(root / task["output_path"])
    task_input = read_json(root / task["input_path"])
    assert output[TASK_BINDING_KEY] == task_input[TASK_BINDING_KEY]
    assert output["quality_score"] == 88
    assert output["event_hint"] == "cached-event"
