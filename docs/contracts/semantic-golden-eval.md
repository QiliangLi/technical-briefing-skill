# Semantic Golden Evaluation

## Goal

Golden evaluation is used as a regression guard for technical briefing quality. It is not intended to judge writing style only, and keyword matching is only used for deterministic checks.

## Layers

### 1. Deterministic guard

Checks facts that can be verified without an LLM:

- numbers and units
- baseline names
- hardware/workload conditions
- source traceability
- required schema fields

### 2. Semantic judge

Checks whether the generated briefing preserves:

- mechanism
- causal relationship
- applicability boundary
- limitations
- unsupported claims

Example:

A paper improving throughput by reducing data movement must not be rewritten as improving throughput through additional compute capacity.

### 3. Human-curated golden cases

Each case records:

- source
- extracted facts
- causal graph
- boundaries
- common failure modes

The purpose is to prevent regressions when optimizing token usage, evidence windows, or agent scheduling.
