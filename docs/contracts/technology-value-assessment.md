# Technology Value Assessment

## Goal

Topical relevance and technical importance are related but not identical.

A routine compatibility release can be highly relevant to a topic while contributing little new architecture or design information. Conversely, a new scheduling, memory, network, storage, or accelerator architecture may deserve a deep-analysis slot even when its lexical/topic relevance score is slightly lower.

PR17 adds a separate technology-value signal. It does **not** replace relevance, source quality, evidence requirements, or the existing project/direction diversity policy.

## Dimensions

Each relevance-batch result may include four 0-5 dimensions:

- `novelty`: new mechanism, abstraction, algorithm, architecture, or capability;
- `architecture_impact`: effect on system boundary, data/control path, hierarchy, placement, scheduling, or deployment architecture;
- `industry_signal`: strength of evidence that the change represents a broader ecosystem/research/platform direction rather than an isolated maintenance event;
- `project_alignment`: degree to which the change affects a current project hypothesis, experiment, implementation choice, or risk.

Python recomputes the total from the four dimensions; an Agent cannot inflate a separate total field.

## Ranking semantics

Deep selection keeps the existing constraints:

- total deep Fact budget;
- per-topic budget;
- per-direction diversity;
- same-project cap.

Within those constraints, the ordering signal is:

```text
technology_selection_score = 0.80 * relevance_score + technology_value_total
```

where `technology_value_total` is in `[0, 20]`.

This gives relevance 80% of the normalized ranking signal while allowing a high-value architecture change to outrank a routine but highly topical update. It does not permit an unrelated candidate into the deep channel because the existing relevance/fulltext/source gates run first.

Final event scoring gets only a small centered technology-value adjustment (at most about +/-6 points); evidence quality and relevance remain dominant.

## Cache semantics

Technology value is cached only alongside an eligible relevance cache entry and uses the same:

- source fingerprint;
- topic;
- direction;
- evaluator version.

Because the evaluator version already hashes the relevance prompt/schema, compact topic/direction cards, project context, and freshness bucket, changes to those inputs invalidate both relevance reuse and technology-value reuse.

## Telemetry

`python briefing.py stats --run latest` adds a `technology_value` block with:

- assessed candidate count;
- average score (0-20);
- number of candidates >=15;
- per-topic count/average/max.

This is a ranking diagnostic, not a quality score and not a substitute for Golden Eval or Fact Check.
