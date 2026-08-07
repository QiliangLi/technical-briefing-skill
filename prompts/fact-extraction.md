# Task: Evidence-First Fact Extraction

Process one source. Read source metadata, the short topic context, and **only** the Evidence Pack referenced by `document.text_path` / `document.chunks`. Do not open unreferenced raw full text, compare unrelated candidates, or guess missing facts. Copy the input `_task` unchanged to the top level of the output. `title` must exactly match the input source title.

Return structured facts, not newsletter prose:

- `event_hint`: short event identity.
- `problem`: concrete problem addressed.
- `mechanism`: distinguishing design/mechanism.
- `evidence`: 0-5 strongest records. Keep material baseline/condition for every number and a precise section/page/figure/table/heading locator.
- `evaluation_context`: workload, scale, hardware/software, baseline, or deployment context.
- `limitations`: explicit limits and clearly labelled missing validation.
- `project_relevance`: project inference, separate from source facts.
- `primary_source_resolved`: true only for a specific primary-source URL with `document.fetch_status=FETCHED` or an exact validated cache hit.
- `quality_score`: 0-100; reduce it when important conditions/boundaries are missing.
- `evidence_gaps`: normally `[]`. Add at most 3 only when a missing fact would materially change interpretation and is plausibly elsewhere in this same source, such as an exact baseline, workload/hardware condition, deployment constraint, or explicit limitation. Each gap needs a concrete `question` and 1-8 source-native literal `terms` (system/baseline/hardware/metric/table/workload names) for deterministic retrieval. Never request more text merely for completeness.

If evidence is insufficient, weaken or omit the claim and record the gap; do not invent numbers. AI HOT summaries are discovery hints, never sole evidence. Return JSON only.
