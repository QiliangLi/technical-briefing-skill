from __future__ import annotations

from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Install low-token planning, Radar taxonomy, quality, and coverage guards."""

    from .coverage_policy import install_coverage_policy
    from .efficiency import install_pipeline_optimizations
    from .quality_guard import install_quality_guards
    from .radar_taxonomy import install_radar_taxonomy

    install_pipeline_optimizations()
    install_radar_taxonomy()
    install_quality_guards()
    install_coverage_policy()
    from .cli import main as cli_main

    return int(cli_main(list(argv) if argv is not None else None))
