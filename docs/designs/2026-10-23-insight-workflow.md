# Insight workflow: proposal board and keyword-driven insight reports

- Status: draft
- Created: 2026-10-23
- Last updated: 2026-10-23

## Problem and evidence

The repository has accumulated 25 archived briefings (`archive/issues/`, 2026-08-02 through 2026-10-23), a knowledge layer (graph, roadmaps, frontier clusters, ideas), and per-run Machine Items and facts in SQLite. Today these assets only feed the next briefing. Nothing turns them into retrospective, higher-altitude technical insight reports.

The user wants a living downstream system that follows briefing updates:

1. Topic proposals are maintained in the background and refreshed as each issue is archived; a personal-assistant interaction asks whether a proposal should proceed to a report, and a complete approval history (approved, approved-with-changes, rejected) is kept.
2. Given a keyword (or a selected proposal), the system first collects what the briefings already gathered on that keyword into a first-class evidence dossier.
3. Gaps in the dossier are filled automatically with material from outside the briefings, and the combined material flows straight into a draft insight report with no intermediate user gate.

## Goals and non-goals

Goals:

- A persistent proposal board with append-only lifecycle events, updated incrementally (waterline) after each archive publication, rendered as a gh-pages page for self-serve browsing.
- Assistant-style asks surfaced at natural session touchpoints, with the full approval record queryable from the board.
- A keyword pipeline: collect → gap analysis → bounded automatic external supplement → draft → deterministic citation validation → gh-pages preview → revision → publish.
- Insight reports live in a versioned `insights/` directory and are published to the gh-pages site.

Non-goals:

- No change to briefing task order, run lifecycle, send behavior, or knowledge backfill.
- No unattended publishing of insight reports; the preview checkpoint is the user gate.
- No email delivery of insights (may be revisited later).
- External supplement material does not automatically enter briefing caches or the knowledge graph; it stays inside the insight's own provenance scope.

## Constraints and invariants

- **Source-layer separation.** Briefing-sourced material and external supplement material are tagged as distinct source layers everywhere (dossier, draft citations, validation). They are never silently merged.
- **Citation integrity.** Every factual claim in a draft must resolve to (a) an archive issue + paper/item reference, (b) a supplement source record, or (c) a knowledge node. The validator enforces this deterministically; opinions are layered separately from facts, following the Machine Item / Reader Projection discipline.
- **Context boundaries.** Dossier assembly and citation validation are deterministic Python and never load all issues or full texts into one context. Semantic passes (gap analysis, supplement relevance, drafting) see only bounded, grouped evidence scoped to the keyword.
- **Consumer-only.** The insight layer reads archives, SQLite, and `knowledge/`; it does not mutate briefing state. Its own state lives under `insights/`.
- **Idempotent updates.** Proposal refresh is keyed by a waterline (last processed archived issue date); re-running after failure must not duplicate proposals or events.
- **Stable identity for supplements.** Supplement sources reuse the repository's URL canonicalization and arXiv version rules so the same external item cannot enter twice under two identities.
- **Publication scope.** gh-pages writing is limited to the site's insight routes and the already-authorized `preview/<run_id>/` path. No mail.

## Proposed design

### Directory and state layout

```text
insights/
  proposals.json          # proposal board: entries + append-only events
  <insight-id>/
    report.md             # final article (draft until published)
    metadata.json         # keyword, proposal lineage, status, waterline snapshot
    sources/
      dossier.json        # briefing-sourced evidence, grouped, with provenance
      gaps.json           # declared gaps after analysis
      supplement/*.json   # external material, source_layer=supplement
    citation-report.json  # validator output
```

`insights/` is a new top-level directory beside `knowledge/`, committed to `main`. Draft work-in-progress may temporarily live under `workspace/` and move into `insights/<id>/` at publish time; nothing under `insights/` is generated per-run by the briefing pipeline.

### Proposal board

Schema (summary):

```json
{
  "proposal_id": "...",
  "title": "...",
  "keywords": ["..."],
  "evidence": {
    "issue_refs": ["2026-10-14", "..."],
    "knowledge_refs": ["roadmap:agent_acceleration", "cluster:..."],
    "recurrence": {"first_seen": "...", "latest": "...", "issue_count": 3}
  },
  "status": "proposed|asked|approved|approved_with_changes|rejected|in_progress|published|superseded",
  "lineage": {"supersedes": "proposal_id", "recurred_from": "proposal_id"},
  "events": [
    {"ts": "...", "actor": "system|user", "action": "proposed|asked|approved|approved_with_changes|rejected|published", "note": "..."}
  }
}
```

- **Update pass.** After each archive publication, a two-part pass runs: deterministic aggregation produces raw signals from the newly archived issue (cross-issue topic recurrence, frontier-cluster movement, roadmap gaps); a bounded Agent task converts signals into 2–4 phrased proposals, deduplicated against the existing board. Identity keys must be evidence-supported, and a topic that was rejected earlier and recurs gets a new proposal linked via `recurred_from`, never a silent re-date.
- **Asking.** The board tracks pending asks (`status=asked`). Asks are surfaced at two touchpoints: the briefing run handoff (the same session that archived the issue reports new proposals and asks) and the start of any later session in this workspace, which checks the board first. There is no outbound push channel (no Feishu, no email); the gh-pages board page is the always-available self-serve view. This is the environment-bounded interpretation of "ask me like a personal assistant" and is stated here deliberately.
- **Approval record.** The `events` list is the audit trail. Approve-with-changes records the user's modification notes; rejections may record an optional reason. The board page renders the full history (approved / modified / rejected).

### Keyword pipeline

1. **Collect** (deterministic). `insight collect --keyword` queries `archive/issues/*/papers.json` + `issue.json`, SQLite Machine Items and facts, and `knowledge/` (graph, roadmaps, frontier clusters), and emits `dossier.json`: material grouped by theme and timeline, every item carrying provenance (issue date, paper/item ID, knowledge node).
2. **Gap analysis** (bounded Agent). Reads only `dossier.json` and the keyword; writes `gaps.json` — questions the existing briefings cannot answer, each gap tied to the themes it belongs to.
3. **Supplement** (deterministic fetch + bounded relevance pass). External fetch for declared gaps, reusing existing collectors (arXiv via the requests + Atom Accept transport; web fallback per the 2026-09-24 design). Bounds (max sources per gap, per run) come from `config/`. Every accepted item is tagged `source_layer=supplement` with stable identity. Automatic; no user gate.
4. **Draft** (bounded Agent). Writes `report.md` from dossier + supplement, separating facts (cited) from interpretation (labeled), citing inline in machine-checkable form (`[issue:2026-09-14#paper:...]`, `[supplement:src_id]`, `[knowledge:node_id]`).
5. **Validate** (deterministic). `insight validate` resolves every citation against the two source layers and the knowledge graph, flags uncited factual claims and layer violations, and writes `citation-report.json`. Failures loop back to drafting (bounded repair rounds), mirroring the INVALID/repair loop of briefing runs.
6. **Preview.** The draft renders to a gh-pages preview page under the standing preview authorization; the user reviews there.
7. **Revise & publish.** User feedback drives revision rounds (amended workflow or direct edits, re-validated). On approval: move/commit `insights/<id>/` to `main`, build the insight's site page and update the site index, mark the proposal `published`.

### Orchestration

- The proposal update pass is the final post-archive wave of the briefing-run ZCode workflow; it commits under normal change governance and reports in the handoff, which is also ask touchpoint #1.
- The keyword pipeline is a saved ZCode workflow (`insight-report`) taking `keyword` (or `proposal_id`) as an argument, with waves mapping to the steps above.
- A session-start catch-up may run the update pass if the waterline lags (for example the briefing workflow could not run its final wave).

## Compatibility and migration

- No schema, table, or task-envelope changes for briefings. Insight state is files under `insights/`; SQLite involvement is read-only.
- The gh-pages site gains routes for the board and published reports, following the existing static-site data-contract pattern; existing routes are untouched.
- `knowledge/` and `archive/` are read-only inputs; no backfill or re-materialization is triggered by insight runs.
- Nothing migrates on day one: `insights/` starts empty, waterline starts at the latest archived issue.

## Failure, recovery, and rollback

- Proposal update failures leave the waterline untouched; a retry reprocesses the same issue idempotently.
- An in-progress keyword run is fully reconstructible from `insights/<id>/` artifacts; a broken run can be deleted and restarted without side effects outside that directory.
- Supplement fetch failures degrade gracefully: the draft proceeds from dossier-only evidence and must declare the unfilled gaps in `gaps.json` and the report.
- Publish is a commit + site rebuild; rollback is a revert commit. There is no mail step, so no resend risk.

## Verification

- Unit tests with fixture archives for: dossier builder queries and grouping, supplement identity/dedup and layer tagging, citation validator resolution and failure modes, proposals board event append and idempotent waterline advance.
- An integration run of `insight collect` + `validate` against the real archive with one sample keyword.
- gh-pages checks: board page renders history correctly; report page builds; preview path isolation.
- The proposal update pass run twice over the same issue must produce a byte-stable board delta (no duplicate events).

## Documentation impact

At implementation time: `docs/architecture.md` (new downstream layer), a new `docs/operations/insight-workflow.md`, a new contract for insight artifacts and the proposals board under `docs/contracts/`, `README.md` (user-facing workflow), `SKILL.md` (session-start pending-ask check and the handoff ask rule), `config/` (supplement bounds, proposal limits), and the site's build/data docs.

## Decision log

- 2026-10-23 — User clarified the three capabilities (background proposals, keyword collection dossier, automatic external supplement) in conversation; earlier draft framing of "no external material" was withdrawn.
- 2026-10-23 — User decision: proposal updates run in the background following archive publication; asks are assistant-style at session touchpoints with a complete approval history; no outbound push channel is in scope.
- 2026-10-23 — User decision: external supplement is automatic with no intermediate gate; the preview page is the single user checkpoint before publish.
- 2026-10-23 — User decision: finished reports live in `insights/` on `main` and are published to the gh-pages site.
