# Task: promote one accepted Idea Candidate

Read only the bounded promotion input. The Candidate is a proposal, not yet a formal
Idea. Return a complete Idea object matching `schemas/idea.schema.json`; do not edit
files directly.

- Preserve the Candidate identity tuple exactly. Its deterministic formal ID is the
  same digest with the `idea_` prefix.
- Use exactly the Candidate's evidence items. Copy issue dates and non-empty source
  URL subsets from `published_evidence`; do not add background knowledge.
- Preserve an existing Idea's identity, type, and decision-log prefix when one is
  present. Explain every appended status decision.
- A new Idea begins at `observing` when it has at least two canonical independent
  sources, otherwise at `seed`.
- `first_seen_issue` is the earliest cited evidence date and `last_updated_issue` is
  the task issue.
- The validation plan stays a suggestion. Never claim a Run, Result, benchmark, or
  experiment was performed.

Echo the exact input `_task` object and return one JSON object matching
`schemas/idea-promotion.schema.json`. Apply is the only writer and rejects a stale
Candidate or stale prior Idea digest.
