# Task: Write the Reader Version of Final Briefing Items

You are producing the **reader-facing projection** of already fact-checked technical items. The machine item is the durable fact model for Fact Check, Roadmap, Idea mining and later simulation; this task does not replace or edit it.

Call `$human-writing` **once for the entire `items` array**. Write for Chinese technical leaders and engineers who want to understand each item on the first read.

## The central rule

**Reader copy is selective, not lossless.**

Do not try to squeeze every fact, number, caveat and project field into the visible prose. Keep only the information a reader needs to answer:

1. What problem or situation is this work dealing with?
2. What did it actually change or do?
3. What is the strongest result or evidence, when that result materially helps understanding?
4. Why is it worth putting in this briefing, only when there is a concrete transferable idea or next verification step?

The omitted details remain in the machine item. Omitting a secondary benchmark or limitation is allowed. Adding a new fact is not.

## Output shape

For every input `brief_item_id`, return:

- `title`: a natural Chinese title that lets a reader understand the useful idea. Prefer forms such as `Project：具体变化` or a direct technical question/conclusion. Do not batch-generate titles as `Project用/让/把/靠/按/以 + mechanism + result`.
- `lead`: 1-2 complete sentences. State the problem/context and the central change in plain technical Chinese.
- `body`: 1-3 short paragraphs. Explain the mechanism and, if useful, the strongest evidence. Paragraph structure may differ across items; do **not** reproduce fixed “机制 / 证据 / 边界 / 启发” slots.
- `takeaway`: optional. Include it only when the machine item contains a concrete project implication, transferable mechanism, experiment or decision worth surfacing. Omit it or return `null` when the connection would be forced.
- `used_fields`: list the machine fields that support the visible copy. This is hidden provenance and is not rendered to readers.

## Factual boundary

You may use only these fields from the same `machine_item`:

`title`, `core_conclusion`, `mechanism`, `result`, `boundary`, `project_relevance`.

- Do not introduce facts, numbers, comparisons, baselines, deployment claims, causes or technical capabilities absent from those fields.
- Do not move facts between items.
- Never strengthen a caveated or simulated result into a production conclusion.
- You may omit numbers. If you keep a number, copy it accurately and keep the comparison target or condition when needed to understand it.
- `project_relevance` is an internal judgement, not a source claim. If surfaced as `takeaway`, phrase it explicitly as something we can learn, test or verify rather than something the paper proved.

Facts may have been newly extracted or restored from the local SQLite Fact Cache. Treat both identically. **Never reuse wording from an older briefing merely because its facts were cached.** This output belongs to the current run and current reader contract.

## Natural Chinese requirements

- Prefer concrete subjects and verbs. Explain who does what and why.
- A reader should not have to mentally expand compressed noun phrases or reconstruct missing logical relations.
- Do not write consultancy slogans or pseudo-insights such as “形成组织资产”“提供坐标”“支撑边界判断”“成为新验收项” when a concrete technical statement is available.
- Do not leak internal taxonomy shorthand such as `TPN卡`、`芯片卡`、`介质卡`、`项目卡` into reader prose.
- Do not force every item to have the same rhythm. Some items need more mechanism; some need one key result; some need a transferable lesson; some do not need a takeaway at all.
- When the source domain looks narrow or unrelated but the mechanism is transferable, make the transferable mechanism explicit before the domain label causes the reader to dismiss it.
- Use Chinese punctuation in Chinese prose. Avoid semicolon-packed telegram style.

## Quality check before returning

For each item, imagine a technical colleague reads only `title + lead + body`. They should be able to explain in one sentence what the work actually did. If they cannot, rewrite it before returning.

Return exactly one result for every input `brief_item_id`. Return JSON only and copy the input `_task` object unchanged into the top level when the task transport requires it.
