# Editorial workbench UI contract

The public GitHub Pages surface is a read-only editorial workbench implemented with static HTML, CSS, and JavaScript under `site/`. It reads published archive data and materialized knowledge objects; it does not write back to either source.

## Routes and page ownership

The primary Hash routes are:

- `#home`: current issue changes, Idea updates, and visible risks;
- `#roadmaps?topic=<topic_id>&branch=<branch_id>`: one materialized Roadmap and its evidence boundary;
- `#ideas`: Candidate, Portfolio, and Validation collections kept visually and structurally separate;
- `#ideas?idea=<idea_id>`: one materialized Idea, its decision history, evidence summary, and validation suggestion;
- `#evidence?idea=<idea_id>&task=<task>`: a readable Evidence Path, not a global relationship graph;
- `#archive?date=<issue_date>`: one published issue and its derived long-term impact.

The legacy `#atlas` and `#graph` routes resolve to `#evidence`. The public feature-plan route remains available at `#features`, but it is not a primary navigation item.

## File boundaries

- `site/index.html` owns the shared shell, navigation, search Dialog, and accessible page root.
- `site/app.js` owns archive and knowledge loading, route orchestration, local-preview path fallback, and search indexing.
- `site/workbench-view.js` owns display-model construction and all page/component rendering.
- `site/data-contract.js` owns dependency-free data normalization and route parsing used by both the browser and tests.
- `site/editorial-tokens.css` owns palette, typography, spacing, elevation, and z-index tokens.
- `site/editorial-components.css` owns the shared shell and component system.
- `site/editorial-pages.css` owns only page-level grids and breakpoint reflow.
- `site/assets/brand-mark.svg` and `site/assets/icons.svg` are fixed, committed assets. Runtime image generation is prohibited.

The previous `styles.css`, `workbench-overrides.css`, `intelligence-lab.css`, and Atlas files remain unreferenced rollback assets until a later cleanup explicitly removes them.

## Data and evidence boundary

- Archive pages consume published archive JSON and Reader sidecars.
- Roadmap and Idea pages consume only `knowledge/index.json` and the materialized object files named by it.
- Components receive display models; they do not infer business meaning from missing fields.
- Missing optional fields remove their row or section. Empty collections render an explanation and the next truthful state.
- Candidate records are never derived from formal Idea records. When no public Candidate collection exists, the Candidate Inbox is an explicit empty state.
- Validation suggestions must say that they are not executed experiments. Full Plan, Run, and Result surfaces appear only when source state says the Idea entered Validation.
- Evidence relationships must resolve to an existing item or remain visibly unresolved. The UI does not draw an unsupported edge.
- Public pages do not expose Owner, budget, approval, private results, internal comments, or fake write actions.

## Visual and responsive contract

The reference desktop viewport is 1586×992 with a 72px sticky top navigation, a 1540px maximum content width, and 24px page gutters. The visual system uses warm off-white surfaces, ink and navy text, restrained brick/olive semantic states, serif display type, sans-serif UI type, 4–6px radii, hairline borders, and no decorative motion.

Breakpoints are implemented at 1440, 1280, 1024, 768, 480, and 320px behavior bands. At widths below 768px:

- the navigation becomes a 56px title bar and menu;
- knowledge status becomes one summary row;
- tables become definition-list cards instead of horizontal scrollers;
- Roadmap rails, Idea rails, and Evidence rails move after primary content;
- Evidence Path, Timeline, and Milestones become vertical;
- all visible interactive targets remain at least 44×44px.

Both `html` and `body` use `overflow-x: clip`. Grid tracks that can shrink use `minmax(0, 1fr)`, headings use `overflow-wrap: anywhere`, and reduced-motion preferences remove non-essential transitions.

## Verification and rollback

Run the focused public-site test with:

```bash
python3 -m pytest tests/test_public_intelligence_lab.py -q
```

Before publication, also parse the three active scripts with `node --check`, inspect all six routes at 1586×992, and check 320, 375, 414, and 768px for horizontal overflow, table degradation, focus visibility, and touch target size.

Rollback is a stylesheet-and-entrypoint change: restore the previous stylesheet and script references in `site/index.html`. Archive and knowledge JSON do not require migration or rollback.
