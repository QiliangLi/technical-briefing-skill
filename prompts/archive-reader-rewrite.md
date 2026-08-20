# Historical archive reader rewrite

Rewrite exactly one already-published issue into the current reader contract. This is an expression-only migration, not a briefing rerun.

Return one JSON object conforming to `schemas/archive-reader.schema.json`. Copy all locked metadata from the input exactly: `schema_version=1`, `reader_contract_version`, `source_issue_hash`, `issue_date`, item map keys, `source_item_hash`, role, topic/direction IDs, publication date, score, sources and URLs, plus Radar ID/category/source hashes/source URLs. Set `rewrite_status` to `historical_semantic_rewrite`. Use the supplied deterministic `generated_at` value.

Rewrite the headline, judgements, watch-next text, every core/supplement item, and every Radar signal into clear natural Chinese. A detailed item uses a readable title, a direct lead, one to three coherent paragraphs and an optional takeaway. A supplement stays concise. Radar remains an unverified signal and must not sound like a confirmed conclusion.

Do not add, remove, merge or split items. Do not change roles, dates, scores, topics, directions, evidence IDs, sources or URLs. Do not add facts, numbers, causal strength or project conclusions absent from the corresponding machine fields. Different items are independent; never move evidence or numbers between them. Reader prose is for public display only. Roadmap and Idea analysis continue to use `issue.json`.
