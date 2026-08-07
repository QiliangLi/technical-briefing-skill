# Task: Evidence-First Fact Extraction

Read the source metadata, the short topic context, and **only the evidence-pack file(s) referenced by `document.text_path` / `document.chunks` in the task input**. Process one source only. Do not compare it with unrelated candidates, and do not open unreferenced raw full-text files merely to increase completeness.

The evidence pack is a deterministic subset of the fetched primary source. It preserves section/page locators and prioritizes method, architecture, evaluation, quantitative results, limitations, and topic-specific terms. If the evidence pack is insufficient for a claim, omit the claim or record the missing validation in `limitations`; do not compensate by guessing.

The input `_task` object identifies this exact source task. Copy it unchanged into the top level of the output. If the document title or content does not match the input source metadata, stop and return no fabricated facts; never substitute facts from another source.

Extract facts rather than writing the newsletter.

Required output:

- `title`: copy the input source title exactly. Translation and editorial rewriting happen only in the later item-writing task.
- `event_hint`: a short event-level identity that can merge an official blog, paper, release, and discussion about the same development.
- `problem`: what concrete problem is addressed.
- `mechanism`: how the system or technique works, with enough detail to distinguish it from generic caching/scheduling/offload.
- `evidence`: 0-5 evidence records. Every number must include baseline/condition when available and a source locator such as section, page, figure, table, heading, or quoted fragment under 20 words.
- `evaluation_context`: workload, scale, hardware/software, comparison baseline, or deployment context.
- `limitations`: explicit limitations plus clearly labelled inferences about missing validation. If the evidence pack omits information needed to verify a stronger claim, say so here.
- `project_relevance`: a project-oriented inference, clearly separate from source claims.
- `primary_source_resolved`: true only when the input URL identifies a specific primary source and `document.fetch_status` is `FETCHED`; a cache hit may reuse a previously validated result for the same source fingerprint and extractor version.
- `quality_score`: 0-100 based on completeness, evidence, and source quality. Reduce the score when the evidence pack lacks evaluation conditions or important boundaries.
- `evidence_gaps`: normally `[]`. Add at most 3 entries only when a **material** fact needed for correct interpretation is missing from the evidence pack but is plausibly present elsewhere in this same source. Each entry must state a concrete `question` and 1-8 source-native `terms` suitable for deterministic section retrieval. Good gaps include the exact benchmark baseline, workload/hardware condition, deployment constraint, or explicit limitation needed to avoid a misleading claim. Do not request more text merely for completeness, background, or curiosity.

When creating `evidence_gaps`, use terms that are likely to appear literally in the source, such as a system name, baseline name, hardware model, metric, table/figure label, workload, or distinctive mechanism term. Do not use vague requests such as `more details`, `evaluation`, or `performance` alone.

Do not invent missing numbers. Do not use AI HOT's generated summary as sole evidence. Return JSON only.
