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

Implemented in this change:

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

## P1: quality-neutral efficiency work after #12

These should reduce wasted work without reducing evidence or editorial quality.

### INVALID targeted repair

Current generic reopen can cause a whole task to be repeated even for transport/schema/format failures. Split retries:

- transport / `_task` / missing field / JSON / sentence-ending errors -> previous output + exact validator errors + schema only;
- factual/evidence errors -> original evidence or a targeted evidence repair;
- cap attempts, then require human inspection rather than looping indefinitely.

### Fetch failure gate

If primary full-text retrieval ends in `FALLBACK`, do not spend a deep fact task on a summary that cannot satisfy `primary_source_resolved`.

- deterministic retry / alternate PDF URL first;
- otherwise mark `DEFERRED_FETCH` and try a later run;
- keep the discovery signal in Radar/appendix if useful.

### Pre-editorial deterministic score gate

After facts/event scoring, events that are deterministically below the minimum observation threshold cannot be rescued by writing because score is immutable.

- skip item-writing and fact-check tasks for those events;
- retain them as deferred/appendix candidates when appropriate.

### Exact cross-source primary dedup

Before relevance review, combine only exact primary identities:

- same arXiv ID/version;
- same DOI;
- same GitHub release/tag/commit;
- same canonical primary URL.

Keep all `discovered_via` provenance and never use fuzzy dedup at this stage.

### Raw full-text cache

Cache normalized fetched PDF/HTML text by immutable source fingerprint separately from facts.

- project-context or fact-prompt changes can rebuild front evidence/facts without another HTTP download/PDF parse;
- mutable web pages remain revalidated.

### Collection concurrency

Run independent collectors concurrently with bounded concurrency while preserving arXiv/request throttles and serializing persistence. This is wall-clock optimization only.

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
