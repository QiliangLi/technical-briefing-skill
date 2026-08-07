from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from briefing_skill.efficiency import estimate_task_reduction


def _ceil_div(value: int, divisor: int) -> int:
    return (max(0, value) + max(1, divisor) - 1) // max(1, divisor)


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate Agent-task reduction after the efficiency refactor")
    parser.add_argument("--candidates", type=int, default=100)
    parser.add_argument("--ambiguous", type=int, default=36)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--facts-before", type=int, default=17)
    parser.add_argument("--fact-budget", type=int, default=16)
    parser.add_argument("--items-before", type=int, default=17)
    parser.add_argument("--item-budget", type=int, default=16)
    parser.add_argument("--writing-batch-size", type=int, default=4)
    parser.add_argument("--fact-check-batch-size", type=int, default=4)
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

    # The legacy estimator models one writing task plus one fact-check task per
    # selected item. Replace only that editorial component with the new batches;
    # relevance/search/fact-extraction assumptions remain unchanged.
    selected_items = min(max(0, args.items_before), max(0, args.item_budget))
    legacy_after = int(result["tasks_after"])
    legacy_editorial = selected_items * 2
    writing_batches = _ceil_div(selected_items, args.writing_batch_size)
    check_batches = _ceil_div(selected_items, args.fact_check_batch_size)
    batched_after = legacy_after - legacy_editorial + writing_batches + check_batches
    before = int(result["tasks_before"])

    result.update(
        {
            "tasks_after_unbatched_editorial": legacy_after,
            "item_writing_tasks_after": writing_batches,
            "fact_check_tasks_after": check_batches,
            "tasks_after": batched_after,
            "task_reduction_ratio": round(0.0 if not before else (before - batched_after) / before, 4),
        }
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
