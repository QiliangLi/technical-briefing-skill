# Editorial workbench UI contract

The public GitHub Pages surface is a read-only editorial workbench implemented with static HTML, CSS, and JavaScript under `site/`. It reads published archive data, materialized knowledge objects, and the derived knowledge graph document; it does not write back to any source.

## Routes and page ownership

The primary Hash routes are:

- `#home`: the freshness watermark (archive head, materialization watermark, analysis state), this issue's real material change from the Issue Change Projection, honest pending/empty states, and visible risks;
- `#roadmaps`: the browsable Roadmap overview — one row or card per Topic with current state, mode, last material change, knowledge lag, branch/open-question counts, and filters (本期变化 / 待补证据 / 长期未更新);
- `#roadmaps?topic=<topic_id>&branch=<branch_id>`: one materialized Roadmap and its evidence boundary, with breadcrumb back to the overview and previous/next Topic navigation (a native `<select>` is never the primary navigation);
- `#ideas`: the honest Idea Portfolio — formal Ideas grouped by recorded status, a read-only lifecycle note that labels Candidate Inbox and Validation as 未启用 until real data objects exist; there is no three-column funnel with empty rails or fake zero counts;
- `#ideas?idea=<idea_id>&view=overview`: one materialized Idea, its decision history, evidence summary, and validation suggestion;
- `#ideas?idea=<idea_id>&view=evidence&mode=path`: the readable Idea evidence path;
- `#ideas?idea=<idea_id>&view=evidence&mode=graph&node=<node_id>&depth=<1|2>`: the Idea evidence subgraph with synchronized node detail and relationship list;
- `#ideas?idea=<idea_id>&view=gaps`: evidence gaps taken from the selected Idea's recorded unknowns;
- `#knowledge` with `lens=structure` and no `topic`/`node`: the global overview — one cluster card per Topic (direction/item counts, last knowledge update, lag badge); clicking a card opens the readable local graph;
- `#knowledge?lens=structure&topic=<topic_id>&direction=<direction_id>&node=<node_id>`: the Topic/Direction skeleton lens; entering a topic-scoped graph fits the focused one-hop neighborhood instead of fitting every node;
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
- The homepage additionally consumes `knowledge/manifest.json` and, when the manifest declares `knowledge_complete`, `knowledge/issue-diffs/<archive_head>.json`. The "本期最重要变化" section renders only the projection's `topic_changes`/`idea_events`; a missing manifest, a non-complete state, or a missing diff renders an explicit pending/degraded note. The homepage never backfills old Roadmap summaries as this issue's change, never lists historical Ideas to look full, and never synthesizes judgement text in the browser.
- Seed baseline copy ("…积累了 N 条专题证据…首版先保留…时间线") is labeled as a baseline timeline (`基线时间线` badge) on Roadmap surfaces and is rejected by the projection's semantic validator inside judgement fields; it must never be displayed as a current judgement.
- `knowledge/graph.json` carries `archive_through_issue` and `knowledge_through_issue` watermarks that are computed and displayed separately; one "graph updated" label must never hide knowledge lagging the archive. The graph page's status area shows the analysis state from the manifest; the raw `input_digest` lives in a collapsed 技术信息 disclosure named 输入校验码 with a copy button — it is build diagnostics, never a content summary.
- Only relations explicitly present in the inputs may be drawn: archive Topic/Direction fields, `synthesis.judgements[].evidence_item_ids`, Roadmap branch `direction_ids`/`evidence_item_ids`/evidence timelines, and Idea `topic_ids`/`evidence_for`/`evidence_against`. Topic names, direction names, and keywords are display and search material only; the frontend never adds edges from titles, names, or keywords.
- Hiding a node kind removes its nodes and every edge that no longer has both endpoints in the final node set; filters can never leave dangling edges or degrade the canvas. Topic/Direction filters constrain items, and judgements/issues are visible only through their explicit `supports_judgement`/`published_in` connections to the visible items, so another Topic's judgements never leak into a filtered view.
- Arrow direction belongs to the relation enumeration. The frontend never swaps source and target to make an arrow "look better". Structural `has_direction`/`has_item`/`tracks`/`organizes` edges are containment or organization, never support, causality, or evolution claims.
- Every rendered edge resolves both endpoints or stays visibly unresolved. Unresolved references render in a dedicated list with reasons and never become confirmed edges.
- The Idea evidence projection may add read-only `assumption`/`decision` nodes derived from Idea fields, labeled as such, without persistent identities. When `knowledge/graph.json` is unavailable, the Idea evidence projection falls back to building the same explicit relations directly from Idea fields and archive items.
- Display limits: default views cap at 60 nodes / 120 edges; "all issues" caps at 250 nodes / 500 edges. Capping keeps the focused node's one-hop neighborhood and explicit judgement relations first, then recent issues, then stable IDs, and states the real counts and the capping reason instead of silently dropping.
- Node selection updates the graph highlight, the detail panel, the relationship list, and the URL together. Edge selection updates the relation detail and list row. Search lists matches first and changes canvas focus only on confirmation.
- Public pages do not expose Owner, budget, approval, private results, internal comments, or fake write actions. The only local interaction is the brief-item feedback toggle (感兴趣/不感兴趣) in the item detail panels: a browser-local demo backed by `site/feedback-store.js` that must stay labeled as browser-local, never claim to affect real Roadmap/Idea/selection state, and ships no export, count, or clear console.

## Visual and responsive contract

The reference desktop viewport is 1586×992 with a 72px sticky top navigation, a 1540px maximum content width, and 24px page gutters. The visual system uses warm off-white surfaces, ink and navy text, restrained brick/olive semantic states, serif display type, sans-serif UI type, 4–6px radii, hairline borders, and no decorative motion. The knowledge-graph workspace uses a fixed-elastic-fixed three-column grid (248px filters | canvas | 344px details); the desktop filter rail can be collapsed from the canvas toolbar, and below 1280px the detail panel drops beneath the canvas so a 1024px viewport still leaves the canvas readable (~700px+).

Semantic alignment contract (shared classes, not per-page one-offs):

| Content | Horizontal | Vertical | Wrapping |
| --- | --- | --- | --- |
| Titles, judgements, summaries, sources | left | top | allowed |
| Status, type, short enums, dates | center | middle | at most two short lines |
| Quantities | right (or metric-card centered) | middle | never |
| Icon + single-line label | left | middle | label may ellipsize |
| CTA / actions | center | middle | never, ≥44px hit area |

Long judgement and summary columns stay left-aligned for readability; `.data-table th/td.cell-center` implements the centered variant. Table column widths must sum to ≤100%; status badges carry `max-width: 100%` and short labels so they can never overflow their cell. All grid/flex children keep `min-width: 0`; `overflow-x: clip` is a last-resort guard, not an acceptance test — checks must inspect element bounds.

Node kinds are differentiated by outline shape, icon, and text label in addition to color. State changes use 120–180ms opacity, border, and position feedback only. The canvas may use a low-contrast positioning grid; no glow, glass, gradient text, or HUD effects.

Breakpoints are implemented at 1440, 1280, 1024, 768, 480, and 320px behavior bands. Data tables switch to definition-list cards at ≤1023px, before a fixed table can no longer hold its content. At widths below 768px:

- the navigation becomes a 56px title bar and menu;
- knowledge status becomes one summary row;
- the knowledge-graph workspace and Idea graph canvas do not mount. `#knowledge` renders a layered path (current object's relations → recent items → judgements → Roadmap/Idea influence in a collapsed disclosure) and the relationship list; the Idea evidence views render the evidence path and relationship list;
- filters enter a native bottom-sheet dialog;
- all visible interactive targets remain at least 44×44px.

The relationship list paginates at 20 rows per page, but every row stays in the DOM (hidden pages included) so it remains the complete, accessible source of truth; the pager states the real page and total counts.

Both `html` and `body` use `overflow-x: clip`. Graph containers never widen the page. Reduced-motion preferences remove non-essential transitions, canvas fitting lands directly in its final state, and SVG/Canvas graphics are hidden from screen readers while the DOM relationship list carries the complete relation set.

## Lens layout, focus, and empty-state contract

The canvas never renders whole-graph coordinates. `site/data-contract.js` produces the filtered display model (visible nodes/edges only); `site/knowledge-layout.js` — a dependency-free, DOM-free module — then generates deterministic per-lens coordinates and the initial viewport for the CURRENT model. Node count thresholds never choose the layout algorithm; the lens and its explicit range do. The layout reads only kind, relation, issue date, and stable IDs; it never adds, drops, or rewrites nodes or edges, and the relationship list is built from the same model.

Per lens:

- `structure`: Topic in a context column, Directions in a compact stack (overlay objects in a trailing column). Default focus is the Topic and the first screen fits the whole local skeleton; only an explicit `node` focuses that node's one hop.
- `evolution`: Issue columns as time, Direction lanes as rows; items sit in their Direction × Issue cell, dense cells wrap into sub-columns, and issue anchors sit at the vertical center of their column so `has_item`/`published_in` edges stay inside their lane or column. Default focus is the URL `direction` if given, otherwise the lane with the most recent item activity, labeled `自动聚焦：…` in the canvas status; the first screen fits that Direction's time slice and always contains at least one Direction, one Item, and one Issue.
- `judgements`: judgement-centered evidence clusters (evidence items in a column left of their judgement), packed into bounded columns; uncited skeleton items form a compact context grid. Default focus is the latest Judgement and the first screen fits its evidence cluster.

Initial-focus priority: a valid URL `node` first, then the lens default, then the lens empty state, and only last the Topic. `fitFocus()` runs only from the explicit 聚焦当前对象 button; collapsing the filter rail resizes the canvas and re-applies the current fit. The renderer accepts an explicit highlight set so a lens first screen keeps its Issue/Judgement nodes readable even though they sit two hops from the focus.

The canvas status line is lens-specific — structure: `N Topic · M Direction`; evolution: `N Direction · M 条目 · K 期`; judgements: `N 判断 · M 条显式证据关系` — and states truncation and scope warnings when caps apply. When a lens has zero of its own objects (structure: Directions; evolution: Items+Issues; judgements: Judgements+`supports_judgement`), the canvas area shows the reason, the current scope, and actions (`扩大到全部期次` / `返回结构`); the shared skeleton survives only as a collapsed 结构上下文 list, and the relationship list and mobile copy state the same fact. The site never borrows another Topic's judgements or renders an uncited item as a judgement.

Edge-length acceptance (enforced by tests over every Topic × `latest|recent3|all`): semantic edges (`has_item`, `published_in`, `supports_judgement`) keep max ≤ 4× their relation's median length, containment edges are bounded outright, coordinates stay bounded (no 10k-unit filtered voids), and identical input produces identical coordinates.

## Browser failure behavior

- When Cytoscape.js fails to load or mount, the page states that graph rendering is unavailable and the relationship list plus node details — built from the same display model — remain fully usable.
- A URL node that does not exist in the current filter keeps the filters and falls back to the default focus with a visible note.
- A missing or invalid `knowledge/graph.json` shows an explicit unavailability note on `#knowledge` and degrades the Idea evidence graph to the explicit-fields projection; Roadmap, Idea Overview, and Archive pages are unaffected.
- A missing `knowledge/manifest.json`, a non-`knowledge_complete` publication state, or a missing/unusable issue diff renders the homepage's honest pending/degraded note ("发布清单缺失" / "本期已归档，长期判断正在分析" / "本期投影缺失"); the site never falls back to browser-inferred change summaries or seed template copy.
- `#roadmaps` without a topic renders the overview; a `topic` that does not resolve to a materialized Roadmap renders an explicit not-found state instead of silently selecting the first entry.

## Verification and rollback

Run the focused public-site tests with:

```bash
python3 -m pytest tests/test_public_intelligence_lab.py tests/test_graph_surfaces.py tests/test_knowledge_graph.py -q
```

Before publication, parse every site script with `node --check`, inspect the three knowledge lenses and the Idea evidence views at 1586×992 and 320, 375, 414, 768, 1024, 1280, and 1440px for horizontal overflow, focus visibility, relationship-list parity, and touch target size, and rebuild the graph twice to confirm byte-identical output (excluding `generated_at`, or pinned via `SOURCE_DATE_EPOCH`).

Rollback order: restore the Evidence navigation entry, stop loading `graph-renderer.js`, `knowledge-graph-view.js`, `idea-evidence-view.js`, and `knowledge/graph.json`, restore the retired `evidence-graph.js`/`evidence-graph.css` entrypoints from git history, then remove the Cytoscape vendor asset. `knowledge/graph.json` may also be deleted outright because it is a derived artifact. Archive and knowledge JSON never require migration or rollback.
