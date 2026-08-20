# Historical archive reader rewrite

Rewrite exactly one already-published issue into the current Reader v2 contract. This is an expression-only migration, not a briefing rerun.

Return one JSON object conforming to `schemas/archive-reader.schema.json`. Copy all locked metadata from the input exactly: `schema_version=1`, `reader_contract_version`, `source_issue_hash`, `issue_date`, item map keys, `source_item_hash`, role, topic/direction IDs, publication date, score, sources and URLs, plus Radar ID/category/source hashes/source URLs. Set `rewrite_status` to `historical_semantic_rewrite`. Use the supplied deterministic `generated_at` value.

Rewrite the headline, judgements, watch-next text, every core/supplement item, and every Radar signal into clear natural Chinese. For each item, `blocks` is the durable reader-facing source of truth: return 1-3 blocks in the order a technical reader should see them, with an optional semantic `heading_key` from the Reader v2 enum. The first block normally needs no heading. Do not force a fixed lead/mechanism/result/boundary/takeaway sequence and do not manufacture a paragraph just to use a heading.

The archive schema still carries `lead`, `body` and `takeaway` as compatibility fields for old templates and tools. Derive them from the same rewrite rather than treating them as the editorial contract: `lead` should mirror the first block text, `body` should mirror the remaining block texts, and `takeaway` should normally be `null`. Do not preserve a formulaic takeaway merely because the old archive had one.

Write as a technical colleague explaining what changed, how it works, what the evidence actually shows, and where the boundary matters. Prefer concrete subjects and verbs. Avoid issue-wide title rhythm collapse and repetitive endings such as “值得关注”“值得借鉴”“可作为参考” when they add no information. Uneven item length is fine.

Do not add, remove, merge or split items. Do not change roles, dates, scores, topics, directions, evidence IDs, sources or URLs. Do not add facts, numbers, causal strength or project conclusions absent from the corresponding machine fields. Different items are independent; never move evidence or numbers between them. Reader prose is for public display only. Roadmap and Idea analysis continue to use `issue.json`.
