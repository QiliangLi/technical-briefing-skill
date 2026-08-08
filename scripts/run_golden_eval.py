from __future__ import annotations

import argparse
import json
from pathlib import Path

from briefing_skill.golden_eval import load_and_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic briefing Golden Quality Eval assertions.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("eval/golden/v1/manifest.json"),
        help="Versioned golden manifest JSON.",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("eval/golden/v1/baseline-results.json"),
        help="Structured fact-extraction results keyed by golden case id.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON report destination.")
    args = parser.parse_args()

    report = load_and_run(args.manifest, args.results)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
