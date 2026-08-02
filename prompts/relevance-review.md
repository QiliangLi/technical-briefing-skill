# Task: Relevance Review

You are screening one candidate for an internal technical briefing. Read only the task input and the referenced short project-context file. Do not fetch or read the full article yet.

Decide whether the candidate is directly relevant to the specified topic and direction.

Rules:

1. Prefer concrete mechanisms, products, deployments, benchmarks, papers, repositories, or architecture changes.
2. Reject generic AI news, marketing claims, broad opinion, beginner tutorials, and items that only share a keyword.
3. For TPN/KVCache, require a network, communication, bandwidth, placement, disaggregation, or token-performance angle; pure single-GPU memory management is insufficient.
4. For Agent acceleration, include CodeGraph, repository indexing, Read/Grep/Glob/code-search reduction, context construction, parallel/speculative tool execution, and end-to-end agent runtime. Do not restrict it to semantic cache.
5. AI HOT is only a discovery source. A candidate discovered there may be relevant, but fulltext must resolve to the original source before final use.
6. Score 0-100. Set `fulltext_required=true` for all potentially usable candidates.
7. Return JSON only, matching the supplied schema.
