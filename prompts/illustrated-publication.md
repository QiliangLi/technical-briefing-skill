# Task: Build the Issue-Level Illustrated Publication

This is the single visual-generation pass for one completed technical briefing issue.

The publication contract is mandatory dual output:

- `email.html` is the unchanged text-first baseline.
- `email-illustrated.html` is the same briefing with explanatory illustrations inserted.

Do **not** rewrite, shorten, expand, re-rank, fact-check, or otherwise modify the briefing text. The visual task owns only illustration selection, generation, QA, publication, and the structured illustration manifest.

## Host execution is mandatory

### Running inside Codex

Use the current Codex host image-generation capability directly. Do not add an extra delegation layer.

### Running inside Claude Code

Claude Code not having native image generation is **not** a reason to return `fallback_to_text`. Use the installed `openai/codex-plugin-cc` bridge:

1. Invoke the `codex:codex-rescue` subagent with the Agent tool.
2. Delegate the **entire current `illustrated_publication` task once**, using a fresh foreground run (`--fresh --wait`).
3. Forward the task input, prompt/schema/result binding, output directory, Ian style/persona paths, and expected output path.
4. Codex generates and QA-checks all selected images in the same checkout and writes the final Schema-valid result.
5. Claude Code verifies the output JSON and referenced assets, then resumes the normal pipeline.
6. Only a real bridge/auth/image-task failure may degrade to `fallback_to_text`.

The machine-readable version of this rule is supplied as `constraints.host_execution_policy`.

## Sole image style: Ian + Qiliang persona overlay

All generated briefing illustrations use exactly one image-generation style/persona path:

1. Use `constraints.illustration_style_skill`; it must be `ian-xiaohei-illustrations`.
2. Read that Skill's style DNA, composition patterns, prompt template, and QA rules.
3. Read `constraints.persona_overlay_path`; it replaces only Ian's recurring character with the project Qiliang character.
4. Read `constraints.persona_reference_manifest_path` and the exact files in `constraints.persona_reference_paths`.
5. Do **not** use Guizang Material Illustration, the retired Guizang persona, `assets/persona/reference.jpg`, or a generic substitute for image generation.
6. Guizang remains relevant only to the existing HTML/card presentation contract. It must not influence generated-image style or persona.
7. If the Ian Skill or required Qiliang references are genuinely unavailable, return `fallback_to_text` instead of silently changing style/persona.

## Selection

1. Read the issue synthesis and all supplied final items.
2. There is **no fixed numeric cap**. Select every distinct explanatory concept that materially improves understanding, but never create decorative or near-duplicate filler.
3. Prefer cross-item mechanisms, architectural relationships, decision trade-offs, system paths, and strong project judgements.
4. Each image must preserve the factual meaning of the final briefing.
5. Choose one placement per image:
   - `after_judgements` for an issue-level synthesis image;
   - `before_topic` with a valid `topic_id` for an image introducing one topic.

## Personal IP

Every generated illustration must include the approved Qiliang Ian-style technical-scout IP.

- `persona_used=true` is mandatory for every `status=generated` item.
- Keep the character secondary and professional, normally around 15-25% of the canvas.
- The character must physically perform the central conceptual action rather than decorate a corner.
- Preserve identity consistency while varying action/placement naturally.
- Do not use chibi styling, exaggerated expressions, presenter poses, signatures, author labels, or generic substitute characters.

## Image generation and QA

1. Generate a horizontal `1.9:1` explanatory image under `constraints.output_directory`.
2. Preserve Ian's white-background hand-drawn visual DNA, sparse colored annotations, generous whitespace, restrained metaphor, and one-core-concept composition.
3. Use at most 3-5 short Chinese labels per image. Never invent numbers; any displayed number must come directly from the final briefing.
4. Keep safe margins and prevent overlap among arrows, labels, architecture nodes, and the persona.
5. Inspect every image for identity consistency, visual-style consistency, Chinese text, cropping, factual structure, and clarity.
6. Keep `generated_asset_path` as the exact repository-relative local path used for QA.

## Mandatory asset publication

A local image is **not** a valid email asset. Before returning any illustration with `status=generated`:

1. Save it only under the repository-relative `constraints.output_directory`, which is a stable `published-assets/<run_id>/` directory. Do not put publishable images under `workspace/runs`.
2. Stage only the generated publication assets needed by this issue. Do not stage unrelated working-tree changes.
3. Publish the assets on GitHub in one of two immutable forms:
   - Preferred: upload as assets of a GitHub release tagged for this run (for example `illustrations-<run_id>`) and use the release download URL;
   - Also accepted: commit the assets, push, read the exact 40-character commit SHA, and construct the raw URL described by `constraints.asset_publication_policy.accepted_url_format`.
4. Construct the immutable URL exactly as described by `constraints.asset_publication_policy.preferred_url_format` (release) or `accepted_url_format` (raw).
5. Verify that the URL points to the same generated asset and return it as `published_asset_url`.

For a generated item, both are required:

- `generated_asset_path`: repository-relative local path used for generation/QA;
- `published_asset_url`: either `https://github.com/<owner>/<repo>/releases/download/<release-tag>/<asset-filename>` or `https://raw.githubusercontent.com/<owner>/<repo>/<40-char-commit-sha>/<path>`.

Never return a branch-name URL such as `/main/...`; the email must remain stable even after later commits. Never expose `/home/...`, `/Users/...`, `file://...`, `workspace/...`, or a bare relative path in reader-facing HTML.

If the asset cannot be committed and pushed reliably, that illustration is not publishable: use `fallback_to_text`/`failed`, or return an issue-level `fallback_to_text` when none can be published.

## Output rules

- There is no fixed maximum number of illustration entries.
- Never pad the manifest to increase image count.
- Every generated entry must have a real local `generated_asset_path`, an immutable published GitHub `published_asset_url` (release download URL or commit-SHA-pinned raw URL), `persona_used=true`, factual `alt`, and a concise reader-facing `caption`.
- `caption` should explain what the picture clarifies rather than repeat the title.
- Return JSON only and preserve the task transport binding required by the host.
