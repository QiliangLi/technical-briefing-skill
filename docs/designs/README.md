# Design documents

Use this directory for active, non-trivial design work. A design belongs here when it can change architecture, pipeline behavior, state, contracts, external effects, quality policy, or several modules at once.

Name each file `YYYY-MM-DD-<short-slug>.md`. Use a lowercase ASCII slug, for example `2026-08-29-reader-cache-lifecycle.md`.

## Lifecycle

1. Create the document with status `draft` before implementation.
2. Record material decisions and unresolved choices while the design is discussed.
3. Change the status to `accepted` when the user or maintainer accepts the design, or when a combined design-and-implementation request has resolved every material choice.
4. Keep the document synchronized with implementation decisions.
5. Change the status to `implemented` only after code, migrations, tests, and current documentation are complete.
6. Move an implemented or superseded design to `docs/history/designs/` only after its durable rules are represented in the current architecture, operations, or contracts documentation. Update every link when moving it.

A design-only request stops after the draft or accepted document is complete. Do not implement it without an explicit implementation request. A combined design-and-implementation request can continue after the design is written and material choices are resolved.

Archiving is a required completion step for the Agent that implements the design, not a background filesystem automation. No cron job or hook moves files on its own. The implementing Agent must update durable documentation, mark the design `implemented`, move it to `docs/history/designs/`, and repair links before handoff.

## Required content

Start with this shape and remove only sections that genuinely do not apply.

```markdown
# Design title

- Status: draft
- Created: YYYY-MM-DD
- Last updated: YYYY-MM-DD

## Problem and evidence

What currently happens, what evidence shows the problem, and why the change is needed.

## Goals and non-goals

What this design must achieve and what it deliberately leaves unchanged.

## Constraints and invariants

Run isolation, idempotency, evidence boundaries, compatibility, security, publication integrity, or other rules that cannot regress.

## Proposed design

The new behavior, ownership, data flow, states, and interfaces.

## Compatibility and migration

How active runs, stored data, caches, archives, configuration, and older task formats continue or migrate.

## Failure, recovery, and rollback

Expected failure states, retry rules, observability, and a safe rollback path.

## Verification

Tests, fixtures, telemetry, manual checks, and acceptance evidence.

## Documentation impact

Every current document, Prompt, Schema, or index that must change with the implementation.

## Decision log

Dated material decisions and the evidence or user direction behind them.
```

## Boundaries

Small bug fixes, typo corrections, dependency pins, and mechanical refactors do not need a new design file unless they change observable behavior or a durable contract. Update the nearest current document directly when that is sufficient.

Do not use this directory as a backlog, meeting-notes dump, implementation diary, or archive. Keep exploratory notes under `docs/history/research-notes/`; keep current operational truth under `docs/operations/` and current contracts under `docs/contracts/`.
