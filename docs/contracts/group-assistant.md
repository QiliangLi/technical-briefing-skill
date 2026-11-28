# Feishu Group Assistant

## Scope and boundaries

The assistant is a separate process outside the briefing pipeline, in `briefing_skill/assistant/`. It takes part in one Feishu group as a member of it: it answers questions addressed to it from the published corpus, joins discussions with what the corpus holds, reviews ideas colleagues propose, reports coverage gaps to the owner, and offers a new issue when it holds something for the group.

- It reads only published records: `archive/index.json`, each issue's `issue.json`, `papers.json` and `reader.json`, and `knowledge/ideas` and `knowledge/roadmaps`. Idea candidates, run directories and caches are never read. The briefing's topic configuration (`config/topics*.yaml`) is read only to name the scopes in a coverage report.
- It binds no model API. Semantic work leaves the process as bounded task files for a host session, the same pattern as the pipeline.
- All state lives under the ignored state directory, `workspace/assistant/` by default. The repository is public; group chat text never enters it. What a host session sees carries sender labels, never names or open IDs. Real names appear only in reports sent to the owner.
- Nothing sends mail, and nothing posts to a group except through the outbox or an explicitly confirmed card push.

## Corpus and index

Five document kinds are indexed, each with a stable ID:

| Kind | ID | Indexed text | Link |
| --- | --- | --- | --- |
| Briefing item | `item:<brief_item_id>` | title and keywords (weighted), reader lead, core conclusion, mechanism, result, boundary | `#archive?date=<issue>&item=<id>` |
| Radar entry | `radar:<paper_key>` | title (weighted), topic and direction names | `#archive?date=<issue>` |
| Idea | `idea:<idea_id>` | title (weighted), problem, hypothesis, mechanism | `#ideas?idea=<id>` |
| Roadmap | `roadmap:<topic_id>` | topic name (weighted), summary, branch names and open questions | `#roadmaps?topic=<id>` |
| Issue judgement | `judgement:<issue>:<n>` | title (weighted) and body, from the issue's reader projection | `#archive?date=<issue>` |

Every document also carries what a reply may quote without a model writing it: `headline` and `lead` from the reader card in `archive/issues/<date>/reader.json`, and for an item `result`, `boundary` and `project_relevance`. All of it is published and checked.

Links are built from `site_base_url` and an ID in the index; the published site's hash routes are the only targets. The snapshot's name is a digest of its inputs, so the same corpus and site address always rebuild byte-identical content apart from the timestamp, and a changed input yields a different digest. `assistant index build` rebuilds; `assistant index validate` reports whether the stored snapshot matches.

Retrieval is lexical: English words plus Chinese character bigrams, BM25 with titles and keywords weighted, and no segmentation dependency.

- A question is searched as it was asked. It is answered directly only when the best hit explains enough of it: strength, coverage and matched units each have to clear a fixed bar. Otherwise it goes to a refinement task.
- A discussion is searched message by message and the rankings fused by reciprocal rank, because read as one block its sentences bury the words that matter. A judgement or a bare radar title ranks below a concrete item or idea, since both match many a message on common words.
- Lexical search cannot bridge wording that shares no term with the library. That is the host session's to bridge: it may run `assistant search --task <id> "<query>"` with the terms restated, at most four times per task, and cite what the searches return.

`assistant ask` shows the decision for one question; `assistant eval` scores the question set in `eval/assistant-questions.json`.

## Admission and policy

Admission reads message metadata only, never the body.

| Message | Outcome |
| --- | --- |
| Mentions the assistant | explicit request, answered when `explicit` is on |
| Direct message from a member of a whitelisted group | explicit request |
| Direct message from anyone else | not processed |
| Another bot, or the assistant's own message | not admitted / dropped |
| Unaddressed in a whitelisted group | looked at as a discussion when the mode is `observe` or `auto`; ignored in `off` |
| Any message in a group outside the whitelist | blocked; the body is not kept |

The policy has two switches: `explicit` (on or off) and the proactive mode. Its version is a hash of exactly those; a decision records the version it was made under, and a look in flight is voided when the version changes (card copy is not). `mute [duration]` pauses speaking without changing the version.

| Mode | What the assistant does with a discussion |
| --- | --- |
| `off` | does not look at it |
| `observe` | decides what it would say and records it; says nothing. This is how a prompt is calibrated |
| `auto` | says it |

Both switches default to on. A state directory that already holds a policy keeps it.

## Looking at discussions

- A thread's first unaddressed message is looked at ten seconds later, whatever comes after it. Messages that arrive before the look is answered join it; the session sees the latest twenty.
- A thread has one look in flight at most, and a new one at most every thirty seconds, so a lively discussion is followed without a task for every message.
- Nothing else gates speaking. There is no minimum of messages or speakers and no daily cap; working hours can be configured and default to all day, every day.
- Three things still stop it: a mute, a 👎 on a reply in that thread (that thread only), and a breaker far above normal use (thirty proactive replies in an hour), which pauses speaking until the hour passes and tells the owner. A run of 👎 over the week turns the mode back to `off`.

## Tasks for a host session

| Task | Queued when | TTL |
| --- | --- | --- |
| `refine` | a mention that retrieval could not answer confidently | 10 minutes |
| `contribute` | a discussion is looked at | 15 minutes |
| `alert` | a new issue is published, while the process runs or while it is down | 24 hours |
| `card_copy` | a card is prepared and has no plain-language copy yet | 24 hours |

A task is one directory under `<state>/tasks/<task_id>/` holding `input.json`, written by the process, and `output.json`, reserved for the host session. `assistant tasks wait` blocks until tasks are ready, holding them ten seconds to batch what arrived together and capping wake-ups per day, and returns read-only execution cards that end with the next step. `assistant tasks apply --task <id>` is the only writer.

A `contribute` input holds the discussion with sender labels, what the assistant already cited in it, at most five candidates with their published lead and boundary, the retrieval strength, the briefing's configured topics and the gaps reported lately. The session chooses one of four:

| Act | When | What the program sends |
| --- | --- | --- |
| `none` | nothing to add | nothing |
| `add` | the library holds something that bears on what is said, or contradicts it | the session's framing, then one or two cited documents |
| `review` | a colleague proposes an idea of their own | the framing, then the closest idea, supporting evidence, limits and what the library lacks |
| `gap` | a substantive matter neither the library nor the topics cover | nothing in the group; a report to the owner |

Apply rejects, finally and silently, an output that:

- fails its schema in `schemas/`;
- cites a document outside the task's candidates and its own searches, or cites again what was already said in that discussion;
- quotes text that is not a verbatim substring of the discussion or the question;
- puts a number in its framing that appears in no cited document and not in the discussion;
- contains a link, or an internal field name in card copy;
- names, as the nearest scope of a gap, a topic or direction that is not configured.

A rejected or expired refinement falls back to the low-confidence answer, marked as not refined; a rejected or expired look ends in silence.

## Replies

Five kinds of message may leave the machine, and only through the outbox:

| Kind | Program checks before sending |
| --- | --- |
| `answer` | the message answered came from a person and mentioned the assistant or was a direct message |
| `recommendation` | an accepted decision to speak covers the thread, and the mode is still `auto` |
| `alert` | an accepted alert covers the issue |
| `report` | a queued report covers the message |
| `card` | a confirmed card push recorded the idea first |

- These checks run when a row is queued and again when it is about to leave. A row that fails is kept as `refused` with the reason.
- The session writes only the framing, one or two sentences saying what in the discussion the reply answers. Titles, dates, numbers and links are the documents' own published text, taken from the index. A reply never introduces the assistant and never reports progress.
- Length is counted in visible characters, links excluded: 700 for an answer, 600 for a contribution, 900 for an alert, 1500 for a report. Long leads are cut at a sentence end before anything is refused.
- A contribution and a review go into the discussion's thread. An alert is one new message naming the issue, at most three picks, each with the session's sentence on what it means for the group.

## Reports to the owner

- A coverage gap is recorded and sent as a direct message: the discussion's gist, who took part by real names, the nearest configured scope and the terms to add. At most three a day; the rest stay in the ledger. A report changes nothing in the briefing; the owner decides.
- A notice goes the same way when the breaker pauses speaking or when the process gives up.
- `assistant report to <open_id>` opens the channel once; `report list` and `report show <id>` read reports back. Discussion text in reports is kept for thirty days, like messages.

## Outbox

Every outbound message is committed together with the decision behind it and sent afterwards. The idempotency key is the outbox row ID, hashed to fit lark-cli's 50-character limit, so a retry after a crash cannot post twice. Send results map to `sent`, `retry` (up to five attempts, then `failed`), or `gone` when the destination no longer exists.

## State and retention

One SQLite ledger in the state directory: `events` (messages), `dispositions` (one per message, with its history), `threads`, `decisions`, `tasks`, `task_searches`, `outbox`, `feedback`, `registry` (card message to idea), `reports`, `cursors` (per-chat history position), `meta` (policy, members and their names, heartbeat, self-check, service) and `pause_log`. Message bodies are cleared after 30 days; hashes and counts stay. Everything under `workspace/assistant/` and `workspace/assistant-e2e/` is ignored by git.

## lark-cli usage

`briefing_skill/assistant/lark.py` is the only code that builds a lark-cli command. It fixes the identity to the bot and refuses any other, with one exception: `event stop` acts on the local daemon and takes no identity. The assistant therefore cannot reach the user's own authorisation on the machine.

- One `lark-cli event consume` child per EventKey, stdin kept open; closing stdin is the graceful stop. A child that exits without an error envelope is restarted with backoff; an error envelope is kept and shown by `status`.
- History is read newest page first and cut at the stored cursor locally, because the chat API returns nothing for a time window. A chat's history lists a thread's root but never its replies, so recently active threads are read in their own container as a second source.
- Live events, history and thread pages all reduce to one trigger keyed by message ID, so a message arriving by several paths is processed once.
- `assistant serve --detach` starts the resident process on its own, so a host session can be reopened without the watcher going down with it.

## End-to-end checks

- `assistant e2e` runs the offline suites: events in, a capturing transport out, no network.
- `assistant e2e --live` starts the resident process on its own state directory and drives the test group as the user. It is bound to one group, refuses any other, prefixes every message with `[E2E]` and never recalls a message. Where a host session is needed it plays one itself, with output built by rule.
- `--discussions` holds the simulated discussions in `eval/assistant-discussions.json` and judges each reply without a model: whether it spoke as the scenario expects, whether its links come from the site, whether it cites something the scenario names and avoids what it forbids, and whether it is short enough. `--session manual` leaves the judging to a real session. Every scenario also records what the corpus holds for it (`reached`, `missed` or `absent`), and an offline test fails when that label no longer holds.
- `--soak-minutes N` keeps the process up and probes it instead.
- The published `config/group-assistant.yaml` carries no test switches; the live run configures its own ignored state directory.
