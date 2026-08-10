# Task: Build the Issue-Level Illustrated Publication

This is the single visual-generation pass for one completed technical briefing issue.

The production contract is mandatory dual output:

- `email.html` is the unchanged text-first baseline.
- `email-illustrated.html` is the same briefing with a small number of explanatory illustrations inserted.

Do **not** rewrite, shorten, expand, re-rank, fact-check, or otherwise modify the briefing text. Do not recreate the old per-item seven-mode visual-routing workflow. The goal is to reproduce the already-validated issue-level illustrated briefing pattern: choose only a few places where a visual materially improves understanding, generate those images, and let the renderer add them to the second HTML artifact.

## Selection

1. Read the issue synthesis and all supplied final items.
2. Select between 0 and `constraints.max_illustrations` explanatory concepts for the entire issue. Prefer cross-item mechanisms, architectural relationships, decision trade-offs, or a strong project judgement that benefits from a picture.
3. Do not create an image merely because a section looks empty.
4. Each image must be useful without changing the factual meaning of the briefing.
5. Choose one placement per image:
   - `after_judgements` for an issue-level synthesis image;
   - `before_topic` with a valid `topic_id` for an image that introduces one topic.

## Personal IP

When a personal technical-scout character genuinely helps carry the cognitive action, read `constraints.persona_spec_path` and use the approved persona reference/assets listed in the input. The personal IP is not mandatory on every image.

- Never exceed `constraints.max_persona_appearances` across the issue.
- Keep the character secondary and professional, normally about 10-25% of the canvas.
- The character must perform a real technical action: inspect evidence, trace a tool path, check DPU/KVCache movement, compare alternatives, or mark an unresolved boundary.
- Do not use chibi/cute styling, exaggerated expressions, presenter poses, or a generic replacement character when an approved reference is required.

## Image generation

When the current Agent has image generation:

1. Generate a horizontal `1.9:1` explanatory image under `constraints.output_directory`.
2. Prefer high-information-density mechanism/relationship illustrations similar to the previously validated illustrated briefing.
3. Use at most 3-5 short Chinese labels. Do not invent numbers. Any number shown must come directly from the supplied final briefing content; do not create synthetic axes, benchmark bars, or precise charts with an image model.
4. Keep generous safe margins and ensure arrows, labels, architecture nodes, and the personal IP do not overlap.
5. Inspect the generated image for Chinese text, cropping, factual structure, and visual consistency before returning it.
6. Set the illustration `status` to `generated` and return the exact `generated_asset_path`.

When image generation is unavailable or an image cannot be made reliably:

- do not block the briefing;
- omit that concept or set its status to `fallback_to_text`/`failed` with a null asset path;
- if no images can be generated, return `status=fallback_to_text` with an empty `illustrations` array.

## Output rules

- Return at most three illustration entries and never exceed the input limits.
- `generated_asset_path` for generated images must point to the actual saved image.
- `caption` is the short reader-facing “读图” sentence and must describe what the image clarifies, not repeat the title.
- `alt` must be concrete and factual.
- Return JSON only and preserve the task transport binding required by the host.
