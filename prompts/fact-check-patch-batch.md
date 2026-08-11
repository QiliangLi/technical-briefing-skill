# Task: Independently Fact Check a Batch with Minimal Patches

Check each entry under `checks` independently against only that entry's structured facts. Evidence from one item must never be used to validate another item.

Return exactly one result for every input `brief_item_id`, with no omissions, duplicates, or extra IDs.

For each item check:

1. Every number and comparison is supported by that item's facts.
2. Baseline, workload, scale, hardware/software, and experimental conditions are retained when they materially change interpretation.
3. Source facts and project inference are clearly separated.
4. Correlation, author opinion, or secondary reporting is not promoted into a certain fact.
5. At least one resolved primary A-level source URL supports the item; a site homepage is unresolved.
6. Every substantive field is a complete sentence and remains within the supplied character budget.
7. Topic, direction, score, publication date, keywords, source URLs, IDs and provenance are immutable.

## Correction authority

Fact Check is a verifier, not a second writer. Never return a replacement item.

If a factual problem is minor and locally repairable, return only the smallest field-level corrections needed. Each correction must contain:

- `field`: one of `title`, `core_conclusion`, `mechanism`, `result`, `boundary`, `project_relevance`;
- `before`: the exact current field text from the input item;
- `after`: the minimally changed replacement text;
- `reason`: the factual reason for that specific change.

Do not rewrite an unaffected field for style, rhythm, concision, variety, or tone. Do not undo the issue-level Chinese style polish merely because you would phrase the sentence differently. Do not transfer facts across items.

Set `pass=true` when the item is factually valid after applying the returned minimal corrections. Set `pass=false` when evidence is insufficient, the primary source is unresolved, or the problem cannot be safely repaired with local field patches; in that case return an empty `corrections` array and explain the blocking issues.

Return JSON only. Copy the input `_task` object unchanged into the top level of the output.
