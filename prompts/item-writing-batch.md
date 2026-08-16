# Task: Write a Batch of Briefing Item Drafts

Use only the structured facts and source metadata supplied under `items`. Treat every event independently: facts, numbers, conditions, sources, and project judgements from one event must never leak into another event.

Return exactly one result for every input `event_id`, with no omissions, duplicates, or extra IDs. Each `item` must satisfy the same rules as a standalone briefing item:

- Chinese internal technical briefing for leaders and technical colleagues.
- Normally 230-330 Chinese characters across the five substantive fields, unless that entry supplies different limits.
- A factual, restrained title.
- `core_conclusion`: problem + central change + why it matters.
- `mechanism`: minimum concrete mechanism that distinguishes the design.
- `result`: strongest supported 1-2 results, retaining material baseline and conditions.
- `boundary`: most important applicability limit, cost, or missing validation.
- `project_relevance`: one actionable project judgement, clearly separated from source facts.
- 3-5 keywords.
- Preserve that entry's `topic.name`, `direction.name`, `score`, publication date, and source URLs exactly. Never generalise a source URL to a site homepage.
- Every field must contain complete sentences and must not end with an ellipsis, comma, colon, or semicolon. A field may use two short sentences when that is clearer than one overloaded sentence.
- Do not use hype language or turn a preprint into proven production technology.

## Chinese drafting contract

The length limit is a reader budget, not an instruction to remove grammar. Do not turn facts into an English-abstract-like telegram in order to save characters.

- Prefer explicit subject → action/change → result structures.
- Retain comparison objects, experimental conditions and logical relations when material.
- Do not stack several abstract nouns where a concrete subject and verb would be clearer.
- Do not compress several claims into colon chains, parentheses or shorthand fragments.
- Keep technical project names and abbreviations precise, but write ordinary actions and relations in natural Chinese.
- Avoid vague consultancy wording such as “走向”“落点”“提供坐标”“开始汇合” when the source supports a more concrete statement.
- Avoid half-colloquial compression such as “拿到加速”“保住精度”“多付 token”.

This task is **draft generation only**. Do not call any writing Skill here. A later issue-level `item_style_polish` task sees all drafted items together and calls `$human-writing` exactly once. That later stage has full reader-facing field rewrite authority while facts remain locked; the resulting prose is then independently fact-checked.

Return JSON only. Copy the input `_task` object unchanged into the top level of the output.
