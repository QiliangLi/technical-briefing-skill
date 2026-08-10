# Illustrated Publication Contract

This document records the visual workflow that has already been validated on the committed `2026-08-09-193020-replay-pr27-33` briefing and is now the production contract.

## Two artifacts are mandatory

Every completed run publishes both files:

```text
workspace/runs/<run_id>/email.html
workspace/runs/<run_id>/email-illustrated.html
```

`email.html` is the text-first baseline. `email-illustrated.html` contains the same reader-facing briefing text plus a small number of explanatory illustrations. Illustration generation must never rewrite or re-rank the briefing.

If image generation is unavailable or every image fails QA, `email-illustrated.html` is still created and deterministically degrades to the baseline content. The second artifact is not optional; only the number of successfully generated images may fall to zero.

## Verified issue-level workflow

The production flow intentionally uses one issue-level Agent task rather than one visual Agent task per briefing item:

```text
fact-checked issue + issue synthesis
  -> illustrated_publication task (one pass per issue)
     -> choose 0-3 genuinely useful explanatory concepts
     -> optionally use the approved personal technical-scout IP at most twice
     -> generate and QA images
     -> illustrations/manifest.json
  -> render email.html
  -> render email-illustrated.html from the same base content + manifest
  -> final reader validation
```

This matches the successful workflow used by the historical illustrated briefing: a few high-information-density diagrams are placed between issue-level judgement and selected topic sections instead of decorating every card.

## Personal IP

The personal visual identity remains the `技术侦察员` defined in `assets/persona/persona-spec.yaml`. Approved persona artwork under `pics/圆框形象/` and `pics/方框形象/` may be used as visual references.

- maximum two appearances per issue;
- normally 10-25% of the canvas;
- professional, restrained, evidence-oriented actions only;
- no chibi/cute styling, exaggerated presenter poses, or evidence occlusion;
- using the persona is optional per image, not optional per publication workflow.

## What is no longer the production workflow

The older per-item design (`visual_routing` -> seven visual modes -> per-item `illustration_brief`) was a broader architecture sketch and was not the path used by the validated illustrated briefing. The active runtime supersedes that execution path with the single issue-level `illustrated_publication` stage.

In particular, production should not create an Agent task for every detailed card merely to decide between `source_figure`, `official_image`, `screenshot`, `chart_redraw`, `material_mechanism`, `persona_metaphor`, and `text_only`. Those concepts may remain useful design vocabulary, but they are not separate production stages or invocation requirements.

## Failure semantics

Image failure is never a briefing failure:

- the baseline `email.html` remains intact;
- missing or failed image entries are skipped;
- `email-illustrated.html` is still produced;
- final validation continues to check the actual send artifact;
- exact factual text remains owned by the fact-checked briefing, not by the image model.

The default send artifact is the illustrated HTML because it is the final publication variant. Local generated images are converted to CID parts by the existing email send path; remote image URLs remain remote.
