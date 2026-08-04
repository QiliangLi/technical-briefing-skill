# Technical Briefing Skill — Architecture

## Product boundary

The Skill produces recurring internal technical intelligence, not a generic AI-news feed. It prioritises project relevance, evidence, deduplication, and readable visual explanation.

## Pipeline

```text
collect
→ deterministic rule filter
→ bounded relevance tasks
→ one-source-at-a-time fulltext extraction
→ structured facts
→ event-level clustering
→ 300–450 Chinese-character item writing
→ independent fact check
→ issue selection and synthesis
→ evidence-first visual routing
→ Guizang illustration/card rendering
→ HTML email
→ human approval
→ send and archive
```

## Context budget

- Raw collection can contain hundreds of items.
- Rule filtering reduces them before any model reads content.
- Relevance tasks contain only metadata and a short summary.
- Fulltext tasks contain one source, split into bounded chunks when needed.
- Downstream steps consume facts JSON, not original documents.
- Issue synthesis sees only 4–6 final items.

## AI HOT policy

AI HOT has elevated discovery priority for Agent, coding-agent, CodeGraph, repository-indexing, KVCache, Prefill/Decode, LLM serving, and cross-region cache keywords. This affects collection and candidate order only. Final evidence still requires a primary source.

## Visual policy

```text
source figure > official image > real screenshot > exact programmatic chart
> Guizang material mechanism > personal judgement metaphor > text-only
```

The personal character is a restrained technical scout. It creates recognition without replacing technical evidence.

## State and idempotency

SQLite stores runs, raw items, candidates, tasks, facts, events, issue items, send history, and ETag state. Task outputs are immutable JSON files. `advance` is idempotent and marks outputs APPLIED after database updates.

## Security

- The default mail backend is the locally authenticated `agently-cli`; SMTP remains an explicit fallback via `EMAIL_BACKEND=smtp`.
- The send command requires an APPROVED issue and explicit `--confirm-send`; agently-cli's confirmation token is persisted only in the ignored run directory between the two calls.
- Internal project context is stored separately from fetched public content.
- A failed send does not mark events as pushed.
