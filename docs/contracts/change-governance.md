# Repository change governance

Read this file for implementation, refactoring, documentation restructuring, file moves, or any change that can alter a public command, task contract, configuration meaning, or repository layout.

## Documentation ownership

- `README.md` is the human onboarding page. Keep it short and avoid copying volatile limits from configuration.
- `SKILL.md` is the Agent runbook. Keep non-obvious execution and safety constraints there.
- `docs/architecture.md`, `docs/operations/`, and `docs/contracts/` describe current behavior.
- `docs/designs/` contains active design work that has not yet been fully absorbed into current documentation.
- `docs/history/` preserves old plans, reviews, conversations, and release snapshots. It is never the source of truth for current behavior.
- `prompts/` and `config/project-context/` are runtime inputs even though they use Markdown.

Documentation required by an in-scope implementation is part of that implementation. Update it without waiting for a separate request. If a change has no documentation impact, state that in the final handoff and explain why.

## Design-first boundary

Read `docs/designs/README.md` and create a design before implementation when a change affects pipeline stages, durable state, schemas, task envelopes, caches, cross-run behavior, public interfaces, evidence or quality policy, external effects, or several modules at once.

Small local fixes and mechanical refactors do not need a new design file unless they change observable behavior or a durable contract. A design-only request stops after the design document; a combined design-and-implementation request may continue after material choices are resolved.

## Documentation synchronization

Use the nearest authoritative document for each change.

| Change | Required documentation |
| --- | --- |
| Setup, common commands, repository navigation, or user-visible workflow | `README.md` |
| Agent task order, evidence scope, required skills, or execution constraints | `SKILL.md` |
| System boundaries, stage ownership, or durable data flow | `docs/architecture.md` |
| Operations, recovery, telemetry, transport, or external integration | the relevant file under `docs/operations/` |
| Schemas, provenance, quality rules, reader contracts, or publication contracts | the relevant file under `docs/contracts/`, plus matching Prompt or Schema when applicable |
| Topic, source, scoring, time-window, or budget defaults | the owning file under `config/`; update prose only when it states the same contract |
| Prompt or task-output changes | matching files under `prompts/` and `schemas/`, semantic validators, fixtures, and tests |
| File or directory moves | `docs/README.md`, every code and documentation reference, packaging metadata, and path-sensitive tests |
| Host-specific execution behavior | `CODEX.md`, `HERMES.md`, or another existing host entrypoint |

Historical files explain earlier decisions. Never patch a file under `docs/history/` and treat that patch as current documentation.

## Repository structure

- Keep the root limited to entrypoints, host instructions, licensing, and build or dependency files. Put new explanatory material under `docs/`.
- Put operations in `docs/operations/`, durable interfaces in `docs/contracts/`, active proposals in `docs/designs/`, and superseded material in `docs/history/`.
- Keep runtime Markdown beside the subsystem that consumes it, such as `prompts/` and `config/project-context/`.
- Do not place generated reports, task outputs, local run state, or temporary drafts in the current documentation tree.
- Before deleting or moving a document, search code, tests, configuration, prompts, packaging files, and other documents for its path. Update all callers in the same change.

## Verification and handoff

Run the narrowest relevant tests while iterating, then expand according to risk. Before handoff:

1. Check local Markdown links and stale references to moved paths.
2. Run `git diff --check` and inspect `git status --short` for generated files, missing move targets, and untracked files that belong to the change.
3. Run the Skill validator when `SKILL.md`, its supporting instructions, or repository structure changes.
4. Report tests and documentation updates. Do not stage or commit unless the user requests it; warn that `git commit -am` omits new and moved-to files.
