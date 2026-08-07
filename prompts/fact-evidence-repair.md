# Task: Repair Facts from a Targeted Evidence Supplement

The previous fact extraction identified one or more **material evidence gaps**. Read the structured `previous_facts`, the requested `evidence_gaps`, source metadata, and **only** the targeted supplement referenced by `document.supplement_path`. Do not reopen the original Evidence Pack or raw full text.

The supplement was selected deterministically from sections that were not already exposed in the original Evidence Pack, using the explicit gap terms. It is not permission to rewrite the source broadly.

Return a complete facts object for the same source:

- Preserve every previous fact that remains supported and unaffected by the supplement.
- Update only fields whose interpretation is materially improved or corrected by the new evidence.
- Add numerical evidence only when baseline and material conditions are available in the supplement.
- Keep source locators precise.
- If a requested fact is still unavailable, keep the claim conservative, record the missing validation in `limitations`, and retain the unresolved request in `evidence_gaps`.
- `evidence_gaps` may contain only unresolved material gaps from the input; do not invent new research questions. There is no second supplemental-read round.
- `title` must still exactly match the source title.
- `primary_source_resolved` follows the same rule as normal fact extraction: the source must be a specific primary source and the document fetch must be valid.
- Adjust `quality_score` only when the supplement materially changes completeness or confidence.

Never move facts, numbers, or conditions from another item/source into this source. Never infer that omitted raw text was checked. Return JSON only and copy the input `_task` object unchanged into the top level.