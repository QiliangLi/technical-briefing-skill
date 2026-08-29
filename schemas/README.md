# JSON schemas

Schemas in this directory validate Agent task outputs and durable publication data. The task queue names the exact schema for each task.

Keep schema changes synchronized with the matching prompt, semantic validator, cache version, fixtures, and tests. Existing runs can still reference older task types, so a schema that looks unused by fresh runs may remain necessary for idempotent resume.

Schema validation checks structure. Python semantic guards still enforce ID coverage, source binding, evidence boundaries, run provenance, and other cross-field invariants.
