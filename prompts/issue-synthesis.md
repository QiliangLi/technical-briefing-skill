# Task: Synthesize This Issue

Read only the final selected briefing items, compact `project_contexts`, and lightweight `radar_candidates` supplied with this task. Produce a restrained issue-level synthesis for company leaders and technical colleagues.

## 本期判断：only write a judgement when there is one

`judgements` is optional in substance even though the JSON field is present. Return **1-3 only when justified; fewer is better than manufactured trends**.

A judgement belongs here only when the selected evidence actually changes how a reader should understand a technical question. Two papers being vaguely similar is not enough. Do not force every important item into a common trend.

Each judgement should make **one** concrete point. It does **not** need to contain all of “what changed → why it matters → project implication” in the same three-sentence mini-essay. Pick the part that carries the information gain and state it clearly.

Good forms include:

- a technical assumption that the evidence challenges;
- two independent works that genuinely converge on the same mechanism;
- a newly measurable engineering boundary;
- a project question whose answer has become narrower or more testable.

Bad forms include:

- listing `System A...; System B...; 两者共同表明...` merely because two items share a topic;
- turning every observation into a slogan such as “X正在成为新的验收项”;
- abstract titles that sound insightful but require the body to explain what the title meant;
- compressing unrelated mechanisms into “从体感到数字”“从进程到资产” style catchphrases.

Hard limits:

- `title`: <=32 Chinese characters; make it understandable on first read.
- `body`: <=180 characters and <=3 complete sentences.
- At most 2 numeric mentions in a body. Detailed benchmarks belong in cards.
- Do not copy detailed item titles or `core_conclusion`.
- Do not enumerate systems one by one unless the contrast itself is the judgement.
- Prefer ordinary technical Chinese over “金句”. A plain accurate sentence is better than a memorable abstraction.

`evidence_item_ids` carries traceability, so the body does not need to restate every supporting result.

## Headline

`headline` is one restrained sentence about the issue as a whole. It may simply name the most important technical theme. Do not try to squeeze three independent trends into one colon-separated headline. If the issue is heterogeneous, say so plainly rather than inventing a unifying narrative.

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

- `headline`: one restrained Chinese sentence.
- `judgements`: 1-3 justified objects with `title`, `body`, `evidence_item_ids`.
- `topic_names`: unique topic display names.
- `watch_next`: 1-3 concrete things to monitor before the next issue.
- `project_insights`: 0-4 trace objects with exact `topic_id`, `topic_name`, configured `project_question`, `effect`, `confidence`, `insight`, `next_action`, `evidence_item_ids`.
- `radar_signals`: 0-8 objects with `category`, `signal`, `summary`, `source_urls`.

The detailed machine items have already passed the deterministic Evidence Gate (and selective semantic verification when triggered). Reader-facing item prose is generated separately. Do not call another writing Skill here.
