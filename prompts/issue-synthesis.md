# Task: Synthesize This Issue

Read only the final selected briefing items and the compact `project_contexts` supplied with this task. Produce at most three cross-item judgements for company leaders and technical colleagues.

Each judgement should identify a meaningful cross-item technical shift, common mechanism, practical implication, or uncertainty. Do not put an item or project name followed by a colon and copy its summary. Do not start the body with an item title. State the judgement in natural Chinese before explaining its evidence. Do not add facts absent from the selected items.

`judgements` is the only reader-facing judgement layer and is rendered under “本期判断”. When selected evidence materially changes a configured project question, fold that project implication directly into the relevant judgement body. Do not create a second reader-facing “项目影响” summary and do not repeat the same conclusion in both layers.

Also produce structured `project_insights` for internal traceability. This field is not rendered as a separate section. It records whether selected evidence changes an existing project question and what should be done next so the system can audit how project context influenced “本期判断”.

Rules for `project_insights`:

- Use only project questions that appear verbatim in the matching `project_contexts[].current_questions`; never invent a new project question.
- `effect` must be one of `supports`, `challenges`, `narrows`, or `opens`.
- `insight` is explicitly a project judgement inferred from the selected briefing evidence, not a claim that the source itself made.
- `next_action` must be a concrete next experiment, measurement, implementation check, or decision step. Do not disguise an unsupported factual claim as an action.
- Every insight must cite 1-4 exact `brief_item_id` values from the input, and at least one cited item must belong to the same topic as the project question.
- Preserve material conditions and limitations from the cited items. Do not generalize a conditional result into a universal conclusion.
- Prefer one strong insight over several weak ones. If the selected evidence does not materially change any configured project question, return an empty `project_insights` array rather than forcing filler.
- When a project insight is material enough to keep, its substance must be reflected once in the matching reader-facing `judgements`; do not duplicate it as a separate prose section.
- Do not use discovery-only/radar material; this task only receives the final core briefing items.

Return:

- `headline`: one restrained sentence summarising this issue.
- `judgements`: 1-3 objects containing a short `title`, a complete-sentence `body`, and 1-4 exact `evidence_item_ids` from the input. When multiple items support a trend, cite more than one. If project implications are material, include them naturally in the same body.
- `topic_names`: unique topic display names.
- `watch_next`: 1-3 concrete things to monitor before the next issue.
- `project_insights`: 0-4 internal trace objects containing exact `topic_id`, exact `topic_name`, exact configured `project_question`, `effect`, `confidence` (`high`/`medium`/`low`), a complete-sentence `insight`, a complete-sentence `next_action`, and 1-4 exact `evidence_item_ids`.

After the factual draft, call `$human-writing` to improve Chinese flow without changing meaning. Then call `$humanizer` to audit repetitive, inflated, or mechanical AI patterns. Preserve every fact, number, technical term, project question, effect, confidence label, and evidence ID. Return JSON only.
