# Task: Synthesize This Issue

Read only the final selected briefing items. Produce at most three cross-item judgements for company leaders and technical colleagues.

Each judgement should identify a meaningful cross-item technical shift, common mechanism, practical implication, or uncertainty. Do not put an item or project name followed by a colon and copy its summary. Do not start the body with an item title. State the judgement in natural Chinese before explaining its evidence. Do not add facts absent from the selected items.

Return:

- `headline`: one restrained sentence summarising this issue.
- `judgements`: 1-3 objects containing a short `title`, a complete-sentence `body`, and 1-4 exact `evidence_item_ids` from the input. When multiple items support a trend, cite more than one.
- `topic_names`: unique topic display names.
- `watch_next`: 1-3 concrete things to monitor before the next issue.

After the factual draft, call `$human-writing` to improve Chinese flow without changing meaning. Then call `$humanizer` to audit repetitive, inflated, or mechanical AI patterns. Preserve every fact, number, technical term, and evidence ID. Return JSON only.
