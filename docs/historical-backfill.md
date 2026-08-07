# Historical Backfill

The rolling 60-day topic window has two separate mechanisms:

1. **External historical backfill** fetches historical A-level primary-source records that were never seen by this installation.
2. **Rolling backlog materialization** copies already-known, unpushed A-level records into a normal briefing run, capped by `backlog_materialize_per_run`.

These mechanisms are deliberately separated so a cold start cannot turn a large historical fetch directly into an unbounded Agent workload.

## Supported deterministic history

### arXiv

Each configured deep-topic direction is a resumable lane. Results are sorted by submitted date and paged backward until the campaign cutoff is crossed or the query is exhausted. The cursor is stored in SQLite `source_state`, so the next invocation continues instead of rescanning page 1.

### GitHub Releases

Each enabled configured repository is a resumable lane using the GitHub Releases API with page cursors. A 404 is recorded as `FAILED_PERMANENT` until the campaign is reset or configuration is fixed; transient failures remain retryable on a later invocation.

### Other A-level sources

Sources without a deterministic paginated collector are reported under `unsupported_sources`. They do not count as completed historical coverage and are not silently represented as a full 60-day backfill.

RSS feeds are not treated as complete historical archives: a feed may retain 10 entries, 100 entries, or only recent posts, and there is no generic way to prove that 60 days were covered.

## Cost controls

Default policy:

```yaml
historical_backfill:
  enabled: true
  lookback_days: 60
  auto_requests_per_run: 4
  manual_max_requests: 32
  arxiv_page_size: 50
  github_page_size: 50
```

A normal `briefing.py run` spends at most `auto_requests_per_run` external requests on unfinished historical lanes before normal collection. Lanes are rotated and GitHub/arXiv are interleaved so a small budget does not permanently starve later directions.

A manual backfill uses the same persisted cursors:

```bash
python briefing.py backfill
python briefing.py backfill --max-requests 64
python briefing.py backfill-status
```

`--reset` restarts the cursor campaign but does not delete historical raw items. Stable source identities are deduplicated before persistence, so a reset or overlap with normal collection does not intentionally create another copy of the same source.

## Agent isolation

Historical backfill itself creates **zero Agent tasks**. Backfilled records are stored under a synthetic historical batch ID outside the normal `runs` table. A subsequent normal run drains eligible records through the existing rolling backlog cap, relevance batching, diversity selection, Evidence Pack, facts cache, editorial batching, and fact-check batching.

With the default `backlog_materialize_per_run: 120`, a manual backfill that discovers 1,000 new records still introduces at most 120 historical A-level records into one normal run before the existing relevance filters and deep budgets apply.

## Status meanings

- `NOT_STARTED`: the lane has not consumed a historical request.
- `IN_PROGRESS`: more pages are required.
- `COMPLETE`: the cutoff was crossed or the source was exhausted.
- `ERROR`: the last request failed transiently and may be retried later.
- `FAILED_PERMANENT`: configuration/source failure should be fixed before retrying.

`backfill-status` also reports the oldest timestamp observed per lane, request counts, fetched-item counts, active/complete/failed lane counts, and unsupported A-level sources.
