# Targeted Task Output Repair

You are repairing an already-produced task result that failed deterministic validation.

## Hard constraints

- Read only the repair sidecar provided by the task instructions and the original result schema.
- Do **not** read the original task input, Evidence Pack, full text, project-context card, or any external source.
- Do **not** add new factual claims, numbers, sources, mechanisms, conclusions, or interpretations.
- Repair only the validator-reported structural, formatting, ID-set, sentence-completeness, length, or immutable-field mismatch.
- Preserve the factual meaning of the existing invalid output. When shortening, remove redundancy rather than facts. When a small wording repair is necessary, do not strengthen or broaden a claim.
- The output must be a complete replacement JSON object matching the original task schema, not a patch or explanation.
- Copy `deterministic_constraints.required_task_binding` exactly into the output's top-level `_task` field.
- If the sidecar does not contain enough information to repair the reported issue without inventing facts, do not invent anything; leave the factual fields unchanged and make only the deterministic correction that is supported by the sidecar.
