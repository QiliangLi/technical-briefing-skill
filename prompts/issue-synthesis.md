# Task: Synthesize This Issue

Read only the final selected briefing items, compact `project_contexts`, and lightweight `radar_candidates` supplied with this task. Produce a restrained issue-level synthesis for company leaders and technical colleagues.

## 本期判断：必须有，但不要强造共同趋势

Return **1-3 judgements; usually 2-3**. The briefing has already selected useful evidence, so readers should get a small number of conclusions before reading the detailed cards.

Each judgement should make **one** concrete technical point that is worth remembering. It may be supported by:

- one strong item that challenges an assumption or gives a counter-intuitive result;
- multiple independent works that genuinely converge on the same mechanism;
- a previously vague engineering question that now has a measurable boundary;
- evidence that supports, challenges or narrows a technical assumption;
- a new direction that is concrete enough to test next.

A judgement does **not** need to combine multiple items. Do not add a second paper merely to make a statement look like a trend. Conversely, when several works really do converge, explain the shared mechanism rather than just listing systems.

A judgement also does **not** need to contain all of “what changed -> why it matters -> project implication”. State the part that carries the information gain. Do not force every judgement back to a configured project question.

Avoid:

- `System A...; System B...; 两者共同表明...` when the works only share a broad topic;
- slogans such as “X正在成为新的验收项”;
- compressed catchphrases such as “从体感到数字”“从进程到资产”;
- abstract titles that require the body to decode what the title meant;
- repeating all benchmark numbers already visible in detailed cards.

Keep the title understandable on first read. The body may use ordinary technical prose instead of being compressed into a fixed sentence count. `evidence_item_ids` provides traceability, so include only the evidence that actually supports the judgement.

## No generated issue headline

Do **not** generate a `headline`. The publication layer owns the fixed briefing title and date. Your job starts with `judgements`.

## Project insights: internal traceability, not reader copy

Produce `project_insights` only when selected **core** evidence materially changes a configured project question.

- Use an exact question from the matching `project_contexts[].current_questions`.
- `effect` is one of `supports`, `challenges`, `narrows`, `opens`.
- `insight` is explicitly our inference from evidence, not a source claim.
- `next_action` is a concrete experiment, measurement, implementation check or decision step.
- Cite 1-4 exact `brief_item_id` values; at least one must come from the same topic.
- Preserve conditions and limitations.
- Return an empty array instead of filler.
- A project insight does not have to become a reader-facing judgement. Only surface it there when it is independently useful to readers.
- Discovery-only/Radar material cannot support `judgements` or `project_insights`.

## Hotspot Radar and 边界探索

`radar_candidates` is intentionally lightweight: title, summary, source metadata, category, source lane and URL. Do not open full text and do not upgrade Radar material to Deep evidence.

Candidates may come from `academic_primary` or `industry_builder`. Papers/primary technical sources remain the evidence backbone, while technical blogs, engineering posts and Builder material can be useful direct observations without an accompanying paper. When useful material exists in both lanes, preserve source diversity rather than defaulting to an all-arXiv Radar.

`边界探索` is intentionally allowed outside configured project boundaries. Do not penalize lack of direct project alignment. Select it when it exposes a transferable mechanism, counter-intuitive systems result, new architecture/hardware abstraction, or a direction that expands the hypothesis space. Do not fabricate a mapping back to an existing project.

Produce `radar_signals` as concrete signals, not an article list:

- Select for information gain, not quotas; use fewer than 8 when appropriate.
- `signal` names a specific mechanism, capability, bottleneck, change or emerging direction.
- `summary` uses 1-2 complete Chinese sentences to explain what changed and why a technical reader may care.
- Mention concrete systems/components/constraints when supplied.
- Never expose internal selection metadata such as rule scores or evidence-lane implementation details.
- Merge candidates only when they truly support the same signal.
- Every `source_urls` entry must be copied exactly from a candidate URL.
- Keep each signal inside the category of its supporting candidates.
- Do not add numbers or causal claims absent from candidate summaries.

## Output

Return JSON only:

- `judgements`: 1-3 concrete objects with `title`, `body`, `evidence_item_ids`; normally 2-3.
- `topic_names`: unique topic display names.
- `watch_next`: 1-3 concrete things to monitor before the next issue.
- `project_insights`: 0-4 trace objects with exact `topic_id`, `topic_name`, configured `project_question`, `effect`, `confidence`, `insight`, `next_action`, `evidence_item_ids`.
- `radar_signals`: 0-8 objects with `category`, `signal`, `summary`, `source_urls`.

The detailed machine items have already passed the deterministic Evidence Gate (and selective semantic verification when triggered). Reader-facing item prose is generated separately. Do not call any writing Skill here. Return JSON only.
