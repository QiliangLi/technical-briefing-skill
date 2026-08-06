from __future__ import annotations

from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Install the low-token planning policy, then enter the stable CLI."""

    from .efficiency import install_pipeline_optimizations

    install_pipeline_optimizations()
    from .cli import main as cli_main

    return int(cli_main(list(argv) if argv is not None else None))
