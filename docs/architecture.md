# Architecture

Technical Briefing Skill turns a large stream of public technical material into an internal briefing that can support engineering decisions. The system favors primary evidence, project relevance, stable identity, and recoverable execution over raw news volume.

## System boundary

Python owns deterministic work and durable state. It collects sources, normalizes identities, filters candidates, builds evidence, schedules tasks, validates outputs, renders email, sends mail, and publishes archives.

The current Agent owns bounded semantic work. It reviews relevance, extracts facts from the supplied evidence, repairs one declared evidence gap when allowed, writes Machine Items, checks risky claims, produces the run-scoped Reader Projection, synthesizes the issue, and plans explanatory illustrations.

The implementation does not bind a model API. The host executes the task files emitted by the CLI.

## Pipeline

```text
current collection + resumable historical backfill
→ stable identity, source grading, cross-run deduplication
→ batched relevance and technology-value review
→ topic-local deep selection + short appendix + Radar
→ primary full text and bounded Evidence Pack
→ facts cache or independent fact extraction
→ optional one-pass targeted evidence repair
→ Machine Item draft
→ deterministic Evidence Gate
→ selective Fact Check for risky items
→ run-scoped Reader Projection
→ issue synthesis
→ illustrated publication
→ email.html + email-illustrated.html
→ validation
→ confirmed send
→ archive and publication
```

Current limits and topic membership live in `config/settings.yaml` and `config/topics*.yaml`. Documents should describe the policy and link to configuration rather than duplicate every changing value.

## Data and state

SQLite stores runs, source state, candidates, tasks, facts, events, issue items, publication history, and usage records. Run-specific files live under `workspace/runs/<run_id>/`; cross-run caches and historical backfill state live in their dedicated workspace locations.

Task outputs are schema-bound files. `advance` applies them to the active run and records the applied state. Re-running `advance`, rendering, resume, or publication retry must not duplicate content or borrow an output from another run.

Stable source identity and cache identity are different. Publication deduplication may treat arXiv revisions as the same event while the relevance and facts caches still require an exact version and evaluator or extractor match.

## Evidence boundary

Relevance tasks see compact topic context and candidate metadata, not full text. Fact extraction sees one source's Evidence Pack. A repair task sees structured old facts and one targeted supplement. Downstream writing consumes structured facts instead of reopening documents.

These boundaries are part of correctness. Shared Agent sessions may reduce startup overhead, but they cannot merge evidence, outputs, schemas, caches, or provenance across sources.

## Machine and reader layers

Machine Items are the durable fact model used by Evidence Gate, Fact Check, Roadmap, Idea analysis, and later simulations. Reader Projection is created once per active run after the machine layer passes its checks. It can omit or reorder material for readability, but it cannot add facts or become a cross-run cache.

## Publication boundary

Rendering always produces `email.html` and `email-illustrated.html`. The illustrated version adds explanatory images without changing the text. Recipient-visible images must use stable absolute publication URLs before send and archive.

Validation promotes an issue to `READY_TO_SEND`. Sending requires explicit user confirmation. Mail transport and archive publication have separate success states so a publication retry cannot resend the email.

## Knowledge graph publication

The public site's knowledge graph is a derived, regenerable artifact, never an authoritative knowledge source:

```text
archive/index.json + archive/issues/<date>/{issue,papers}.json
knowledge/index.json + roadmaps/*.json + ideas/*.json
→ Graph Builder (briefing_skill/knowledge_graph.py, NetworkX-validated)
→ knowledge/graph.json (deterministic nodes/edges/coordinates, dual watermarks)
→ static site (#knowledge route: data-contract.js filtered model
   → knowledge-layout.js per-lens local layout → Cytoscape.js renderer)
```

The builder reads only those authoritative inputs, derives edges only from explicit fields, and reports unresolvable references in an `unresolved` list instead of drawing them. `knowledge/graph.json` carries separate `archive_through_issue` and `knowledge_through_issue` watermarks because the archive and materialized knowledge can lag each other. The Pages workflow rebuilds and validates the graph before assembling the site, so a graph that does not match current inputs blocks publication rather than shipping stale.

Freshness is stated, not implied. After the graph gates, the same workflow rebuilds and validates `knowledge/manifest.json` (`briefing_skill/knowledge_publication.py`) and validates the per-issue projections under `knowledge/issue-diffs/`. The manifest records the archive head, the materialization watermark, the analysis target, and a `publication_state` (`archive_only` → `analysis_pending` → `knowledge_complete`, plus operator-marked `analysis_failed`); the issue diffs bind homepage "current judgement" text to applied tasks, published evidence, and the graph snapshot id. A manifest claiming `knowledge_complete` while watermarks lag, the graph is stale, or the head issue's diff is missing fails publication; pending states publish with an explicit pending notice, and the homepage renders the projections as-is instead of repackaging old Roadmap summaries as this issue's change. See `docs/contracts/knowledge-materialization.md` and `docs/contracts/editorial-workbench-ui.md`.

## Where details live

- Operational behavior is documented in `docs/operations/`.
- Data, writing, evidence, and publication contracts are documented in `docs/contracts/`.
- Dated plans and reviews are kept in `docs/history/` and are not authoritative.
