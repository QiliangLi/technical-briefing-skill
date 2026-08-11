# Persona references

The active briefing illustration persona is the project-local Qiliang override for `ian-xiaohei-illustrations`.

Authoritative files:

```text
assets/persona/ian-qiliang/overlay.md
assets/persona/ian-qiliang/reference-manifest.yaml
```

`reference-manifest.yaml` points to the required identity, action, and wide-scene image anchors under `pics/`. The runtime validates that every required anchor exists before creating `illustrated_publication`.

Do not add or rely on `assets/persona/reference.jpg` for new briefing illustrations. Do not substitute the retired Guizang persona or a generic technical-scout character when an Ian/Qiliang reference is missing; fail the image path explicitly and preserve the text-first briefing instead.

The Guizang-derived HTML/card presentation remains independent from this image-generation contract and is intentionally unchanged.
