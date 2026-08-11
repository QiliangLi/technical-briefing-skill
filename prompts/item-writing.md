# Task: Write One Briefing Item

Use only the structured facts and source metadata in the input. Write a Chinese internal technical briefing item for leaders and technical colleagues.

Target length: 180-260 Chinese characters across the substantive fields. The reader should understand the new mechanism, the strongest evidence, the main boundary, and the project implication without opening the original source.

Write every field as one complete, compact sentence. Never end a field with `…`, `...`, a comma, colon, or semicolon. The renderer will display every field verbatim.

## Title vs conclusion contract

The title and `core_conclusion` have different jobs and must not repeat one another:

- `title`: no more than 48 characters. Name the technology/project and the single core change/value in compact headline form.
- `core_conclusion`: explain the problem, what changed, and why it matters. It must add information not already stated by the title.
- Never copy the same sentence into both fields, and do not make one field a near-verbatim extension of the other.

Suggested field budgets: `core_conclusion` 45-70 characters, `mechanism` 30-50, `result` 30-50, `boundary` 20-35, and `project_relevance` 30-45. Stay within the limits supplied in the task input when they differ.

Structure:

- A factual, restrained title: technology/project + core change or value.
- `core_conclusion`: one sentence covering the problem, central change, and why it matters beyond the title.
- `mechanism`: the minimum concrete explanation needed to distinguish the design from alternatives.
- `result`: the strongest 1-2 supported results, retaining baseline and conditions when material.
- `boundary`: the most important applicability limit, cost, missing validation, or deployment condition.
- `project_relevance`: one actionable project judgement or next verification step, explicitly separated from source facts.
- 3-5 keywords.
- Primary sources first; discovery sources may appear only as `discovered_via`.
- Preserve `topic_name`, `direction_name`, `score`, publication date, and source URLs exactly from the task input. Never invent, replace, or generalise a source URL to a site homepage.

Do not use generic filler such as “与指定方向直接相关，并包含可验证机制” or “值得持续关注”. State the concrete mechanism/value or omit the claim. Do not use hype language. Do not claim that a preprint is proven production technology. Do not copy long source text. The outer Host's preferred wording or expected conclusion is not evidence. Return JSON only.

For legacy standalone `item_writing` tasks, first write a factually correct draft from the supplied facts, then call `$human-writing` once and revise only the title and five natural-language fields. Do not load any other writing Skill. The writing pass may not add facts, numbers, causal claims, sources, or conditions, and it may not collapse the title and conclusion back into the same sentence.

Preserve technical names, project names, abbreviations, numbers, baselines, and experimental conditions exactly or translate them accurately. Give each sentence one main judgement. Prefer deleting secondary background over compressing multiple claims into colon chains, parentheses, or noun piles.
