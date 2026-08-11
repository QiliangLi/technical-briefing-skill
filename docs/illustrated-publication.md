# Illustrated Publication Contract

This document records the visual workflow that has already been validated on the committed `2026-08-09-193020-replay-pr27-33` briefing and is now the production contract.

## Two artifacts are mandatory

Every completed run publishes both files:

```text
workspace/runs/<run_id>/email.html
workspace/runs/<run_id>/email-illustrated.html
```

`email.html` is the text-first baseline. `email-illustrated.html` contains the same reader-facing briefing text plus explanatory illustrations. Illustration generation must never rewrite or re-rank the briefing.

If image generation is unavailable or every image fails QA, `email-illustrated.html` is still created and deterministically degrades to the baseline content. The second artifact is not optional; only the number of successfully generated images may fall to zero.

## Verified issue-level workflow

The factual/text issue is finalized and its baseline email is rendered before any issue-level illustration task starts. `issue/issue.json` is therefore an immutable publication input, and `email.html` is already available regardless of image-generation success:

```text
fact-checked issue + issue synthesis
  -> finalize immutable issue/issue.json
  -> render deterministic email.html baseline
  -> READY_FOR_RENDER
  -> illustrated_publication task (one pass per issue)
     -> read only the finalized IssueDocument
     -> choose every distinct explanatory concept that materially improves understanding
     -> no fixed numeric illustration cap
     -> every generated image includes the approved personal technical-scout IP
     -> generate and QA images
     -> illustrations/manifest.json
  -> render email-illustrated.html from the exact baseline + manifest
  -> final reader validation on the actual send artifact
```

The important dependency rule is that illustration generation may delay the final enhanced publication artifact, but it can never delay or rewrite `issue/issue.json` or the baseline `email.html`. The run is promoted to final validation/send only after the illustration task has either produced a valid manifest or explicitly degraded to text.

This matches the successful workflow used by the historical illustrated briefing: high-information-density diagrams are placed between issue-level judgement and selected topic sections instead of decorating individual cards without purpose.

The image count is content-driven rather than quota-driven. A dense issue may need more than three images; a sparse issue may need fewer or none. The Agent must avoid decorative, redundant, or near-duplicate images, but there is no fixed upper bound.

## Host-specific image generation

The publication contract is host-independent; only the way the `illustrated_publication` task reaches an image-capable Codex runtime differs.

### Codex host

When the whole Skill is running in Codex, the Agent uses the current Codex image-generation capability directly. There is no delegation hop and no special setup in the briefing workflow.

### Claude Code host

The Claude Code models used for this workflow currently do not provide native image generation. That must **not** be interpreted as `image generation unavailable`.

The expected Claude Code setup already has [`openai/codex-plugin-cc`](https://github.com/openai/codex-plugin-cc) installed. For `illustrated_publication`, Claude Code must:

1. invoke the plugin's `codex:codex-rescue` **subagent** through the Claude Code `Agent` tool;
2. delegate the entire current issue-level illustration task in one fresh foreground run (`--fresh --wait`), not one Codex task per image;
3. forward the same task input, Prompt, Schema/result binding, persona references, output directory and expected result path;
4. let Codex generate and QA all selected images in the same repository checkout and write the Schema-valid task result JSON itself;
5. verify the produced task JSON/assets and then continue the ordinary `advance` flow.

`codex:codex-rescue` is a subagent, not a Skill. Do not call `Skill(codex:codex-rescue)` and do not recursively wrap `/codex:rescue` inside another Skill. The plugin's rescue runtime is write-capable and uses the same local Codex installation/authentication and repository checkout.

The reason for using a single foreground delegated task is important: image count remains content-driven, but delegation count does not scale with image count. The factual IssueDocument and baseline email are already complete before delegation starts; only the enhanced publication artifact waits for the image-capable task.

Only a genuine bridge failure (plugin unavailable, Codex unauthenticated, delegated run failure, or image QA failure) may trigger `fallback_to_text` on Claude Code. The absence of native Claude image generation by itself is never a fallback condition.

## Personal IP

The personal visual identity remains the `技术侦察员` defined in `assets/persona/persona-spec.yaml`. Approved persona artwork under `pics/圆框形象/` and `pics/方框形象/` may be used as visual references.

For every AI-generated explanatory illustration:

- the approved personal IP must appear;
- the character is normally about 10-25% of the canvas and remains secondary to the technical mechanism;
- the character performs a real technical action such as inspecting evidence, tracing a path, checking DPU/KVCache movement, comparing alternatives, or marking a boundary;
- role and placement may vary across images while identity remains stable;
- no chibi/cute styling, exaggerated presenter poses, generic replacement character, or evidence occlusion.

Mandatory IP presence is a visual-identity invariant, not a requirement for the character to dominate the composition.

## What is no longer the production workflow

The older per-item design (`visual_routing` -> seven visual modes -> per-item `illustration_brief`) was a broader architecture sketch and was not the path used by the validated illustrated briefing. The active runtime supersedes that execution path with the single issue-level `illustrated_publication` stage.

In particular, production should not create an Agent task for every detailed card merely to decide between `source_figure`, `official_image`, `screenshot`, `chart_redraw`, `material_mechanism`, `persona_metaphor`, and `text_only`. Those concepts may remain useful design vocabulary, but they are not separate production stages or invocation requirements.

## Failure semantics

Image failure is never a briefing-content failure:

- the immutable `issue/issue.json` and baseline `email.html` are already complete before image generation starts;
- missing or failed image entries are skipped;
- a generated image that does not include the required personal IP is not admitted to the illustrated artifact;
- on Claude Code, failure means the Codex bridge/task actually failed, not merely that Claude lacks native image generation;
- `email-illustrated.html` is still produced;
- final validation continues to check the actual send artifact;
- exact factual text remains owned by the fact-checked briefing, not by the image model.

The default send artifact is the illustrated HTML because it is the final publication variant. Local generated images are converted to CID parts by the existing email send path; remote image URLs remain remote.
