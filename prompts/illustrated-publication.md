# Task: Build the Topic-Scoped Illustrated Publication

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

## Selection: at most one image per topic

The purpose of an illustration is to make the topic's key information intuitively understandable, not to maximize image count.

1. Each supplied `topic_id` may receive **zero or one** image. The total image count never exceeds the number of topics.
2. Rank items inside a topic by the supplied `score` and prefer items with `in_issue_judgements=true`; observation items may inform the picture but must not crowd out key core items.
3. When one key item dominates the topic, the image explains that item's central mechanism. When several key items matter, design **one** image that synthesizes their shared mechanism or the topic-level judgement; never build a collage of unrelated motifs.
4. Skip the topic entirely when no honest visual synthesis exists. An empty manifest is valid; decorative or near-duplicate filler is not.
5. Every generated image must record `bound_item_ids`: 1-4 `brief_item_id` values from the **same** topic that the image actually explains.
6. Each image must preserve the factual meaning of the bound items. Never mix measurements or mechanisms from different items into one causal picture.

## Placement

There is exactly one placement: `before_topic` with a valid `topic_id`. Python inserts the image immediately before that topic's header in the email, so a reader can always attribute the image to the topic it explains.

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
3. Use at most 3-5 short Chinese labels per image. Never invent numbers; any displayed number must come directly from the bound items.
4. Keep safe margins and prevent overlap among arrows, labels, architecture nodes, and the persona.
5. Inspect every image for identity consistency, visual-style consistency, Chinese text, cropping, factual structure, and clarity.
6. Keep `generated_asset_path` as the exact repository-relative local path used for QA.
7. The `caption` must name the covered items (their short titles) so the reader can map the image back to its cards.

## Mandatory asset publication

A local image is **not** a valid email asset. Before returning any illustration with `status=generated`:

1. Save it only under the repository-relative `constraints.output_directory`, which is a stable `published-assets/<run_id>/` directory. Do not put publishable images under `workspace/runs`.
2. Stage only the generated publication assets needed by this issue. Do not stage unrelated working-tree changes.
3. Publish the assets on GitHub in two immutable forms:
   - Primary: commit the assets, push, read the exact 40-character commit SHA, and construct the raw URL described by `constraints.asset_publication_policy.preferred_url_format`;
   - Backup: upload the same files as assets of a GitHub release tagged for this run (for example `illustrations-<run_id>`) and record the release download URL.
4. Construct both URLs exactly as described by `constraints.asset_publication_policy.preferred_url_format` (raw, primary) and `backup_url_format` (release, backup).
5. Verify that each URL points to the same generated asset and return them as `published_asset_url` (raw primary) and `backup_asset_url` (release backup).

For a generated item, both are required:

- `generated_asset_path`: repository-relative local path used for generation/QA;
- `published_asset_url`: `https://raw.githubusercontent.com/<owner>/<repo>/<40-char-commit-sha>/<path>` (primary);
- `backup_asset_url`: `https://github.com/<owner>/<repo>/releases/download/<release-tag>/<asset-filename>` (backup; may be null only when the release upload genuinely failed, which must be explained in `qa_notes`).

Never return a branch-name URL such as `/main/...`; the email must remain stable even after later commits. Never expose `/home/...`, `/Users/...`, `file://...`, `workspace/...`, or a bare relative path in reader-facing HTML.

If the asset cannot be committed and pushed reliably, that illustration is not publishable: use `fallback_to_text`/`failed`, or return an issue-level `fallback_to_text` when none can be published.

## Output rules

- There is no minimum image count and no reward for volume: return one entry per topic you decided to illustrate, and nothing else.
- Never pad the manifest to increase image count.
- Every generated entry must have a real local `generated_asset_path`, an immutable published GitHub `published_asset_url` (release download URL or commit-SHA-pinned raw URL), `persona_used=true`, `topic_id`, non-empty `bound_item_ids` from that topic, factual `alt`, and a concise reader-facing `caption` that names the covered items.
- `caption` should explain what the picture clarifies rather than repeat the title.
- Return JSON only and preserve the task transport binding required by the host.
