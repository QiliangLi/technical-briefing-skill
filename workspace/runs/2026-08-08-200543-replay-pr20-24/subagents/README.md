# Subagent session transcripts — replay run 2026-08-08-200543-replay-pr20-24

Per-agent JSONL logs for the subagents dispatched during the PR20-24 offline
replay. Filename prefix = role (`arpy-` = replay agents, named rpy-* by the
host); the standalone `agent-ad6712f6*` is the code-investigation Explorer.

| prefix        | stage / role                  | count |
|---------------|-------------------------------|-------|
| `arpy-rel-`   | relevance_batch               | 4     |
| `arpy-fev-`/`arpy-fe-` | fact_extraction      | 8     |
| `arpy-frp-`   | fact_evidence_repair          | 2     |
| `arpy-iw-`    | item_writing_batch            | 7     |
| `arpy-fc-`    | fact_check_batch              | 4     |
| `ad6712f6`    | codebase investigation (map PR20-24 + offline guard) | 1 |

The host orchestrator transcript is `../claude-code-session-2026-08-08-200543-replay-pr20-24.jsonl`
(this single session covers both the original run and the replay).
Original-run subagents are archived under `../../2026-08-08-200543/subagents/`.
