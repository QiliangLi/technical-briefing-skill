from __future__ import annotations

from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Install briefing quality, coverage, and cost-control policies."""

    from .balanced_evidence import install_balanced_evidence
    from .cache_fastpath import install_fact_cache_fastpath
    from .cost_schema import install_cost_schema
    from .coverage_policy import install_coverage_policy
    from .deep_efficiency import install_deep_efficiency
    from .deep_eligibility import install_deep_eligibility_contract
    from .deep_eligibility_demo import install_deep_eligibility_demo
    from .deep_eligibility_version import install_deep_eligibility_cache_version
    from .deep_selection_contract import install_deep_selection_contract
    from .deep_selection_guard import install_deep_selection_guard
    from .editorial_batch import install_editorial_batching
    from .efficiency import install_pipeline_optimizations
    from .evidence_repair import install_evidence_repair
    from .execution_envelope import install_execution_envelope_contract
    from .executor_usage import install_executor_usage_telemetry
    from .fact_cache_provenance import install_fact_cache_provenance
    from .fact_cache_text_normalization import install_fact_cache_source_normalization
    from .fact_check_minimal_patch import install_minimal_fact_check_patches
    from .fact_stage import install_fact_stage
    from .final_reader_contract import install_final_reader_contract
    from .historical_backfill import install_historical_backfill
    from .illustrated_publication import install_illustrated_publication
    from .invalid_repair import install_invalid_targeted_repair
    from .issue_style_polish import install_issue_style_polish
    from .no_human_review import install_no_human_review_gate
    from .primary_fulltext_cache import install_primary_fulltext_cache
    from .project_insight import install_project_insight_layer
    from .quality_guard import install_quality_guards
    from .radar_signal_synthesis import install_radar_signal_synthesis
    from .radar_taxonomy import install_radar_taxonomy
    from .reader_facing_quality import install_reader_facing_quality
    from .reader_writing_contract import install_reader_writing_contract
    from .release_family import install_release_family_aggregation
    from .relevance_efficiency import install_relevance_efficiency
    from .safe_efficiency import install_safe_efficiency
    from .safe_efficiency_stats import install_safe_efficiency_stats
    from .session_grouping import install_session_grouping
    from .technology_value import install_technology_value_assessment
    from .telemetry import install_task_telemetry
    from .topic_appendix_render import install_topic_appendix_rendering
    from .topic_local_deep import install_topic_local_deep_policy
    from .value_scoring import install_value_scoring

    install_cost_schema()
    install_pipeline_optimizations()
    install_relevance_efficiency()
    install_radar_taxonomy()
    install_quality_guards()
    install_coverage_policy()
    install_release_family_aggregation()
    install_topic_appendix_rendering()
    install_value_scoring()
    install_safe_efficiency()
    install_primary_fulltext_cache()
    install_deep_efficiency()
    install_task_telemetry()
    install_fact_cache_fastpath()
    install_evidence_repair()
    install_editorial_batching()
    install_issue_style_polish()
    # The style pass owns final prose. Fact Check may only apply explicit guarded
    # field-level factual patches, and the polished output is checked against the
    # reader-writing contract before Fact Check begins.
    install_minimal_fact_check_patches()
    install_historical_backfill()
    install_session_grouping()
    install_invalid_targeted_repair()
    install_safe_efficiency_stats()
    install_deep_eligibility_cache_version()
    install_technology_value_assessment()
    install_deep_eligibility_contract()
    install_deep_eligibility_demo()
    install_project_insight_layer()
    install_deep_selection_guard()
    install_topic_local_deep_policy()
    install_deep_selection_contract()
    install_balanced_evidence()
    install_fact_cache_provenance()
    install_fact_cache_source_normalization()
    install_fact_stage()
    install_reader_facing_quality()
    install_radar_signal_synthesis()
    install_reader_writing_contract()
    install_final_reader_contract()
    install_illustrated_publication()
    install_no_human_review_gate()
    install_execution_envelope_contract()
    install_executor_usage_telemetry()
    from .cli import main as cli_main

    return int(cli_main(list(argv) if argv is not None else None))
