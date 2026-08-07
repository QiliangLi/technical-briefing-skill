from __future__ import annotations

import shutil
from pathlib import Path

from briefing_skill.cache_fastpath import install_fact_cache_fastpath
from briefing_skill.config import ConfigBundle
from briefing_skill.cost_schema import install_cost_schema
from briefing_skill.coverage_policy import install_coverage_policy
from briefing_skill.db import Database
from briefing_skill.deep_efficiency import install_deep_efficiency
from briefing_skill.editorial_batch import install_editorial_batching
from briefing_skill.efficiency import install_pipeline_optimizations
from briefing_skill.evidence_repair import install_evidence_repair
from briefing_skill.paths import Paths
from briefing_skill.pipeline import Pipeline
from briefing_skill.quality_guard import install_quality_guards
from briefing_skill.radar_taxonomy import install_radar_taxonomy
from briefing_skill.release_family import install_release_family_aggregation
from briefing_skill.tasks import TASK_BINDING_KEY
from briefing_skill.telemetry import install_task_telemetry
from briefing_skill.topic_appendix_render import install_topic_appendix_rendering
from briefing_skill.utils import now_iso, read_json, write_json
from briefing_skill.value_scoring import install_value_scoring


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    paths = Paths(root)
    config = ConfigBundle.load(paths)
    run_id = "ci-evidence-repair-smoke"
    db_path = root / "workspace" / "evidence-repair-smoke.sqlite"
    run_dir = root / "workspace" / "runs" / run_id
    db_path.unlink(missing_ok=True)
    shutil.rmtree(run_dir, ignore_errors=True)

    install_cost_schema()
    install_pipeline_optimizations()
    install_radar_taxonomy()
    install_quality_guards()
    install_coverage_policy()
    install_release_family_aggregation()
    install_topic_appendix_rendering()
    install_value_scoring()
    install_deep_efficiency()
    install_task_telemetry()
    install_fact_cache_fastpath()
    install_evidence_repair()
    install_editorial_batching()

    db = Database(db_path)
    db.init()
    db.create_run(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    topic = config.topic("tpn")
    direction = topic["directions"][0]
    created = now_iso()
    raw_id = "raw-repair-smoke"
    candidate_id = "candidate-repair-smoke"
    url = "https://arxiv.org/abs/2608.99999v1"
    db.execute(
        """
        INSERT INTO raw_items(
            id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
            original_url,aihot_url,canonical_url,identity_key,published_at,discovered_at,
            authors_json,external_id,topic_hint,direction_hint,priority,content_hash,payload_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            raw_id, run_id, "arxiv", "arXiv", "A", 0,
            "Evidence repair smoke paper", "KV cache transfer benchmark", url, "", url,
            "arxiv:2608.99999", created, created, "[]", "http://arxiv.org/abs/2608.99999v1",
            "tpn", direction["id"], 100, "repair-smoke-content", "{}", created,
        ),
    )
    db.execute(
        """
        INSERT INTO candidates(
            id,run_id,raw_item_id,topic_id,direction_id,rule_score,relevant,relevance_score,
            relevance_reason,fulltext_required,status,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            candidate_id, run_id, raw_id, "tpn", direction["id"], 95, 1, 95,
            "directly relevant", 1, "FACT_TASKED", created,
        ),
    )

    document_id = "repair-smoke-document"
    raw_path = run_dir / "documents" / f"{document_id}.md"
    evidence_path = run_dir / "documents" / f"{document_id}.evidence.md"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_text = (
        "# Abstract\nA KV cache transfer system.\n\n"
        "# Architecture\nThe design coalesces remote block transfers.\n\n"
        "# Evaluation Setup\nExperiments use 8 NVIDIA A100 GPUs with batch size 16 and Baseline-X. "
        "The workload uses long-context decode requests.\n\n"
        "# Results\nThe system reduces P99 latency relative to Baseline-X.\n\n"
        "# Limitations\nThe evaluation covers one cluster only.\n\n"
        + ("unrelated background text without the requested hardware term.\n" * 100)
    )
    evidence_text = (
        "# Deterministic Evidence Pack\n\n"
        "## Evidence locator: Abstract\nA KV cache transfer system.\n\n"
        "## Evidence locator: Architecture\nThe design coalesces remote block transfers.\n\n"
        "## Evidence locator: Results\nThe system reduces P99 latency relative to Baseline-X.\n"
    )
    raw_path.write_text(raw_text, encoding="utf-8")
    evidence_path.write_text(evidence_text, encoding="utf-8")

    pipeline = Pipeline(root, config, db, run_id)
    task = pipeline.tasks.create(
        run_id,
        "fact_extraction",
        candidate_id,
        {
            "candidate_id": candidate_id,
            "source": {
                "title": "Evidence repair smoke paper",
                "summary": "KV cache transfer benchmark",
                "url": url,
                "published_at": created,
                "discovery_source": "arXiv",
                "source_level": "A",
                "discovery_only": False,
            },
            "topic": {
                "id": topic["id"],
                "name": topic["name"],
                "current_questions": topic.get("current_questions", []),
                "valuable_evidence": topic.get("valuable_evidence", []),
            },
            "direction": direction,
            "project_context_path": str(config.context_path(paths, "tpn").relative_to(root)),
            "document": {
                "document_id": document_id,
                "url": url,
                "fetch_status": "FETCHED",
                "text_path": str(evidence_path.relative_to(root)),
                "chunks": [str(evidence_path.relative_to(root))],
                "raw_char_count": len(raw_text),
                "evidence_char_count": len(evidence_text),
                "source_fingerprint": "repair-smoke-fingerprint",
                "extractor_version": "repair-smoke-version",
                "fact_cache_eligible": True,
                "fact_cache_hit": False,
            },
        },
        prompt="fact-extraction.md",
        schema="facts.schema.json",
        priority=95,
    )
    task_input = read_json(root / task["input_path"])
    first_facts = {
        "title": "Evidence repair smoke paper",
        "event_hint": "evidence-repair-smoke",
        "problem": "KV cache transfers compete for network resources.",
        "mechanism": "The system coalesces remote KV cache block transfers.",
        "evidence": [],
        "evaluation_context": "The Evidence Pack does not expose the exact hardware or batch size.",
        "limitations": "Hardware and workload conditions must be verified before interpreting the result.",
        "project_relevance": "The transfer mechanism is relevant to state-aware network scheduling.",
        "primary_source_resolved": True,
        "quality_score": 72,
        "evidence_gaps": [
            {
                "question": "What hardware, batch size and baseline were used?",
                "terms": ["A100", "batch size", "Baseline-X"],
            }
        ],
    }
    write_json(root / task["output_path"], {TASK_BINDING_KEY: task_input[TASK_BINDING_KEY], **first_facts})
    completed, failed = pipeline.tasks.sync(run_id)
    assert completed == 1 and failed == 0
    completed_task = db.fetchone("SELECT * FROM tasks WHERE id=?", (task["id"],))
    pipeline._apply_task(completed_task)
    db.execute("UPDATE tasks SET status='APPLIED' WHERE id=?", (task["id"],))

    repair = db.fetchone(
        "SELECT * FROM tasks WHERE run_id=? AND task_type='fact_evidence_repair'",
        (run_id,),
    )
    assert repair is not None and repair["status"] == "PENDING"
    candidate = db.fetchone("SELECT status FROM candidates WHERE id=?", (candidate_id,))
    assert candidate["status"] == "FACT_REPAIR_TASKED"
    repair_input = read_json(root / repair["input_path"])
    supplement_path = root / repair_input["document"]["supplement_path"]
    supplement = supplement_path.read_text(encoding="utf-8")
    assert "Evaluation Setup" in supplement
    assert "8 NVIDIA A100 GPUs" in supplement
    assert len(supplement) <= int(config.settings["efficiency"]["evidence_repair_max_chars"])

    repaired_facts = {
        **first_facts,
        "evaluation_context": "Experiments use 8 NVIDIA A100 GPUs, batch size 16, Baseline-X, and long-context decode requests.",
        "limitations": "The evaluation still covers only one cluster.",
        "quality_score": 88,
        "evidence_gaps": [],
    }
    write_json(
        root / repair["output_path"],
        {TASK_BINDING_KEY: repair_input[TASK_BINDING_KEY], **repaired_facts},
    )
    completed, failed = pipeline.tasks.sync(run_id)
    assert completed == 1 and failed == 0
    completed_repair = db.fetchone("SELECT * FROM tasks WHERE id=?", (repair["id"],))
    pipeline._apply_task(completed_repair)
    db.execute("UPDATE tasks SET status='APPLIED' WHERE id=?", (repair["id"],))

    candidate = db.fetchone("SELECT status FROM candidates WHERE id=?", (candidate_id,))
    assert candidate["status"] == "FACTS_READY"
    facts_row = db.fetchone("SELECT * FROM facts WHERE run_id=? AND candidate_id=?", (run_id, candidate_id))
    facts = read_json(root / facts_row["json_path"])
    assert "8 NVIDIA A100 GPUs" in facts["evaluation_context"]
    assert facts["evidence_gaps"] == []
    assert db.fetchone("SELECT COUNT(*) AS n FROM fact_cache")["n"] == 1
    assert db.fetchone(
        "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='fact_evidence_repair'",
        (run_id,),
    )["n"] == 1

    shutil.rmtree(run_dir, ignore_errors=True)
    db_path.unlink(missing_ok=True)
    print("evidence repair smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
