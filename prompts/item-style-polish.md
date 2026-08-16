# Task: Rewrite All Briefing Items into Natural Technical Chinese

This is the **single issue-level Chinese editorial pass** after all detailed item drafts have been written and before fact checking.

Call `$human-writing` **once for the entire `items` array**. Do not invoke `$human-writing` separately for each item, and do not load any other writing Skill in this stage.

The drafts are fact containers, not wording constraints. Your job is to rewrite the reader-facing fields into natural, professional Chinese while preserving the exact factual content of each item. **Do not default to KEEP and do not limit yourself to minimal patches.** If a sentence has compressed abstract-style Chinese, English word order, noun piling, missing logical relations, or telegraphic phrasing, rewrite the whole field.

## What you may edit

For every `brief_item_id`, return these reader-facing fields:

- `title`
- `core_conclusion`
- `mechanism`
- `result`
- `boundary`
- `project_relevance`

## Hard factual invariants

1. Preserve every fact, number, comparison, baseline, condition, caveat, causal strength and project/source boundary already present in that item's draft.
2. Never move a fact, number, condition or judgement from one item into another item.
3. Do not add new facts, examples, benchmarks, causes, implications or source claims.
4. Do not modify topic, direction, score, publication date, source URLs, keywords, importance, type or any other non-style field. They are intentionally omitted from the output.
5. Preserve the distinction between source facts and `project_relevance`; the latter remains an internal project judgement, not a statement made by the source.
6. The reconstructed item must stay within the supplied total length contract. Field-level lengths are flexible within the schema: readability takes priority over forcing every idea into one short sentence.

## Technical Chinese editorial contract

Write for Chinese technical leaders and engineers who should understand the item without mentally translating an English abstract.

- Prefer a clear subject → action/change → result or implication structure.
- Keep necessary comparison objects, conditions and logical connectors. Do not delete them merely to save characters.
- One sentence should carry one main judgement. A field may use two short complete sentences when that is clearer than one overloaded sentence.
- Avoid strings of abstract nouns such as “计量能力—资源治理—调度问题” when a concrete subject and verb can express the same meaning.
- Preserve established English project names, abbreviations and technical terms, but express ordinary actions and relations in natural Chinese.
- Avoid report-like filler or vague consultancy wording such as “走向”“落点”“提供坐标”“开始汇合”“成为前置条件” unless the phrase is genuinely the most precise description of the supported fact.
- Avoid half-colloquial compression such as “拿到加速”“保住精度”“多付 token” when a precise Chinese comparison can be stated directly.
- When a number matters, make its baseline or comparison target explicit if that target is already present in the draft.
- Use Chinese punctuation in Chinese prose except where punctuation is part of a technical identifier or code term.
- Vary sentence rhythm across the issue, but never trade precision for stylistic novelty.

## Examples of the required transformation

Bad: `强Actor用Atomic反增约20%输入token，部分条件未展开。`
Better structure: `对能力较强的 Actor，Atomic 接口反而使输入 token 增加约 20%；论文对这一现象的适用条件尚未充分展开。`

Bad: `算子化编排对Agent Cache与工具结果的跨节点调度有直接借鉴价值。`
Better structure: `OpRAG 将检索、记忆和更新统一抽象为可调度算子，这种设计可作为 Agent Cache 和工具结果跨节点调度的参考。`

These examples demonstrate syntax and readability only. Never copy their facts into another item.

The next pipeline stage independently fact-checks the rewritten text against structured facts. This stage therefore has broad **language rewrite authority** but zero **fact creation authority**.

Return exactly one result for every input `brief_item_id`, in the same issue-level call. Return JSON only and copy the input `_task` object unchanged into the top level of the output when the task transport requires it.
