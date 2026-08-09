from __future__ import annotations

import json
from typing import Any

from .utils import now_iso, read_json


TOPIC_FITS = {"direct", "adjacent", "tangential", "off_topic"}

# Product-level semantic contracts. The Agent classifies the primary contribution;
# Python decides whether that classification is allowed to enter Deep.
DEEP_ENTRY_CONTRACTS: dict[str, dict[str, Any]] = {
    "tpn": {
        "allowed_core_contributions": [
            "network_state_awareness",
            "kv_network_scheduling",
            "kv_transfer",
            "pd_communication",
            "token_metric_network",
        ],
        "min_relevance_score": 65,
        "min_technology_value_score": 12,
        "boundary": "The core contribution must involve network/communication/bandwidth/placement or token-performance-aware infrastructure, not only model-side KV optimization.",
    },
    "memory_dsa": {
        "allowed_core_contributions": [
            "memory_semantics",
            "cxl_pooling",
            "data_movement_offload",
            "compression_checksum_offload",
        ],
        "min_relevance_score": 65,
        "min_technology_value_score": 11,
        "boundary": "The core contribution must change memory semantics/pooling or DSA/IAA-style data movement/processing offload, not merely use remote memory as an experimental setting.",
    },
    "dpu_inline": {
        "allowed_core_contributions": [
            "inline_datapath",
            "protocol_offload",
            "storage_metadata_offload",
            "security_offload",
            "kv_cache_offload",
        ],
        "min_relevance_score": 65,
        "min_technology_value_score": 12,
        "boundary": "DPU/SmartNIC/IPU in-path execution must be a core mechanism or deployment boundary, not a passing platform mention.",
    },
    "agent_acceleration": {
        "allowed_core_contributions": [
            "repository_retrieval",
            "context_delivery",
            "tool_execution",
            "agent_runtime",
            "state_consistency",
        ],
        "min_relevance_score": 65,
        "min_technology_value_score": 12,
        "boundary": "The work must directly reduce or control LLM/software-Agent repository exploration, context delivery, tool execution, runtime cost/latency, or state correctness; generic 'agentic' applications do not qualify.",
    },
    "cross_region": {
        "allowed_core_contributions": [
            "wan_transfer",
            "cross_cluster_migration",
            "remote_state_access",
            "transport_compression",
            "cross_region_consistency",
        ],
        "min_relevance_score": 65,
        "min_technology_value_score": 12,
        "boundary": "Cross-region/WAN/cross-cluster transfer, migration, remote access, bandwidth reduction, or consistency must be a core evaluated problem; local KV compression or tokenization alone does not qualify.",
    },
    "optical_network": {
        "allowed_core_contributions": [
            "optical_interconnect",
            "optical_switching",
            "co_packaged_optics",
            "photonic_transport",
        ],
        "min_relevance_score": 65,
        "min_technology_value_score": 12,
        "boundary": "Optical transport/interconnect/switching/packaging must be a core technical contribution rather than an incidental deployment detail.",
    },
    "ai_chip_accelerator": {
        "allowed_core_contributions": [
            "hardware_architecture",
            "accelerator_execution",
            "memory_hierarchy",
            "interconnect",
            "chiplet_packaging",
            "hardware_software_codesign",
        ],
        "min_relevance_score": 65,
        "min_technology_value_score": 12,
        "boundary": "Hardware architecture, accelerator execution, memory hierarchy, interconnect, packaging, or hardware-software co-design must be central; an algorithm benchmarked on a GPU is not sufficient.",
    },
    "storage_media": {
        "allowed_core_contributions": [
            "flash_nand_hbf",
            "emerging_nvm",
            "magnetic_recording",
            "media_controller_codesign",
        ],
        "min_relevance_score": 65,
        "min_technology_value_score": 12,
        "boundary": "The core advance must be a storage medium/device or media-controller co-design; HBM-only, CXL memory semantics, and DPU storage offload belong to other topics.",
    },
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def technology_value_total(result: dict[str, Any]) -> float:
    value = result.get("technology_value")
    if not isinstance(value, dict):
        return 0.0
    return round(
        sum(
            max(0.0, min(5.0, _number((value.get(name) or {}).get("score"))))
            for name in ("novelty", "architecture_impact", "industry_signal", "project_alignment")
        ),
        2,
    )


def deep_entry_contract(topic_id: str) -> dict[str, Any] | None:
    contract = DEEP_ENTRY_CONTRACTS.get(str(topic_id or ""))
    return dict(contract) if contract else None


def derive_deep_eligibility(
    result: dict[str, Any],
    candidate_input: dict[str, Any],
    contract: dict[str, Any],
) -> tuple[bool, str]:
    """Derive the expensive Deep path from structured Agent evidence, not its boolean."""

    reasons: list[str] = []
    if not bool(result.get("relevant")):
        reasons.append("not relevant")
    if _number(result.get("score")) < _number(contract.get("min_relevance_score"), 65):
        reasons.append("relevance below Deep threshold")
    if str(result.get("topic_fit") or "") != "direct":
        reasons.append("topic_fit is not direct")
    if bool(result.get("boundary_conflict")):
        reasons.append("topic boundary conflict")

    allowed = {str(value) for value in contract.get("allowed_core_contributions") or []}
    contribution = str(result.get("core_contribution") or "")
    if contribution not in allowed:
        reasons.append("core contribution is outside the topic Deep contract")

    expected_direction = str(candidate_input.get("direction_id") or "")
    if str(result.get("matched_direction_id") or "") != expected_direction:
        reasons.append("direction binding mismatch")

    source = candidate_input.get("source") or {}
    if str(source.get("source_level") or "").upper() != "A" or bool(source.get("discovery_only")):
        reasons.append("Deep requires resolved A-level non-discovery source")

    tech = technology_value_total(result)
    if tech < _number(contract.get("min_technology_value_score"), 12):
        reasons.append("Technology Value below Deep threshold")

    if reasons:
        return False, "; ".join(reasons)
    return True, "passes structured topic-fit, source, relevance, and Technology Value gates"


def deep_eligibility_semantic_errors(
    task: dict[str, Any],
    input_data: dict[str, Any],
    data: dict[str, Any],
) -> list[str]:
    try:
        metadata = json.loads(task.get("metadata_json") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        metadata = {}
    if task.get("task_type") != "relevance_batch" or not metadata.get("deep_entry_contract_required"):
        return []

    contract = input_data.get("deep_entry_contract") or {}
    candidates = {
        str(row.get("candidate_id") or ""): row
        for row in input_data.get("candidates") or []
    }
    allowed = {str(value) for value in contract.get("allowed_core_contributions") or []}
    errors: list[str] = []
    for index, result in enumerate(data.get("results") or []):
        candidate_id = str(result.get("candidate_id") or "")
        candidate = candidates.get(candidate_id) or {}
        fit = str(result.get("topic_fit") or "")
        if fit not in TOPIC_FITS:
            errors.append(f"relevance result {index} requires topic_fit in {sorted(TOPIC_FITS)}")
        contribution = str(result.get("core_contribution") or "")
        if not contribution:
            errors.append(f"relevance result {index} requires core_contribution")
        if fit == "direct" and contribution not in allowed:
            errors.append(
                f"relevance result {index} direct core_contribution must be allowed by the topic contract"
            )
        if not isinstance(result.get("boundary_conflict"), bool):
            errors.append(f"relevance result {index} requires boolean boundary_conflict")
        if str(result.get("matched_direction_id") or "") != str(candidate.get("direction_id") or ""):
            errors.append(f"relevance result {index} matched_direction_id must equal the routed direction_id")
    return errors


def ensure_deep_eligibility_schema(db) -> None:
    with db.connect() as conn:
        additions = {
            "topic_fit": "TEXT",
            "core_contribution": "TEXT",
            "boundary_conflict": "INTEGER",
            "matched_direction_id": "TEXT",
            "deep_eligible": "INTEGER",
            "deep_eligibility_reason": "TEXT",
        }
        candidate_columns = {row[1] for row in conn.execute("PRAGMA table_info(candidates)")}
        if candidate_columns:
            for name, sql_type in additions.items():
                if name not in candidate_columns:
                    conn.execute(f"ALTER TABLE candidates ADD COLUMN {name} {sql_type}")

        cache_columns = {row[1] for row in conn.execute("PRAGMA table_info(relevance_cache)")}
        if cache_columns:
            for name, sql_type in additions.items():
                if name not in cache_columns:
                    conn.execute(f"ALTER TABLE relevance_cache ADD COLUMN {name} {sql_type}")


def _cache_identity(config, root, row: dict[str, Any]) -> tuple[str, str, str, str]:
    from . import relevance_efficiency

    topic_id = str(row.get("topic_id") or "")
    direction_id = str(row.get("direction_id") or "")
    fingerprint = relevance_efficiency.relevance_source_fingerprint(row)
    version = relevance_efficiency.relevance_evaluator_version(
        config,
        root,
        topic_id,
        direction_id,
        row.get("published_at"),
    )
    return fingerprint, topic_id, direction_id, version


def store_deep_eligibility_cache(config, db, root, candidate_id: str) -> None:
    ensure_deep_eligibility_schema(db)
    row = db.fetchone(
        """
        SELECT c.*,r.source_id,r.identity_key,r.external_id,r.content_hash,
               r.canonical_url,r.original_url,r.title,r.summary,r.payload_json,r.published_at
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id WHERE c.id=?
        """,
        (candidate_id,),
    )
    if not row or row.get("deep_eligible") is None:
        return
    fingerprint, topic_id, direction_id, version = _cache_identity(config, root, row)
    db.execute(
        """
        UPDATE relevance_cache
        SET topic_fit=?,core_contribution=?,boundary_conflict=?,matched_direction_id=?,
            deep_eligible=?,deep_eligibility_reason=?,last_used_at=?
        WHERE source_fingerprint=? AND topic_id=? AND direction_id=? AND evaluator_version=?
        """,
        (
            row.get("topic_fit"),
            row.get("core_contribution"),
            row.get("boundary_conflict"),
            row.get("matched_direction_id"),
            row.get("deep_eligible"),
            row.get("deep_eligibility_reason"),
            now_iso(),
            fingerprint,
            topic_id,
            direction_id,
            version,
        ),
    )


def install_deep_eligibility_contract() -> None:
    """Make Deep admission deterministic from structured semantic evidence."""

    from . import relevance_efficiency
    from .db import Database
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_deep_eligibility_contract_installed", False):
        return

    original_db_init = Database.init

    def db_init(self) -> None:
        original_db_init(self)
        ensure_deep_eligibility_schema(self)

    Database.init = db_init

    original_create = TaskService.create

    def create(self, *args, **kwargs):
        task_type = args[1] if len(args) > 1 else kwargs.get("task_type")
        input_data = args[3] if len(args) > 3 else kwargs.get("input_data")
        if task_type == "relevance_batch" and isinstance(input_data, dict):
            topic_id = str((input_data.get("topic") or {}).get("id") or "")
            contract = deep_entry_contract(topic_id)
            if contract:
                input_data = {**input_data, "deep_entry_contract": contract}
                if len(args) > 3:
                    args = (*args[:3], input_data, *args[4:])
                else:
                    kwargs["input_data"] = input_data
                metadata = dict(kwargs.get("metadata") or {})
                metadata["deep_entry_contract_required"] = True
                metadata["deep_entry_contract_version"] = 1
                kwargs["metadata"] = metadata
        return original_create(self, *args, **kwargs)

    TaskService.create = create

    original_semantic_errors = TaskService._semantic_errors

    def semantic_errors(self, task, input_data, data):
        errors = list(original_semantic_errors(self, task, input_data, data))
        errors.extend(deep_eligibility_semantic_errors(task, input_data, data))
        return errors

    TaskService._semantic_errors = semantic_errors

    original_cached = relevance_efficiency.apply_cached_relevance

    def apply_cached_relevance(config, db, root, row: dict[str, Any]) -> bool:
        hit = original_cached(config, db, root, row)
        if not hit:
            return False
        contract = deep_entry_contract(str(row.get("topic_id") or ""))
        if not contract:
            return True
        ensure_deep_eligibility_schema(db)
        fingerprint, topic_id, direction_id, version = _cache_identity(config, root, row)
        cache = db.fetchone(
            """
            SELECT topic_fit,core_contribution,boundary_conflict,matched_direction_id,
                   deep_eligible,deep_eligibility_reason
            FROM relevance_cache
            WHERE source_fingerprint=? AND topic_id=? AND direction_id=? AND evaluator_version=?
            """,
            (fingerprint, topic_id, direction_id, version),
        )
        if not cache or cache.get("deep_eligible") is None:
            # A legacy cache entry cannot bypass the new semantic contract.
            db.execute(
                """
                UPDATE candidates SET relevant=NULL,relevance_score=NULL,relevance_reason=NULL,
                    fulltext_required=0,status='PENDING_RELEVANCE',topic_fit=NULL,
                    core_contribution=NULL,boundary_conflict=NULL,matched_direction_id=NULL,
                    deep_eligible=NULL,deep_eligibility_reason=NULL WHERE id=?
                """,
                (row["id"],),
            )
            return False
        deep = bool(cache.get("deep_eligible"))
        current = db.fetchone("SELECT relevant FROM candidates WHERE id=?", (row["id"],)) or {}
        relevant = bool(current.get("relevant"))
        status = "RELEVANT" if deep else ("RADAR" if relevant else "REJECTED")
        db.execute(
            """
            UPDATE candidates SET topic_fit=?,core_contribution=?,boundary_conflict=?,
                matched_direction_id=?,deep_eligible=?,deep_eligibility_reason=?,
                fulltext_required=?,status=? WHERE id=?
            """,
            (
                cache.get("topic_fit"),
                cache.get("core_contribution"),
                cache.get("boundary_conflict"),
                cache.get("matched_direction_id"),
                cache.get("deep_eligible"),
                cache.get("deep_eligibility_reason"),
                int(deep),
                status,
                row["id"],
            ),
        )
        return True

    relevance_efficiency.apply_cached_relevance = apply_cached_relevance

    original_apply = Pipeline._apply_task

    def apply_task(self, task: dict[str, Any]) -> None:
        original_apply(self, task)
        if task.get("task_type") != "relevance_batch":
            return
        try:
            metadata = json.loads(task.get("metadata_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            metadata = {}
        if not metadata.get("deep_entry_contract_required"):
            return

        ensure_deep_eligibility_schema(self.db)
        output = self.tasks.read_result(task)
        task_input = read_json(self.root / task["input_path"], {})
        contract = task_input.get("deep_entry_contract") or {}
        candidates = {
            str(row.get("candidate_id") or ""): row
            for row in task_input.get("candidates") or []
        }
        for result in output.get("results") or []:
            candidate_id = str(result.get("candidate_id") or "")
            candidate_input = candidates.get(candidate_id)
            if not candidate_input:
                continue
            deep, reason = derive_deep_eligibility(result, candidate_input, contract)
            relevant = bool(result.get("relevant"))
            status = "RELEVANT" if deep else ("RADAR" if relevant else "REJECTED")
            self.db.execute(
                """
                UPDATE candidates SET topic_fit=?,core_contribution=?,boundary_conflict=?,
                    matched_direction_id=?,deep_eligible=?,deep_eligibility_reason=?,
                    fulltext_required=?,status=? WHERE id=?
                """,
                (
                    result.get("topic_fit"),
                    result.get("core_contribution"),
                    int(bool(result.get("boundary_conflict"))),
                    result.get("matched_direction_id"),
                    int(deep),
                    reason,
                    int(deep),
                    status,
                    candidate_id,
                ),
            )
            # Relevance cache was populated by the inner wrapper before this final
            # deterministic override. Rewrite both fulltext admission and audit fields.
            relevance_efficiency.store_relevance_candidate(
                self.config, self.db, self.root, candidate_id
            )
            store_deep_eligibility_cache(self.config, self.db, self.root, candidate_id)

    Pipeline._apply_task = apply_task
    Pipeline._deep_eligibility_contract_installed = True
