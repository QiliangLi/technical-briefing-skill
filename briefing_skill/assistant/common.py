"""Helpers shared by the assistant's command functions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..paths import discover_root
from ..utils import now_iso
from .config import AssistantConfig, default_state_dir
from .retrieval import LexicalIndex, ensure_index


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def context(args: argparse.Namespace) -> tuple[Path, AssistantConfig, Path]:
    """Resolve the repository root, the effective config and the state directory."""

    root = Path(args.root).resolve() if getattr(args, "root", None) else discover_root()
    state_dir = Path(args.state_dir).resolve() if getattr(args, "state_dir", None) else default_state_dir(root)
    return root, AssistantConfig.load(root, state_dir), state_dir


def load_index(root: Path, config: AssistantConfig, state_dir: Path) -> LexicalIndex:
    index, _ = ensure_index(root, config, state_dir, created_at=now_iso())
    return index
