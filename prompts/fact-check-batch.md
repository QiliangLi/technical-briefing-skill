# Task: Independently Fact Check a Batch

Check each entry under `checks` independently against only that entry's structured facts. Evidence from one item must never be used to validate another item.

Return exactly one result for every input `brief_item_id`, with no omissions, duplicates, or extra IDs.

For each item check:

1. Every number and comparison is supported by that item's facts.
2. Baseline, workload, scale, hardware/software, and experimental conditions are retained when they materially change interpretation.
3. Source facts and project inference are clearly separated.
4. Correlation, author opinion, or secondary reporting is not promoted into a certain fact.
5. At least one resolved primary A-level source URL supports the item; a site homepage is unresolved.
6. Every substantive field is a complete sentence and does not end with an ellipsis, comma, colon, or semicolon.
7. The combined substantive text remains within that entry's supplied character budget.
8. Topic, direction, score, publication date, and source URLs are immutable.

If problems are minor, return a fully corrected item in `corrected_item`. If evidence is insufficient or the primary source is unresolved, set `pass=false` and explain why. Do not transfer facts or corrections across entries.

Return JSON only. Copy the input `_task` object unchanged into the top level of the output.