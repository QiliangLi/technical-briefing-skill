# Feishu Group Assistant

## Scope and boundaries

The assistant is a separate process outside the briefing pipeline, in `briefing_skill/assistant/`. It answers questions raised in one Feishu group from the published corpus and collects colleagues' verdicts on ideas.

- It reads only published records: `archive/index.json`, each issue's `issue.json` and `papers.json`, and `knowledge/ideas` and `knowledge/roadmaps`. Idea candidates, run directories and caches are never read.
- It binds no model API. Semantic work leaves the process as bounded task files for a host session, the same pattern as the pipeline.
- All state lives under the ignored state directory, `workspace/assistant/` by default. The repository is public; group chat text never enters it. What a host session sees carries sender labels, never names or open IDs.
- Nothing sends mail, and nothing posts to a group except through the outbox or an explicitly confirmed card push.

## Corpus and index

Four document kinds are indexed, each with a stable ID:

| Kind | ID | Indexed text | Link |
| --- | --- | --- | --- |
| Briefing item | `item:<brief_item_id>` | title and keywords (weighted), core conclusion, mechanism | `#archive?date=<issue>&item=<id>` |
| Radar entry | `radar:<paper_key>` | title (weighted), topic and direction names | `#archive?date=<issue>` |
| Idea | `idea:<idea_id>` | title (weighted), problem, hypothesis, mechanism | `#ideas?idea=<id>` |
| Roadmap | `roadmap:<topic_id>` | topic name (weighted), summary, branch names and open questions | `#roadmaps?topic=<id>` |

Links are built from `site_base_url` and an ID in the index; the published site's hash routes are the only targets. The snapshot's name is a digest of its inputs, so the same corpus and site address always rebuild byte-identical content apart from the timestamp, and a changed input yields a different digest. `assistant index build` rebuilds; `assistant index validate` reports whether the stored snapshot matches.

Retrieval is lexical: English words plus Chinese character bigrams, BM25 with titles and keywords weighted, and no segmentation dependency. A question is answered directly only when the best hit explains enough of it: strength, coverage and matched units each have to clear a fixed bar. Otherwise the question goes to a refinement task. `assistant ask` shows the decision for one question; `assistant eval` scores the question set in `eval/assistant-questions.json`.

## Admission and policy

Admission reads message metadata only, never the body.

| Message | Outcome |
| --- | --- |
| Mentions the assistant | explicit request, answered in every mode when `explicit` is on |
| Direct message from a member of a whitelisted group | explicit request |
| Direct message from anyone else | not processed |
| Another bot, or the assistant's own message | not admitted / dropped |
| Unaddressed in a whitelisted group | inferred candidate: assessed when the mode is `observe` or `auto`, ignored in `off` |
| Any message in a group outside the whitelist | blocked; the body is not kept |

The policy has three parts: `explicit` (on or off), the proactive mode (`off`, `observe`, `auto`) and one switch per rule. Its version is a hash of exactly those. Every decision records the version it was made under, and a pending task whose version no longer matches is voided. `mute [duration]` pauses proactive replies without changing the version.

The two proactive rules are named units with a plain-language instruction each: `prior_art` (someone is looking for prior work that the corpus holds) and `related_evidence` (a published, verified result bears directly on the discussion). An assessment gives exactly one verdict per enabled rule.

## Replies

Three kinds of message may leave the machine, and only through the outbox:

| Kind | Program checks before sending |
| --- | --- |
| `answer` | the message answered came from a person and mentioned the assistant or was a direct message |
| `recommendation` | an accepted assessment with a matched rule covers the discussion, and the mode is still `auto` |
| `card` | a confirmed card push recorded the idea first |

- These checks run when a row is queued and again when it is about to leave. A row that fails is kept as `refused` with the reason.
- Every reply fits 100 words; links do not count. Long text is shortened first, refused only if nothing fits.
- Every link comes from the index. Reply prose quotes a document's own published conclusion; the model never writes about a paper.
- One reply per mention, so the slow path sends no "working on it".
- A recommendation is one sentence with one link, sent into the discussion's thread.

Proactive recommendations stand behind gates that are code constants (`briefing_skill/assistant/constants.py`): a discussion needs several messages from several people and a quiet interval; it is assessed only in working hours, not within a day of the last recommendation in that thread, and not past a daily cap. A discussion under a sent idea card needs only one message, because the card invites discussion. A 👎 on a recommendation silences that thread. Hitting the daily cap, or a run of 👎, turns the mode back to `off` and records why.

## Semantic task protocol

| Task | Queued when | TTL |
| --- | --- | --- |
| `refine` | a mention that retrieval could not answer confidently | 10 minutes |
| `assess` | an unaddressed discussion passes the shape gates | 5 minutes |
| `card_copy` | a card is prepared and has no plain-language copy yet | 24 hours |

A task is one directory under `<state>/tasks/<task_id>/` holding `input.json`, written by the process, and `output.json`, reserved for the host session. The input carries a `_task` envelope and a bounded payload. `assistant tasks wait` blocks until tasks are ready, holding them for a short batch window and capping wake-ups per day, and returns read-only execution cards that end with the next step. `assistant tasks apply --task <id>` is the only writer.

Apply rejects, finally and silently, an output that:

- fails its schema in `schemas/`;
- selects a document outside the task's candidates, or names a rule that was not enabled;
- quotes text that is not a verbatim substring of the question or the discussion;
- contains a link the index does not carry, or an internal field name in card copy;
- belongs to a task that expired or whose policy version changed (card copy excepted).

A rejected or expired refinement falls back to the low-confidence answer, marked as not refined; a rejected or expired assessment ends in silence. The host session reads only what its card names, writes one JSON object, and never calls `lark-cli`.

## Outbox

Every outbound message is committed together with the decision behind it and sent afterwards. The idempotency key is the outbox row ID, hashed to fit lark-cli's 50-character limit, so a retry after a crash cannot post twice. Send results map to `sent`, `retry` (up to five attempts, then `failed`), or `gone` when the destination no longer exists.

## State and retention

One SQLite ledger in the state directory: `events` (messages), `dispositions` (one per message, with its history), `threads`, `decisions`, `tasks`, `outbox`, `feedback`, `registry` (card message to idea), `cursors` (per-chat history position), `meta` (policy, members, heartbeat, self-check, service) and `pause_log`. Message bodies are cleared after 30 days; hashes and counts stay. Everything under `workspace/assistant/` and `workspace/assistant-e2e/` is ignored by git.

## lark-cli usage

`briefing_skill/assistant/lark.py` is the only code that builds a lark-cli command. It fixes the identity to the bot and refuses any other, with one exception: `event stop` acts on the local daemon and takes no identity. The assistant therefore cannot reach the user's own authorisation on the machine.

- One `lark-cli event consume` child per EventKey, stdin kept open; closing stdin is the graceful stop. A child that exits without an error envelope is restarted with backoff; an error envelope is kept and shown by `status`.
- History is read newest page first and cut at the stored cursor locally, because the chat API returns nothing for a time window. A chat's history lists a thread's root but never its replies, so recently active threads are read in their own container as a second source.
- Live events, history and thread pages all reduce to one trigger keyed by message ID, so a message arriving by several paths is processed once.

## End-to-end checks

- `assistant e2e` runs the offline suites: events in, a capturing transport out, no network.
- `assistant e2e --live` starts the resident process on its own state directory and drives the test group as the user. It is bound to one group, refuses any other, prefixes every message with `[E2E]` and never recalls a message. Where a host session is needed it plays one itself, with output built by rule.
- `--soak-minutes N` keeps the process up and probes it instead of running the scenarios.
- The published `config/group-assistant.yaml` carries no test switches; the live run configures its own ignored state directory.
