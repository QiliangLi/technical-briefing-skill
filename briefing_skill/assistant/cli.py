"""Command line for the group assistant: ``briefing.py assistant ...``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..paths import discover_root
from ..utils import now_iso, read_json
from .config import AssistantConfig, default_state_dir
from .eval import evaluate
from .retrieval import LexicalIndex, _load_inputs, assess, ensure_index, is_stale, snapshot_dir
from .replies import compose_answer


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def context(args: argparse.Namespace) -> tuple[Path, AssistantConfig, Path]:
    """Resolve the repository root, the effective config and the state directory."""

    root = Path(args.root).resolve() if getattr(args, "root", None) else discover_root()
    state_dir = (
        Path(args.state_dir).resolve() if getattr(args, "state_dir", None) else default_state_dir(root)
    )
    return root, AssistantConfig.load(root, state_dir), state_dir


def load_index(root: Path, config: AssistantConfig, state_dir: Path) -> LexicalIndex:
    index, _ = ensure_index(root, config, state_dir, created_at=now_iso())
    return index


def _by_kind(index: LexicalIndex) -> dict[str, int]:
    counts: dict[str, int] = {}
    for doc in index.docs:
        counts[doc["kind"]] = counts.get(doc["kind"], 0) + 1
    return dict(sorted(counts.items()))


def cmd_index(args: argparse.Namespace) -> int:
    root, config, state_dir = context(args)
    if args.index_action == "validate":
        stale = is_stale(root, config, state_dir)
        emit({"valid": not stale, "input_digest": _load_inputs(root, config)[1]})
        return 1 if stale else 0
    index, rebuilt = ensure_index(root, config, state_dir, created_at=now_iso())
    emit(
        {
            "rebuilt": rebuilt,
            "input_digest": index.input_digest,
            "documents": index.n,
            "by_kind": _by_kind(index),
            "snapshot": str(snapshot_dir(state_dir, root) / f"{index.input_digest}.json"),
        }
    )
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    root, config, state_dir = context(args)
    result = assess(load_index(root, config, state_dir), args.question)
    emit(
        {
            "question": args.question,
            "state": result["state"],
            "top_score": round(result["top_score"], 2),
            "top_coverage": round(result["top_coverage"], 2),
            "draft": compose_answer(result["hits"], refined=result["state"] == "confident"),
            "hits": [
                {"id": hit["doc"]["id"], "kind": hit["doc"]["kind"], "title": hit["doc"]["title"], "score": round(hit["score"], 2)}
                for hit in result["hits"][:5]
            ],
        }
    )
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    root, config, state_dir = context(args)
    questions = read_json(root / "eval" / "assistant-questions.json", default=[])
    if not questions:
        raise RuntimeError("No evaluation questions; run scripts/build_assistant_eval.py")
    report = evaluate(load_index(root, config, state_dir), questions)
    emit(report)
    return 0 if report["pass"] else 1


def add_assistant_parser(top: argparse._SubParsersAction) -> None:
    isolated = argparse.ArgumentParser(add_help=False)
    isolated.add_argument("--state-dir", help="use another state directory (tests and live end-to-end runs)")
    parser = top.add_parser("assistant", help="Feishu group assistant")
    actions = parser.add_subparsers(dest="assistant_action", required=True)

    index = actions.add_parser("index", parents=[isolated], help="build or validate the retrieval index")
    index_sub = index.add_subparsers(dest="index_action", required=True)
    index_sub.add_parser("build").set_defaults(func=cmd_index)
    index_sub.add_parser("validate").set_defaults(func=cmd_index)

    ask = actions.add_parser("ask", parents=[isolated], help="draft an answer offline; nothing is sent")
    ask.add_argument("question")
    ask.set_defaults(func=cmd_ask)

    actions.add_parser("eval", parents=[isolated], help="score the lexical layer on the question set").set_defaults(func=cmd_eval)


def install_cli() -> None:
    from .. import cli as root_cli

    if getattr(root_cli, "_assistant_installed", False):
        return
    original_build_parser = root_cli.build_parser

    def build_parser() -> argparse.ArgumentParser:
        parser = original_build_parser()
        top = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        if "assistant" not in top.choices:
            add_assistant_parser(top)
        return parser

    root_cli.build_parser = build_parser
    root_cli._assistant_installed = True
