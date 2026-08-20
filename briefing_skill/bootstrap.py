from __future__ import annotations

from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Install briefing quality, coverage, and cost-control policies."""

    from .agently_transport import install_agently_transport
    from .archive_reader_v2 import install_archive_reader_v2_persistence
    from .balanced_evidence import install_balanced_evidence
    from .cache_fastpath import install_fact_cache_fastpath
    from .candidate_assessment import install_candidate_assessment
    from .cost_schema import install_cost_schema
    from .coverage_policy import install_coverage_policy
    from .deep_efficiency import install_deep_efficiency
    from .deep_eligibility import install_deep_eligibility_contract
    from .deep_eligibility_demo import install_deep_eligibility_demo
    from .deep_eligibility_version import install_deep_eligibility_cache_version
    from .deep_selection_contract import install_deep_selection_contract
    from .deep_selection_guard import install_deep_selection_guard
    from .discovery_stage import install_discovery_stage
    from .editorial_batch import install_editorial_batching
    from .efficiency import install_pipeline_optimizations
    from .evidence_repair import install_evidence_repair
    from .execution_envelope import install_execution_envelope_contract
    from .executor_usage import install_executor_usage_telemetry
    from .fact_cache_provenance import install_fact_cache_provenance
    from .fact_cache_text_normalization import install_fact_cache_source_normalization
    from .fact_check_minimal_patch import install_minimal_fact_check_patches
    from .fact_stage import install_fact_stage
    from .frontier_source_lanes import install_frontier_source_lanes
    from .historical_backfill import install_historical_backfill
    from .illustrated_publication import install_illustrated_publication
    from .invalid_repair import install_invalid_targeted_repair
    from .issue_stage import install_issue_stage
    from .issue_style_polish import install_issue_style_polish
    from .knowledge_materialization import install_knowledge_materialization
    from .no_human_review import install_no_human_review_gate
    from .primary_fulltext_cache import install_primary_fulltext_cache
    from .project_insight import install_project_insight_layer
    from .publication_dedup_bridge import install_publication_dedup_bridge
    from .publication_history import install_publication_history
    from .publication_history_runtime import install_publication_history_runtime
    from .publication_stage import install_publication_stage
    from .quality_guard import install_quality_guards
    from .radar_signal_synthesis import install_radar_signal_synthesis
    from .radar_taxonomy import install_radar_taxonomy
    from .reader_blocks_renderer_v2 import install_reader_blocks_renderer_v2
    from .reader_projection import install_reader_projection
    from .reader_projection_v2 import install_reader_projection_v2
    from .reader_quality_guard_v2 import install_reader_quality_guard_v2
    from .reader_writing_contract import install_reader_writing_contract
    from .release_family import install_release_family_aggregation
    from .relevance_efficiency import install_relevance_efficiency
    from .safe_efficiency import install_safe_efficiency
    from .safe_efficiency_stats import install_safe_efficiency_stats
    from .selective_fact_check import install_selective_fact_check
    from .session_grouping import install_session_grouping
    from .technology_value import install_technology_value_assessment
    from .telemetry import install_task_telemetry
    from .topic_local_deep import install_topic_local_deep_policy
    from .value_scoring import install_value_scoring

    install_cost_schema()
    install_pipeline_optimizations()
    install_relevance_efficiency()
    install_radar_taxonomy()
    # Frontier is a separate observation lane: fixed blogs/builders can feed it and
    # lack of direct project alignment is explicitly not a rejection condition.
    install_frontier_source_lanes()
    install_quality_guards()
    install_coverage_policy()
    # DiscoveryStage consumes the rolling backlog + coverage policy and creates at
    # most one Agent task containing up to four independent gap-search lanes.
    install_discovery_stage()
    install_release_family_aggregation()
    install_value_scoring()
    install_safe_efficiency()
    install_primary_fulltext_cache()

    # EvidenceStage: one canonical Balanced EvidenceBuilder, followed by V2 cache.
    install_deep_efficiency()
    install_task_telemetry()
    install_fact_cache_fastpath()
    install_evidence_repair()

    # EditorialStage owns machine-item drafting. Existing Fact Check remains available
    # as a guarded minimal patch verifier, but new runs invoke it only when the
    # deterministic Evidence Gate finds a semantic risk.
    install_editorial_batching()
    install_issue_style_polish()
    install_minimal_fact_check_patches()

    install_historical_backfill()
    install_session_grouping()
    install_invalid_targeted_repair()
    install_safe_efficiency_stats()

    # AssessmentStage: one Agent result produces relevance + Technology Value +
    # semantic Deep signals, then Python derives Deep eligibility and persists one
    # CandidateAssessment. TopicLocalSelection is the final runtime selector.
    install_deep_eligibility_cache_version()
    install_technology_value_assessment()
    install_deep_eligibility_contract()
    install_deep_eligibility_demo()
    install_candidate_assessment()
    install_project_insight_layer()
    install_deep_selection_guard()
    install_topic_local_deep_policy()
    install_deep_selection_contract()

    # Balanced-evidence compatibility layer now contributes telemetry only.
    install_balanced_evidence()
    install_fact_cache_provenance()
    install_fact_cache_source_normalization()
    install_fact_stage()

    # IssueStage owns deterministic final selection. Reader Projection still binds
    # prose to the final fact-checked item, while Reader v2 lets the model choose the
    # card's natural paragraph order and semantic heading keys. The legacy Editorial
    # Intent module remains available only for v1 archive/interrupted-run rendering.
    install_radar_signal_synthesis()
    install_reader_writing_contract()
    install_issue_stage()
    install_reader_projection()
    install_reader_projection_v2()
    install_reader_quality_guard_v2()
    install_reader_blocks_renderer_v2()
    install_archive_reader_v2_persistence()
    install_selective_fact_check()
    install_publication_stage()
    install_illustrated_publication()
    # The final transport owns public image URLs and Agently body+HTML attachment.
    install_agently_transport()
    install_no_human_review_gate()
    # Delivery history is installed last so there is exactly one canonical SENT owner.
    install_publication_history()
    install_publication_history_runtime()
    install_publication_dedup_bridge()

    install_execution_envelope_contract()
    install_executor_usage_telemetry()
    # Published machine records feed a separate, bounded Roadmap/Idea materializer.
    # It never reads candidates, full text, or reader projections.
    install_knowledge_materialization()
    from .cli import main as cli_main

    return int(cli_main(list(argv) if argv is not None else None))