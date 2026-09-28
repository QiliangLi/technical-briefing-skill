# Design: arXiv outage web-search fallback

Date: 2026-09-24. Status: accepted for implementation.

## Problem

The arXiv export API can put the egress IP on a multi-day blocklist (observed
2026-09-23..25: 406 for every request, single-request/25-min grinds included).
When that happens both discovery channels through arXiv die: the live
direction queries in `ArxivCollector` and the 60-day backfill lanes. The
committed hardening (retry backoff, per-run circuit breaker, descriptive UA)
only degrades gracefully; it recovers nothing. In run 2026-09-23-105822 the
missed qualifying papers were only recovered through two ad-hoc manual
`agent_web_search` batches executed by the host Agent with its own web-search
capability — a path that existed in the task machinery but was never triggered
by channel failure.

The coverage-gap planner does not help on its own: coverage is proven by any
A-level raw row in the topic (GitHub releases, AI HOT promotions), so
arXiv-starved directions routinely count as "covered" and get no lane.

## Proposal

Productize the fallback that worked: when the arXiv lane ends a collect
circuit-broken, the discovery stage automatically plans one supplemental
`agent_web_search` batch targeting **channel-starved directions** — directions
that are normally fed by arXiv queries and whose topic received zero
arXiv-source A-level rows this run.

Mechanics:

1. `ArxivCollector` exposes `circuit_open` (set when the breaker opens).
   `CollectionService.collect` records `execution.arxiv_blocked` in
   `collection.json`.
2. New `plan_channel_starved_searches(pipeline)` in `discovery_stage.py`
   builds lanes for those directions (same search-dict shape as the gap
   planner, `search_reason: arXiv channel blocked this run`), ordered by
   topic priority, capped by a new setting
   `agent_web_search_outage_extra` (default 4). Because the blocked channel
   IS arXiv, the lanes scope the web search to paper venues via
   `ARXIV_OUTAGE_PREFERRED_DOMAINS` (arxiv.org first, then OpenReview,
   ACM DL, USENIX) instead of each topic's vendor-domain preferences.
3. The installed `prepare_agent_search` keeps its one-batch-per-run guard for
   normal runs, but creates the supplement batch when: a search batch already
   exists AND `arxiv_blocked` AND no `supplement_batch` task exists yet. The
   supplement batch is marked `metadata.supplement_batch` with the outage
   reason, so it is idempotent across resumes.
4. `SKILL.md` documents the provision: the per-issue open-web-search budget
   of 4 gains a bounded +4 outage allowance, used only for the supplemental
   batch and only when the arXiv circuit breaker opened that run.

Normal runs are unchanged: no flag, no extra lanes, no budget change.

## Alternatives considered

- Deterministic mirror collector (OpenAlex / Semantic Scholar) with the same
  query semantics: more robust than Agent search, but a new source with its
  own mapping and freshness semantics. Deferred; revisit if outages recur
  after this provision ships.
- Treating arXiv-blocked directions as coverage gaps in the existing planner:
  would silently change the coverage contract stated in SKILL.md; the
  explicit outage flag keeps the two notions separate.

## Risks

- The supplement lanes still require host-Agent execution (web search is not
  a Python collector); in unattended runs the task simply waits like any
  other Agent task.
- Lane quality depends on direction `queries[0]`; the batch stays within the
  existing schema and per-lane validation.
