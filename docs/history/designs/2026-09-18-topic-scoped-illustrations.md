# Topic-scoped issue illustrations

- Status: implemented
- Created: 2026-09-18
- Last updated: 2026-09-18

## Problem and evidence

The last two runs exposed two linked defects in the issue-level illustration pass:

1. **Selection drifts toward coverage, not key information.** Run 2026-09-16 produced 6 images and run 2026-09-18 produced 9 for 13 items. In 2026-09-18 the top-scored item (UPA, 91.24) received no image while the four lowest-scored observation items (73.3/73.1/72.2/71.8) all did. Root cause: `_illustration_input` strips `score` and judgement membership from the items handed to the visual Agent, and both the prompt and `docs/contracts/illustrated-publication.md` instruct "no fixed numeric cap … select every distinct explanatory concept". The Agent literally cannot see which items matter and is told to maximize concept coverage.
2. **Layout cannot express image→item proximity.** The placement vocabulary is only `after_judgements` / `before_topic`, and `render_illustrated_html` assigns overflow images to the *first unused content row* in DOM order, ignoring the recorded evidence binding. Measured on the sent 2026-09-18 email: only 4 of 9 images were within one card of a bound item; image 05 sat 10 cards away from its item, physically between two unrelated items. Semantic slots (1 + one per topic) are structurally mismatched with an unbounded image count, so most images were scattered mechanically.

The maintainer's direction: the goal is not fewer images but images that make the key information intuitively understandable. Each topic gets **at most one** image; when a topic contains several high-value items, that single image must synthesize them; a topic may also have **zero** images.

## Goals and non-goals

Goals:

- One topic, at most one image, placed immediately before that topic's header in the email, so a reader can always attribute the image to the topic it explains.
- The topic image is chosen from the topic's **key items** (score plus membership in issue judgements), and when several key items exist it visually synthesizes their shared mechanism instead of picking one at random.
- Python deterministically enforces the policy at task-output validation time, so an Agent manifest that violates the per-topic cap, the placement rule, or the binding rule is rejected (`INVALID`) rather than repaired downstream.
- The reader can map an image to its source cards: the caption must name the covered items.

Non-goals:

- No per-item inline illustrations; item cards stay text-only.
- No restoration of the issue-level `after_judgements` synthesis image (judgements already carry textual item anchors; the user policy is topic-scoped).
- No change to generation hosting, persona contract, publication URLs, dual-HTML output, or the Codex delegation flow.

## Constraints and invariants

- `issue/issue.json` and the baseline `email.html` remain immutable inputs to the visual pass; illustration may never rewrite, re-rank, or delay them.
- Every `status=generated` image still requires `persona_used=true`, a QA'd local asset path, and immutable published URLs (commit-SHA raw primary + release backup). Existing publication gates are unchanged.
- Non-adjacent image placement is preserved (with ≤1 image per topic placed before a topic header, adjacency cannot occur, but the guard stays as a defense).
- Deterministic validation remains Python-owned; the prompt states the same policy, but enforcement never relies on prompt compliance alone.
- Fail-closed behavior: an image whose topic anchor is missing from the rendered email is skipped and final provenance validation fails, forcing an explicit decision before send (existing semantics).
- Active-run compatibility: config/task-contract changes take effect from new run boundaries; archived runs and their manifests are never re-interpreted.

## Proposed design

### Selection contract (prompt + input)

`_illustration_input` adds, per item: `score` and `in_issue_judgements` (true when the id appears in any `synthesis.judgements[].evidence_item_ids`). The constraint block text changes from "no fixed cap" to the topic-scoped policy.

The rewritten selection rules in `prompts/illustrated-publication.md`:

1. Decide per topic: zero or one image. Total images ≤ number of topics.
2. Within a topic, key items are those with high `score` and `in_issue_judgements=true`; observations may inform the picture but must not crowd out key core items.
3. One dominant key item → the image explains that item's central mechanism. Several key items → one image synthesizes their shared mechanism or the topic-level judgement; never a collage of unrelated motifs.
4. Skip the topic when no honest visual synthesis exists. An empty manifest is valid.
5. Every generated image records `bound_item_ids` (1–4 item ids from the same topic) and a caption that names the covered items so the reader can map image to cards.

### Manifest schema

- `placement` enum reduces to `["before_topic"]`; `after_judgements` is removed.
- `topic_id` becomes a required non-empty string.
- New required-for-generated field `bound_item_ids`: 1–4 unique `brief_item_id` strings.
- All other fields (persona, assets, QA notes) unchanged.

### Deterministic gates

New `illustrated_publication` checks in `TaskService._semantic_errors` (they run at sync/apply time for every task output):

- every illustration uses `placement="before_topic"` with a non-empty `topic_id` that exists in the issue's items;
- at most one non-fallback illustration per `topic_id`;
- generated images carry non-empty unique `bound_item_ids` referencing items of the **same** topic, ≤4 entries;
- the count of non-fallback illustrations does not exceed the number of distinct topics.

### Rendering

`render_illustrated_html` reduces to topic-slot insertion: each generated image with a resolved asset is inserted immediately before its topic's header row (guarded by the existing non-adjacency check). The `after_judgements` slot, the deterministic topic-fallback, and the first-unused-row overflow path are removed; with the gate enforcing ≤1 per topic, no legitimate manifest needs them, and an illegitimate one now fails earlier.

## Compatibility and migration

- Archived runs: untouched; history is never re-interpreted.
- In-flight runs: none at design time (latest run is `SENT`). New runs create the task from the new input/schema automatically; the schema digest change forces fresh task inputs at the new run boundary, matching the "config changes activate at run boundaries" rule.
- `demo` fallback (empty illustrations) and `agently_transport.render_publication_html` (published-URL rewriting for generated images) are unaffected.
- `publication_manifest` provenance checks keep validating manifest↔HTML consistency; the simplified renderer still tags inserted rows with slot metadata.

## Failure, recovery, and rollback

- Agent returns an over-cap or wrongly-bound manifest → task output marked `INVALID` with a precise gate message; the Agent rewrites the manifest (normal reopen-invalid flow).
- Topic anchor missing at render time → image skipped → provenance validation fails before send (unchanged fail-closed path).
- Rollback: revert the commit; old prompt/schema/renderer return. No stored state depends on the new fields until a run applies a new-format manifest, and those manifests are run-scoped.

## Verification

- Unit tests: per-topic gate (cap, placement, binding, topic existence, count); renderer inserts each image before its topic header and nothing else; input includes `score`/`in_issue_judgements`; empty manifest still degrades to baseline; persona/URL requirements unchanged.
- Update the two existing tests that asserted "no numeric cap" behavior.
- Full relevant suites: `tests/test_illustrated_publication.py`, `tests/test_deterministic_publication.py`, `tests/test_public_trace_scan.py`.
- Manual acceptance on the next real run: every topic image sits directly before its topic header; captions name covered items; no image far from its topic.

## Documentation impact

- `SKILL.md` — visual rules section: replace the "no fixed cap" paragraph with the topic-scoped policy; drop "不设每期出现次数上限" phrasing accordingly.
- `docs/contracts/illustrated-publication.md` — selection policy, placement vocabulary, workflow description.
- `prompts/illustrated-publication.md`, `schemas/illustrated-publication.schema.json` — as designed above.

## Decision log

- 2026-09-18 — Maintainer direction after two affected runs: images must serve intuitive understanding of key information; ≤1 image per topic; synthesize high-value items into one image; zero images allowed. Basis for the whole design.
- 2026-09-18 — Remove the issue-level `after_judgements` slot: the user policy is topic-scoped and judgements already anchor items textually; keeping a fifth "issue image" would re-open the count drift the design closes. (Implementation decision within the accepted direction.)
- 2026-09-18 — Enforcement lives in Python task validation, not only the prompt, consistent with the repo invariant that deterministic gates own policy compliance.

- 2026-09-18 — Implemented; durable rules absorbed into SKILL.md and docs/contracts/illustrated-publication.md, design moved to docs/history/designs/.
