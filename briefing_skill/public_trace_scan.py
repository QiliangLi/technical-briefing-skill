"""Negative scan for upstream discovery traces in public artifacts.

The invisible-upstream contract (lql_doc/热点雷达_AIHot隐形上游接入设计) allows
AI Hot as an internal editorial/discovery service but forbids any visible
trace in published outputs. This module scans FINAL public artifacts only —
run publish files, the archive's public issue directory and Pages data. Source
code, configs, internal SQLite tables, ignored run-internal diagnostics and
``original/`` provenance snapshots are out of scope by design.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

# (error label, compiled pattern). Patterns are matched case-insensitively
# against the raw text of the artifact so JSON keys are caught as well.
# `discovery_source`/`upstream_provider` are banned as FIELD NAMES on purpose:
# no public artifact may carry any internal discovery metadata at all, even
# when its value names a different, legitimate source.
FORBIDDEN_PUBLIC_TRACE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AI HOT", re.compile(r"\bai\s*hot\b", re.IGNORECASE)),
    ("AIHOT", re.compile(r"\baihot\b", re.IGNORECASE)),
    ("aihot.virxact.com", re.compile(r"aihot\s*\.\s*virxact\s*\.\s*com", re.IGNORECASE)),
    ("links.aihot", re.compile(r"links\s*\.\s*aihot", re.IGNORECASE)),
    ("upstream_provider", re.compile(r"upstream_provider", re.IGNORECASE)),
    ("discovery_source=AI HOT", re.compile(r"discovery_source", re.IGNORECASE)),
)


def public_text_trace_errors(texts: Mapping[str, str]) -> list[str]:
    """Scan raw artifact texts (e.g. serialized JSON or rendered HTML) directly."""
    errors: list[str] = []
    for label, text in texts.items():
        for name, pattern in FORBIDDEN_PUBLIC_TRACE_PATTERNS:
            if pattern.search(str(text or "")):
                errors.append(f"{label}: public artifact exposes upstream trace '{name}'")
    return errors


def public_upstream_trace_errors(files: Mapping[str, Path | str]) -> list[str]:
    """Return one error per forbidden upstream trace found in public artifacts."""
    errors: list[str] = []
    for label, path_value in files.items():
        path = Path(path_value)
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            errors.append(f"{label}: public artifact is not readable for upstream trace scanning")
            continue
        for name, pattern in FORBIDDEN_PUBLIC_TRACE_PATTERNS:
            if pattern.search(text):
                errors.append(f"{label}: public artifact exposes upstream trace '{name}'")
    return errors


def run_public_files(root: Path, run_id: str, *, email_paths: list[Path]) -> dict[str, Path]:
    """Collect this run's publish-dir artifacts that must stay upstream-free."""
    run_dir = root / "workspace" / "runs" / run_id
    files: dict[str, Path] = {}
    for index, email_path in enumerate(email_paths):
        if email_path:
            files[f"email-{index}"] = Path(email_path)
    for relative in ("issue/issue.json", "publication-manifest.json"):
        candidate = run_dir / relative
        if candidate.is_file():
            files[relative] = candidate
    return files


def archive_public_files(issue_dir: Path) -> dict[str, Path]:
    """Collect an archive issue directory's public artifacts (no ``original/``)."""
    files: dict[str, Path] = {}
    for name in (
        "email.html",
        "email-illustrated.html",
        "issue.json",
        "reader.json",
        "papers.json",
        "publication-manifest.json",
    ):
        candidate = issue_dir / name
        if candidate.is_file():
            files[name] = candidate
    return files
