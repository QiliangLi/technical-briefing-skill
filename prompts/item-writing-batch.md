# Task: Write a Batch of Briefing Item Drafts

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

This task is **draft generation only**. Do not call any writing Skill here. A later issue-level `item_style_polish` task sees all drafted items together and calls `$human-writing` exactly once for cross-item Chinese style cleanup. That later pass may change wording but not facts; the polished result is then independently fact-checked.

Return JSON only. Copy the input `_task` object unchanged into the top level of the output.
