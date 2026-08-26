from __future__ import annotations

from typing import Any

from .evidence_gate import evidence_gate
from .utils import read_json, stable_hash, write_json


def _write_gate_report(pipeline, rows: list[dict[str, Any]]) -> None:
    path = pipeline.root / "workspace" / "runs" / pipeline.run_id / "evidence_gate.json"
    existing_rows: list[dict[str, Any]] = []
    if path.is_file():
        try:
            existing_rows = list(read_json(path, {}).get("items") or [])
        except (OSError, ValueError):
            existing_rows = []
    merged = {str(row.get("brief_item_id")): row for row in existing_rows}
    for row in rows:
        merged[str(row.get("brief_item_id"))] = row
    items = sorted(merged.values(), key=lambda row: str(row.get("brief_item_id")))
    write_json(
        path,
        {
            "run_id": pipeline.run_id,
            "gate_version": 1,
            "items": items,
            "summary": {
                "pass": sum(1 for row in items if row["decision"] == "PASS"),
                "review": sum(1 for row in items if row["decision"] == "REVIEW"),
            },
        },
    )


def install_selective_fact_check() -> None:
    """Use deterministic grounding checks first and invoke LLM Fact Check only on risk."""

    from .editorial_batch import _pack_batches, _policy, plan_fact_check_entries
    from .pipeline import Pipeline

    if getattr(Pipeline, "_selective_fact_check_installed", False):
        return

    original_prepare_checks = Pipeline._maybe_prepare_checks

    def maybe_prepare_checks(self) -> None:
        # Preserve exact resumability for historical/partially-started contracts.
        if self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type='item_style_polish' LIMIT 1",
            (self.run_id,),
        ):
            return original_prepare_checks(self)
        batched_run = self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type='item_writing_batch' LIMIT 1",
            (self.run_id,),
        )
        if not batched_run and self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type IN ('fact_check','fact_check_batch') LIMIT 1",
            (self.run_id,),
        ):
            return original_prepare_checks(self)
        # Batched runs may gain fact-checked items after earlier gate batches were
        # applied (topic-floor upgrades); only unfinished batches still own the stage.
        if self.db.fetchone(
            """
            SELECT 1 FROM tasks
            WHERE run_id=? AND task_type IN ('fact_check','fact_check_batch')
              AND status IN ('PENDING','INVALID','COMPLETED')
            LIMIT 1
            """,
            (self.run_id,),
        ):
            return

        writing_unfinished = self.db.fetchone(
            """
            SELECT COUNT(*) AS n FROM tasks
            WHERE run_id=? AND task_type IN ('item_writing','item_writing_batch')
              AND status IN ('PENDING','INVALID','COMPLETED')
            """,
            (self.run_id,),
        )["n"]
        if writing_unfinished:
            return

        entries = plan_fact_check_entries(self)
        if not entries:
            return original_prepare_checks(self)

        report_rows: list[dict[str, Any]] = []
        review_entries: list[dict[str, Any]] = []
        for entry in entries:
            payload = entry["payload"]
            item = dict(payload.get("brief_item") or {})
            facts = list(payload.get("facts") or [])
            decision = evidence_gate(item, facts)
            brief_item_id = str(payload["brief_item_id"])
            report_rows.append(
                {
                    "brief_item_id": brief_item_id,
                    **decision,
                    "fact_cache_provenance_present": any(
                        bool(fact.get("_cache") or fact.get("cache_hit") or fact.get("fact_cache_hit"))
                        for fact in facts
                    ),
                }
            )
            if decision["decision"] == "PASS":
                self.db.execute(
                    "UPDATE brief_items SET fact_check_status='PASS' WHERE id=? AND run_id=?",
                    (brief_item_id, self.run_id),
                )
            else:
                review_entries.append(entry)

        _write_gate_report(self, report_rows)

        if not review_entries:
            self.db.update_run(self.run_id, stage="EVIDENCE_GATE_PASSED")
            return

        policy = _policy(self.config)
        batch_size = max(1, int(policy.get("fact_check_batch_size", 4)))
        char_limit = max(12000, int(policy.get("editorial_batch_max_input_chars", 65000)))
        for index, batch in enumerate(
            _pack_batches(review_entries, max_items=batch_size, max_chars=char_limit),
            1,
        ):
            item_ids = [str(row["payload"]["brief_item_id"]) for row in batch]
            entity_id = stable_hash(self.run_id, "selective-fact-check", *item_ids)
            checks = []
            decisions = {row["brief_item_id"]: row for row in report_rows}
            for row in batch:
                check = dict(row["payload"])
                check["evidence_gate"] = decisions[str(check["brief_item_id"])]
                checks.append(check)
            self.tasks.create(
                self.run_id,
                "fact_check_batch",
                entity_id,
                {
                    "batch_id": f"selective-fact-check-{index}",
                    "checks": checks,
                    "constraints": {
                        "independent_items": True,
                        "no_cross_item_evidence": True,
                        "only_review_evidence_gate_risks": True,
                    },
                },
                prompt="fact-check-batch.md",
                schema="fact-check-batch.schema.json",
                priority=max(row["priority"] for row in batch),
                metadata={
                    "verification_mode": "selective_after_evidence_gate",
                    "gate_version": 1,
                },
            )
        self.db.update_run(self.run_id, stage="AWAITING_SELECTIVE_FACT_CHECK")

    Pipeline._maybe_prepare_checks = maybe_prepare_checks
    Pipeline._selective_fact_check_installed = True
