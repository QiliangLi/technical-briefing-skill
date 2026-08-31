# Documentation

This directory separates current documentation from dated project records. Start with `../README.md` for setup and `../SKILL.md` for Agent execution.

## Current architecture

- [Architecture](architecture.md) explains the pipeline, state boundaries, evidence boundary, and publication flow.

## Active designs

- [Design document rules and template](designs/README.md)
- [Roadmap, Idea Bank, and Evidence model redesign](designs/2026-08-29-roadmap-idea-bank-evidence-model-redesign.md)
- [Roadmap, Idea Bank, and Evidence Workbench blueprint](designs/2026-08-29-roadmap-idea-bank-evidence-workbench-blueprint.md)
- [Technical intelligence workbench UI screen content brief](designs/2026-08-30-technical-intelligence-ui-screen-content-brief.md)
- [Technical intelligence workbench UI style brief pack](designs/2026-08-30-technical-intelligence-ui-style-brief-pack.md)
- [Evidence Graph UI generation brief](designs/2026-08-31-evidence-graph-ui-generation-brief.md)
- [Evidence Graph UI pixel-accurate implementation plan](designs/2026-08-31-evidence-graph-ui-implementation-spec.md)

Create non-trivial designs under `designs/` before implementation. Once an implementation is complete, move durable behavior into the current architecture, operations, or contracts documentation. Historical design records belong under `history/designs/` only after that transfer is complete.

## Operations

- [Agently publication transport](operations/agently-publication-transport.md)
- [AI HOT invisible upstream](operations/aihot-invisible-upstream.md)
- [Execution telemetry](operations/execution-telemetry.md)
- [Historical backfill](operations/historical-backfill.md)

These files describe how a current installation behaves and how to diagnose it.

## Contracts

- [Repository change governance](contracts/change-governance.md)
- [Code review invariants](contracts/code-review-invariants.md)
- [Editorial workbench UI](contracts/editorial-workbench-ui.md)
- [Archive reader](contracts/archive-reader-contract.md)
- [Human edit feedback](contracts/human-edit-feedback.md)
- [Illustrated publication](contracts/illustrated-publication.md)
- [Knowledge materialization](contracts/knowledge-materialization.md)
- [Project insight layer](contracts/project-insight-layer.md)
- [Semantic golden evaluation](contracts/semantic-golden-eval.md)
- [Technology value assessment](contracts/technology-value-assessment.md)

These files define durable interfaces and quality rules. Prompt and schema details remain in `../prompts/` and `../schemas/`.

## History

[History](history/README.md) contains old plans, release snapshots, reviews, conversations, and exploratory design notes. Files there explain how the repository evolved; they must not be used as the source of truth for current commands or defaults.

- [Implemented editorial workbench UI design](history/designs/2026-08-31-editorial-workbench-ui-implementation-spec.md)
