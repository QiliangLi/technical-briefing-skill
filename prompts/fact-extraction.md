# Task: Evidence-First Fact Extraction

Read the source metadata, the short topic context, and the document/chunk files referenced in the input. Process one source only. Do not compare it with unrelated candidates.

Extract facts rather than writing the newsletter.

Required output:

- `title`: the source's factual title.
- `event_hint`: a short event-level identity that can merge an official blog, paper, release, and discussion about the same development.
- `problem`: what concrete problem is addressed.
- `mechanism`: how the system or technique works, with enough detail to distinguish it from generic caching/scheduling/offload.
- `evidence`: 0-5 evidence records. Every number must include baseline/condition when available and a source locator such as section, page, figure, table, heading, or quoted fragment under 20 words.
- `evaluation_context`: workload, scale, hardware/software, comparison baseline, or deployment context.
- `limitations`: explicit limitations plus clearly labelled inferences about missing validation.
- `project_relevance`: a project-oriented inference, clearly separate from source claims.
- `primary_source_resolved`: false when the available document is only a discovery summary or secondary report.
- `quality_score`: 0-100 based on completeness, evidence, and source quality.

Do not invent missing numbers. Do not use AI HOT's generated summary as sole evidence. Return JSON only.
