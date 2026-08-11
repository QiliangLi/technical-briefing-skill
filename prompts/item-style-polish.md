# Task: Polish All Briefing Items Once

This is the **single issue-level Chinese style pass** after all detailed item drafts have been written and before fact checking.

Call `$human-writing` **once for the entire `items` array**. Do not call `$humanizer`. Do not invoke `$human-writing` separately for each item.

The goal is narrow: make the whole issue read like natural, restrained Chinese technical writing while preserving the exact information carried by every item.

## What you may edit

For every `brief_item_id`, return only these reader-facing fields:

- `title`
- `core_conclusion`
- `mechanism`
- `result`
- `boundary`
- `project_relevance`

## Hard invariants

1. Preserve every fact, number, comparison, baseline, condition, caveat, causal strength and project/source boundary already present in that item's draft.
2. Never move a fact, number, condition or judgement from one item into another item.
3. Do not add new facts, examples, benchmarks, causes, implications or source claims.
4. Do not modify topic, direction, score, publication date, source URLs, keywords, importance, type or any other non-style field. They are intentionally omitted from the output.
5. Preserve the distinction between source facts and `project_relevance`; the latter remains an internal project judgement, not a statement made by the source.
6. Each substantive field remains one complete compact sentence and stays within the supplied product length contract after reconstruction.

## Issue-level style goals

Use the whole issue to remove cross-item repetition that a four-item batch cannot see. In particular:

- avoid every item starting with the same template such as “该工作提出”“其核心在于”“实验结果表明”“这意味着”；
- avoid institutional, promotional and model-like phrasing such as “具有重要意义”“提供了新的思路”“值得持续关注” when the underlying fact can be stated directly;
- prefer plain technical Chinese, concrete subjects and verbs, and naturally varied sentence rhythm;
- keep technical terms precise; do not replace established terminology merely to sound different;
- do not make the prose chatty, literary, cute or opinionated;
- do not inflate a preprint, benchmark or conditional result into a general production conclusion.

The next pipeline stage independently fact-checks the polished text against structured facts. Your job here is style preservation, not factual expansion or a second fact extraction.

Return exactly one result for every input `brief_item_id`, in the same issue-level call. Return JSON only and copy the input `_task` object unchanged into the top level of the output.