from __future__ import annotations

from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Install briefing quality, coverage, and cost-control policies."""

    from .cost_schema import install_cost_schema
    from .coverage_policy import install_coverage_policy
    from .deep_efficiency import install_deep_efficiency
    from .efficiency import install_pipeline_optimizations
    from .quality_guard import install_quality_guards
    from .radar_taxonomy import install_radar_taxonomy
    from .telemetry import install_task_telemetry
    from .topic_appendix_render import install_topic_appendix_rendering
    from .value_scoring import install_value_scoring

    install_cost_schema()
    install_pipeline_optimizations()
    install_radar_taxonomy()
    install_quality_guards()
    install_coverage_policy()
    install_topic_appendix_rendering()
    install_value_scoring()
    install_deep_efficiency()
    install_task_telemetry()
    from .cli import main as cli_main

    return int(cli_main(list(argv) if argv is not None else None))
