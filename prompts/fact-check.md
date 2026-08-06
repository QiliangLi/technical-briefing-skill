# Task: Independent Fact Check

Compare the proposed briefing item against the structured facts.

Check:

1. Every number and comparison is supported.
2. Baseline, workload, scale, and experimental conditions are retained when they materially change interpretation.
3. Source facts and project inference are clearly separated.
4. The item does not turn correlation, author opinion, or a secondary report into a certain fact.
5. The source list contains at least one resolved primary A-level source URL for every item. A site homepage such as `https://arxiv.org` is unresolved and must fail.
6. The text is informative but not an overlong paper review.
7. Every substantive field is a complete sentence and does not end with an ellipsis, comma, colon, or semicolon.
8. The combined substantive text remains within the supplied character budget.

Do not change topic, direction, score, publication date, or source URLs. If problems are minor, return a fully corrected item in `corrected_item`. If evidence is insufficient or the primary source is unresolved, set `pass=false` and explain why. Return JSON only.
