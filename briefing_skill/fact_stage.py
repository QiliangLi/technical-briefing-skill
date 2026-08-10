from __future__ import annotations

from typing import Any

from .utils import read_json


def cache_commit_eligible(candidate: dict[str, Any] | None, facts: dict[str, Any]) -> bool:
    """Return whether facts are final enough to enter the cross-run cache.

    Cache is an output of Fact finalization, never of partial extraction.  A candidate
    must have reached FACTS_READY and the persisted facts must contain no unresolved
    evidence gaps. Primary-source and provenance eligibility remain enforced by V2.
    """

    if not candidate or str(candidate.get("status") or "") != "FACTS_READY":
        return False
    if facts.get("evidence_gaps"):
        return False
    return True


def install_fact_stage() -> None:
    """Make Fact finalization the single commit point for reusable Fact Cache V2.

    The existing extraction, Evidence Repair, cache-hit fast path and Facts schema stay
    unchanged. This layer only removes legacy V1 writes and makes V2 cache persistence
    follow the final candidate state, including successful repair outputs.
    """

    from . import evidence_repair, fact_cache_provenance
    from .pipeline import Pipeline

    if getattr(Pipeline, "_fact_stage_installed", False):
        return

    original_store_v2 = fact_cache_provenance._store_fact_cache_v2

    def store_finalized_v2(service, task, task_input, facts, raw) -> None:
        candidate_id = str(task_input.get("candidate_id") or task.get("entity_id") or "")
        candidate = service.db.fetchone(
            "SELECT status FROM candidates WHERE id=?",
            (candidate_id,),
        )
        if not cache_commit_eligible(candidate, facts):
            return
        original_store_v2(service, task, task_input, facts, raw)

    # fact_cache_provenance resolves this module global at apply time, so replacing
    # the store function here guards both normal extraction and any future callers.
    fact_cache_provenance._store_fact_cache_v2 = store_finalized_v2

    # Legacy V1 is no longer a production cache. Evidence Repair used to write the
    # old `fact_cache` table directly; keep historical rows readable for diagnostics
    # but make that runtime write path inert.
    def legacy_cache_disabled(*_args, **_kwargs) -> None:
        return None

    evidence_repair._cache_repaired_facts = legacy_cache_disabled

    original_apply = Pipeline._apply_task

    def apply_task(self, task: dict[str, Any]) -> None:
        original_apply(self, task)
        if task.get("task_type") != "fact_evidence_repair":
            return

        repair_input = read_json(self.root / task["input_path"], {})
        candidate_id = str(repair_input.get("candidate_id") or task.get("entity_id") or "")
        previous_task_id = str(repair_input.get("previous_task_id") or "")
        if not candidate_id or not previous_task_id:
            return

        previous_task = self.db.fetchone("SELECT * FROM tasks WHERE id=?", (previous_task_id,))
        if not previous_task or previous_task.get("task_type") != "fact_extraction":
            return
        original_input = read_json(self.root / previous_task["input_path"], {})
        document = original_input.get("document") or {}
        if document.get("fact_cache_v2_hit") or not document.get("fact_cache_v2_eligible"):
            return

        facts_row = self.db.fetchone(
            "SELECT * FROM facts WHERE run_id=? AND candidate_id=?",
            (self.run_id, candidate_id),
        )
        if not facts_row:
            return
        facts = read_json(self.root / facts_row["json_path"], {})
        candidate = self.db.fetchone("SELECT raw_item_id,status FROM candidates WHERE id=?", (candidate_id,))
        raw = self.db.fetchone(
            "SELECT * FROM raw_items WHERE id=?",
            (candidate["raw_item_id"],),
        ) if candidate else None
        if not raw:
            return

        # Use the original extraction document for source/evidence provenance. Repair
        # is already part of extractor_version; the supplement merely completes facts
        # for that exact source/evidence policy and must not create a second namespace.
        store_finalized_v2(self, previous_task, original_input, facts, raw)

    Pipeline._apply_task = apply_task
    Pipeline._fact_stage_installed = True
