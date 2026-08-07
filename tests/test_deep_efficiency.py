from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from briefing_skill.cost_schema import ensure_cost_schema
from briefing_skill.db import Database
from briefing_skill.deep_efficiency import (
    _runtime_extractor_version,
    build_evidence_pack,
    install_deep_efficiency,
)
from briefing_skill.fulltext import FulltextService
from briefing_skill.pipeline import Pipeline
from briefing_skill.tasks import TASK_BINDING_KEY, TaskService
from briefing_skill.utils import now_iso, read_json, write_json


def test_evidence_pack_is_front_excerpt_for_initial_paper_understanding():
    filler = "Introduction explains the problem and mechanism in context. " * 160
    text = (
        "# Abstract\nA network-aware KV cache system reduces remote transfer overhead.\n\n"
        "# Introduction\nThe paper motivates cache placement by network cost and describes its core idea.\n\n"
        f"{filler}\n\n"
        "# Evaluation\nOn 8 GPUs, P99 latency falls by 31% versus baseline A at the same workload.\n\n"
        "# Limitations\nThe evaluation covers one cluster only.\n"
    )
    pack = build_evidence_pack(text, {}, {}, max_chars=2200)
    assert len(pack) <= 2200
    assert text.strip().startswith(pack)
    assert "# Abstract" in pack
    assert "# Introduction" in pack
    assert "network cost" in pack
    assert "P99 latency falls by 31%" not in pack
    assert "# Limitations" not in pack


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


def _restore_attr(obj, name: str, value, existed: bool) -> None:
    if existed:
        setattr(obj, name, value)
    elif hasattr(obj, name):
        delattr(obj, name)


def _test_config(root: Path):
    context_path = root / "config" / "project-context" / "tpn.md"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text("Focus on KV transfer cost and network placement.", encoding="utf-8")
    directions = {
        "kv_transfer": {"id": "kv_transfer", "name": "KV transfer", "include_terms": ["kv cache", "transfer"]},
        "pd_disaggregation": {"id": "pd_disaggregation", "name": "PD", "include_terms": ["prefill", "decode"]},
    }
    return SimpleNamespace(
        settings={
            "efficiency": {
                "fact_cache_enabled": True,
                "fact_extractor_version": "front-evidence-v2",
                "evidence_pack_max_chars": 18000,
                "evidence_repair_enabled": True,
                "evidence_repair_max_chars": 9000,
            }
        },
        topic=lambda topic_id: {
            "id": topic_id,
            "name": "TPN",
            "current_questions": ["How does network placement help?"],
            "valuable_evidence": ["P99", "bandwidth"],
        },
        direction=lambda topic_id, direction_id: directions[direction_id],
        context_path=lambda paths, topic_id: context_path,
    )


def test_fact_cache_version_changes_with_direction_and_project_context(tmp_path):
    config = _test_config(tmp_path)
    first = _runtime_extractor_version(config, tmp_path, "tpn", "kv_transfer")
    other_direction = _runtime_extractor_version(config, tmp_path, "tpn", "pd_disaggregation")
    assert first != other_direction

    context = config.context_path(None, "tpn")
    context.write_text("Now focus on cross-region WAN constraints.", encoding="utf-8")
    changed_context = _runtime_extractor_version(config, tmp_path, "tpn", "kv_transfer")
    assert changed_context != first


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
    config = _test_config(root)

    from briefing_skill.deep_efficiency import _source_fingerprint
    raw = db.fetchone("SELECT * FROM raw_items WHERE id=?", (candidate["raw_item_id"],))
    fingerprint = _source_fingerprint(raw)
    version = _runtime_extractor_version(config, root, "tpn", "kv_transfer")
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
        "evidence_gaps": [],
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
            cache_key, fingerprint, version, raw["original_url"], raw["identity_key"],
            raw["external_id"], raw["content_hash"], str(cache_path.relative_to(root)), 88, "cached-event",
            90000, 17000, now_iso(), now_iso(),
        ),
    )

    snapshots = {
        "fetch": (FulltextService.fetch_candidate, hasattr(FulltextService, "fetch_candidate")),
        "create": (TaskService.create, hasattr(TaskService, "create")),
        "apply": (Pipeline._apply_task, hasattr(Pipeline, "_apply_task")),
        "fetch_flag": (getattr(FulltextService, "_evidence_pack_installed", None), hasattr(FulltextService, "_evidence_pack_installed")),
        "task_flag": (getattr(TaskService, "_fact_cache_installed", None), hasattr(TaskService, "_fact_cache_installed")),
        "pipeline_flag": (getattr(Pipeline, "_fact_cache_installed", None), hasattr(Pipeline, "_fact_cache_installed")),
    }
    try:
        install_deep_efficiency()
        service = FulltextService(config, db, run_dir)
        manifest = service.fetch_candidate(run_id, candidate)
        service.close()
        assert manifest["fact_cache_hit"] is True
        assert manifest["raw_char_count"] == 90000
        assert manifest["evidence_char_count"] == 17000
        assert manifest["evidence_strategy"] == "front-evidence-v2"

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
    finally:
        _restore_attr(FulltextService, "fetch_candidate", *snapshots["fetch"])
        _restore_attr(TaskService, "create", *snapshots["create"])
        _restore_attr(Pipeline, "_apply_task", *snapshots["apply"])
        _restore_attr(FulltextService, "_evidence_pack_installed", *snapshots["fetch_flag"])
        _restore_attr(TaskService, "_fact_cache_installed", *snapshots["task_flag"])
        _restore_attr(Pipeline, "_fact_cache_installed", *snapshots["pipeline_flag"])
