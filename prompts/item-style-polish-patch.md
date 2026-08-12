# Task: Sparse Issue-Level Style Polish

This is the **single issue-level Chinese style pass** after all detailed item drafts have been written and before fact checking.

Call `$human-writing` **once for the entire `items` array**. Do not invoke it separately for each item and do not load any other writing Skill.

The default action is **KEEP**. Most already-good fields should not appear in the output at all. Your job is to identify only clear reader-facing wording defects that are worth changing, not to produce a fresh rewrite of every item.

## Output contract: sparse patches only

Return a top-level `patches` array. Each patch has:

- `brief_item_id`: target item;
- `field`: exactly one editable reader-facing field;
- `before`: byte-for-byte copy of the current field value;
- `after`: the minimally improved replacement;
- `reason`: concise explanation of the concrete wording defect.

If nothing clearly needs editing, return `{"patches": []}`.

Never return a complete item and never return an unchanged field as a patch.

## Editable fields

- `title`
- `core_conclusion`
- `mechanism`
- `result`
- `boundary`
- `project_relevance`

Titles, numbers, technical terms, product/project names, causal strength and comparison wording should be treated as **preserve by default**. Edit them only when the wording itself is clearly malformed and the meaning can be preserved exactly.

## Hard invariants

1. `before` must exactly match the supplied current field. Do not normalize punctuation or whitespace in `before`.
2. Make the smallest sufficient change. Do not rewrite neighboring fields merely for stylistic consistency.
3. Preserve every fact, number, comparison, baseline, condition, caveat, causal strength, technical term and project/source boundary.
4. Never move a fact, number, condition or judgement from one item into another.
5. Do not add facts, examples, benchmarks, causes, implications or source claims.
6. Do not modify topic, direction, score, publication date, URLs, keywords, importance, type, provenance or any other non-style field.
7. Preserve the distinction between source facts and `project_relevance`; project relevance remains an internal project judgement.
8. The reconstructed item must continue to satisfy the supplied product length contract.
9. Do not emit two patches for the same `(brief_item_id, field)`.

## What is worth patching

Patch only concrete defects such as:

- an obviously ungrammatical or awkward sentence;
- a machine-like repeated template that materially hurts readability;
- unnecessary promotional/institutional phrasing when the same fact can be stated directly;
- broken reference, subject-predicate relation, or punctuation that makes meaning hard to follow.

Do **not** patch just to make wording “more varied”. In particular, do not turn precise phrases into chatty expressions such as “基本守住”, “跑得更顺”, “更香” or similar colloquial substitutions.

The next stage independently fact-checks the resulting reader text. This stage is a conservative editor, not a second writer or fact extractor.

Return JSON only and copy the input `_task` object unchanged into the top level of the output when the task transport requires it.
