# Quality-First Optimization Roadmap

This roadmap separates output-quality work from cost work. The hard rule is: **do not reduce source recall, first-read evidence budget, fact fields, primary-source requirements, or downstream fact checking merely to make task/token numbers smaller.**

## Current quality invariants

- Deep channel requires a resolved A-level primary source.
- Up to 16 candidates may receive deep fact extraction; topic/project/direction diversity remains enabled.
- First-pass fact extraction sees up to 18k characters from the primary source.
- Material missing baseline/hardware/workload/deployment/limitation evidence may trigger one targeted supplement of at most 9k characters.
- Writing and fact checking may amortize Agent startup, but every item remains independently schema- and provenance-bound.
- Facts-cache reuse is allowed only for strong version identities and must match the current technical interpretation context.
- Human approval remains mandatory before sending.

## PR #12: correctness hardening

Implemented:

1. **Discovery -> primary source resolution**
   - deterministically promotes only known primary identities such as arXiv, DOI, GitHub and specific OpenReview pages;
   - preserves `discovered_via` provenance;
   - generic blogs/news are not automatically upgraded.

2. **Context-aware fact cache**
   - binds cache reuse to source version plus topic, direction, compact judging cards, project context and evidence policy;
   - prompt/schema/repair changes continue to invalidate cache;
   - prevents facts/project relevance extracted for one interpretation from being reused under another.

3. **Front-18k first read + targeted suffix repair**
   - first fact task reads the source beginning in original order, normally abstract/introduction/early design;
   - no heuristic section jumping during the first read;
   - a material evidence gap may search only the unread suffix and return at most 9k supplemental evidence.

4. **Event clustering hardening**
   - fuzzy merge requires the same topic and direction;
   - distinct strong arXiv/DOI/GitHub release/commit identities never merge solely due to similar titles.

5. **Quality telemetry**
   - primary-source resolve rate;
   - discovery-primary promotions;
   - final evidence-gap rate;
   - numeric evidence condition/baseline coverage;
   - repair count/success proxy;
   - fact-check pass/fail rate.

6. **AI-chip discovery coverage**
   - adds chip-topic boosts/allowlists to existing discovery feeds without weakening final evidence requirements.

## PR #13: quality-neutral efficiency hardening

Implemented in the follow-up safe-efficiency pass:

### INVALID targeted repair

Simple deterministic failures no longer require re-reading the expensive task context.

- `_task`, sentence-ending, length, immutable-field and exact-ID-set failures may use one small repair sidecar;
- the sidecar contains the previous invalid output, exact validator error and deterministic constraints only;
- the retry is forbidden from reading the original Evidence Pack/full text/project context or adding facts;
- substantive factual/evidence failures still use the normal evidence-aware path;
- targeted repair is capped at one attempt.

### Fetch failure gate with deep-budget refill

A `FALLBACK` summary cannot satisfy primary-source deep evidence requirements, so it no longer consumes a Fact Agent task.

- the failed candidate is retained as `DEFERRED_FETCH` with an audit record;
- a vacated deep slot is refilled from the next already-relevant A-level `DEFERRED_BUDGET` candidate;
- refill obeys the unchanged total and per-topic deep budgets, so fetch failures do not silently shrink information volume or expand the configured budget.

### Pre-editorial deterministic score gate

After facts/event scoring, events below the lowest selectable final issue role skip Writer + Fact Check.

- expanded mode uses the observation threshold;
- compact mode uses the issue minimum;
- downstream writing/fact checking cannot change the deterministic score, so these events could not otherwise enter the issue;
- facts and event audit state remain available.

### Exact immutable cross-source primary dedup

Before relevance review, duplicate discovery paths are collapsed only when the same immutable primary version can be proven within the same topic/direction.

- explicit arXiv `vN`, DOI, GitHub release/tag/commit identities are eligible;
- arXiv v1 and v2 remain distinct;
- unversioned arXiv links deliberately remain separate because revision equality cannot be proven;
- cross-topic/direction analysis remains separate;
- all `discovered_via` provenance is retained.

### Raw full-text cache

Normalized fetched PDF/HTML text is cached separately from facts.

- native immutable sources reuse local normalized text without another HTTP/PDF parse;
- deterministically promoted discovery records with an explicit immutable primary version can reuse the same raw text across discovery channels;
- Front-18k construction and facts remain topic/context-specific;
- mutable or unversioned sources remain conservative and are re-fetched.

### Safe-efficiency telemetry

`stats` adds deterministic counters for:

- exact-primary candidates suppressed;
- fetch-deferred candidates;
- below-floor editorial events skipped;
- raw-fulltext cache hits;
- targeted INVALID repairs and repair-sidecar character savings.

These are avoided-work/cache proxies, not measured Codex billing.

## Next quality-neutral efficiency work

### Collection concurrency

Run independent collectors concurrently with bounded concurrency while preserving arXiv/request throttles and serializing persistence. This is wall-clock optimization only.

### More deterministic local transforms

Inspect production INVALID telemetry before expanding the targeted-repair allowlist. Only errors whose repair can be proven not to require new factual evidence should move to local or small-context repair paths.

## P1/P2: quality improvements requiring measured validation

### Relevance score decomposition

Return the rubric components instead of only one opaque 0-100 score:

- project relevance;
- technical novelty/substance;
- evidence specificity;
- actionability;
- freshness.

Use deterministic post-fact evidence metrics for final evidence quality instead of relying heavily on the fact Agent's self-rated `quality_score`. Avoid double-counting freshness/evidence between relevance and final ranking.

### Quality floor before diversity fairness

Diversity should operate among sufficiently strong candidates. Do not give a deep slot to a weak topic merely to make every topic appear in every issue. The exact floor should be chosen from production evaluation rather than guessed.

### Dynamic item-length budget

Keep an issue-level reading budget while allowing more space for evidence-dense papers and less for routine releases. Do not globally expand every item.

### Fixed primary-source coverage

Add deterministic high-quality sources for AI chips, DPU/CXL/optical topics (official engineering sources and major systems/hardware venues) before increasing generic web-search volume.

## P0 infrastructure before aggressive future cost changes

### Golden quality evaluation set

Build a small versioned corpus of representative sources with assertions such as:

- must capture mechanism X;
- must retain number Y with baseline/condition Z;
- must record limitation A;
- must not claim B;
- must resolve source identity correctly;
- must not merge event C with D.

Metrics should include mechanism recall, unsupported-claim rate, baseline/condition retention, boundary retention, source/locator validity and final fact-check corrections. Future changes to evidence size, deep budget or model calls should not merge unless they hold this baseline.

### Human edit telemetry

Where approval tooling permits, record structured differences between generated and approved content. A cost optimization that reduces Agent work but materially increases human correction is not a successful optimization.

## Architectural cleanup (later, separate PR)

The bootstrap currently composes many behavior wrappers/monkey patches and installation order matters. Once a Golden Eval exists, migrate behavior-preservingly toward explicit stages:

`Collector -> PrimarySourceResolver -> CandidatePlanner -> RelevanceReviewer -> DeepSelector -> DocumentStore -> EvidenceBuilder -> FactExtractor -> EventClusterer -> EditorialSelector -> Writer -> FactChecker -> IssueBuilder`

Do not mix this refactor with ranking/evidence-policy changes; first prove identical behavior on the Golden Eval.
