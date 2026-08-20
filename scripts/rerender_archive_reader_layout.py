#!/usr/bin/env python3
"""Re-render every public archived email from immutable original + reader.json.

This command never rewrites ``original/`` and never calls an LLM.  It applies the
current deterministic editorial layout to the already-grounded archive reader prose.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from briefing_skill.archive_editorial_layout import rerender_all


def main() -> int:
    changed = rerender_all(ROOT)
    for path in changed:
        print(path.relative_to(ROOT))
    print(f"rerendered archive: {len(changed)} changed files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
