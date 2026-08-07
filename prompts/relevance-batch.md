# Task: Batch Relevance Review

Screen a batch of candidates for one internal technical topic. Read only the task input and the referenced short project-context file. Do not fetch or read full articles.

For every input candidate, return exactly one result with the same `candidate_id`.

Rules:

1. Prefer concrete mechanisms, products, deployments, benchmarks, papers, repositories, releases, or architecture changes.
2. Reject generic AI news, marketing claims, broad opinion, beginner tutorials, and keyword-only matches.
3. The deep channel requires a resolved A-level source. Discovery and horizontal signals belong in Radar unless the input is already an A-level primary source.
4. For TPN/KVCache, require a network, communication, bandwidth, placement, disaggregation, cache-routing, or token-performance angle.
5. For Agent acceleration, include repository indexing, code graph, Read/Grep/Glob reduction, context construction, tool-chain execution, and end-to-end agent runtime.
6. `fulltext_required=true` only when the candidate is worth competing for the limited deep-analysis budget.
7. Judge candidates independently. Do not lower one score merely because another candidate in the batch is stronger.
8. Return JSON only and match the supplied schema.
