# Task: Materialize one Topic Roadmap and its Idea updates

You are updating one bounded Topic from published briefing records. The input contains
the complete published Machine evidence for that Topic through one issue, the IDs added
by the triggering issue, the previous Roadmap, and existing Ideas associated with the
Topic. Do not read candidate pools, source full text, reader projections, another task,
or the public website.

## Evidence boundary

- Treat only `published_evidence` as evidence. Reader-facing prose and unstated domain
  knowledge are not evidence.
- Every branch, stage, change, supporting/contrary Idea claim, and rejection must cite
  exact published `item_id` values and a non-empty subset of that item's `source_urls`.
- Keep source fact separate from your cross-issue inference. Use `inferred` when the
  relationship is your synthesis rather than an explicit result.
- Do not infer semantic relations from titles alone.
- Radar is a discovery signal, not a verified technical conclusion. Evidence without a
  stable Topic assignment must not be silently assigned to this Roadmap.

## Roadmap

Return the complete current Roadmap, not an append-only patch. Use Direction or a stable
mechanism as the branch. A stage means multiple records support a recognizable technical
phase or transition. When evidence only establishes that items appeared, set
`view_mode=evidence_timeline`, leave `stages` empty, and put the records in each branch's
`evidence_timeline`. Never manufacture a technology history to make the page look full.

Exception: when `topic.topic_id=frontier_exploration`, return `roadmap: null`. Frontier is
not a stable technology Topic and must never own a catch-all Roadmap.

Allowed judgement states are:

- `supported`: multiple published records support the judgement;
- `emerging`: an early signal with limited evidence;
- `contested`: published evidence conflicts;
- `inferred`: a cross-record interpretation.

Python decides `material_change` versus `no_material_change` by comparing branch/stage
judgements. New evidence by itself does not force a version bump.

The Roadmap `summary` is the homepage "current judgement" source. It must answer
"how should we see this topic now" in one actionable sentence grounded in cited
evidence (for example, which branch is winning, what the limiting factor is, or
what would change the judgement). It must never be a template about evidence
counts, "证据时间线", or waiting for more data; the Issue Change Projection
validator rejects such copy. When the evidence genuinely supports only a signal
timeline, say what the signals show and what observation would upgrade the view.

## Ideas

Return only new or updated Ideas; unchanged existing Ideas may be omitted.

- `research_hypothesis` is a falsifiable question that can be tested by simulation,
  data analysis, benchmark, prototype, or continued observation.
- `solution_concept` states a concrete problem, mechanism, and expected effect that may
  become a project proposal.
- A measurement action such as “补测 P95” is not an Idea. It belongs in
  `validation_plan` under a real hypothesis or solution.
- Identity is `problem_key + mechanism_key + target_key`, not `project_question`. Use
  stable lower_snake_case ASCII keys. Compute `idea_id` as the first 20 hexadecimal
  characters of SHA-256 over the three keys joined by the unit-separator character,
  prefixed with `idea_`. For an existing Idea, keep its identity and ID exactly.
- Do not merge Ideas merely because they share a Topic or project question.
- Automatic rejection requires contrary published evidence and an appended `rejected`
  decision. Do not reject merely because validation data or tools are unavailable.
- A rejected Idea may reopen only with new evidence and an appended `reopened` decision.
- Existing `decision_log` rows are append-only.

`validation_plan` is advice only. Set `execution_status=suggestion_only`. Specify the
minimal model, inputs or scan ranges, baselines, metrics, support criteria, rejection
criteria, and uncovered real-world conditions. Never invent a simulation or experiment
result.

## Frontier clusters

Every published Radar record is routed to `frontier_exploration`; its original Radar
category is preserved as `frontier_category` and `direction_name`. For a Frontier task,
return the complete current cluster list. New clusters use `status=temporary`,
`promotion_reason=null`, and `promotion_target=null`.

A cluster may become `promoted` only after recurrence across published issues, a stable
mechanism, or a bound Idea. Promotion must be explicit and must set
`promotion_target.topic_id`, `promotion_target.topic_name`, and
`promotion_target.branch_id` to a stable non-Frontier Roadmap destination. Frontier itself
never becomes a Roadmap. A promoted cluster enters that Roadmap only through a subsequent
bounded task for its stable target Topic; the evidence may only enter the exact bound
branch. For stable Topic tasks, do not edit `frontier_clusters`.

Return JSON matching `schemas/knowledge-materialization.schema.json` and echo the exact
top-level `_task` binding from the input.
