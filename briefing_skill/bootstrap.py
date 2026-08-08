from __future__ import annotations

from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Install briefing quality, coverage, and cost-control policies."""

    from .cache_fastpath import install_fact_cache_fastpath
    from .cost_schema import install_cost_schema
    from .coverage_policy import install_coverage_policy
    from .deep_efficiency import install_deep_efficiency
    from .editorial_batch import install_editorial_batching
    from .efficiency import install_pipeline_optimizations
    from .evidence_repair import install_evidence_repair
    from .historical_backfill import install_historical_backfill
    from .invalid_repair import install_invalid_targeted_repair
    from .quality_guard import install_quality_guards
    from .radar_taxonomy import install_radar_taxonomy
    from .release_family import install_release_family_aggregation
    from .relevance_efficiency import install_relevance_efficiency
    from .safe_efficiency import install_safe_efficiency
    from .safe_efficiency_stats import install_safe_efficiency_stats
    from .session_grouping import install_session_grouping
    from .telemetry import install_task_telemetry
    from .topic_appendix_render import install_topic_appendix_rendering
    from .value_scoring import install_value_scoring

    install_cost_schema()
    install_pipeline_optimizations()
    # Install before coverage_policy so its prepare_relevance wrapper first
    # materialises the rolling backlog and only then enters the cache fast path.
    install_relevance_efficiency()
    install_radar_taxonomy()
    install_quality_guards()
    install_coverage_policy()
    install_release_family_aggregation()
    install_topic_appendix_rendering()
    install_value_scoring()
    # This layer must precede deep-efficiency so its raw-fulltext cache becomes
    # the underlying fetch path captured by the context-aware Evidence wrapper.
    install_safe_efficiency()
    install_deep_efficiency()
    install_task_telemetry()
    install_fact_cache_fastpath()
    install_evidence_repair()
    install_editorial_batching()
    # Install after the existing CLI extensions so the backfill parser preserves
    # commands such as `stats`, while the wrapped `run` gets a small auto budget.
    install_historical_backfill()
    # Session grouping changes task-dispatch instructions and stats only.
    install_session_grouping()
    # INVALID repair is last in the task-dispatch chain so repairable fact tasks are
    # isolated from session grouping and receive the small sidecar path.
    install_invalid_targeted_repair()
    # Stats composition is intentionally final so it preserves all earlier stats
    # extensions and only appends quality-neutral efficiency counters.
    install_safe_efficiency_stats()
    from .cli import main as cli_main

    return int(cli_main(list(argv) if argv is not None else None))
