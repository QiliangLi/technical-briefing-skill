# Golden Quality Eval

This directory contains versioned deterministic regression cases for technical-briefing fact quality.

## What v1 protects

The initial `v1` corpus is synthetic and focuses on failure modes that are easy to measure deterministically:

- mechanism retention;
- numeric result retention;
- material baseline retention;
- workload/hardware/network condition retention;
- boundary/limitation retention;
- primary-source-resolution flag;
- rejection of known unsupported conclusions.

Run the checked-in baseline:

```bash
python scripts/run_golden_eval.py
```

Evaluate a candidate set of structured Fact outputs:

```bash
python scripts/run_golden_eval.py \
  --manifest eval/golden/v1/manifest.json \
  --results /path/to/candidate-results.json \
  --output /tmp/golden-report.json
```

The results file is an object keyed by case id, either directly or under a top-level `results` field.

## Merge policy

The synthetic v1 gate is intentionally not enough to justify aggressive quality/cost changes by itself. Before changing any of the following, add frozen production-primary-source cases with accepted assertions/results:

- first-read Evidence Pack size (currently Front <=18k);
- supplemental Evidence Repair budget (currently <=9k once);
- total/per-topic deep Fact budget;
- relevance or issue thresholds;
- required fact fields;
- primary-source requirements;
- Fact Check coverage.

A future change should fail closed if it loses a required mechanism, numeric baseline/condition, boundary, locator, or introduces a forbidden unsupported claim.

## Adding a case

Each manifest case should include:

1. a stable case id and technical routing context;
2. a source excerpt or source reference suitable for regenerating the result;
3. required fields;
4. mechanism/boundary terms that must survive extraction;
5. important evidence with exact value plus baseline/condition/locator terms;
6. unsupported claims that must never appear.

For production cases, prefer immutable primary-source versions (arXiv `vN`, DOI-backed publication, GitHub release/tag/commit) and keep source licensing/copyright constraints in mind. Store assertions and short source references rather than copying unnecessary full documents into the repository.
