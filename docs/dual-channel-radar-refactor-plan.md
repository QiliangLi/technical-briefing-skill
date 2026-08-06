# Dual Channel Radar Refactor Plan

## Motivation

The current pipeline already contains deep topics (TPN, DPU, Agent acceleration, KVCache, AI Infra) and an AI HOT radar path. However, discovery, deep analysis, and radar summarization should not share the same expensive LLM workflow.

## Target architecture

```text
All sources
  |
  +-- Deep Research Channel
  |      TPN / DPU / Memory / Agent acceleration / Cross region / Optical
  |      -> relevance screening
  |      -> evidence extraction
  |      -> item writing
  |      -> fact check
  |
  +-- Radar Channel
         AI Infra / Agent ecosystem / KVCache ecosystem / storage media
         -> lightweight batch classification
         -> deduplication
         -> radar card
         -> promote important signals to deep channel
```

## Changes

1. Add explicit horizontal radar categories:

- AI Infra
- Agent ecosystem
- KVCache ecosystem
- Storage media

2. Keep deep topics unchanged.

3. Introduce different budgets:

- Deep channel: 6-10 validated items per issue.
- Radar channel: <=8 lightweight observations.

4. Search policy:

- Do not use broad web search for every direction by default.
- Use fixed high quality feeds first.
- Search only for missing coverage or promoted radar signals.

5. Promotion rule:

Radar items become deep items only when they have:

- first party source;
- concrete mechanism;
- measurable evidence or deployment information;
- direct project relevance.

## Expected impact

- Reduce unnecessary full text extraction.
- Reduce agent context size.
- Preserve coverage of AI Infra, Agent, KVCache and storage evolution.
- Keep final email focused instead of becoming a news dump.
