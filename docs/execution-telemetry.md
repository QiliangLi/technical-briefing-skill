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

### Pipeline metrics

- run id
- git revision / skill version
- topic configuration version
- task counts by stage
- cache hit rates
- agent session grouping
- wall clock time

### Token metrics

The deterministic task telemetry remains useful for repeatable regressions, but
`agent_read_chars_proxy` is **not** an API/Claude/Codex token bill. It measures the
business payload written by the pipeline and does not include executor/harness context,
prompt-cache traffic, or host orchestration.

When executor transcripts expose usage, import the actual counters and keep their
components separate:

- `input_tokens`
- `cache_creation_input_tokens`
- `cache_read_input_tokens`
- `output_tokens`

`cache_creation_input_tokens` and `cache_read_input_tokens` must never be silently
folded into ordinary input. The distinction is required to explain cases where business
payload shrinks while real executor usage grows.

The normalized layer remains provider-neutral. PR26 ships a Claude Code JSONL adapter
because that is the executor used by the production run; another executor should map its
native usage fields into the same normalized schema rather than changing pipeline logic.

## Importing Claude Code usage

The importer reads local JSONL transcripts. It does not call an Anthropic API and does
not require the repository to know the location of a user's Claude configuration.

Typical run:

```bash
python briefing.py import-usage \
  --run 2026-08-08-200543-replay-pr20-24 \
  --host-log /path/to/claude-code-session.jsonl \
  --subagent-dir /path/to/subagents \
  --replace

python briefing.py stats --run 2026-08-08-200543-replay-pr20-24
```

Multiple `--host-log` and `--subagent-log` arguments are accepted. `--subagent-dir`
loads all `*.jsonl` files in one directory.

### Host-session boundaries

A Claude Code host session can contain several briefing runs plus unrelated coding work.
The importer therefore does **not** assume that an entire session belongs to one run.
By default, host records are bounded by that briefing run's SQLite `created_at` /
`updated_at` lifecycle. For a replay/debug session where a more precise boundary is
known, override it explicitly:

```bash
python briefing.py import-usage \
  --run RUN_ID \
  --host-log /path/to/session.jsonl \
  --host-start 2026-08-08T15:55:00+00:00 \
  --host-end   2026-08-08T16:30:00+00:00 \
  --subagent-dir /path/to/subagents \
  --replace
```

The report records the chosen host window. This makes original-run/replay comparisons
possible even when both were executed in one long Claude Code session.

## Attribution rules

### Subagents

Task IDs and task types are recovered from the task paths/IDs embedded in the delegated
prompt and matched against the run's SQLite tasks when available. A session that handles
several compatible tasks is attributed to that stage as one session; token usage is
**not divided arbitrarily among individual tasks**.

If the same task ID appears in a later agent session, that later session is counted as a
retry. This directly exposes patterns such as an item-writing task being run again by a
`-b` replacement agent without relying on the agent's display name.

### Host

Host calls inside the chosen run window are classified conservatively:

- an exact task reference -> that task stage when unambiguous;
- briefing CLI/run references -> `host_orchestration`;
- everything else -> `host_other`.

The importer does not scan the whole transcript for the first run ID and then attribute
all later messages to it. Parent traversal is bounded so a long shared session does not
create false precision.

## `stats` output

After usage is imported, `python briefing.py stats --run ...` adds:

```text
actual_token_usage
  totals
  by_scope       # host vs agent
  by_stage       # relevance/fact/repair/writing/fact-check/host...
  by_model
  agent_sessions
  retry
  error_records
  host_window
```

`total_tokens` is a usage-volume sum of the four native counters. It is deliberately not
called a monetary bill: pricing, service tier and provider-specific discounts are outside
the normalized telemetry layer.

If no transcript usage has been imported, `actual_token_usage.available=false` and the
existing deterministic character proxies remain visible.

## Cost attribution

Statistics should be grouped by stage whenever the executor log contains enough evidence:

- collection
- relevance analysis
- fact extraction
- evidence repair
- writing
- fact checking
- synthesis / host orchestration
- rendering

Unknown or mixed stages remain explicit rather than being guessed into a convenient
category.

## Quality correlation

Telemetry is stored together with quality indicators:

- primary source resolution rate
- evidence gap rate
- fact check pass rate
- golden evaluation score

The objective is to optimize cost while preserving output quality. PR26 is observational:
it makes the real cost components measurable but intentionally does not yet shorten
evidence, lower the deep budget, remove fact checking, or change retry policy.