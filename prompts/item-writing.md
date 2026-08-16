# Task: Write One Briefing Item

Use only the structured facts and source metadata in the input. Write a Chinese internal technical briefing item for leaders and technical colleagues.

Target length: normally 230-330 Chinese characters across the substantive fields, unless the task input supplies different limits. This is a reader-comprehension budget, not a compression contest: the reader should understand the mechanism, strongest evidence, main boundary, and project implication without reconstructing omitted relations or opening the original source.

Every substantive field must contain complete sentences and must not end with `…`, `...`, a comma, colon, or semicolon. A field may contain two short sentences when that is clearer than forcing several claims into one overloaded sentence.

## Title vs conclusion contract

The title and `core_conclusion` have different jobs and must not repeat one another:

- `title`: no more than 48 characters. Name the technology/project and the single core change/value in a factual headline.
- `core_conclusion`: explain the problem, what changed, and why it matters. It must add information not already stated by the title.
- Never copy the same sentence into both fields, and do not make one field a near-verbatim extension of the other.

Field lengths are **soft editorial guidance**, not targets to fill or compress against. Keep each field only as long as needed to state its job clearly and stay inside the schema and total limits supplied by the task.

Structure:

- A factual, restrained title: technology/project + core change or value.
- `core_conclusion`: problem + central change + why it matters beyond the title.
- `mechanism`: the minimum concrete explanation needed to distinguish the design from alternatives.
- `result`: the strongest 1-2 supported results, retaining baseline and conditions when material.
- `boundary`: the most important applicability limit, cost, missing validation, or deployment condition.
- `project_relevance`: one actionable project judgement or next verification step, explicitly separated from source facts.
- 3-5 keywords.
- Primary sources first; discovery sources may appear only as `discovered_via`.
- Preserve `topic_name`, `direction_name`, `score`, publication date, and source URLs exactly from the task input. Never invent, replace, or generalise a source URL to a site homepage.

## Chinese drafting rules

- Prefer clear subjects and verbs. Do not translate an English abstract by preserving its noun-heavy word order.
- Keep comparison objects, conditions and logical connectors when they are needed to understand a number or conclusion.
- Do not create telegraphic phrases by deleting “对于”“相比”“结果表明”“因此”等 relations merely to save characters.
- Avoid long noun piles, colon chains and parenthetical packing. Split one overloaded sentence into two complete sentences when necessary.
- Preserve established technical names and abbreviations, but express ordinary actions and relations in natural Chinese.
- Avoid vague consultancy language such as “走向”“落点”“提供坐标”“开始汇合” when a concrete technical change can be stated instead.
- Avoid half-colloquial compression such as “拿到加速”“保住精度”“多付 token”. State the precise comparison directly.

Do not use generic filler such as “与指定方向直接相关，并包含可验证机制” or “值得持续关注”. State the concrete mechanism/value or omit the claim. Do not use hype language. Do not claim that a preprint is proven production technology. Do not copy long source text. The outer Host's preferred wording or expected conclusion is not evidence. Return JSON only.

For legacy standalone `item_writing` tasks, first write a factually correct draft from the supplied facts, then call `$human-writing` once and revise only the title and five natural-language fields. Do not load any other writing Skill. The writing pass may rewrite those fields fully but may not add facts, numbers, causal claims, sources, or conditions, and it may not collapse the title and conclusion back into the same sentence.

Preserve technical names, project names, abbreviations, numbers, baselines, and experimental conditions exactly or translate them accurately. Give each sentence one main judgement. Prefer deleting secondary background over compressing multiple claims into an unnatural sentence.
