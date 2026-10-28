# Insight repository: proposal board and keyword-driven insight reports

- Status: draft
- Created: 2026-10-23
- Last updated: 2026-10-26

> This document is drafted inside the briefing repository and will move to the new insight repository as its initial design when that repository is created (user direction, 2026-10-23).

## Problem and evidence

The briefing repository has accumulated 25 archived briefings (`archive/issues/`, 2026-08-02 through 2026-10-23), a knowledge layer (graph, roadmaps, frontier clusters, ideas), and a published gh-pages site. Today these assets only feed the next briefing. Nothing turns them into retrospective, higher-altitude technical insight reports.

The user wants a living downstream system that follows briefing updates:

1. Topic proposals are maintained in the background and refreshed as issues are archived; a personal-assistant interaction asks whether a proposal should proceed to a report, and a complete approval history (approved, approved-with-changes, rejected) is kept.
2. Given a keyword (or a selected proposal), the system first collects what the briefings already gathered on that keyword into a first-class evidence dossier.
3. Gaps in the dossier are filled automatically with material from outside the briefings, and the combined material flows straight into a draft insight report with no intermediate user gate.

**Home: a separate repository.** The two systems intersect only at published artifacts (user direction, 2026-10-23). Verified evidence: each archived issue's `issue.json` (~74 KB) carries the full structured fact layer — 12 core items, 26 items, 14 observations, each with `core_conclusion / mechanism / result / boundary / project_relevance / keywords` — plus dense written synthesis judgements with evidence IDs and `watch_next`; `papers.json` adds per-paper metadata (topic, direction, role, score, source level); `knowledge/` adds cross-run structures. The dossier needs nothing from the briefing repository's SQLite database, run directories, or workspace state, so a clean artifact-only boundary exists.

## Goals and non-goals

Goals:

- A new standalone insight repository consuming only published briefing artifacts (`archive/`, `knowledge/`), with its own state, its own gh-pages site, and zero code dependency on the briefing repository.
- A persistent proposal board with append-only lifecycle events, updated incrementally (waterline) as new issues appear, rendered as a site page for self-serve browsing.
- Assistant-style asks surfaced at session touchpoints in the insight repository, with the full approval record queryable from the board.
- A keyword pipeline: sync → collect → gap analysis → bounded automatic external supplement → draft → deterministic citation validation → preview → revision → publish.

Non-goals:

- No change to briefing task order, run lifecycle, send behavior, knowledge backfill, or briefing repo code (an advisory note about the external consumer is the only briefing-repo touch).
- No unattended publishing of insight reports; the preview checkpoint is the user gate.
- No email delivery of insights and no multi-platform self-media distribution (may be revisited later).

## Constraints and invariants

- **Published-artifact-only boundary.** The insight repository reads `archive/issues/<date>/{issue,papers}.json`, `archive/index.json`, and `knowledge/*.json` from a local synced copy of the briefing repository. It never reads the briefing SQLite database, run directories, or workspace state, and never writes to the briefing repository.
- **Immutable snapshots.** Sync materializes new issues into checksummed, append-only snapshots; semantic passes see snapshots only, never live checkout state. Issue snapshots never change once written; the knowledge layer syncs to latest with a checksum in the sync manifest.
- **Source-layer separation.** Briefing-sourced material and external supplement material are tagged as distinct source layers everywhere (dossier, draft citations, validation). They are never silently merged.
- **Citation integrity.** Every factual claim in a draft must resolve to (a) an issue snapshot + item reference, (b) a supplement source record, or (c) a knowledge node. The validator enforces this deterministically; opinions are layered separately from facts.
- **Context boundaries.** Dossier assembly, sync, and citation validation are deterministic Python and never load all issues into one context. Semantic passes (gap analysis, supplement relevance, drafting) see only bounded, grouped evidence scoped to the keyword.
- **Idempotent updates.** Proposal refresh is keyed by a waterline (last synced issue date); re-running after failure must not duplicate proposals or events.
- **Stable identity for supplements.** Supplement sources use URL canonicalization and arXiv version rules so the same external item cannot enter twice under two identities.
- **Publication scope.** The insight repository publishes to its own gh-pages site; no mail.

## Proposed design

### Repository topology and sync layer

```text
briefing repository (read-only source of truth)
  archive/issues/<date>/{issue,papers}.json   archive/index.json   knowledge/*.json
        │  git fetch (scheduled or session-start)
        ▼
insight repository
  snapshots/issues/<date>/{issue,papers,sources}.json   # immutable, checksummed
  snapshots/knowledge/                                  # synced to latest, checksummed
  snapshots/manifest.json                               # waterline + checksums
  proposals.json                                        # proposal board + events
  insights/<insight-id>/report.md, metadata.json, sources/{dossier,gaps,supplement}, citation-report.json
```

- `insight sync` fetches the configured briefing-repo remote, compares `archive/index.json` against the waterline, copies new issues into immutable snapshots, refreshes `snapshots/knowledge/`, and records checksums. Failure leaves the waterline untouched; a retry is idempotent.
- Triggers: a scheduled automation in the insight workspace (primary), a session-start catch-up when the waterline lags (fallback). A GitHub Actions cron with a cross-repo checkout token is a documented alternative for laptop-independent scheduling; decided at implementation.
- The consumed file list is the contract. The briefing repository's contracts documentation gains one advisory line: these artifacts have an external consumer; format changes should consider it.

### Proposal board

Schema (summary):

```json
{
  "proposal_id": "...",
  "title": "...",
  "angle": "...",
  "outline_sketch": ["..."],
  "keywords": ["..."],
  "evidence": {
    "issue_refs": ["2026-10-14"],
    "knowledge_refs": ["roadmap:agent_acceleration"],
    "density": {"have": "3 issues, 7 items, 2 roadmap nodes", "supplement_need": "low|medium|high"},
    "recurrence": {"first_seen": "...", "latest": "...", "issue_count": 3}
  },
  "status": "proposed|asked|approved|approved_with_changes|rejected|in_progress|published|superseded",
  "lineage": {"supersedes": "proposal_id", "recurred_from": "proposal_id"},
  "events": [
    {"ts": "...", "actor": "system|user", "action": "proposed|asked|approved|approved_with_changes|rejected|published", "note": "..."}
  ]
}
```

- Each batch offers 3–4 proposals. The fields beyond the title (angle, outline sketch, evidence density) exist so the user can judge a direction before any writing happens; evidence density states what the briefings already hold versus how much supplementing a report would need.
- **Update pass.** After each sync that advances the waterline: deterministic aggregation produces raw signals from the new issue snapshot — cross-issue topic recurrence, emergence/acceleration statistics computed directly from the existing `topic_id`, `direction_id`, and `keywords` fields over time, frontier-cluster movement, roadmap gaps, and cross-issue contradictions (a new item's `result` or `boundary` conflicting with an earlier issue's claim); a bounded Agent task converts signals into 2–4 phrased proposals, deduplicated against the existing board and novelty-checked against already-published reports. Identity keys must be evidence-supported; a rejected topic that recurs gets a new proposal linked via `recurred_from`, never a silent re-date.
- **Asking.** The board tracks pending asks (`status=asked`). Asks surface at two touchpoints: the sync/update handoff in the session where the update ran, and the start of any later session in the insight workspace. There is no outbound push channel (no Feishu, no email); the board page is the always-available self-serve view.
- **Approval record.** The `events` list is the audit trail. Approve-with-changes records the user's modification notes; rejections may record an optional reason. The board page renders the full history (approved / modified / rejected).

### Keyword pipeline

1. **Collect** (deterministic). `insight collect --keyword` queries the issue snapshots and knowledge snapshot, and emits `dossier.json`: material grouped by theme and timeline, every item carrying provenance (issue date, item/paper ID, knowledge node).
2. **Gap analysis** (bounded Agent). Enumerate the questions a reader of this report would need answered, check dossier coverage per question, and write `gaps.json` — unanswered questions, each tied to the themes it belongs to.
3. **Supplement** (deterministic fetch + bounded relevance pass). External fetch for declared gaps, reusing the briefing stack's proven fetch patterns (arXiv via requests + Atom Accept transport; web fallback). Bounds (max sources per gap, per run) come from config. Every accepted item is tagged `source_layer=supplement` with stable identity. Automatic; no user gate.
4. **Draft** (bounded Agent). Outline first, then prose. Writes `report.md` from dossier + supplement, separating facts (cited) from interpretation (labeled), citing inline in machine-checkable form (`[issue:2026-09-14#item:...]`, `[supplement:src_id]`, `[knowledge:node_id]`). Cross-issue contradictions found during collection are surfaced explicitly with their resolution status, never smoothed over.
5. **Validate** (deterministic). `insight validate` resolves every citation against the two source layers and the knowledge snapshot, flags uncited factual claims and layer violations, and writes `citation-report.json`. Failures loop back to drafting in bounded repair rounds.
6. **Preview.** The draft renders to a preview page on the insight site; the user reviews there. This is the single user gate.
7. **Revise & publish.** User feedback drives revision rounds (re-validated each round), collected as margin comments on the preview page where feasible; revision history is distilled into user-editable drafting habits applied to future reports. On approval: commit `insights/<id>/`, build the report page and update the site index via a deterministic publisher, mark the proposal `published`.

### Orchestration

- The keyword pipeline is a saved ZCode workflow (`insight-report`) taking `keyword` (or `proposal_id`) as an argument, with waves mapping to the steps above.
- The sync + proposal update pass is a second saved workflow or automation script, runnable on schedule and on demand.

## Prior art

Reviewed 2026-10-23 and 2026-10-26. This section is corroboration, not a dependency: no external code is reused, and because the field moves fast, repository age was checked explicitly (last-push dates as of 2026-10-26).

- **Primary reference: the briefing repository itself.** Task envelopes with schemas and semantic validators, evidence boundaries, the deterministic Evidence Gate, INVALID/repair loops, and ZCode workflow waves are proven across 25 published issues against this exact data and the user's own quality bar. The insight repository copies this architecture; everything below is secondary.
- **Current paradigm: deep-research agents.** bytedance/deer-flow (84k stars, pushed 2026-10-26), huggingface/smolagents (30k, 2026-10-22), and langchain-ai/open_deep_research (12.7k, 2026-08) share a planner → tool-using researcher → reporter shape with cited output. The insight pipeline has the same shape with the web tools swapped for corpus tools (snapshot queries) plus a bounded external fetch. assafelovic/gpt-researcher (30k, pushed 2026-10-10) is the closest in shape: its `report_source=local` mode researches over a `DOC_PATH` document folder and a hybrid mode combines local documents with web research — the same local-corpus-plus-supplement structure as this pipeline. How its reports distinguish local from web citations should be checked at implementation, since source-layer separation is a hard invariant here.
- **Corpus-grounded cited synthesis.** Future-House/paper-qa (9.5k, pushed 2026-10-26) is actively maintained: scored, bounded evidence gathering over a private document set with citations, plus contradiction search across documents. It corroborates the dossier loop and the cross-issue contradiction signal.
- **Interaction layer: garycaogan/content-workbench** (github.com/garycaogan/content-workbench, ~50 stars, created 2026-10-14, pushed 2026-10-16) — a personal content workbench: material → candidate topics each carrying the author's verbatim quotes → style-constrained drafting → margin-comment revision with one-click apply → one-click push that stops at draft boxes. It matches this design's interaction model closely (evidence-attached proposals, AI adds no facts, human presses publish) and contributes two concrete patterns: margin-comment revision on the preview page (sharper than conversational feedback) and edit-habit learning (revisions logged, distilled into explicit user-editable drafting habits). It does not match the core problem — its corpus is the author's own words (first-person mining, no external supplement) rather than accumulated third-party technical evidence needing cross-issue synthesis — and its distribution targets are out of scope. It supersedes article-writer as the interaction reference.
- **Reviewed and set aside as stale.** AutoSurvey (last push 2025-02), ResearchAgent (2025-08), STORM (2025-09), article-writer (2025-11), AI-Scientist (2025-12), SurveyX (2026-01): their multi-stage scaffolds (chunked parallel section writing, simulated multi-perspective dialogue) largely compensated for 2024-era context and coherence limits and are not adopted as design steps. The model-independent invariants they also embody — citation-per-claim verification, novelty bookkeeping against published work, a human selection gate — are stated in this design on its own terms. Topic-modeling tools (BERTopic, BERTrend) are unnecessary here because items already carry `topic_id`, `direction_id`, and `keywords`, so trend statistics are direct counts. Daily aggregation digests (for example elbruno/weekly-ai-news-digest) are the briefing pipeline's own category and were excluded.

## Compatibility and migration

- The briefing repository changes not at all (advisory contract note aside). The insight repository starts empty: initial `insight sync` backfills snapshots for all 25 archived issues and sets the waterline.
- The insight site is independent; cross-linking from the briefing site is a later option, not a dependency.
- When the insight repository is created, this document moves there and becomes its initial design; the briefing repository records the move in its decision log.

## Failure, recovery, and rollback

- Sync failures (briefing repo unreachable, partial fetch) leave the waterline untouched; retry is idempotent. The system degrades to stale snapshots with a visible lag indicator.
- An in-progress keyword run is fully reconstructible from `insights/<id>/` artifacts; a broken run can be deleted and restarted without side effects outside that directory.
- Supplement fetch failures degrade gracefully: the draft proceeds from dossier-only evidence and must declare unfilled gaps in `gaps.json` and the report.
- Publish is a commit + site rebuild; rollback is a revert commit. There is no mail step, so no resend risk.

## Verification

- Unit tests with fixture snapshots for: sync waterline advance and checksum stability, dossier builder queries and grouping, supplement identity/dedup and layer tagging, citation validator resolution and failure modes, proposals board event append and idempotent update.
- An integration run of `insight sync` + `collect` + `validate` against the real 25-issue archive with one sample keyword.
- Site checks: board page renders history correctly; report page builds; preview isolation.
- The proposal update pass run twice over the same synced issue must produce a byte-stable board delta (no duplicate events).

## Documentation impact

In the insight repository (when created): its own README, operations doc, and artifact contract derived from this design. In the briefing repository: one advisory line in the relevant contracts document noting the external consumer of `archive/issues/` and `knowledge/` formats, plus the decision-log entry when this document moves.

## Decision log

- 2026-10-23 — User clarified the three capabilities (background proposals, keyword collection dossier, automatic external supplement); an earlier "no external material" framing was withdrawn.
- 2026-10-23 — User decision: proposal updates run in the background following archive publication; asks are assistant-style at session touchpoints with a complete approval history; no outbound push channel is in scope.
- 2026-10-23 — User decision: external supplement is automatic with no intermediate gate; the preview page is the single user checkpoint before publish.
- 2026-10-23 — User decision: finished reports are published artifacts (versioned directory + site).
- 2026-10-23 — User direction: implement as a separate repository because the systems intersect only at published artifacts. Artifact richness verified (`issue.json` structured fact layer; no SQLite dependency). Design updated to the separate-repo topology; this document will move to the new repository as its initial design.
- 2026-10-23 — Related-work survey completed; borrow list recorded (article-writer, elbruno digest, STORM, gpt-researcher, Easel/AIWriteX) with explicit not-adopted items.
- 2026-10-23 — Related-work list re-centered after user review: the aggregation digest (elbruno) was a category mismatch and is now listed as excluded; corpus-synthesis (SurveyX/AutoSurvey, PaperQA2), idea-generation (AI-Scientist, ResearchAgent), and temporal weak-signal (BERTopic/BERTrend) references added. Cross-issue contradiction detection, novelty check against published reports, and emergence classification were added to the proposal signals as a result.
- 2026-10-26 — User challenged reference freshness. Last-push dates checked: six of ten surveyed repositories had not been pushed in 9–20 months, and their multi-stage scaffolds were judged compensations for 2024-era model limits. Prior-art section slimmed to dated corroboration; the briefing repository's own mechanics named as the primary reference; current deep-research agents (deer-flow, smolagents, open_deep_research) added as the paradigm reference; repository attributions removed from design steps; topic-modeling tools dropped in favor of direct statistics over existing fields.
- 2026-10-26 — User asked whether garycaogan/content-workbench fits. Assessed: strong fit for the interaction layer (evidence-attached topic selection, margin-comment revision, edit-habit learning, publish stops at draft boxes), opposite direction for the core problem (first-person verbatim mining, no external supplement, no longitudinal archive machinery). Added as the interaction-layer reference, superseding article-writer; margin comments and habit learning written into the revise step.
