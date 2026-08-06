# Low-token dual-channel execution design

## Goal

Reduce end-to-end Agent time and subscription usage without lowering four quality bars:

1. important-event recall;
2. factual accuracy and primary-source provenance;
3. Chinese readability;
4. coverage of deep topics plus AI Infra, Agent, KVCache, and storage-media signals.

## Implemented architecture

```text
Fixed feeds and aggregators
        |
        +-- Deep channel
        |     resolved A-level sources only
        |     deterministic accept/reject
        |     batched review for ambiguous items
        |     per-topic fact budget
        |     existing fact extraction -> writing -> fact check
        |
        +-- Radar channel
              discovery-only/B-level/horizontal signals
              no full-text extraction by default
              AI Infra / Agent ecosystem / KVCache ecosystem / storage media
              cross-source and cross-issue deduplication
```

## Implemented changes

### Gap-driven open search

`prepare_agent_search` first checks whether fixed sources already cover each deep direction. Only a resolved, non-discovery A-level URL counts as coverage. A Follow Builders, YeeKal, AI HOT, or other B-level clue therefore cannot suppress primary-source search. The pipeline creates at most four searches, only for the highest-priority uncovered directions. `ai_infra_horizontal` is supplied by the broad Radar and no longer creates one open-search task for every sub-direction.

### Batched relevance

Candidates are separated conservatively:

- resolved A-level candidates with a rule score of at least 85 are accepted without another model call;
- candidates below 15 are rejected deterministically;
- discovery-only, B/C, and non-promoted horizontal candidates go to Radar;
- only ambiguous A-level candidates create `relevance_batch` tasks, grouped by topic and capped at 12 candidates per task.

The batch prompt still judges every candidate independently and requires `fulltext_required=true` before a candidate can enter the deep channel. Semantic validation rejects missing, duplicate, or unknown candidate IDs, so batching cannot silently drop an item.

### Deep-analysis budget

Before full-text extraction, candidates are ranked by relevance score, rule score, source priority, and topic diversity. At most ten candidates and three per topic are processed deeply. Deferred candidates remain in SQLite with `DEFERRED_BUDGET`; they are not deleted and can be reconsidered after configuration changes.

### Broad Radar

The existing email Radar now reads all current-run raw sources instead of only AI HOT. It classifies technical signals into:

- AI Infra;
- Agent ecosystem;
- KVCache ecosystem;
- storage and media.

Generic model and business news is excluded. Radar items reuse the existing cross-issue history and issue-level deduplication and do not create full-text, writing, or fact-check tasks.

### Compatibility

The database schema, fact extraction, item writing, fact checking, synthesis, rendering, review, and email flow remain unchanged. `briefing_skill.bootstrap` installs the efficiency policy and primary-source quality guards before entering the existing CLI, so both `python briefing.py` and the installed `technical-briefing` command use the optimized path.

## Validation

Automated tests cover:

- deterministic accept/reject/Radar routing;
- horizontal promotion threshold;
- topic-diverse deep budgets;
- resolved A-level coverage detection before web search;
- exact input/output integrity for relevance batches;
- all four requested Radar categories;
- representative task-count reduction;
- the existing full offline Demo and renderer validation.

The representative estimator uses the shape of the previous run: 18 open searches, 100 relevance candidates, 17 fact extractions, 17 item drafts, and 17 fact checks. With 36 ambiguous candidates, batch size 12, a ten-item fact budget, and four gap searches, planned Agent tasks fall from 169 to 37, a 78.1% reduction.

This is a deterministic task-count estimate, not a measured Codex token bill. The final GitHub Actions run installed the package, compiled the Python tree, completed the full Demo with no renderer validation failures, and passed 66 tests.

## Rollout guardrails

Run the old and new selectors against the same collected data for two or three issues. Keep the policy enabled only when:

- every manually mandatory event remains in either the deep channel or Radar;
- no unsupported number or causal claim is introduced;
- topic coverage is not narrower;
- manual edits do not increase;
- Agent task count drops by at least 60%.
