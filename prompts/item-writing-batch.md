# Task: Write a Batch of Briefing Items

Use only the structured facts and source metadata supplied under `items`. Treat every event independently: facts, numbers, conditions, sources, and project judgements from one event must never leak into another event.

Return exactly one result for every input `event_id`, with no omissions, duplicates, or extra IDs. Each `item` must satisfy the same rules as a standalone briefing item:

- Chinese internal technical briefing for leaders and technical colleagues.
- 180-260 Chinese characters across the five substantive fields, unless that entry supplies different limits.
- A factual, restrained title.
- `core_conclusion`: problem + central change + why it matters.
- `mechanism`: minimum concrete mechanism that distinguishes the design.
- `result`: strongest supported 1-2 results, retaining material baseline and conditions.
- `boundary`: most important applicability limit, cost, or missing validation.
- `project_relevance`: one actionable project judgement, clearly separated from source facts.
- 3-5 keywords.
- Preserve that entry's `topic.name`, `direction.name`, `score`, publication date, and source URLs exactly. Never generalise a source URL to a site homepage.
- Every field must be one complete compact sentence and must not end with an ellipsis, comma, colon, or semicolon.
- Do not use hype language or turn a preprint into proven production technology.

Work in three passes to reduce repeated editorial overhead:

1. Draft every item independently from its own structured facts.
2. Call `$human-writing` once for the batch and revise only titles plus the five natural-language fields; preserve all facts, numbers, conditions, IDs, scores, dates, and sources.
3. Call `$humanizer` once for the batch to audit mechanical AI phrasing; again, it must not add or change facts.

Return JSON only. Copy the input `_task` object unchanged into the top level of the output.