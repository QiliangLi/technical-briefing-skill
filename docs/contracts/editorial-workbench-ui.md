# Editorial workbench UI contract

The public GitHub Pages surface is a read-only editorial workbench implemented with static HTML, CSS, and JavaScript under `site/`. It reads published archive data, materialized knowledge objects, and the derived knowledge graph document; it does not write back to any source.

## Routes and page ownership

The primary Hash routes are:

- `#home`: current issue changes, Idea updates, and visible risks;
- `#roadmaps?topic=<topic_id>&branch=<branch_id>`: one materialized Roadmap and its evidence boundary;
- `#ideas`: Candidate, Portfolio, and Validation collections kept visually and structurally separate;
- `#ideas?idea=<idea_id>&view=overview`: one materialized Idea, its decision history, evidence summary, and validation suggestion;
- `#ideas?idea=<idea_id>&view=evidence&mode=path`: the readable Idea evidence path;
- `#ideas?idea=<idea_id>&view=evidence&mode=graph&node=<node_id>&depth=<1|2>`: the Idea evidence subgraph with synchronized node detail and relationship list;
- `#ideas?idea=<idea_id>&view=gaps`: evidence gaps taken from the selected Idea's recorded unknowns;
- `#knowledge?lens=structure&topic=<topic_id>&direction=<direction_id>&node=<node_id>`: the default Topic/Direction skeleton lens;
- `#knowledge?lens=evolution&topic=<topic_id>&from=<date>&to=<date>&node=<node_id>`: issue-by-issue expansion of Direction items;
- `#knowledge?lens=judgements&topic=<topic_id>&node=<node_id>`: editor judgements and their explicit evidence items.

Knowledge-lens filter parameters: `range` is `latest|recent3|all|custom` (default `recent3`; paired `from`/`to` implies `custom`), `overlay` is a comma list of `roadmap,idea` influence overlays (default off), `hide` excludes node kinds after lens selection, and `unresolved=1` restricts the view to objects carrying unresolved references. Invalid lens or range values fall back to `structure` and `recent3`; invalid Idea view falls back to `overview`, invalid mode to `path`, invalid depth to one hop. The public feature-plan route remains available at `#features`, but it is not a primary navigation item.

### Legacy bookmark normalization

Old routes never render a second page; `site/data-contract.js` maps them once during route parsing:

| Legacy route | Normalized to |
| --- | --- |
| `#evidence?idea=<id>&view=path` | `#ideas?idea=<id>&view=evidence&mode=path` |
| `#evidence?idea=<id>&view=graph` | `#ideas?idea=<id>&view=evidence&mode=graph` |
| `#evidence?idea=<id>&view=gaps` | `#ideas?idea=<id>&view=gaps` |
| `#graph?...` | with `idea` → the Idea evidence graph; otherwise `#knowledge` |
| `#atlas?...` | `#knowledge?lens=evolution`, preserving convertible `issue` (as `from`/`to`) and `topic` parameters |

## File boundaries

- `site/index.html` owns the shared shell, navigation, search dialog, and accessible page root. It loads the self-hosted Cytoscape.js distribution before any graph module.
- `site/app.js` owns archive and knowledge loading, lazy `knowledge/graph.json` loading for the routes that need it, route orchestration, renderer teardown on route change, local-preview path fallback, and search indexing.
- `site/workbench-view.js` owns the Home, Roadmap, Idea Hub, Idea Overview, Archive, and Features pages, and dispatches to the dedicated graph-surface views.
- `site/knowledge-graph-view.js` owns the `#knowledge` page: lenses, filters, overlays, node details, relationship list, unresolved-references view, and the below-768px layered path.
- `site/idea-evidence-view.js` owns the Idea evidence path, evidence subgraph, and evidence gaps views.
- `site/data-contract.js` owns dependency-free data normalization, route parsing with legacy normalization, `validateKnowledgeGraph()`, and the two projections `buildKnowledgeGraphModel()` and `buildIdeaEvidenceGraphModel()`. It computes no layout coordinates.
- `site/graph-renderer.js` owns Cytoscape.js initialization, element mounting, selection, focus neighborhood, keyboard traversal, viewport control, and destruction. It receives a validated display model only; it never reads source JSON or infers relationships.
- `site/graph-styles.js` owns node/relation selector styles, arrowheads, focus and dimmed states, and the kind/relation label tables shared by both graph surfaces.
- `site/knowledge-graph.css` owns the knowledge-graph workspace, graph-surface chrome, relationship lists, and graph-only responsive behavior including the mobile layered paths.
- `site/editorial-tokens.css`, `site/editorial-components.css`, and `site/editorial-pages.css` keep their previous ownership.
- `site/feedback-store.js` owns the browser-local feedback event store (append-only toggle events in localStorage). It performs no network calls, no real state writes, and is rendered only through the shared `feedbackButtons()`/`bindFeedbackEvents()` primitives in `site/workbench-view.js`.
- `site/assets/vendor/` holds the locked, self-hosted Cytoscape.js distribution with its license and version record. Runtime CDN requests are prohibited.
- `site/assets/brand-mark.svg` and `site/assets/icons.svg` are fixed, committed assets; graph node/filter symbols use the same monochrome sprite. Runtime image generation is prohibited.

The previous `styles.css`, `workbench-overrides.css`, `intelligence-lab.css`, Atlas assets, and the retired `evidence-graph.js`/`evidence-graph.css` DOM/SVG renderer remain unreferenced rollback material recoverable from git history.

## Data and evidence boundary

- Archive pages consume published archive JSON and Reader sidecars. Roadmap and Idea pages consume only `knowledge/index.json` and the materialized object files named by it. The `#knowledge` page and the Idea evidence graph consume `knowledge/graph.json`, a regenerable derived publication.
- `knowledge/graph.json` carries `archive_through_issue` and `knowledge_through_issue` watermarks that are computed and displayed separately; one "graph updated" label must never hide knowledge lagging the archive.
- Only relations explicitly present in the inputs may be drawn: archive Topic/Direction fields, `synthesis.judgements[].evidence_item_ids`, Roadmap branch `direction_ids`/`evidence_item_ids`/evidence timelines, and Idea `topic_ids`/`evidence_for`/`evidence_against`. Topic names, direction names, and keywords are display and search material only; the frontend never adds edges from titles, names, or keywords.
- Hiding a node kind removes its nodes and every edge that no longer has both endpoints in the final node set; filters can never leave dangling edges or degrade the canvas. Topic/Direction filters constrain items, and judgements/issues are visible only through their explicit `supports_judgement`/`published_in` connections to the visible items, so another Topic's judgements never leak into a filtered view.
- Arrow direction belongs to the relation enumeration. The frontend never swaps source and target to make an arrow "look better". Structural `has_direction`/`has_item`/`tracks`/`organizes` edges are containment or organization, never support, causality, or evolution claims.
- Every rendered edge resolves both endpoints or stays visibly unresolved. Unresolved references render in a dedicated list with reasons and never become confirmed edges.
- The Idea evidence projection may add read-only `assumption`/`decision` nodes derived from Idea fields, labeled as such, without persistent identities. When `knowledge/graph.json` is unavailable, the Idea evidence projection falls back to building the same explicit relations directly from Idea fields and archive items.
- Display limits: default views cap at 60 nodes / 120 edges; "all issues" caps at 250 nodes / 500 edges. Capping keeps the focused node's one-hop neighborhood and explicit judgement relations first, then recent issues, then stable IDs, and states the real counts and the capping reason instead of silently dropping.
- Node selection updates the graph highlight, the detail panel, the relationship list, and the URL together. Edge selection updates the relation detail and list row. Search lists matches first and changes canvas focus only on confirmation.
- Public pages do not expose Owner, budget, approval, private results, internal comments, or fake write actions. The only local interaction is the brief-item feedback toggle (感兴趣/不感兴趣) in the item detail panels: a browser-local demo backed by `site/feedback-store.js` that must stay labeled as browser-local, never claim to affect real Roadmap/Idea/selection state, and ships no export, count, or clear console.

## Visual and responsive contract

The reference desktop viewport is 1586×992 with a 72px sticky top navigation, a 1540px maximum content width, and 24px page gutters. The visual system uses warm off-white surfaces, ink and navy text, restrained brick/olive semantic states, serif display type, sans-serif UI type, 4–6px radii, hairline borders, and no decorative motion. The knowledge-graph workspace uses a fixed-elastic-fixed three-column grid (248px filters | canvas | 344px details).

Node kinds are differentiated by outline shape, icon, and text label in addition to color. State changes use 120–180ms opacity, border, and position feedback only. The canvas may use a low-contrast positioning grid; no glow, glass, gradient text, or HUD effects.

Breakpoints are implemented at 1440, 1280, 1024, 768, 480, and 320px behavior bands. At widths below 768px:

- the navigation becomes a 56px title bar and menu;
- knowledge status becomes one summary row;
- tables become definition-list cards instead of horizontal scrollers;
- the knowledge-graph workspace and Idea graph canvas do not mount. `#knowledge` renders a layered path (current object's relations → recent items → judgements → Roadmap/Idea influence) and the relationship list; the Idea evidence views render the evidence path and relationship list;
- filters enter a native bottom-sheet dialog;
- all visible interactive targets remain at least 44×44px.

Both `html` and `body` use `overflow-x: clip`. Graph containers never widen the page. Reduced-motion preferences remove non-essential transitions, canvas fitting lands directly in its final state, and SVG/Canvas graphics are hidden from screen readers while the DOM relationship list carries the complete relation set.

## Browser failure behavior

- When Cytoscape.js fails to load or mount, the page states that graph rendering is unavailable and the relationship list plus node details — built from the same display model — remain fully usable.
- A URL node that does not exist in the current filter keeps the filters and falls back to the default focus with a visible note.
- A missing or invalid `knowledge/graph.json` shows an explicit unavailability note on `#knowledge` and degrades the Idea evidence graph to the explicit-fields projection; Roadmap, Idea Overview, and Archive pages are unaffected.

## Verification and rollback

Run the focused public-site tests with:

```bash
python3 -m pytest tests/test_public_intelligence_lab.py tests/test_graph_surfaces.py tests/test_knowledge_graph.py -q
```

Before publication, parse every site script with `node --check`, inspect the three knowledge lenses and the Idea evidence views at 1586×992 and 320, 375, 414, 768, 1024, 1280, and 1440px for horizontal overflow, focus visibility, relationship-list parity, and touch target size, and rebuild the graph twice to confirm byte-identical output (excluding `generated_at`, or pinned via `SOURCE_DATE_EPOCH`).

Rollback order: restore the Evidence navigation entry, stop loading `graph-renderer.js`, `knowledge-graph-view.js`, `idea-evidence-view.js`, and `knowledge/graph.json`, restore the retired `evidence-graph.js`/`evidence-graph.css` entrypoints from git history, then remove the Cytoscape vendor asset. `knowledge/graph.json` may also be deleted outright because it is a derived artifact. Archive and knowledge JSON never require migration or rollback.
