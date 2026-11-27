"""Feishu group assistant.

A deterministic core that watches one Feishu group and answers from the
published corpus. It is independent of the briefing pipeline: semantic work is
emitted as bounded task files for a host session, never as a bound model API.
"""

from __future__ import annotations


def install_assistant() -> None:
    """Register the ``assistant`` and ``feedback`` commands with the CLI."""

    from .cli import install_cli

    install_cli()
