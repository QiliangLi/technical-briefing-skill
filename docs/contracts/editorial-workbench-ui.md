# Editorial workbench UI contract

The public GitHub Pages surface is a read-only editorial workbench implemented with static HTML, CSS, and JavaScript under `site/`. It reads published archive data and materialized knowledge objects; it does not write back to either source.

## Routes and page ownership

The primary Hash routes are:

- `#home`: current issue changes, Idea updates, and visible risks;
- `#roadmaps?topic=<topic_id>&branch=<branch_id>`: one materialized Roadmap and its evidence boundary;
- `#ideas`: Candidate, Portfolio, and Validation collections kept visually and structurally separate;
- `#ideas?idea=<idea_id>`: one materialized Idea, its decision history, evidence summary, and validation suggestion;
- `#evidence?idea=<idea_id>&view=path&task=<task>`: the default readable Evidence Path; omitting `view` remains equivalent to `path`;
- `#evidence?idea=<idea_id>&view=graph&node=<node_id>&depth=<1|2>&candidates=<0|1>`: a deterministic projection of explicit Evidence relationships with synchronized node detail and relationship list;
- `#evidence?idea=<idea_id>&view=gaps&task=<task>`: evidence gaps taken from the selected Idea's recorded unknowns;
- `#evidence?view=atlas&scope=<all|latest>&mode=<topic|keyword>&issue=<issue_date>&topic=<topic_id>`: an Archive Atlas whose connections express archive containment only;
- `#archive?date=<issue_date>`: one published issue and its derived long-term impact.

The legacy `#graph` and `#atlas` routes preserve their query parameters and normalize to the corresponding `graph` and `atlas` Evidence subviews. Invalid graph depth falls back to one hop, candidates default off, and invalid view names fall back to `path`. The public feature-plan route remains available at `#features`, but it is not a primary navigation item.

## File boundaries

- `site/index.html` owns the shared shell, navigation, search Dialog, and accessible page root.
- `site/app.js` owns archive and knowledge loading, route orchestration, local-preview path fallback, search indexing, and passing the complete read-only Archive/Knowledge context into Evidence views.
- `site/workbench-view.js` owns the four Evidence tabs, path/gap/graph/atlas view orchestration, shared detail rendering, relationship-list rendering, and URL synchronization.
- `site/data-contract.js` owns dependency-free data normalization, route parsing, stable graph IDs, `buildEvidenceGraphModel()`, and `buildArchiveAtlasModel()`.
- `site/evidence-graph.js` owns deterministic Evidence/Atlas layout, DOM/SVG mounting, selection, keyboard traversal, pan/zoom, fit, and minimap behavior. It does not read source JSON or infer relationships.
- `site/evidence-graph.css` owns graph/atlas geometry, node and relation visuals, graph-only responsive behavior, and the mobile Evidence Path. It does not override unrelated pages.
- `site/editorial-tokens.css` owns palette, typography, spacing, elevation, and z-index tokens.
- `site/editorial-components.css` owns the shared shell and component system.
- `site/editorial-pages.css` owns only page-level grids and breakpoint reflow.
- `site/assets/brand-mark.svg` and `site/assets/icons.svg` are fixed, committed assets; Evidence node/filter symbols use the same monochrome sprite. Runtime image generation is prohibited.

The previous `styles.css`, `workbench-overrides.css`, `intelligence-lab.css`, and Atlas files remain unreferenced rollback assets until a later cleanup explicitly removes them.

## Data and evidence boundary

- Archive pages consume published archive JSON and Reader sidecars.
- Roadmap and Idea pages consume only `knowledge/index.json` and the materialized object files named by it.
- Components receive display models; they do not infer business meaning from missing fields.
- Missing optional fields remove their row or section. Empty collections render an explanation and the next truthful state.
- Candidate records are never derived from formal Idea records. When no public Candidate collection exists, the Candidate Inbox is an explicit empty state.
- Validation suggestions must say that they are not executed experiments. Full Plan, Run, and Result surfaces appear only when source state says the Idea entered Validation.
- Evidence relationships must resolve to an existing item or remain visibly unresolved. The UI does not draw an unsupported edge.
- Source-to-evidence links come only from published Archive objects and their public URLs. Evidence-to-Idea links come only from `evidence_for` and `evidence_against`; Evidence-to-Roadmap links come only from branch `evidence_item_ids` or evidence timeline references.
- Assumption nodes are read-only projections of an Idea's `unknowns` or `hypothesis` and always say that they came from an Idea field. They do not receive persistent identities.
- An ordinary Claim node appears only when a source object provides a locatable Claim. Current objects do not, so the graph shows a dashed `Claim 尚未物化` placeholder without a confirmed downstream edge; an evidence `reason` never becomes a Claim.
- Every rendered edge carries source ID, target ID, relation type, and provenance. Missing Archive targets stay in the unresolved list. Candidate edges additionally require a rule name and version and remain disabled when none exist.
- One-hop is the default. Two-hop expansion admits only additional explicitly referenced Roadmap evidence, then stops at 40 nodes or 80 edges with a visible truncation state. The projection never uses title matching or browser-side semantic inference.
- Archive Atlas edges are all `contains`; the page always states that structural connections are not support, challenge, or causality.
- Public pages do not expose Owner, budget, approval, private results, internal comments, or fake write actions.

## Visual and responsive contract

The reference desktop viewport is 1586×992 with a 72px sticky top navigation, a 1540px maximum content width, and 24px page gutters. The visual system uses warm off-white surfaces, ink and navy text, restrained brick/olive semantic states, serif display type, sans-serif UI type, 4–6px radii, hairline borders, and no decorative motion.

Breakpoints are implemented at 1440, 1280, 1024, 768, 480, and 320px behavior bands. At widths below 768px:

- the navigation becomes a 56px title bar and menu;
- knowledge status becomes one summary row;
- tables become definition-list cards instead of horizontal scrollers;
- Roadmap rails, Idea rails, and Evidence rails move after primary content;
- Evidence Graph does not mount a shrunken desktop canvas. It becomes a two-column vertical Evidence Path at 360–767px and a single-column path at 320–359px, with a native filter dialog, definition-card detail, and compact relationship list;
- the active Evidence tab remains horizontally scrollable and the Evidence title bar stays 56px high;
- all visible interactive targets remain at least 44×44px.

Both `html` and `body` use `overflow-x: clip`. Grid tracks that can shrink use `minmax(0, 1fr)`, headings use `overflow-wrap: anywhere`, and reduced-motion preferences remove non-essential transitions.

## Verification and rollback

Run the focused public-site test with:

```bash
python3 -m pytest tests/test_public_intelligence_lab.py tests/test_evidence_graph.py -q
```

Before publication, parse `data-contract.js`, `app.js`, `workbench-view.js`, and `evidence-graph.js` with `node --check`. Inspect the four Evidence subviews at 1586×992, graph conflict and invalid-node fallbacks, and 320, 360, 375, 390, 414, 430, 768, 1024, 1280, and 1440px for horizontal overflow, focus visibility, relationship-list parity, and touch target size. Determinism tests must build both models and both layouts twice from the same input and compare the complete result.

Rollback restores the legacy Evidence renderer, removes the `evidence-graph.css` and `evidence-graph.js` entrypoint references, and lets graph/atlas aliases fall back to the path view. Archive and knowledge JSON do not require migration or rollback; the old unreferenced Atlas assets remain available as behavioral reference only.
