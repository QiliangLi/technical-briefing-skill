# Task: Evidence-First Fact Extraction

Read the source metadata, the short topic context, and the document/chunk files referenced in the input. Process one source only. Do not compare it with unrelated candidates.

The input `_task` object identifies this exact source task. Copy it unchanged into the top level of the output. If the document title or content does not match the input source metadata, stop and return no fabricated facts; never substitute facts from another source.

Extract facts rather than writing the newsletter.

Required output:

- `title`: copy the input source title exactly. Translation and editorial rewriting happen only in the later item-writing task.
- `event_hint`: a short event-level identity that can merge an official blog, paper, release, and discussion about the same development.
- `problem`: what concrete problem is addressed.
- `mechanism`: how the system or technique works, with enough detail to distinguish it from generic caching/scheduling/offload.
- `evidence`: 0-5 evidence records. Every number must include baseline/condition when available and a source locator such as section, page, figure, table, heading, or quoted fragment under 20 words.
- `evaluation_context`: workload, scale, hardware/software, comparison baseline, or deployment context.
- `limitations`: explicit limitations plus clearly labelled inferences about missing validation.
- `project_relevance`: a project-oriented inference, clearly separate from source claims.
- `primary_source_resolved`: true only when the input URL identifies a specific primary source and the referenced document was fetched; otherwise false.
- `quality_score`: 0-100 based on completeness, evidence, and source quality.

Do not invent missing numbers. Do not use AI HOT's generated summary as sole evidence. Return JSON only.
