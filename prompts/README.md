# Runtime prompts

Files in this directory are executable pipeline inputs, not general documentation. The task returned by `python briefing.py tasks next --run latest` names the exact prompt and schema to use.

Current runs primarily use the batched and run-scoped task family, including `agent-web-search-batch.md`, `relevance-batch.md`, `fact-extraction.md`, `fact-evidence-repair.md`, `item-writing-batch.md`, `fact-check-batch.md`, `reader-item-writing.md`, `issue-synthesis.md`, `knowledge-materialization.md`, and `illustrated-publication.md`.

The `assistant-*.md` prompts belong to the Feishu group assistant, not to the task queue. Its resident process writes a bounded task file, a host session reads the prompt and schema named on that task's card, and `python briefing.py assistant tasks apply` validates the output. See `docs/operations/group-assistant.md`.

Several singular or older prompts remain for idempotent resume of runs created by earlier pipeline versions. Do not delete or rewrite them only because a fresh run no longer creates that task type. The task queue is the authority for which prompt applies to an existing run.
