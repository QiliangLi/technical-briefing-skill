# Task: write plain-language copy for one idea card

One idea from the published Idea bank is about to be shared with the department
as a card. Its stored wording is abstract; colleagues need plain language. Read
only the bounded task input.

- `idea` is the stored idea. Say what problem it addresses, what it expects to
  happen and why it matters to the team, in words a colleague can act on.
- Do not add facts, numbers or claims that are not in `idea`.
- Do not use internal field names or identifiers in the copy.
- Write in Chinese.

Return one JSON object matching `schemas/assistant-card-copy.schema.json` to
the output path named in `_task`. Do not send any message, do not call
`lark-cli` and do not edit other files. Apply is the only writer and enforces
the length limits.
