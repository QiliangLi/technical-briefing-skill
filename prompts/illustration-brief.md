# Task: Prepare or Generate a Supporting Illustration

Use the visual plan and briefing item to prepare one central illustration compatible with Guizang Social Card.

When the current Agent has image generation:

1. Read the vendored Guizang Material Illustration SKILL and relevant references.
2. Generate one 1.9:1 horizontal supporting image with generous safe margins.
3. Save it under the requested output directory.
4. Inspect Chinese labels, arrows, cropping, factual structure, and visual consistency.
5. Set `status=generated` and provide `generated_asset_path`.

When image generation is unavailable:

1. Produce a complete reproducible prompt.
2. Set `status=waiting_for_image_generation`.
3. Leave `generated_asset_path` empty. The workflow will fall back to a source image or text card.

Personal technical-scout character rules:

- Use the approved reference image only when present.
- Stable features: short black hair, thin-frame glasses, white shirt, slightly loose dark-blue striped tie, calm and thoughtful expression.
- Professional, low-detail, restrained; not chibi, cute, theatrical, or presenter-like.
- Character occupies 10-25% of the image and performs a real action such as checking evidence, filtering duplicates, following a tool path, inspecting DPU offload, or moving KVCache blocks.

Return JSON only.
