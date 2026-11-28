"""The deterministic core of the group assistant.

Every message passes Source filters and the admission table before anything
else. A question addressed to the assistant is answered at once when retrieval
is confident and refined by a host session otherwise. Everything else in the
group is looked at moments after it arrives and handed to a host session,
which decides whether and how to speak. The program builds every reply from
published text, checks what the session wrote, and is the only writer of
assistant state.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from ..utils import read_json, stable_hash
from . import outbox, reports, tasks, topics
from .config import AssistantConfig
from .constants import (
    ADD_ITEMS,
    ANSWER_MAX_ITEMS,
    BREAKER_LIMIT,
    CARD_REACTIONS,
    CLUSTER_MAX_GAP_SECONDS,
    CLUSTER_WINDOW_SECONDS,
    CONTEXT_NEIGHBOURS,
    CONTRIBUTE_CANDIDATES,
    DEBOUNCE_SECONDS,
    DISLIKE_PAUSE_MIN_SAMPLES,
    DISLIKE_PAUSE_RATIO,
    EXPLICIT_RATE_PER_MINUTE,
    MESSAGE_CHAR_LIMIT,
    REFINE_CANDIDATES,
    REPORT_LOOKBACK_DAYS,
    REPORTS_PER_DAY,
    REPORT_TERMS,
    REPLY_REACTIONS,
    REVIEW_ITEMS,
    STALE_SECONDS,
    THREAD_MIN_INTERVAL_SECONDS,
    WINDOW_MAX_MESSAGES,
)
from .events import Trigger
from .policy import Policy, admit
from .replies import NO_MATCH_TEXT, URL, compose_add, compose_alert, compose_answer, compose_review
from .retrieval import LexicalIndex, assess, search_discussion
from .store import Store, text_hash
from .timeutil import day_start, iso, local

INTERNAL_FIELD = re.compile(r"hypothesis|problem_key|mechanism_key|validation_plan|decision_log|idea_id|brief_item")
TRUNCATED_NOTE = "…（已截断）"
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def candidate(doc: dict[str, Any], score: float = 0.0) -> dict[str, Any]:
    """What a host session may see of one published document."""

    return {
        "id": doc["id"],
        "kind": doc["kind"],
        "title": doc.get("headline") or doc["title"],
        "date": doc.get("issue_date") or "",
        "lead": (doc.get("lead") or doc.get("summary") or "")[:300],
        "boundary": (doc.get("boundary") or "")[:200],
        "status": doc.get("status") or "",
        "score": round(score, 3),
    }


def _published(doc: dict[str, Any]) -> str:
    """Every word of a document a framing may echo a number from."""

    return " ".join(str(doc.get(field) or "") for field in ("title", "headline", "lead", "summary", "result", "boundary", "project_relevance"))


def _numbers(text: str) -> set[str]:
    return set(NUMBER.findall(text or ""))


class Engine:
    def __init__(
        self,
        store: Store,
        index: LexicalIndex,
        config: AssistantConfig,
        root: Path,
        state_dir: Path,
        *,
        bot_ids: tuple[str, ...] = (),
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.store = store
        self.index = index
        self.config = config
        self.root = root
        self.state_dir = state_dir
        self.bot_ids = set(bot_ids)
        self.clock = clock
        self.tasks_dir = tasks.tasks_root(state_dir)
        self.known_urls = frozenset(doc["url"] for doc in index.docs)
        self._topics = topics.load_topics(root)

    # ---- intake -----------------------------------------------------------------

    def reindex(self, index: LexicalIndex) -> None:
        """Swap in a rebuilt index; tasks in flight keep the candidates they were cut from."""

        self.index = index
        self.known_urls = frozenset(doc["url"] for doc in index.docs)

    def ingest(self, trigger: Trigger) -> dict[str, str]:
        """Run one message through Source filters, admission and the answer path."""

        now = self.clock()
        if trigger.sender_id in self.bot_ids or self._is_own(trigger):
            return {"decision": "dropped_own"}
        open_to_assistant = trigger.is_direct or trigger.chat_id in self.config.chat_whitelist
        with self.store.transaction() as connection:
            # A chat the assistant is not open to keeps the fact of a message, never its body.
            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO events(trigger_id, message_id, chat_id, thread_key, sender_id, is_bot,
                                             is_mention, is_direct, is_reply, created_ms, text, text_hash,
                                             first_via, received_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trigger.trigger_id, trigger.message_id, trigger.chat_id, trigger.thread_key, trigger.sender_id,
                    int(trigger.is_bot), int(trigger.is_mention), int(trigger.is_direct), int(trigger.is_reply),
                    trigger.created_ms, trigger.text if open_to_assistant else "", text_hash(trigger.text),
                    trigger.via, iso(now),
                ),
            ).rowcount
            self.store.record_arrival(trigger.trigger_id, trigger.via, iso(now))
            if not inserted:
                return {"decision": "duplicate", "via": trigger.via}

            policy = Policy.load(self.store)
            if not open_to_assistant:
                outcome, thread_key = ("blocked", "chat_not_whitelisted"), trigger.thread_key
            else:
                thread_key = self._discussion_key(connection, trigger)
                connection.execute("UPDATE events SET thread_key=? WHERE trigger_id=?", (thread_key, trigger.trigger_id))
                self._touch_thread(connection, thread_key, trigger, now)
                self._anchor_thread(connection, thread_key, trigger)
                if now * 1000 - trigger.created_ms > STALE_SECONDS * 1000:
                    # A message redelivered long after it was written must not start a reply now.
                    outcome = ("blocked", "stale")
                else:
                    admitted, reason = admit(trigger, policy, self.members())
                    if admitted is None:
                        outcome = ("blocked", reason)
                    elif admitted == "explicit":
                        outcome = self._answer(connection, trigger, thread_key, policy, now)
                    else:
                        outcome = ("pending", "awaiting_look")
            self._set_disposition(connection, trigger, thread_key, outcome[0], outcome[1], now)
        return {"decision": outcome[0], "reason": outcome[1]}

    def _is_own(self, trigger: Trigger) -> bool:
        """A message the assistant sent, read back from history under the app's ID rather than the bot's."""

        return self.store.fetchone(
            "SELECT 1 FROM outbox WHERE message_id=? UNION SELECT 1 FROM registry WHERE message_id=?",
            (trigger.message_id, trigger.message_id),
        ) is not None

    def members(self) -> set[str]:
        members: set[str] = set()
        for open_ids in self.store.get_meta("members", {}).values():
            members.update(open_ids)
        return members

    def _discussion_key(self, connection: Any, trigger: Trigger) -> str:
        """Replies join their thread; standalone messages join a time cluster."""

        if trigger.is_reply or trigger.is_direct:
            return trigger.thread_key
        # The message itself is already stored, so look past it for the cluster.
        last = connection.execute(
            "SELECT thread_key, created_ms FROM events WHERE chat_id=? AND is_reply=0 AND trigger_id <> ? ORDER BY created_ms DESC, trigger_id DESC LIMIT 1",
            (trigger.chat_id, trigger.trigger_id),
        ).fetchone()
        if last is None:
            return trigger.thread_key
        first = connection.execute(
            "SELECT MIN(created_ms) AS first_ms FROM events WHERE thread_key=?", (last["thread_key"],)
        ).fetchone()
        gap = (trigger.created_ms - last["created_ms"]) / 1000
        span = (trigger.created_ms - first["first_ms"]) / 1000
        if 0 <= gap <= CLUSTER_MAX_GAP_SECONDS and span <= CLUSTER_WINDOW_SECONDS:
            return last["thread_key"]
        return trigger.thread_key

    def _anchor_thread(self, connection: Any, thread_key: str, trigger: Trigger) -> None:
        """A discussion under a sent idea card is anchored to that idea."""

        anchor = connection.execute(
            "SELECT idea_id FROM registry WHERE message_id=?", (trigger.root_id or trigger.message_id,)
        ).fetchone()
        if anchor is not None:
            connection.execute("UPDATE threads SET anchor_idea_id=? WHERE thread_key=?", (anchor["idea_id"], thread_key))

    def _touch_thread(self, connection: Any, thread_key: str, trigger: Trigger, now: float) -> None:
        """Track the message a discussion is named by, its Feishu thread and when it was last active."""

        connection.execute(
            """
            INSERT INTO threads(thread_key, chat_id, root_message_id, thread_id, last_activity_ms, updated_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_key) DO UPDATE SET
                thread_id=COALESCE(threads.thread_id, excluded.thread_id),
                last_activity_ms=MAX(threads.last_activity_ms, excluded.last_activity_ms), updated_at=excluded.updated_at
            """,
            (
                thread_key, trigger.chat_id, thread_key.split(":", 1)[1], trigger.thread_id or None,
                trigger.created_ms, iso(now),
            ),
        )

    def _set_disposition(
        self, connection: Any, trigger: Trigger, thread_key: str, decision: str, reason: str, now: float
    ) -> None:
        """Every message keeps exactly one disposition row; later moves append to its history."""

        row = connection.execute("SELECT history_json FROM dispositions WHERE trigger_id=?", (trigger.trigger_id,)).fetchone()
        history = json.loads(row["history_json"]) if row else []
        history.append({"decision": decision, "reason": reason, "at": iso(now)})
        connection.execute(
            """
            INSERT INTO dispositions(trigger_id, chat_id, thread_key, sender_id, decision, reason, history_json,
                                     created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trigger_id) DO UPDATE SET decision=excluded.decision, reason=excluded.reason,
                                                  history_json=excluded.history_json, updated_at=excluded.updated_at
            """,
            (
                trigger.trigger_id, trigger.chat_id, thread_key, trigger.sender_id, decision, reason,
                json.dumps(history, ensure_ascii=False), iso(now), iso(now),
            ),
        )

    def _move(self, connection: Any, where: str, params: tuple, source: str, decision: str, reason: str, now: float) -> int:
        rows = connection.execute(
            f"SELECT trigger_id, history_json FROM dispositions WHERE {where} AND decision=?", (*params, source)
        ).fetchall()
        for row in rows:
            history = json.loads(row["history_json"])
            history.append({"decision": decision, "reason": reason, "at": iso(now)})
            connection.execute(
                "UPDATE dispositions SET decision=?, reason=?, history_json=?, updated_at=? WHERE trigger_id=?",
                (decision, reason, json.dumps(history, ensure_ascii=False), iso(now), row["trigger_id"]),
            )
        return len(rows)

    # ---- answering --------------------------------------------------------------

    def _rate_limited(self, connection: Any, trigger: Trigger, now: float) -> bool:
        row = connection.execute(
            "SELECT COUNT(*) AS total FROM dispositions WHERE sender_id=? AND decision IN ('answered', 'refine') AND updated_at >= ?",
            (trigger.sender_id, iso(now - 60)),
        ).fetchone()
        return int(row["total"]) >= EXPLICIT_RATE_PER_MINUTE

    def _answer(
        self, connection: Any, trigger: Trigger, thread_key: str, policy: Policy, now: float
    ) -> tuple[str, str]:
        if self._rate_limited(connection, trigger, now):
            return "blocked", "rate_limited"
        result = assess(self.index, trigger.text)
        if result["state"] == "confident":
            self._queue_answer(
                connection, f"answer:{trigger.trigger_id}", trigger.chat_id, trigger.message_id,
                compose_answer(result["hits"], refined=True), thread_key, now,
            )
            self._record_decision(
                connection, "answer", trigger.trigger_id, thread_key, policy, "answered", now,
                ((hit["doc"]["id"], hit["score"]) for hit in result["hits"][:ANSWER_MAX_ITEMS]),
            )
            return "answered", "confident"
        tasks.create(
            connection, self.state_dir, kind="refine", trigger_id=trigger.trigger_id, thread_key=thread_key,
            policy_version=policy.version, now=now,
            payload={
                "question": trigger.text,
                "candidates": [candidate(hit["doc"], hit["score"]) for hit in result["hits"][:REFINE_CANDIDATES]],
                "fallback_doc_ids": [hit["doc"]["id"] for hit in result["hits"][:ANSWER_MAX_ITEMS]],
            },
        )
        return "refine", result["state"]

    def _queue_answer(
        self, connection: Any, key: str, chat_id: str, reply_to: str, text: str, thread_key: str, now: float
    ) -> None:
        outbox.enqueue(
            self.store, connection, key=key, kind="answer", chat_id=chat_id, reply_to=reply_to, text=text,
            thread_key=thread_key, now=now,
        )

    def _queue_refined_answer(self, connection: Any, task: dict[str, Any], text: str, now: float) -> None:
        """Answer the message that a refinement task belongs to."""

        event = self.store.fetchone("SELECT chat_id, message_id FROM events WHERE trigger_id=?", (task["trigger_id"],))
        if event is not None:
            self._queue_answer(connection, f"answer:{task['trigger_id']}", event["chat_id"], event["message_id"], text, task["thread_key"], now)

    def _fallback_answer(self, payload: dict[str, Any]) -> str:
        docs = [self.index.get(doc_id) for doc_id in payload.get("fallback_doc_ids") or []]
        return compose_answer([{"doc": doc} for doc in docs if doc], refined=False, unrefined=True)

    # ---- looking at discussions ---------------------------------------------------

    def sweep(self) -> dict[str, int]:
        """Look at what has arrived in the group, and finish tasks that will never be applied."""

        now = self.clock()
        policy = Policy.load(self.store)
        closed = 0
        for task in tasks.expire_stale(self.store, now):
            self._close(task, policy, now, "expired")
            closed += 1
        # Card copy does not depend on the policy, so a mode change leaves it in flight.
        for task in self.store.fetchall("SELECT * FROM tasks WHERE status='pending'"):
            if task["kind"] != "card_copy" and task["policy_version"] != policy.version:
                self._close(task, policy, now, "policy_changed")
                closed += 1
        return {"closed": closed, "looked": self._look_at_discussions(policy, now)}

    def _close(self, task: dict[str, Any], policy: Policy, now: float, why: str) -> None:
        """Finish a task that will never be applied: fall back or stay silent."""

        with self.store.transaction() as connection:
            if task["kind"] == "refine":
                payload = read_json(Path(task["input_path"]), {})
                self._queue_refined_answer(connection, task, self._fallback_answer(payload), now)
                self._move(connection, "trigger_id=?", (task["trigger_id"],), "refine", "answered", f"refine_{why}", now)
            elif task["kind"] == "contribute":
                self._move(connection, "thread_key=?", (task["thread_key"],), "evaluating", "silent", f"contribute_{why}", now)
        status = "expired" if why == "expired" else "invalid"
        tasks.mark(self.store, task["task_id"], status, now, result_json=json.dumps({"outcome": why}))

    def _look_at_discussions(self, policy: Policy, now: float) -> int:
        """Look at every discussion whose first waiting message arrived DEBOUNCE_SECONDS ago.

        Nothing waits for the discussion to go quiet: a lively one is looked at
        while it is still going, and what arrives before the look is answered
        joins it.
        """

        rows = self.store.fetchall(
            """
            SELECT d.thread_key AS thread_key, MIN(e.created_ms) AS first_ms
            FROM dispositions d JOIN events e ON e.trigger_id = d.trigger_id
            WHERE d.decision='pending'
            GROUP BY d.thread_key
            """
        )
        looked = 0
        for row in rows:
            if now * 1000 - row["first_ms"] < DEBOUNCE_SECONDS * 1000:
                continue
            with self.store.transaction() as connection:
                looked += self._look(connection, row["thread_key"], policy, now)
        return looked

    def _look(self, connection: Any, thread_key: str, policy: Policy, now: float) -> int:
        thread = connection.execute("SELECT * FROM threads WHERE thread_key=?", (thread_key,)).fetchone()
        if thread is None:
            self._move(connection, "thread_key=?", (thread_key,), "pending", "ignored", "no_thread", now)
            return 1
        in_flight = connection.execute(
            "SELECT * FROM tasks WHERE kind='contribute' AND thread_key=? AND status='pending'", (thread_key,)
        ).fetchone()
        if in_flight is not None:
            # The session is still thinking about this discussion: fold in what arrived since.
            self._refresh_contribution(connection, in_flight, thread, now)
            return 0
        if now * 1000 - (thread["last_task_ms"] or 0) < THREAD_MIN_INTERVAL_SECONDS * 1000:
            return 0
        reason = self._speech_gate(thread, policy, now)
        if reason:
            if reason == "breaker":
                self._breaker_notice(connection, now)
            self._move(connection, "thread_key=?", (thread_key,), "pending", "ignored", reason, now)
            return 1
        self._queue_contribution(connection, thread_key, thread, policy, now)
        connection.execute("UPDATE threads SET last_task_ms=?, updated_at=? WHERE thread_key=?", (int(now * 1000), iso(now), thread_key))
        return 1

    def _speech_gate(self, thread: dict[str, Any], policy: Policy, now: float) -> str:
        """Why the assistant may not speak in this discussion now; empty when it may."""

        if policy.proactive == "off":
            return "proactive_off"
        if policy.is_muted(now):
            return "muted"
        if thread["muted_at"]:
            return "thread_muted"
        if not self.config.is_working_time(local(now)):
            return "outside_working_hours"
        if self._proactive_last_hour(now) >= BREAKER_LIMIT:
            return "breaker"
        return ""

    def _proactive_last_hour(self, now: float) -> int:
        return self.store.fetchone(
            "SELECT COUNT(*) AS n FROM outbox WHERE kind IN ('recommendation', 'alert') AND status='sent' AND sent_at >= ?",
            (iso(now - 3600),),
        )["n"]

    def _breaker_notice(self, connection: Any, now: float) -> None:
        if self.store.fetchone("SELECT 1 FROM reports WHERE kind='notice' AND created_at >= ?", (iso(now - 3600),)) is None:
            self._notice(connection, f"主动发言一小时超过了 {BREAKER_LIMIT} 条，已暂停主动发言，点名照常回答。", now)

    def _queue_contribution(self, connection: Any, thread_key: str, thread: dict[str, Any], policy: Policy, now: float) -> None:
        tasks.create(
            connection, self.state_dir, kind="contribute", thread_key=thread_key, policy_version=policy.version,
            now=now, payload=self._contribution_payload(thread_key, thread, now),
        )
        self._move(connection, "thread_key=?", (thread_key,), "pending", "evaluating", "looking", now)

    def _refresh_contribution(self, connection: Any, task: dict[str, Any], thread: dict[str, Any], now: float) -> None:
        """More of the discussion arrived while the session was still thinking: give it the latest."""

        tasks.write_input(task, self._contribution_payload(task["thread_key"], thread, now))
        self._move(connection, "thread_key=?", (task["thread_key"],), "pending", "evaluating", "looking", now)

    def _contribution_payload(self, thread_key: str, thread: dict[str, Any], now: float) -> dict[str, Any]:
        messages, nearby, _ = self._discussion_window(thread_key)
        hits = search_discussion(self.index, [message["text"] for message in messages], CONTRIBUTE_CANDIDATES)
        payload: dict[str, Any] = {
            "messages": messages,
            "nearby": nearby,
            "already_said": self._already_said(thread_key),
            "retrieval": {"strength": hits[0]["strength"] if hits else 0.0},
            "candidates": [candidate(hit["doc"], hit["score"]) for hit in hits],
            "topics": self._topics,
            "recent_reports": self.store.fetchall(
                "SELECT title, created_at FROM reports WHERE kind='gap' AND created_at >= ? ORDER BY created_at DESC LIMIT 10",
                (iso(now - REPORT_LOOKBACK_DAYS * 86400),),
            ),
        }
        if thread["anchor_idea_id"]:
            payload["anchored_idea"] = candidate(self.index.get(f"idea:{thread['anchor_idea_id']}") or {"id": "", "kind": "idea", "title": ""})
        return payload

    def queue_alert(self, issue_date: str, now: float) -> bool:
        """A new issue is out: ask the session which of it matters to this group. At most once an issue."""

        key = f"alert:{issue_date}"
        policy = Policy.load(self.store)
        with self.store.transaction() as connection:
            done = connection.execute(
                "SELECT 1 FROM tasks WHERE kind='alert' AND thread_key=? UNION SELECT 1 FROM decisions WHERE kind='alert' AND thread_key=?",
                (key, key),
            ).fetchone()
            if done:
                return False
            tasks.create(
                connection, self.state_dir, kind="alert", thread_key=key, policy_version=policy.version, now=now,
                payload=self._alert_payload(issue_date, now),
            )
        return True

    def _alert_payload(self, issue_date: str, now: float) -> dict[str, Any]:
        """A new issue beside what the group has been discussing, so the session can tie them together."""

        issue = [doc for doc in self.index.docs if doc["kind"] in ("item", "judgement") and doc.get("issue_date") == issue_date]
        discussions: list[dict[str, Any]] = []
        threads = self.store.fetchall(
            "SELECT thread_key FROM threads WHERE anchor_idea_id IS NULL ORDER BY last_activity_ms DESC LIMIT 12"
        )
        for thread in threads:
            discussions += self._discussion_window(thread["thread_key"])[0][-3:]
        for message in discussions:
            message["text"] = message["text"][:200]
        return {
            "issue": {"date": issue_date, "headline": self._issue_headline(issue_date)},
            "items": [
                {**candidate(doc), "project_relevance": (doc.get("project_relevance") or "")[:200]}
                for doc in issue if doc["kind"] == "item"
            ],
            "judgements": [candidate(doc) for doc in issue if doc["kind"] == "judgement"],
            "discussions": discussions[-40:],
            "reported_gaps": self.store.fetchall(
                "SELECT title FROM reports WHERE kind='gap' AND created_at >= ? ORDER BY created_at DESC LIMIT 10",
                (iso(now - REPORT_LOOKBACK_DAYS * 86400),),
            ),
        }

    def _issue_headline(self, issue_date: str) -> str:
        reader = read_json(self.root / "archive" / "issues" / issue_date / "reader.json", {})
        return str(reader.get("headline") or "")[:200]

    def _already_said(self, thread_key: str) -> list[dict[str, Any]]:
        """What the assistant has cited in this discussion before, so it does not repeat itself."""

        said: list[dict[str, Any]] = []
        rows = self.store.fetchall(
            "SELECT doc_ids_json, created_at FROM decisions WHERE thread_key=? AND outcome IN ('said', 'answered', 'refined') ORDER BY created_at",
            (thread_key,),
        )
        for row in rows:
            for doc_id in json.loads(row["doc_ids_json"]):
                doc = self.index.get(doc_id)
                if doc is not None:
                    said.append({"id": doc_id, "title": doc.get("headline") or doc["title"], "at": row["created_at"]})
        return said[:10]

    def _discussion_window(self, thread_key: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
        """The latest messages of a discussion with senders replaced by labels, and the labels themselves."""

        rows = self.store.fetchall(
            "SELECT * FROM events WHERE thread_key=? ORDER BY created_ms DESC, trigger_id DESC LIMIT ?",
            (thread_key, WINDOW_MAX_MESSAGES),
        )[::-1]
        nearby: list[dict[str, Any]] = []
        if rows:
            nearby = self.store.fetchall(
                "SELECT * FROM events WHERE chat_id=? AND created_ms < ? AND thread_key <> ? ORDER BY created_ms DESC LIMIT ?",
                (rows[0]["chat_id"], rows[0]["created_ms"], thread_key, CONTEXT_NEIGHBOURS),
            )[::-1]
        aliases: dict[str, str] = {}

        def label(sender_id: str) -> str:
            if sender_id not in aliases:
                aliases[sender_id] = f"同事 {chr(ord('A') + len(aliases))}"
            return aliases[sender_id]

        def shape(row: dict[str, Any], with_time: bool) -> dict[str, Any]:
            text = row["text"][:MESSAGE_CHAR_LIMIT] + (TRUNCATED_NOTE if len(row["text"]) > MESSAGE_CHAR_LIMIT else "")
            message = {"sender": label(row["sender_id"]), "text": text}
            return {**message, "at": iso(row["created_ms"] / 1000)} if with_time else message

        return [shape(row, True) for row in rows], [shape(row, False) for row in nearby], aliases

    # ---- applying what a session wrote ---------------------------------------------

    def apply_task(self, task_id: str, output: dict[str, Any] | None, output_error: str = "") -> dict[str, Any]:
        """Validate a host session's output and act on it. Invalid output is final."""

        task = tasks.get(self.store, task_id)
        if task is None:
            return {"ok": False, "errors": [f"Unknown task: {task_id}"]}
        now = self.clock()
        policy = Policy.load(self.store)
        if task["status"] == "pending" and tasks.is_expired(task, now):
            tasks.expire_stale(self.store, now)
            self._close(task, policy, now, "expired")
            return {"ok": False, "errors": [f"Task expired at {iso(task['expires_ms'] / 1000)}"]}
        if task["status"] != "pending":
            return {"ok": False, "errors": [f"Task is already {task['status']}"]}
        payload = read_json(Path(task["input_path"]), {})
        errors = [output_error] if output_error else tasks.schema_errors(task["kind"], output or {}, self.root)
        if task["kind"] != "card_copy" and task["policy_version"] != policy.version:
            errors.append("The policy changed after this task was created")
        if not errors:
            errors = self._semantic_errors(task, output or {}, payload)
        if errors:
            self._reject(task, policy, now)
            return {"ok": False, "errors": errors}
        outcome = self._accept(task, output or {}, payload, policy, now)
        return {"ok": True, **outcome}

    def _semantic_errors(self, task: dict[str, Any], output: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        foreign = self._foreign_urls(output)
        if foreign:
            errors.append(f"Output contains a link outside the index: {foreign[0]}")
        if task["kind"] == "refine":
            errors += self._refine_errors(task, output, payload)
        elif task["kind"] == "contribute":
            errors += self._contribute_errors(task, output, payload)
        elif task["kind"] == "alert":
            errors += self._alert_errors(output, payload)
        elif task["kind"] == "card_copy":
            for field in ("headline", "summary", "why_it_matters"):
                if INTERNAL_FIELD.search(output.get(field) or ""):
                    errors.append(f"{field} contains an internal field name")
        return errors

    def _foreign_urls(self, value: Any) -> list[str]:
        """Links in a host session's output that the published corpus does not carry."""

        if isinstance(value, str):
            return [url for url in URL.findall(value) if not any(url.startswith(known) for known in self.known_urls)]
        if isinstance(value, dict):
            return [url for item in value.values() for url in self._foreign_urls(item)]
        if isinstance(value, list):
            return [url for item in value for url in self._foreign_urls(item)]
        return []

    def _citable(self, task: dict[str, Any], payload: dict[str, Any]) -> set[str]:
        """Every document the session was shown for this task, by the input or by its own searches."""

        return {candidate["id"] for candidate in payload.get("candidates") or []} | tasks.seen_ids(self.store, task["task_id"])

    def _check_citations(self, citations: list[dict[str, Any]], citable: set[str], texts: list[str], errors: list[str]) -> list[dict[str, Any]]:
        """Every citation must name a document the session saw and quote the discussion verbatim."""

        docs = []
        for citation in citations:
            if citation["doc_id"] not in citable:
                errors.append(f"doc_id was not shown for this task: {citation['doc_id']}")
            elif not any(citation["quote"] in text for text in texts):
                errors.append(f"quote is not verbatim from the discussion: {citation['quote']!r}")
            doc = self.index.get(citation["doc_id"])
            if doc is not None:
                docs.append(doc)
        return docs

    def _framing_errors(self, framing: str, quote: str, docs: list[dict[str, Any]], texts: list[str]) -> list[str]:
        """The framing must answer the discussion and may only use numbers it was given."""

        errors = []
        if not any(quote in text for text in texts):
            errors.append(f"quote is not verbatim: {quote!r}")
        allowed = _numbers(" ".join([*(_published(doc) for doc in docs if doc), *texts]))
        for number in sorted(_numbers(framing) - allowed):
            errors.append(f"a number in the framing appears in no cited document nor in the discussion: {number}")
        return errors

    def _refine_errors(self, task: dict[str, Any], output: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        citable = self._citable(task, payload)
        question = payload.get("question", "")
        docs = []
        for selection in output.get("selected") or []:
            if selection["doc_id"] not in citable:
                errors.append(f"doc_id was not shown for this task: {selection['doc_id']}")
            if selection["quote"] not in question:
                errors.append(f"quote is not verbatim from the question: {selection['quote']!r}")
            doc = self.index.get(selection["doc_id"])
            if doc is not None:
                docs.append(doc)
        if output.get("none_relevant") and output.get("selected"):
            errors.append("none_relevant cannot be combined with a selection")
        if output.get("framing"):
            errors += self._framing_errors(output["framing"], (output.get("selected") or [{"quote": ""}])[0]["quote"], docs, [question])
        return errors

    def _contribute_errors(self, task: dict[str, Any], output: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        texts = [message["text"] for message in (payload.get("messages") or []) + (payload.get("nearby") or [])]
        citable = self._citable(task, payload)
        said = {item["id"] for item in payload.get("already_said") or []}
        act = output["act"]
        if act == "add":
            docs = self._check_citations(output["items"], citable, texts, errors)
            for citation in output["items"]:
                if citation["doc_id"] in said:
                    errors.append(f"already said in this discussion: {citation['doc_id']}")
            errors += self._framing_errors(output["framing"], output["quote"], docs, texts)
        elif act == "review":
            review = output["review"]
            ids = [review["closest_idea"]] if review["closest_idea"] else []
            for doc_id in ids:
                if doc_id not in citable:
                    errors.append(f"doc_id was not shown for this task: {doc_id}")
                elif (self.index.get(doc_id) or {}).get("kind") != "idea":
                    errors.append(f"closest_idea must be an idea: {doc_id}")
            docs = [self.index.get(doc_id) for doc_id in ids if self.index.get(doc_id)]
            docs += self._check_citations(list(review["supporting"]) + list(review["counter"]), citable, texts, errors)
            errors += self._framing_errors(output["framing"], output["quote"], docs, texts)
        elif act == "gap":
            gap = output["gap"]
            if not any(output["quote"] in text for text in texts):
                errors.append(f"quote is not verbatim: {output['quote']!r}")
            if gap["nearest"] and gap["nearest"] not in topics.known_scope_ids(self._topics):
                errors.append(f"nearest must name a configured topic or direction: {gap['nearest']}")
        return errors

    def _alert_errors(self, output: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        shown = {doc["id"] for doc in [*(payload.get("items") or []), *(payload.get("judgements") or [])]}
        texts = [message["text"] for message in payload.get("discussions") or []]
        for pick in output["picks"]:
            if pick["doc_id"] not in shown:
                errors.append(f"doc_id is not from this issue: {pick['doc_id']}")
            errors += self._framing_errors(pick["why"], pick["quote"], [self.index.get(pick["doc_id"])], texts)
        return errors

    def _reject(self, task: dict[str, Any], policy: Policy, now: float) -> None:
        """Invalid output is final: fall back or stay silent, never ask again."""

        self._close(task, policy, now, "invalid")

    def _accept(self, task: dict[str, Any], output: dict[str, Any], payload: dict[str, Any], policy: Policy, now: float) -> dict[str, Any]:
        outcome: dict[str, Any] = {}
        with self.store.transaction() as connection:
            if task["kind"] == "refine":
                outcome = self._apply_refine(connection, task, output, policy, now)
            elif task["kind"] == "contribute":
                outcome = self._apply_contribution(connection, task, output, policy, now)
            elif task["kind"] == "alert":
                outcome = self._apply_alert(connection, task, output, policy, now)
            else:
                drafts = self.store.get_meta("card_drafts", {})
                idea_id = payload.get("idea", {}).get("idea_id", "")
                drafts[idea_id] = {**output, "task_id": task["task_id"]}
                self.store.set_meta("card_drafts", drafts, connection)
                outcome = {"outcome": "card_draft_stored", "idea_id": idea_id}
        tasks.mark(self.store, task["task_id"], "applied", now, result_json=json.dumps(outcome, ensure_ascii=False))
        return outcome

    def _apply_refine(self, connection: Any, task: dict[str, Any], output: dict[str, Any], policy: Policy, now: float) -> dict[str, Any]:
        docs = [self.index.get(selection["doc_id"]) for selection in output.get("selected") or []]
        found = [doc for doc in docs if doc]
        framing = output.get("framing") or ""
        text = compose_answer([{"doc": doc} for doc in found], framing=framing, refined=True) if found else NO_MATCH_TEXT
        self._queue_refined_answer(connection, task, text, now)
        reason = "refined" if found else "none_relevant"
        self._move(connection, "trigger_id=?", (task["trigger_id"],), "refine", "answered", reason, now)
        self._record_decision(
            connection, "refine", task["trigger_id"], task["thread_key"], policy, reason, now, ((doc["id"], 0.0) for doc in found)
        )
        return {"outcome": reason}

    def _apply_contribution(self, connection: Any, task: dict[str, Any], output: dict[str, Any], policy: Policy, now: float) -> dict[str, Any]:
        act = output["act"]
        thread_key = task["thread_key"]
        draft = None
        if act == "none":
            outcome = "silent"
        elif act == "gap":
            self._save_report(connection, task, output, now)
            outcome = "reported"
        else:
            draft = self._draft(act, output)
            if policy.proactive == "observe":
                outcome = "observe_would_say"
            else:
                chat_id, root = thread_key.split(":", 1)
                outbox.enqueue(
                    self.store, connection, key=f"recommendation:{thread_key}:{int(now)}", kind="recommendation",
                    chat_id=chat_id, reply_to=root, text=draft or "", thread_key=thread_key, now=now,
                )
                outcome = "said"
        cited = [citation["doc_id"] for citation in output.get("items") or []]
        if act == "review":
            cited += [output["review"]["closest_idea"]] if output["review"]["closest_idea"] else []
            cited += [c["doc_id"] for c in output["review"]["supporting"]]
        self._record_decision(
            connection, "contribute", None, thread_key, policy, outcome, now, ((doc_id, 0.0) for doc_id in cited), act=act, draft=draft
        )
        target = {"said": "spoken", "reported": "reported"}.get(outcome, "silent")
        self._move(connection, "thread_key=?", (thread_key,), "evaluating", target, f"{act}:{outcome}", now)
        return {"outcome": outcome, "act": act}

    def _apply_alert(self, connection: Any, task: dict[str, Any], output: dict[str, Any], policy: Policy, now: float) -> dict[str, Any]:
        issue_date = task["thread_key"][len("alert:"):]
        draft = compose_alert(
            issue_date, [{"why": pick["why"], "doc": self.index.get(pick["doc_id"])} for pick in output["picks"]]
        ) if output["picks"] else None
        outcome = "silent"
        if draft is not None:
            if policy.proactive == "observe":
                outcome = "observe_would_say"
            else:
                outbox.enqueue(
                    self.store, connection, key=task["thread_key"], kind="alert", chat_id=self.config.chat_whitelist[0],
                    reply_to="", text=draft, thread_key=task["thread_key"], now=now,
                )
                outcome = "said"
        self._record_decision(
            connection, "alert", None, task["thread_key"], policy, outcome, now,
            ((pick["doc_id"], 0.0) for pick in output["picks"]), act="alert", draft=draft,
        )
        return {"outcome": outcome, "picks": len(output["picks"])}

    def _draft(self, act: str, output: dict[str, Any]) -> str | None:
        if act == "add":
            docs = [self.index.get(citation["doc_id"]) for citation in output["items"]]
            return compose_add(output["framing"], [doc for doc in docs if doc])
        review = output["review"]
        closest = self.index.get(review["closest_idea"]) if review["closest_idea"] else None
        supporting = [self.index.get(c["doc_id"]) for c in review["supporting"]]
        counter = [self.index.get(c["doc_id"]) for c in review["counter"]]
        return compose_review(
            output["framing"], closest=closest, supporting=[doc for doc in supporting if doc],
            counter=[doc for doc in counter if doc], missing=review["missing"],
        )

    def _save_report(self, connection: Any, task: dict[str, Any], output: dict[str, Any], now: float) -> str:
        """Record a coverage gap and, within the day's budget, tell the owner privately."""

        messages, _, aliases = self._discussion_window(task["thread_key"])
        names = self.store.get_meta("member_names", {})
        nearest = output["gap"]["nearest"] or ""
        report_id = f"gap-{stable_hash(task['thread_key'], int(now * 1000))[:16]}"
        created_at = iso(now)
        body = {
            "texts": [message["text"] for message in messages],
            "names": [names.get(sender_id) or label for sender_id, label in aliases.items()],
            "summary": output["gap"]["summary"],
            "nearest": nearest,
            "nearest_label": reports.scope_label(nearest, self._topics) if nearest else "",
            "terms": output["gap"]["terms"][:REPORT_TERMS],
            "placement": output["gap"]["placement"],
        }
        status = "recorded"
        owner = self.store.get_meta("report_to")
        if owner and self._reports_today(now) < REPORTS_PER_DAY:
            outbox.enqueue(
                self.store, connection, key=f"report:{report_id}", kind="report", chat_id=owner["chat_id"], reply_to="",
                text=reports.gap_text(report_id, body, created_at=created_at), thread_key=task["thread_key"], now=now,
            )
            status = "queued"
        connection.execute(
            "INSERT INTO reports(id, kind, thread_key, title, body_json, status, created_at) VALUES(?, 'gap', ?, ?, ?, ?, ?)",
            (report_id, task["thread_key"], body["summary"][:80], json.dumps(body, ensure_ascii=False), status, created_at),
        )
        return report_id

    def _reports_today(self, now: float) -> int:
        return self.store.fetchone(
            "SELECT COUNT(*) AS n FROM reports WHERE kind='gap' AND status IN ('queued', 'sent') AND created_at >= ?",
            (iso(day_start(now)),),
        )["n"]

    def _notice(self, connection: Any, text: str, now: float) -> None:
        """Tell the owner privately that the assistant stopped speaking on its own."""

        owner = self.store.get_meta("report_to")
        notice_id = f"notice-{stable_hash(text, int(now * 1000))[:12]}"
        status = "recorded"
        if owner:
            outbox.enqueue(
                self.store, connection, key=f"report:{notice_id}", kind="report", chat_id=owner["chat_id"], reply_to="",
                text=reports.notice_text(text), thread_key=None, now=now,
            )
            status = "queued"
        connection.execute(
            "INSERT INTO reports(id, kind, thread_key, title, body_json, status, created_at) VALUES(?, 'notice', NULL, ?, ?, ?, ?)",
            (notice_id, text[:80], json.dumps({"text": text}, ensure_ascii=False), status, iso(now)),
        )

    def _record_decision(
        self, connection: Any, kind: str, trigger_id: str | None, thread_key: str | None, policy: Policy,
        outcome: str, now: float, cited: Iterable[tuple[str, float]] = (), *, act: str | None = None, draft: str | None = None,
    ) -> None:
        cited = list(cited)
        connection.execute(
            """
            INSERT OR IGNORE INTO decisions(id, kind, thread_key, trigger_id, policy_version, mode, outcome, act,
                                           rules_json, doc_ids_json, scores_json, draft, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?, ?)
            """,
            (
                stable_hash(kind, trigger_id or thread_key or act, policy.version, int(now * 1000))[:16], kind, thread_key,
                trigger_id, policy.version, "explicit" if kind != "contribute" else policy.proactive, outcome, act,
                json.dumps([doc_id for doc_id, _ in cited]), json.dumps({doc_id: round(score, 3) for doc_id, score in cited}),
                draft, iso(now),
            ),
        )

    # ---- feedback ---------------------------------------------------------------

    def on_reaction(self, reaction: dict[str, Any], now: float | None = None) -> dict[str, Any]:
        """Record a 👍 / 👎 on a reply or an idea card. A 👎 on a reply also silences that discussion."""

        now = self.clock() if now is None else now
        emoji, message_id = reaction.get("emoji") or "", reaction.get("message_id") or ""
        if reaction.get("operator_is_bot"):
            return {"recorded": False}
        # Outbox and registry have different columns, so look them up in turn.
        reply = self.store.fetchone("SELECT * FROM outbox WHERE message_id=?", (message_id,))
        card = None if reply else self.store.fetchone("SELECT * FROM registry WHERE message_id=?", (message_id,))
        message = reply or card
        if message is None:
            return {"recorded": False}
        choice = (CARD_REACTIONS if card else REPLY_REACTIONS).get(emoji)
        if choice is None:
            return {"recorded": False}
        feedback_id = f"{message_id}:{reaction.get('operator_id') or ''}:{choice}"
        with self.store.transaction() as connection:
            if reaction.get("removed"):
                removed = connection.execute("DELETE FROM feedback WHERE id=?", (feedback_id,)).rowcount
                return {"removed": removed > 0}
            connection.execute(
                "INSERT OR IGNORE INTO feedback(id, message_id, idea_id, choice, operator_id, source, created_at) VALUES(?, ?, ?, ?, ?, 'reaction', ?)",
                (
                    feedback_id, message_id, message.get("idea_id") or None, choice, reaction.get("operator_id") or "", iso(now),
                ),
            )
            if reply and choice == "down":
                connection.execute(
                    "UPDATE threads SET muted_at=? WHERE thread_key=? AND muted_at IS NULL", (iso(now), reply["thread_key"])
                )
        paused = self._pause_on_dislikes(now) if reply else 0
        return {"recorded": True, "choice": choice, "paused": paused}

    def on_card_action(self, action: dict[str, Any], now: float | None = None) -> dict[str, Any]:
        """Record a button press on an idea card, trusting the registry over the payload."""

        now = self.clock() if now is None else now
        card = self.store.fetchone("SELECT * FROM registry WHERE message_id=?", (action.get("message_id"),))
        if card is None or not action.get("choice") or action.get("operator_id") in self.bot_ids:
            return {"recorded": False}
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO feedback(id, message_id, idea_id, choice, operator_id, source, created_at) VALUES(?, ?, ?, ?, ?, 'button', ?)",
                (f"{card['message_id']}:{action['operator_id']}:{action['choice']}", card["message_id"], card["idea_id"],
                 action["choice"], action["operator_id"], iso(now)),
            )
        return {"recorded": True, "idea_id": card["idea_id"], "choice": action["choice"]}

    def _pause_on_dislikes(self, now: float) -> int:
        rows = self.store.fetchall(
            """
            SELECT f.choice FROM feedback f JOIN outbox o ON o.message_id=f.message_id
            WHERE f.source='reaction' AND f.created_at >= ?
            """,
            (iso(now - 7 * 86400),),
        )
        if len(rows) < DISLIKE_PAUSE_MIN_SAMPLES:
            return 0
        downs = sum(1 for row in rows if row["choice"] == "down")
        if downs / len(rows) < DISLIKE_PAUSE_RATIO:
            return 0
        policy = Policy.load(self.store)
        if policy.proactive == "off":
            return 0
        with self.store.transaction() as connection:
            policy.proactive = "off"
            policy.save(self.store, connection)
            connection.execute("INSERT INTO pause_log(reason, created_at) VALUES(?, ?)", ("dislike_ratio", iso(now)))
        return 1
