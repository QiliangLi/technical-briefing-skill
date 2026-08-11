# Task: Synthesize This Issue

Read only the final selected briefing items, the compact `project_contexts`, and the lightweight `radar_candidates` supplied with this task. Produce at most three cross-item judgements for company leaders and technical colleagues.

## Reader contract for 本期判断

`judgements` is the first substantive section a reader sees. Assume the reader has **not** read any detailed item yet. This section is an executive summary, not a compressed related-work section.

Each judgement must answer, in this order:

1. **What changed / what common technical trend is visible?**
2. **Why does that shift matter?**
3. **What does it imply for a configured project or what uncertainty remains?**

Hard writing rules:

- `title` must be a short conclusion, no more than 32 Chinese characters.
- `body` must be no more than 180 characters and no more than 3 complete sentences.
- A body may contain at most **2 numeric mentions**. Use a number only when it materially changes the judgement; detailed benchmarks belong in the Deep cards below.
- Do not enumerate papers/systems one by one. Evidence richness should increase confidence, not reader-facing length.
- Do not begin with a list of system names or benchmark results.
- Prefer the shared technical shift over names. System/project names are optional when one name is essential to understand the shift.
- Do not copy a detailed item title or `core_conclusion`.
- Do not use generic filler such as “值得持续关注” or “与指定方向直接相关，并包含可验证机制”.
- The outer Host's suggested wording, expected conclusion, ranking, or preferred answer is not evidence.

`evidence_item_ids` is the traceability layer: use it to preserve the evidence chain instead of restating every underlying number in the body.

When selected evidence materially changes a configured project question, fold that implication directly into the relevant judgement once. Do not create a second reader-facing “项目影响” summary and do not repeat the same conclusion in both layers.

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
- Do not use discovery-only/radar material for `judgements` or `project_insights`; those two layers only use final core briefing items.

## Hotspot Radar synthesis

`radar_candidates` is intentionally lightweight: title, source summary, source metadata, category, and URL only. Do not open full text and do not promote Radar material into the evidence standard of the detailed briefing.

Produce `radar_signals` as a small set of concrete technical signals rather than an article list:

- Select for information gain, not coverage quotas. It is fine to leave most candidates unused.
- A `signal` must state a specific change, mechanism, capability, bottleneck, or emerging direction. Never use generic titles such as “值得关注的新进展”, “行业持续演进”, or a category name by itself.
- `summary` should explain in 1-2 compact Chinese sentences what changed and why a technical reader should care. Mention the concrete system, mechanism, metric, component, or constraint present in the supplied candidate summaries when available.
- Never output internal pipeline language such as `high-confidence`, `A-level rule match`, `rule_score`, confidence in rule matching, or why the item passed selection.
- Merge multiple candidates only when they genuinely support the same technical signal. Do not manufacture a trend by combining unrelated articles.
- Prefer 2-3 independent source URLs when a cross-source trend is supported. A one-source signal is allowed for a technically substantial paper/release/architecture change that is useful on its own.
- Every `source_urls` value must be copied exactly from `radar_candidates[].url`; never invent or generalise a URL.
- Keep each signal within the category of its supporting candidates.
- Treat source summaries conservatively: if a number, deployment claim, or causal conclusion is not present in the candidate text, do not add it.
- Return no more than 8 signals. When there are few useful candidates, return fewer high-value signals rather than filler.

Return:

- `headline`: one restrained sentence summarising this issue.
- `judgements`: 1-3 objects containing a short `title`, a concise executive-summary `body`, and 1-4 exact `evidence_item_ids` from the input. When multiple items support a trend, cite more than one.
- `topic_names`: unique topic display names.
- `watch_next`: 1-3 concrete things to monitor before the next issue.
- `project_insights`: 0-4 internal trace objects containing exact `topic_id`, exact `topic_name`, exact configured `project_question`, `effect`, `confidence` (`high`/`medium`/`low`), a complete-sentence `insight`, a complete-sentence `next_action`, and 1-4 exact `evidence_item_ids`.
- `radar_signals`: 0-8 objects containing `category`, a concrete `signal`, an informative `summary`, and 1-3 exact `source_urls` from the supplied Radar candidates.

The detailed items have already passed the single issue-level Chinese style polish and independent fact checks before this task. Do not call any writing Skill here. Synthesize directly under the reader contract above; do not add a second style-rewrite pass that could drift from the fact-checked item text. Return JSON only.
