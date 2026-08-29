# Repository instructions

This file is an index. Load only the guidance needed for the current task. `SKILL.md` is the briefing execution runbook, not a prerequisite for unrelated repository maintenance.

## Task routing

| Task | Read |
| --- | --- |
| Run or resume a briefing | `SKILL.md`, then only the Prompt, input, context card, and Schema named by `python briefing.py tasks next --run latest` |
| Discuss or propose a non-trivial design | `docs/designs/README.md` and `docs/contracts/change-governance.md` |
| Change Agent workflow, evidence scope, or briefing task order | `SKILL.md`, `docs/contracts/change-governance.md`, and the relevant current contract |
| Implement, refactor, change configuration, or move files | `docs/contracts/change-governance.md`; also read `docs/contracts/code-review-invariants.md` when pipeline state or publication behavior is involved |
| Review pipeline, state, rendering, mail, or publication code | `docs/contracts/code-review-invariants.md` and the relevant current contract |
| Change documentation structure or paths | `docs/README.md` and `docs/contracts/change-governance.md` |
| Diagnose or operate a subsystem | the relevant file under `docs/operations/` or `docs/contracts/` |

## Always

- Briefing execution uses the task queue. Repository maintenance, documentation, testing, and code review do not.
- Never load all candidates or all full texts into one context. Grouped fact extraction never merges source evidence, outputs, schemas, caches, or provenance.
- Treat implementation and `config/*.yaml` as the source of truth for current defaults. `docs/history/` is historical only.
- Update affected current documentation as part of an implementation. A design-only request stops before code changes.
- Do not send mail without explicit user confirmation and `--confirm-send`.
- Do not stage or commit unless the user requests it.
