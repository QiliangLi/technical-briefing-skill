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
    from .quality_guard import install_quality_guards
    from .radar_taxonomy import install_radar_taxonomy
    from .release_family import install_release_family_aggregation
    from .telemetry import install_task_telemetry
    from .topic_appendix_render import install_topic_appendix_rendering
    from .value_scoring import install_value_scoring

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
    from .cli import main as cli_main

    return int(cli_main(list(argv) if argv is not None else None))
