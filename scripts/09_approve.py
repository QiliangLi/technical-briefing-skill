#!/usr/bin/env python3
"""Approve all reviewed items for the selected run."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from briefing_skill.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["--root", str(ROOT), "approve", "--all", *sys.argv[1:]]))
