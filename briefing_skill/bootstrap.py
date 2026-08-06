from __future__ import annotations

from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Install low-token planning and quality guards, then enter the stable CLI."""

    from .efficiency import install_pipeline_optimizations
    from .quality_guard import install_quality_guards

    install_pipeline_optimizations()
    install_quality_guards()
    from .cli import main as cli_main

    return int(cli_main(list(argv) if argv is not None else None))
