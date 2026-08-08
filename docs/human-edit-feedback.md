# Human Edit Telemetry / Quality Feedback Foundation

## Goal

The briefing pipeline already has deterministic source, fact, ranking, and project-insight quality guards. Human review is the final signal: what was accepted, rejected, shortened, expanded, or technically rewritten before the briefing was sent.

This layer records that signal without changing generation behavior yet. It is intentionally **observational first**: a small number of edits must not silently rewrite prompts or ranking policy.

## Review model

The review page exposes six fields from each fact-checked briefing item:

- title
- core conclusion
- mechanism
- result / evidence
- boundary
- project relevance

The reviewer may edit these fields and independently approve or reject each item.

### Immutable Agent output

`brief_items.json_path` remains the immutable Agent-authored artifact. Human review never overwrites it.

Edited text is written to:

```text
workspace/runs/<run_id>/reviewed_items/<brief_item_id>.json
```

The reviewed sidecar is used when rebuilding the approved issue/email. If all fields are reset to the Agent text, the sidecar is removed.

### Reopen behavior

The final approved `issue.json` contains only approved items, but the review page is rebuilt from `issue_items` + immutable `brief_items` + reviewed sidecars. Therefore a previously rejected candidate is still visible when review is reopened and can be restored later.

## Feedback commit rule

A sidecar may exist before final validation so a reviewer does not lose typed edits when validation fails. That sidecar is **not** considered quality feedback yet.

Feedback tables are updated only after:

1. the requested approval/edit set is validated;
2. the approved issue is rebuilt;
3. the email is rebuilt;
4. the existing final renderer/email validator passes.

This prevents failed or abandoned edits from contaminating the feedback signal.

## Stored feedback

Two local SQLite tables are created lazily:

### `human_review_items`

One latest validated decision per issue/item:

- approved / rejected
- topic and direction snapshot
- number of changed fields
- reviewed sidecar path when present
- review timestamp

### `human_review_edits`

Only fields that differ from the immutable Agent text are stored:

- original text
- reviewed text
- `SequenceMatcher` similarity
- character delta
- review timestamp

If a field is reset to the Agent text, its diff row disappears on the next validated review.

## Telemetry

`python briefing.py stats --run <run>` gains `human_edit_feedback` with both the selected run and cumulative history:

- reviewed / approved / rejected items
- approval rate
- approved items with edits and item edit rate
- changed fields and field edit rate
- mean field text retention
- per-field change frequency
- per-field shorten / lengthen count and net character delta
- per-topic review / approval / rejection / edited-approved counts

The cumulative block is deliberately based on the latest validated state of each issue/item rather than every save click.

## Quality boundary

This PR does **not** automatically feed human edits into:

- relevance scoring
- Technology Value
- fact extraction
- item writing prompts
- issue synthesis
- Project Insight

The reason is sample efficiency and drift control. A few manual corrections may be one-off fixes rather than stable preferences. A later feedback-application layer can use this telemetry only after explicit minimum-sample and stability rules are defined and evaluated against Golden/production cases.

## Cost

Human review and diff computation are deterministic local work. They create no Agent task, no fulltext read, and no new model invocation.
