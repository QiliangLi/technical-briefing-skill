# Task: Batched Agent-Native Web Discovery

Process every entry under `searches` within this single Agent invocation. Each entry is an independent coverage-gap search lane. Do not transfer results, topic assumptions, direction assumptions, dates, or preferred domains across lanes.

For each lane:

1. Use the current Agent's web-search capability for that lane's narrow `query`.
2. Only return material whose **original publication date** is inside that lane's exact `date_from` to `date_to` window.
3. Prioritise original papers, official engineering blogs/documentation, official repositories/releases, and conference pages.
4. Return at most that lane's `max_results` items.
5. Reject results with an unknown publication date or a date outside the lane window. Search-index, crawl, discovery, or page-update time is not a substitute for original publication date.
6. This is discovery only. Do not answer the technical question, perform relevance scoring, compare lanes, or synthesise results across topics.

Return exactly one result group for every input `search_id`, with the exact same `topic_id` and `direction_id`. A lane with no acceptable results must still be returned with an empty `items` array.

For every accepted item return title, URL, publisher, published date, source level, short discovery summary, and whether it is a primary source.

Return JSON only.