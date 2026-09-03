# Task: discover auditable Idea Candidates from published evidence

Work on exactly the bounded input named by the task. Do not read another task,
candidate pools, source full text, Reader prose, the website, or unpublished data.

## Evidence boundary

- `published_evidence` is the only evidence. Every cited item, issue date, and URL
  must be copied from it.
- A Radar `discovery_signal` or `unverified` record cannot support a Candidate.
- Use the canonical source identity as `independence_group`: arXiv versions of the
  same paper are one group, not independent confirmation.
- A Topic match is only a reason to inspect records together. It is not evidence
  that their mechanisms combine.

## Direct mode

Inspect the one trigger item. Create a Candidate only when the item supports all
four elements: a concrete problem, an explainable mechanism, a target object, and
a testable effect. Otherwise return one `no_ops` row for that item. A benchmark or
measurement suggestion alone normally belongs in an Idea validation plan.

## Synthesis mode

Use at least one `trigger_evidence_item_id`. Create a synthesis Candidate only when
the cited records jointly support a mechanism that no single record already states.
`cross_issue_synthesis` must cite at least two issue dates.
`cross_source_synthesis` must cite at least two canonical independence groups in one
issue. Do not use repeated coverage of the same paper as independent evidence.

## Identity and disposition

Identity is the tuple `problem_key + mechanism_key + target_key`. Compare that tuple
and its meaning with `previous_candidates` and `existing_ideas`.

- `proposed`: complete and genuinely distinct; awaits human promotion.
- `duplicate`: same identity/meaning; point to the existing Candidate or Idea.
- `deferred`: complete, but missing independent support, an applicability boundary,
  or a human lineage decision.
- `dismissed`: missing a problem, mechanism, target, testable effect, or eligible
  evidence. State the missing element in `disposition_reason`.

Candidate decisions are append-only. Preserve every previous decision exactly and
append one event for a change. `validation_plan.execution_status` is always
`suggestion_only`; never describe a proposed check as an executed result.

Return one JSON object matching `schemas/idea-candidate-discovery.schema.json` and
echo the input `_task` object exactly at the output top level. In direct mode every
trigger item must appear in a Candidate evidence list or a reasoned no-op. In both
modes `covered_trigger_item_ids` must exactly equal the input triggers.
