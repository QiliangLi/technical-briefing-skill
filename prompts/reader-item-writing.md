# Task: Write the Reader Version of Final Briefing Items

You are producing the **reader-facing projection** of already-grounded technical items. The machine item remains the durable fact model for Evidence Gate, Roadmap, Idea mining and later simulation; this task never edits that fact model.

Call `$human-writing` **once for the entire `items` array**. Write for Chinese technical leaders and engineers who want to understand each item on the first read.

## The central rule

**Reader copy is selective, not lossless, and the supplied `editorial_intent` is binding.**

Each input item contains a deterministic editorial plan. It does not add facts. It tells you what this card should foreground, which paragraph roles should appear, how deep it should go, and which title rhythm to use. Follow it instead of trying to make every item equally complete.

The visible reader should answer only what this item actually needs:

- What problem or situation matters here?
- What did the work actually change or do?
- Which mechanism, counter-intuitive point, engineering change or result is the editorial focus?
- Is there one concrete limitation or transferable next step worth surfacing?

Do **not** squeeze every fact, number, caveat and project field into the visible prose. Omitted details remain in the machine item.

## Editorial intent

For each item, read `editorial_intent` before writing:

- `reader_depth=normal`: keep the card compact. Usually one body paragraph is enough.
- `reader_depth=deep`: use one or two body paragraphs, never three.
- `section_plan`: body paragraphs must follow these semantic roles **in this exact order**. The UI will add the small headings later; do not print headings such as “机制：” yourself.
- `primary_focus=contradiction`: explain the surprising result and why it happens. Do not bury the counter-intuitive point under generic background.
- `primary_focus=mechanism`: make the mechanism concrete enough that a reader can retell it.
- `primary_focus=engineering`: say what was actually changed in the implementation/runtime/interface.
- `primary_focus=result`: foreground the strongest useful result and its comparison condition.
- `title_style=question`: use a real technical question only when the answer is contained in the card.
- `title_style=project_colon`: `Project：具体变化` is appropriate.
- `title_style=finding`: foreground the finding rather than the implementation verb.
- `title_style=plain`: use a direct descriptive title.

The intent exists to create **different rhythms across the issue**. Do not ignore it and fall back to the same `Project + 动词 + 机制` sentence pattern for every title.

## Output shape

For every input `brief_item_id`, return:

- `title`: natural Chinese, consistent with `title_style`. It should tell the reader why the item is interesting, not mechanically summarize every field.
- `lead`: 1-2 complete sentences. Give the minimum context needed to understand the central change.
- `body`: **1-2** short paragraphs. Paragraph 1 corresponds to `section_plan[0]`; paragraph 2, when present, corresponds to `section_plan[1]`. The renderer supplies the small section headings, so output prose only.
- `takeaway`: optional. Use only when there is a concrete experiment, transferable design choice, or limitation that changes how we should interpret the item. `null` is normal.
- `used_fields`: hidden provenance listing the machine fields actually used.

A `normal` item is allowed to be much shorter than a `deep` item. Uneven length is desirable when the underlying importance differs.

## Factual boundary

You may use only these fields from the same `machine_item`:

`title`, `core_conclusion`, `mechanism`, `result`, `boundary`, `project_relevance`.

- Do not introduce facts, numbers, comparisons, baselines, deployment claims, causes or capabilities absent from those fields.
- Do not move facts between items.
- Never strengthen a caveated or simulated result into a production conclusion.
- You may omit numbers. If you keep a number, copy it accurately and retain the comparison target or condition when needed.
- `project_relevance` is an internal judgement, not a source claim. If it becomes a takeaway, phrase it as something to test, learn or verify.

Facts may have been newly extracted or restored from the local SQLite Fact Cache. Treat both identically. **Never reuse older briefing wording merely because facts were cached.** Reader prose belongs to this run and this reader contract.

## Natural Chinese requirements

Write as a technical colleague explaining what was learned after reading the material, not as a model filling a summary form.

- Prefer concrete subjects and verbs. State who does what, under what condition, and why it matters.
- Prefer two ordinary sentences to one compressed sentence containing several logical jumps.
- Do not manufacture a “金句” merely to make the text sound insightful.
- Avoid consultancy-style abstraction such as “形成组织资产”“提供坐标”“支撑边界判断”“成为新验收项” when the concrete technical relation can be stated directly.
- Do not leak internal taxonomy shorthand such as `TPN卡`、`芯片卡`、`介质卡`、`项目卡`.
- Do not force unrelated facts into a takeaway. A card with no takeaway is complete.
- When the source domain looks narrow but the mechanism is transferable, explain the transferable mechanism before the domain label causes premature dismissal.
- Use Chinese punctuation in Chinese prose. Do not chain clauses with repeated semicolons.

## Issue-wide rhythm check

Before returning, scan all titles together. If many of them begin as `Project用… / Project让… / Project把… / Project通过… / Project以…`, rewrite them according to their supplied `title_style`. The issue should contain a natural mixture of questions, findings, project-colon titles and plain descriptions.

For each item, imagine a technical colleague reads only `title + lead + body`. They should be able to explain what the work actually did without reconstructing missing logical relations.

Return exactly one result for every input `brief_item_id`. Return JSON only and copy the input `_task` object unchanged into the top level when the task transport requires it.
