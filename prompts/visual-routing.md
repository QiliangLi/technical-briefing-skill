# Task: Visual Asset Routing

Choose the most useful visual evidence for one briefing item. The goal is understanding and credibility, not decorative illustration.

Priority order:

1. `source_figure`: a clear paper/official architecture figure.
2. `official_image`: official product/hardware/architecture image.
3. `screenshot`: real repository, UI, trace, or execution result.
4. `chart_redraw`: exact data can be programmatically redrawn.
5. `material_mechanism`: an abstract mechanism or process needs a labelled Guizang material illustration.
6. `persona_metaphor`: the key content is the author's project judgement, and the personal technical-scout character can carry the cognitive action.
7. `text_only`: no visual would add real information.

Rules:

- Never choose an AI image only because the card looks empty.
- Exact numerical charts must be generated programmatically, not by an image model.
- Use at most 3-5 short Chinese labels in a generated mechanism image.
- The personal character is secondary, professional, and must not cover evidence.
- `persona_metaphor` should be rare; use it for “why it matters / what to verify”, not for factual benchmark evidence.
- Return JSON only.
