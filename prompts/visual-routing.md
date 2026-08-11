# Task: Visual Asset Routing

Choose the most useful visual evidence for one briefing item. The goal is understanding and credibility, not decorative illustration.

This prompt exists only for legacy/compatibility runs. New runs use the single issue-level `illustrated_publication` task. If an AI-generated illustration is still required here, its image style/persona must follow `ian-xiaohei-illustrations` plus the project Qiliang overlay; Guizang is not an image-generation style.

Priority order:

1. `source_figure`: a clear paper/official architecture figure.
2. `official_image`: official product/hardware/architecture image.
3. `screenshot`: real repository, UI, trace, or execution result.
4. `chart_redraw`: exact data can be programmatically redrawn.
5. `material_mechanism`: an abstract mechanism or process needs an Ian-style explanatory illustration.
6. `persona_metaphor`: the key content is the author's project judgement, and the Qiliang Ian-style technical-scout character can carry the cognitive action.
7. `text_only`: no visual would add real information.

Rules:

- Never choose an AI image only because the card looks empty.
- Exact numerical charts must be generated programmatically, not by an image model.
- Use at most 3-5 short Chinese labels in a generated mechanism image.
- Any generated character must be the approved Qiliang Ian persona and must perform a real conceptual action.
- Do not request or fall back to Guizang Material Illustration or the retired Guizang persona.
- The existing Guizang Social Card/HTML layout may still host the resulting image; layout style and image-generation style are separate concerns.
- Return JSON only.
