# Task: Write One Briefing Item

Use only the structured facts and source metadata in the input. Write a Chinese internal technical briefing item for leaders and technical colleagues.

Target length: 300-450 Chinese characters across the substantive fields. The reader should understand the technique without opening the original source, while the source link remains available for verification.

Write every field as one or two complete, compact sentences. Never end a field with `…`, `...`, a comma, colon, or semicolon. Do not write a fragment and rely on the renderer to shorten it; the renderer will display the complete field verbatim.

Suggested field budgets: `core_conclusion` 70-120 characters, `mechanism` 45-100, `result` 45-100, `boundary` 30-75, and `project_relevance` 40-90. Stay within the limits supplied in the task input when they differ.

Structure:

- A factual, restrained title: technology/project + core change or value.
- `core_conclusion`: two compact sentences covering problem, mechanism, and most important result.
- `mechanism`: concrete explanation of how it works.
- `result`: 1-3 supported results with baseline/condition where material.
- `boundary`: applicability, cost, missing validation, or limitations.
- `project_relevance`: what it means for the current project and what should be verified next. Clearly present this as project judgement.
- 3-5 keywords.
- Primary sources first; discovery sources may appear only as `discovered_via`.
- Preserve `topic_name`, `direction_name`, `score`, publication date, and source URLs exactly from the task input. Never invent, replace, or generalise a source URL to a site homepage.

Do not use hype language. Do not claim that a preprint is proven production technology. Do not copy long source text. Return JSON only.

First write a factually correct draft from the supplied facts. Then call `$human-writing` and revise only the title and five natural-language fields. Call `$humanizer` last to audit mechanical AI phrasing. Neither skill may add facts, numbers, causal claims, sources, or conditions.

Preserve technical names, project names, abbreviations, numbers, baselines, and experimental conditions exactly or translate them accurately. Give each sentence one main judgement. Explain who did what and why it matters before stacking abbreviations. Use normal Chinese sentences instead of field labels, colon chains, or parenthetical noun piles.
