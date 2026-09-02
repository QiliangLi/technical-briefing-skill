# Project Insight Layer

## Purpose

The briefing pipeline now separates three questions that should not be collapsed into one score:

1. **Topical relevance** — does the item belong to a configured technical topic/direction?
2. **Technology value** — is the mechanism, architecture change, industry signal, or project alignment important enough to prioritize for deep reading?
3. **Project insight** — after the selected evidence has been fact-checked, does it materially change one of the project's existing questions, and what should be done next?

Project Insight is intentionally issue-level. A single source is often not enough to change a project decision, and adding another per-item Agent pass would add cost without improving the evidence boundary.

## Pipeline

```text
fact-checked core briefing items
+ compact project context cards for topics actually present
        |
        v
existing issue_synthesis task
        |
        +--> cross-item judgements
        |
        +--> project_insights
                - configured project question
                - effect on current judgement
                - confidence
                - bounded project inference
                - concrete next action
                - exact evidence item IDs
```

No additional Agent task type, full-text fetch, or Evidence Pack is introduced.

## Project Insight contract

Each insight contains:

| Field | Meaning |
| --- | --- |
| `topic_id` / `topic_name` | Exact configured topic identity. |
| `project_question` | Exact question from the topic's configured `current_questions`; the Agent cannot invent a new project question. |
| `effect` | `supports`, `challenges`, `narrows`, or `opens`. |
| `confidence` | `high`, `medium`, or `low`; this is confidence in the project inference, not a source-quality score. |
| `insight` | A project judgement derived from the selected evidence. It must not be presented as a source fact. |
| `next_action` | A concrete experiment, measurement, implementation check, or decision step. |
| `evidence_item_ids` | Exact fact-checked core briefing items supporting the inference. |

An empty `project_insights` array is valid and preferred when the current issue does not materially change any configured project question.

## Evidence and semantic guards

New Project Insight synthesis tasks fail validation when they:

- invent or paraphrase a project question instead of selecting an exact configured question;
- reference an unknown or duplicate briefing item ID;
- cite no evidence from the same topic as the project question;
- use an unsupported effect or confidence value;
- return incomplete `insight` or `next_action` sentences;
- duplicate the same topic/question/effect insight;
- omit `project_insights` entirely.

The schema keeps the new top-level field optional so unfinished pre-PR18 `issue_synthesis` tasks remain resumable. New tasks carry `project_insights_required=true` metadata, which activates the semantic requirement.

## Topic coverage

Project context cards are built dynamically from `ConfigBundle.topic_list()` rather than from a hard-coded subset. The regression suite requires every configured topic to have both non-empty project questions and a project judgement card. This currently covers all nine deep topics plus the Frontier and horizontal AI-Infra observation topics, including the separately loaded chip, storage-media, accelerator-storage-I/O, and frontier extensions.

Only topics represented by selected core items are sent to one issue-synthesis task, avoiding irrelevant project context.

## Output and telemetry

Project insights are stored in the normal issue synthesis and exposed in the final email as a separate **项目影响** block. Every displayed insight links back to its evidence briefing items. Renderer validation fails if project insights exist in the issue but are not present in the email.

`python briefing.py stats --run <run>` exposes:

```text
project_insights:
  count
  by_effect
  by_topic
  evidence_item_refs
```

These metrics describe evidence-bound project judgements; they are not a quality score.

## Cost boundary

Project Insight reuses the existing `issue_synthesis` task, so task count does not increase. The only incremental Agent cost is the compact project context plus the structured insight output. It does not change:

- the configured 36-item deep Fact safety budget;
- the Front `<=18k` first-read budget;
- the one-pass `<=9k` Evidence Repair budget;
- source-resolution or A-level primary-source requirements;
- topic/project/direction diversity rules;
- per-item Fact Check.
