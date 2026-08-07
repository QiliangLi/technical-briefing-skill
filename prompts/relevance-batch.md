# Task: Batch Relevance Review

Screen a batch of candidates for one internal technical topic. Read only the task input and the referenced short project-context file. Do not fetch or read full articles.

For every input candidate, return exactly one result with the same `candidate_id`.

The numeric `rule_score` in the input is only a lexical-routing score. Do not treat it as evidence that the item is important.

## Value score

Assign `score` from 0-100 using this rubric:

- project relevance: 0-35 — does it answer a current topic question or change a design choice;
- technical novelty/substance: 0-25 — new mechanism, architecture, data path, algorithm, deployment method, or non-trivial capability;
- evidence specificity: 0-20 — concrete benchmark, scale, baseline, quantitative result, implementation detail, or primary artifact;
- actionability: 0-15 — can the team derive a design hypothesis, experiment, implementation choice, or risk from it;
- freshness: 0-5 — use freshness only as a small tie-breaker. A strong 30-60 day item can outrank a weak item from today.

`relevant=true` means the item is genuinely related and worth retaining. `fulltext_required=true` means it is strong enough to compete for one of the expensive Top4-style deep-analysis slots. As a default, require score >=65 and concrete technical substance for `fulltext_required=true`.

## Quality guards

1. Prefer concrete mechanisms, products, deployments, benchmarks, papers, repositories, releases, or architecture changes.
2. Reject generic AI news, marketing claims, broad opinion, beginner tutorials, and keyword-only matches.
3. The deep channel requires a resolved A-level source. Discovery and horizontal signals belong in Radar unless the input is already an A-level primary source.
4. For TPN/KVCache, require a network, communication, bandwidth, placement, disaggregation, cache-routing, or token-performance angle.
5. For Agent acceleration, include repository indexing, code graph, Read/Grep/Glob reduction, context construction, tool-chain execution, and end-to-end agent runtime.
6. A compatibility-only, dependency-only, routine bug-fix, documentation, CI/build, or version-bump release may be `relevant=true`, but normally must have `fulltext_required=false` and score below 60 unless it materially changes capability, performance, architecture, or deployment constraints.
7. Do not let several updates from the same project crowd out different mechanisms or projects. Judge each independently, but reserve high scores for distinct technical contribution rather than release frequency.
8. `reason` must be a concise 1-2 sentence Chinese summary of what changed and why it matters. It may be shown later in the topic appendix, so do not write process commentary such as “建议阅读全文” or “关键词匹配”。
9. Do not lower one candidate merely because another candidate in the batch is stronger; the downstream selector handles diversity and capacity.
10. Return JSON only and match the supplied schema.
