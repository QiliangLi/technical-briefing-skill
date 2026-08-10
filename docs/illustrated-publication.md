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

The production flow intentionally uses one issue-level Agent task rather than one visual Agent task per briefing item:

```text
fact-checked issue + issue synthesis
  -> illustrated_publication task (one pass per issue)
     -> choose every distinct explanatory concept that materially improves understanding
     -> no fixed numeric illustration cap
     -> every generated image includes the approved personal technical-scout IP
     -> generate and QA images
     -> illustrations/manifest.json
  -> render email.html
  -> render email-illustrated.html from the same base content + manifest
  -> final reader validation
```

This matches the successful workflow used by the historical illustrated briefing: high-information-density diagrams are placed between issue-level judgement and selected topic sections instead of decorating individual cards without purpose.

The image count is content-driven rather than quota-driven. A dense issue may need more than three images; a sparse issue may need fewer or none. The Agent must avoid decorative, redundant, or near-duplicate images, but there is no fixed upper bound.

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

Image failure is never a briefing failure:

- the baseline `email.html` remains intact;
- missing or failed image entries are skipped;
- a generated image that does not include the required personal IP is not admitted to the illustrated artifact;
- `email-illustrated.html` is still produced;
- final validation continues to check the actual send artifact;
- exact factual text remains owned by the fact-checked briefing, not by the image model.

The default send artifact is the illustrated HTML because it is the final publication variant. Local generated images are converted to CID parts by the existing email send path; remote image URLs remain remote.
