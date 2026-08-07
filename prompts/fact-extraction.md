# Task: Evidence-First Fact Extraction

Process one source. Read source metadata, the short topic context, and **only** the Evidence Pack referenced by `document.text_path` / `document.chunks`. The normal Evidence Pack is the beginning of the primary source (roughly abstract + introduction + early design context), not a claim that later evaluation sections were reviewed. Do not open unreferenced raw full text, compare unrelated candidates, or guess missing facts. Copy the input `_task` unchanged to the top level of the output. `title` must exactly match the input source title.

Return structured facts, not newsletter prose:

- `event_hint`: short event identity.
- `problem`: concrete problem addressed.
- `mechanism`: distinguishing design/mechanism.
- `evidence`: 0-5 strongest records already supported by the visible Evidence Pack. Keep material baseline/condition for every number and a precise section/page/figure/table/heading locator.
- `evaluation_context`: workload, scale, hardware/software, baseline, or deployment context that is actually visible.
- `limitations`: explicit limits and clearly labelled missing validation.
- `project_relevance`: project inference, separate from source facts.
- `primary_source_resolved`: true only for a specific primary-source URL with `document.fetch_status=FETCHED` or an exact validated cache hit.
- `quality_score`: 0-100; reduce it when important conditions/boundaries are missing.
- `evidence_gaps`: normally `[]`. Add at most 3 only when a missing fact would materially change the final briefing and is plausibly later in this same source, such as the exact baseline behind a headline speedup, workload/hardware condition, deployment constraint, or explicit limitation. Each gap needs a concrete `question` and 1-8 source-native literal `terms` (system/baseline/hardware/metric/table/workload names) for deterministic retrieval. Never request later text merely for completeness.

Treat abstract/introduction performance claims as **claims**, not fully verified experiment facts, when the visible front evidence omits their baseline or material conditions. In that case either weaken the claim or request the specific missing evidence through `evidence_gaps`; the one-shot repair stage will search only the unread suffix of the same primary source.

If evidence is insufficient, weaken or omit the claim and record the gap; do not invent numbers. AI HOT summaries may explain discovery provenance, but final facts must come from the fetched primary source. Return JSON only.
