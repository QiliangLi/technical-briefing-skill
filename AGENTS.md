# Agent compatibility

Read `SKILL.md` first. Use `python briefing.py tasks next` to obtain one bounded task. Never load all candidates or all fulltexts into one context. Write JSON to the exact output path, then call `python briefing.py advance`.

## Code Review Rules

### Run isolation and idempotency
- Treat cross-run data leakage and duplicate re-application as correctness bugs. Reads and writes for candidates, facts, events, issue items, assets, and generated outputs must stay scoped to the active run unless code explicitly accesses archived/history data. `advance` and resume paths must remain idempotent: rerunning them must not duplicate issue content or re-apply outputs from an earlier run.

### Briefing integrity and report time
- Flag changes that can silently drop configured briefing sections/items, bypass fact-check/selection/final-writing stages, replace polished output with raw intermediate text, or derive the report date from stale filesystem/database state. The final date must come from the active run and configured timezone; missing or invalid upstream data should surface through an explicit error or documented fallback instead of silently collapsing the output.

### Published email assets
- Final email HTML must not reference local or relative run paths for images recipients need to load. Before send/archive, image references must resolve to stable browser/email-accessible absolute URLs (for example, published GitHub asset URLs), and rendering changes must preserve independent layout of adjacent figures rather than allowing them to concatenate or overlap.
