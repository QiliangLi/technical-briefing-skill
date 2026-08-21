#!/usr/bin/env python3
"""Negative upstream-trace scan over an assembled Pages publication tree.

Scans the public data the Pages site actually serves (archive/, knowledge/)
for forbidden AI Hot traces. Site source code (JS/CSS) and immutable
``original/`` provenance snapshots are out of scope by design.

Usage:
    python scripts/scan_public_traces.py <publish_dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from briefing_skill.public_trace_scan import FORBIDDEN_PUBLIC_TRACE_PATTERNS  # noqa: E402


def scan_tree(root: Path) -> list[str]:
    errors: list[str] = []
    for section in ("archive", "knowledge"):
        base = root / section
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if "original" in relative.parts:
                continue
            if path.suffix.lower() not in {".json", ".html", ".htm", ".md", ".txt", ".js"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                errors.append(f"{relative}: not readable for trace scanning")
                continue
            for name, pattern in FORBIDDEN_PUBLIC_TRACE_PATTERNS:
                if pattern.search(text):
                    errors.append(f"{relative}: exposes upstream trace '{name}'")
    return errors


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else REPOSITORY_ROOT
    if not target.is_dir():
        print(f"publish dir not found: {target}", file=sys.stderr)
        return 2
    errors = scan_tree(target)
    if errors:
        print("public trace scan failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"public trace scan passed: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
