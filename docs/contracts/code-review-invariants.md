# Code review invariants

Read this file when reviewing or changing pipeline state, selection and writing stages, rendering, mail delivery, archive publication, or related recovery behavior.

## Run isolation and idempotency

- Treat cross-run data leakage and duplicate re-application as correctness bugs.
- Scope candidates, facts, events, issue items, assets, and generated outputs to the active run unless code explicitly reads archived or historical data.
- Keep `advance`, resume, rendering, and publication retry paths idempotent. Re-running them must not duplicate issue content or re-apply an older run's output.

## Briefing integrity and report time

- Flag changes that can silently drop configured sections or items, bypass selection, Evidence Gate, required Fact Check, Reader Projection, or final validation.
- Do not replace polished reader output with raw Machine Item text.
- Derive the report date from the active run and configured timezone. Missing or invalid upstream dates need an explicit error or documented fallback.

## Published email assets

- Final email HTML must not reference local or relative run paths for recipient-visible images.
- Before send and archive, every image must resolve to a stable browser and email-accessible absolute URL, such as a commit-pinned GitHub asset URL.
- Preserve independent layout for adjacent figures so images cannot concatenate or overlap.

## External effects

- Do not send mail without explicit user confirmation and `--confirm-send`.
- Do not treat successful mail transport as successful archive publication. Publication retries must remain separate and idempotent.
- Do not commit tokens, `.env`, run databases, task transcripts, or other local workspace state.
