# Task: Build the Issue-Level Illustrated Publication

This is the single visual-generation pass for one completed technical briefing issue.

The production contract is mandatory dual output:

- `email.html` is the unchanged text-first baseline.
- `email-illustrated.html` is the same briefing with explanatory illustrations inserted.

Do **not** rewrite, shorten, expand, re-rank, fact-check, or otherwise modify the briefing text. Do not recreate the old per-item seven-mode visual-routing workflow. The goal is to reproduce the already-validated issue-level illustrated briefing pattern: identify every distinct place where a visual materially improves understanding, generate those images, and let the renderer add them to the second HTML artifact.

## Host execution is mandatory

The illustration contract is the same on every host, but image generation is routed differently.

### Running inside Codex

Use the current Codex host's image-generation capability directly. Do not add an extra delegation layer just because this repository also supports Claude Code.

### Running inside Claude Code

Claude Code's model not having native image generation is **not** a reason to return `fallback_to_text`. This repository assumes the already-installed `openai/codex-plugin-cc` bridge is available for this case.

1. Invoke the plugin's **`codex:codex-rescue` subagent via the `Agent` tool**. It is a subagent, not a Skill; do not call `Skill(codex:codex-rescue)` or recursively invoke `/codex:rescue` from another Skill.
2. Delegate the **entire current `illustrated_publication` task once**, rather than delegating one image at a time. Use a fresh foreground Codex run (`--fresh --wait`) because the pipeline needs the generated assets and task JSON before `advance` can continue.
3. Forward enough exact task transport context for Codex to work in the same checkout: the current task input, this prompt, the required Schema/result binding, `constraints.output_directory`, Ian style/persona paths, and the expected task output path.
4. Tell Codex to use its image-generation capability to create all selected images under `constraints.output_directory`, perform the same QA below, and write the final Schema-valid task result JSON to the expected output path. The rescue runtime is write-capable and uses the same local repository checkout.
5. After Codex returns, Claude Code should verify that the expected output JSON and referenced image files exist and satisfy the Schema, then continue the normal task/`advance` flow. Do not paraphrase Codex stdout into a second, independently reconstructed manifest.
6. Only if the Codex bridge is unavailable, unauthenticated, or the delegated image-generation task actually fails may this task degrade to `fallback_to_text`. Lack of native Claude image generation alone is never a valid fallback reason.

The machine-readable version of this rule is also supplied as `constraints.host_execution_policy`.

## Sole image style: Ian + Qiliang persona overlay

All AI-generated briefing illustrations in this project use exactly one image-generation style/persona path:

1. Use the installed Skill named by `constraints.illustration_style_skill`. It must be `ian-xiaohei-illustrations`.
2. Read the Ian Skill's original style DNA, composition patterns, prompt template, and QA rules.
3. Then read `constraints.persona_overlay_path`; it replaces only Ian's recurring “小黑” character with the project Qiliang character.
4. Read `constraints.persona_reference_manifest_path`. Its `identity_anchor`, `action_anchor`, and `wide_scene_anchor` are the authoritative reference set.
5. Use the exact repository files supplied in `constraints.persona_reference_paths`. The task builder verifies these files exist before this task is created; still verify they are readable before generation.
6. Do **not** use Guizang Material Illustration, the old Guizang persona spec, `assets/persona/reference.jpg`, or a generic substitute character as an image-generation style or identity source.
7. Guizang remains relevant only to the existing HTML/card presentation contract. It must not influence the generated illustration's visual style or persona.
8. If the Ian Skill or the required Qiliang overlay/reference files are genuinely unavailable at execution time, return `fallback_to_text` rather than silently switching to another illustration style/persona.

Do not modify the installed Ian Skill or user/plugin directories. The project overlay is the only permitted character override.

## Selection

1. Read the issue synthesis and all supplied final items.
2. There is **no fixed numeric cap** on illustration count. Select as many distinct explanatory concepts as are genuinely useful for this issue.
3. Prefer cross-item mechanisms, architectural relationships, decision trade-offs, system paths, or strong project judgements that benefit from a picture.
4. Do not create an image merely because a section looks empty. Do not generate decorative, redundant, or near-duplicate images.
5. A dense issue may legitimately need more than three images; a sparse issue may need fewer or none.
6. Each image must be useful without changing the factual meaning of the briefing.
7. Choose one placement per image:
   - `after_judgements` for an issue-level synthesis image;
   - `before_topic` with a valid `topic_id` for an image that introduces one topic.

## Personal IP

Every AI-generated illustration must include the approved Qiliang Ian-style technical-scout IP from the project overlay/reference manifest.

- `persona_used` must be `true` for every illustration whose `status` is `generated`.
- The overlay is authoritative for appearance, clothing, expression, action semantics, and persona behavior; do not merge it with the retired Guizang persona description.
- The character remains secondary and professional, normally about 15-25% of the canvas; mandatory presence does not mean the character becomes a portrait subject.
- The character must physically perform the core conceptual action rather than merely observe it or decorate a corner.
- Vary the action and placement naturally across images when helpful, while preserving the same approved identity.
- Do not use chibi/cute styling, exaggerated expressions, presenter poses, signatures, author labels, or a generic replacement character.

## Image generation

Once the host routing above has provided an image-capable Codex execution context:

1. Generate a horizontal `1.9:1` explanatory image under `constraints.output_directory`.
2. Preserve Ian's white-background hand-drawn visual DNA, sparse colored annotations, generous whitespace, restrained absurd metaphor, and one-core-concept composition.
3. Use at most 3-5 short Chinese labels **per image**. Do not invent numbers. Any number shown must come directly from the supplied final briefing content; do not create synthetic axes, benchmark bars, or precise charts with an image model.
4. Keep generous safe margins and ensure arrows, labels, architecture nodes, and the personal IP do not overlap.
5. Inspect each generated image for Qiliang identity consistency, Ian visual consistency, Chinese text, cropping, factual structure, and visual clarity before returning it.
6. Set the illustration `status` to `generated`, set `persona_used=true`, and return the exact `generated_asset_path`.

When image generation is genuinely unavailable after applying the host-routing and Ian-style rules, or an individual image cannot be made reliably:

- do not block the briefing;
- omit that concept or set its status to `fallback_to_text`/`failed` with a null asset path;
- if no images can be generated, return `status=fallback_to_text` with an empty `illustrations` array.

## Output rules

- There is no fixed maximum number of illustration entries. Return one entry for each distinct concept that passed the usefulness and QA checks.
- Never pad the manifest with decorative or duplicate images just to increase image count.
- `generated_asset_path` for generated images must point to the actual saved image.
- `caption` is the short reader-facing “读图” sentence and must describe what the image clarifies, not repeat the title.
- `alt` must be concrete and factual.
- Return JSON only and preserve the task transport binding required by the host.
