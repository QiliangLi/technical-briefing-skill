from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from briefing_skill.efficiency import estimate_task_reduction


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate Agent-task reduction after the efficiency refactor")
    parser.add_argument("--candidates", type=int, default=100)
    parser.add_argument("--ambiguous", type=int, default=36)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--facts-before", type=int, default=17)
    parser.add_argument("--fact-budget", type=int, default=10)
    parser.add_argument("--items-before", type=int, default=17)
    parser.add_argument("--item-budget", type=int, default=10)
    parser.add_argument("--search-before", type=int, default=18)
    parser.add_argument("--search-after", type=int, default=4)
    args = parser.parse_args()
    result = estimate_task_reduction(
        candidates=args.candidates,
        ambiguous_candidates=args.ambiguous,
        batch_size=args.batch_size,
        fact_candidates_before=args.facts_before,
        fact_budget=args.fact_budget,
        item_candidates_before=args.items_before,
        item_budget=args.item_budget,
        search_before=args.search_before,
        search_after=args.search_after,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
