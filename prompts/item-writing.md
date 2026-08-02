# Task: Write One Briefing Item

Use only the structured facts and source metadata in the input. Write a Chinese internal technical briefing item for leaders and technical colleagues.

Target length: 300-450 Chinese characters across the substantive fields. The reader should understand the technique without opening the original source, while the source link remains available for verification.

Structure:

- A factual, restrained title: technology/project + core change or value.
- `core_conclusion`: two compact sentences covering problem, mechanism, and most important result.
- `mechanism`: concrete explanation of how it works.
- `result`: 1-3 supported results with baseline/condition where material.
- `boundary`: applicability, cost, missing validation, or limitations.
- `project_relevance`: what it means for the current project and what should be verified next. Clearly present this as project judgement.
- 3-5 keywords.
- Primary sources first; discovery sources may appear only as `discovered_via`.

Do not use hype language. Do not claim that a preprint is proven production technology. Do not copy long source text. Return JSON only.
