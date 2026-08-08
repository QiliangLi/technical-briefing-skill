# Execution Telemetry Requirements

## Goal

Every complete technical briefing generation run should leave enough execution data to answer:

- How much model work was performed?
- Which pipeline stage consumed the most resources?
- Did an optimization reduce cost without reducing quality?

Telemetry is a mandatory part of a production run, not an optional post-processing step.

## Default behavior

After a successful end-to-end generation, the workflow MUST automatically run:

```bash
python briefing.py stats --run latest
```

A full generation run should not be considered complete until statistics are collected.

## Metrics

The telemetry layer should record:

### Pipeline metrics

- run id
- git revision / skill version
- topic configuration version
- task counts by stage
- cache hit rates
- agent session grouping
- wall clock time

### Token metrics (when executor exposes usage)

The skill must not depend on a specific model provider. Supported executors may report:

- model name
- input tokens
- output tokens
- cached tokens
- latency

If the executor does not expose token usage, the report must clearly state that token usage is unavailable and fall back to deterministic cost proxies.

## Cost attribution

Statistics should be grouped by stage:

- collection
- relevance analysis
- fact extraction
- evidence repair
- writing
- fact checking
- rendering

## Quality correlation

Telemetry should be stored together with quality indicators:

- primary source resolution rate
- evidence gap rate
- fact check pass rate
- golden evaluation score

The objective is to optimize cost while preserving output quality.
