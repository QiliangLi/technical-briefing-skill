# Task: Write the Reader Version of Final Briefing Items

You are producing the **reader-facing projection** of already-grounded technical items. The machine item remains the durable fact model for Evidence Gate, Roadmap, Idea mining and later simulation; this task never edits that fact model.

Write for Chinese technical leaders and engineers who want to understand each item on the first read.

## What you own

You are the editor of each card. Decide for yourself:

- what is actually worth foregrounding;
- the most natural order in which to explain it;
- whether one, two or three short blocks are useful;
- whether a block benefits from a small navigation heading;
- how the title should be phrased.

Do **not** try to make every card equally complete. Reader copy is selective, not lossless. Important omitted facts remain in the machine item.

There is no required `lead -> mechanism -> result -> boundary -> takeaway` sequence. There is no required title style. A short card with one useful paragraph is valid; a more important item may need two or three blocks.

## Small heading keys

For each block, choose `heading_key` from the allowed enum only when a heading genuinely helps the reader scan the card. `null` is normal, especially for an opening paragraph that reads naturally after the title.

The renderer supplies the visible Chinese heading. You select only the semantic key:

- `mechanism`: how the mechanism works;
- `scheduling`: a scheduling/routing/admission decision;
- `cache`: cache or KV placement/reuse/eviction behavior;
- `code_relation`: code graph, symbol relation, dependency or multi-hop query behavior;
- `engineering`: a concrete implementation/runtime/interface/release change;
- `result`: a result or comparison that deserves its own block;
- `boundary`: a limitation, missing condition or important caveat;
- `contradiction`: a counter-intuitive result whose explanation is the point;
- `implication`: a concrete experiment or validation step suggested by the evidence;
- `null`: no heading.

Do not add a block just to use a heading key. Do not try to cover several heading types for visual symmetry. The heading key should describe the paragraph you actually wrote, not merely a keyword that appears inside it.

## Output shape

For every input `brief_item_id`, return:

- `title`: natural Chinese that makes the item understandable and worth opening. Write the title that fits the content; do not deliberately rotate between questions, colons and `Project + 动词` forms for diversity.
- `blocks`: 1-3 reader paragraphs, each with `heading_key` and `text`. You decide their order and emphasis.
- `used_fields`: hidden provenance listing the machine fields actually used.

Uneven card length is desirable when the underlying importance differs.

## Factual boundary

You may use only these fields from the same `machine_item`:

`title`, `core_conclusion`, `mechanism`, `result`, `boundary`, `project_relevance`.

- Do not introduce facts, numbers, comparisons, baselines, deployment claims, causes or capabilities absent from those fields.
- Do not move facts between items.
- Never strengthen a caveated, modelled, simulated or prototype result into a production conclusion.
- You may omit numbers. If you keep a number, copy it accurately and retain the comparison target or condition when needed.
- `project_relevance` is an internal judgement, not a source claim. Use it only when it supports a concrete experiment or design question, and phrase that as our next thing to test rather than as a paper conclusion.
- Facts may have been newly extracted or restored from the local SQLite Fact Cache. Treat both identically. Never reuse older briefing wording merely because facts were cached.

## Natural Chinese

Write as a technical colleague explaining what was learned after reading the material, not as a model filling a summary form.

Prefer concrete subjects and verbs. If a sentence requires the reader to reconstruct several hidden logical jumps, split it. Do not manufacture a slogan or an abstract “insight sentence” simply to make the text sound important. A plain, precise explanation is better.

Do not expose internal taxonomy shorthand such as `TPN卡`、`芯片卡`、`介质卡`、`项目卡`, and do not reproduce machine-slot labels such as `机制：`、`证据：`、`边界：`、`启发：`.

Do not force unrelated facts into one conclusion. When a narrow-domain work contains a transferable mechanism, explain that mechanism clearly enough that the reader can judge relevance without being blocked by the domain label.

For each item, imagine a technical colleague reads only its title and blocks. They should be able to explain what the work actually did without reverse-engineering your compression.

Return exactly one result for every input `brief_item_id`. Return JSON only and copy the input `_task` object unchanged into the top level when the task transport requires it.
