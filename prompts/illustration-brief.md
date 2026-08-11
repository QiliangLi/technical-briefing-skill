# Task: Prepare or Generate a Supporting Illustration

This prompt is retained only for legacy/compatibility runs. Prepare one central illustration that can be placed inside the existing Guizang Social Card/HTML layout, but **do not use Guizang as the image-generation style**.

The sole AI illustration path is:

```text
ian-xiaohei-illustrations
+ assets/persona/ian-qiliang/overlay.md
+ assets/persona/ian-qiliang/reference-manifest.yaml
```

Ignore legacy task-input fields such as `material_skill_path`, `persona_spec_path`, or `persona_reference` if they point to Guizang or `assets/persona/reference.jpg`. They are not authoritative for image generation anymore.

When the current Agent has image generation:

1. Read and follow the installed `ian-xiaohei-illustrations` Skill.
2. Read `assets/persona/ian-qiliang/overlay.md`; replace only Ian's recurring character with Qiliang.
3. Read `assets/persona/ian-qiliang/reference-manifest.yaml` and verify its identity/action/wide-scene anchor files exist before generation.
4. Generate one 1.9:1 horizontal supporting image with Ian's white-background hand-drawn visual DNA, generous whitespace, restrained annotations, and a single core concept.
5. Save it under the requested output directory.
6. Inspect Chinese labels, arrows, cropping, factual structure, Ian visual consistency, and Qiliang identity consistency.
7. Set `status=generated` and provide `generated_asset_path`.

When image generation is unavailable, the Ian Skill is unavailable, or any required Qiliang reference anchor is missing:

1. Do not substitute Guizang Material Illustration, a generic technical scout, or another persona.
2. Produce a complete reproducible Ian/Qiliang prompt when useful.
3. Set `status=waiting_for_image_generation` or the closest schema-valid fallback state expected by the legacy task.
4. Leave `generated_asset_path` empty. The workflow will fall back to a source image or text card.

Personal technical-scout rules come only from the Qiliang overlay/reference manifest:

- Short slightly tousled black hair and thin black round/softly-rounded glasses.
- Black knit sweater over a crisp white shirt collar, dark trousers, calm serious expression.
- Professional, hand-drawn, restrained, slightly absurd; not chibi, cute, theatrical, or presenter-like.
- Character normally occupies about 15-25% of the image and physically performs the core conceptual action.
- Never add the retired white-shirt/blue-tie Guizang persona description to the Ian character.

The Guizang Social Card/HTML layout remains unchanged; only the image-generation style/persona is replaced.

Return JSON only.
