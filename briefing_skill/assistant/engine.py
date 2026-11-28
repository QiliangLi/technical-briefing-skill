"""The deterministic core of the group assistant.

Every message passes Source filters and the admission table before anything
else. The engine is the only writer of assistant state. It answers directly
when lexical retrieval is confident and queues a semantic task otherwise.
Proactive recommendations stay behind code-enforced gates; the host session
only proposes, and a proposal that fails a check ends in silence.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from ..utils import read_json, stable_hash
from . import outbox, tasks
from .config import AssistantConfig
from .constants import (
    ANCHORED_MIN_MESSAGES,
    ASSESS_CANDIDATES,
    CLUSTER_MAX_GAP_SECONDS,
    CLUSTER_WINDOW_SECONDS,
    CONTEXT_NEIGHBOURS,
    DAILY_PROACTIVE_CAP,
    DISLIKE_PAUSE_MIN_SAMPLES,
    DISLIKE_PAUSE_RATIO,
    EMOJI_THUMBS_DOWN,
    EMOJI_THUMBS_UP,
    EXPLICIT_RATE_PER_MINUTE,
    MESSAGE_CHAR_LIMIT,
    OBSERVE_COOLDOWN_SECONDS,
    QUIET_SECONDS,
    REFINE_CANDIDATES,
    SHAPE_MIN_MESSAGES,
    SHAPE_MIN_SENDERS,
    STALE_SECONDS,
    THREAD_COOLDOWN_SECONDS,
    WINDOW_MAX_MESSAGES,
)
from .events import Trigger
from .policy import RULES, Policy, admit
from .replies import NO_MATCH_TEXT, URL, compose_answer, compose_recommendation, first_sentence
from .retrieval import LexicalIndex, assess
from .store import Store, text_hash
from .timeutil import day_key, iso, local

INTERNAL_FIELD = re.compile(r"hypothesis|problem_key|mechanism_key|validation_plan|decision_log|idea_id|brief_item")
TRUNCATED_NOTE = "…（已截断）"


def _candidate(doc: dict[str, Any], score: float = 0.0) -> dict[str, Any]:
    """What the host session may see of one retrieval hit."""
    return {
        "id": doc["id"],
        "kind": doc["kind"],
        "title": doc["title"],
        "date": doc.get("issue_date") or "",
        "summary": first_sentence(doc.get("summary") or "", 120),
        "score": round(score, 3),
    }


def _scores(pairs: Iterable[tuple[str, float]]) -> str:
    return json.dumps({doc_id: round(score, 3) for doc_id, score in pairs})


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

    # ---- intake -----------------------------------------------------------------

    def reindex(self, index: LexicalIndex) -> None:
        """Swap in a rebuilt index; tasks in flight keep the candidates they were cut from."""

        self.index = index
        self.known_urls = frozenset(doc["url"] for doc in index.docs)

    def ingest(self, trigger: Trigger) -> dict[str, str]:
        """Run one message through Source filters, admission and the answer path."""

        now = self.clock()
        if trigger.sender_id in self.bot_ids:
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
                        outcome = ("pending", "awaiting_shape")
            self._set_disposition(connection, trigger, thread_key, outcome[0], outcome[1], now)
        return {"decision": outcome[0], "reason": outcome[1]}

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
                ((hit["doc"]["id"], hit["score"]) for hit in result["hits"][:3]),
            )
            return "answered", "confident"
        tasks.create(
            connection,
            self.state_dir,
            kind="refine",
            trigger_id=trigger.trigger_id,
            thread_key=thread_key,
            policy_version=policy.version,
            now=now,
            payload={
                "question": trigger.text,
                "candidates": [_candidate(hit["doc"], hit["score"]) for hit in result["hits"][:REFINE_CANDIDATES]],
                "fallback_doc_ids": [hit["doc"]["id"] for hit in result["hits"][:3]],
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
            key = f"answer:{task['trigger_id']}"
            self._queue_answer(connection, key, event["chat_id"], event["message_id"], text, task["thread_key"], now)

    def _fallback_answer(self, payload: dict[str, Any]) -> str:
        docs = [self.index.get(doc_id) for doc_id in payload.get("fallback_doc_ids") or []]
        return compose_answer([{"doc": doc} for doc in docs if doc], refined=False, unrefined=True)

    # ---- periodic work ----------------------------------------------------------

    def sweep(self) -> dict[str, int]:
        """Evaluate quiet discussions, close stale tasks and apply the self-checks."""

        now = self.clock()
        policy = Policy.load(self.store)
        closed = 0
        for task in tasks.expire_stale(self.store, now):
            self._close(task, policy, now, "expired")
            closed += 1
        for task in self.store.fetchall("SELECT * FROM tasks WHERE status='pending'"):
            if task["policy_version"] != policy.version:
                self._close(task, policy, now, "policy_changed")
                closed += 1
        assessed = self._evaluate_discussions(policy, now)
        paused = self._auto_pause(policy, now)
        return {"closed": closed, "assessed": assessed, "paused": paused}

    def _close(self, task: dict[str, Any], policy: Policy, now: float, why: str) -> None:
        """Finish a task that will never be applied: fall back or stay silent."""

        with self.store.transaction() as connection:
            if task["kind"] == "refine":
                payload = read_json(Path(task["input_path"]), {})
                self._queue_refined_answer(connection, task, self._fallback_answer(payload), now)
                self._move(connection, "trigger_id=?", (task["trigger_id"],), "refine", "answered", f"refine_{why}", now)
            elif task["kind"] == "assess":
                self._move(connection, "thread_key=?", (task["thread_key"],), "evaluating", "ignored", f"assess_{why}", now)
        status = "expired" if why == "expired" else "invalid"
        tasks.mark(self.store, task["task_id"], status, now, result_json=json.dumps({"outcome": why}))

    def _evaluate_discussions(self, policy: Policy, now: float) -> int:
        # Only the messages still waiting for a verdict count as this round of
        # the discussion, so one late reply cannot reopen an old thread.
        pending_threads = self.store.fetchall(
            """
            SELECT d.thread_key AS thread_key, MAX(e.created_ms) AS last_ms, COUNT(*) AS messages,
                   COUNT(DISTINCT e.sender_id) AS senders
            FROM dispositions d JOIN events e ON e.trigger_id = d.trigger_id
            WHERE d.decision='pending'
            GROUP BY d.thread_key
            """
        )
        assessed = 0
        for row in pending_threads:
            if now * 1000 - row["last_ms"] < QUIET_SECONDS * 1000:
                continue
            with self.store.transaction() as connection:
                thread = connection.execute("SELECT * FROM threads WHERE thread_key=?", (row["thread_key"],)).fetchone()
                reason = self._shape_gate(row, thread, policy, now)
                if reason:
                    outcome = ("ignored", reason)
                else:
                    self._queue_assessment(connection, row["thread_key"], thread, policy, now)
                    outcome = ("evaluating", "assessment_created")
                self._move(connection, "thread_key=?", (row["thread_key"],), "pending", outcome[0], outcome[1], now)
            assessed += 1
        return assessed

    def _shape_gate(self, row: dict[str, Any], thread: dict[str, Any], policy: Policy, now: float) -> str:
        """Return why a quiet discussion is not assessed, or an empty string to assess it."""

        anchored = bool(thread["anchor_idea_id"])
        if row["messages"] < (ANCHORED_MIN_MESSAGES if anchored else SHAPE_MIN_MESSAGES):
            return "too_few_messages"
        if row["senders"] < (1 if anchored else SHAPE_MIN_SENDERS):
            return "single_speaker"
        if policy.proactive == "off":
            return "proactive_off"
        if policy.is_muted(now):
            return "muted"
        if thread["muted_at"]:
            return "thread_muted"
        if not self.config.is_working_time(local(now)):
            return "outside_working_hours"
        last_recommended = thread["last_recommended_ms"] or 0
        if now * 1000 - last_recommended < THREAD_COOLDOWN_SECONDS * 1000:
            return "thread_cooldown"
        if policy.proactive == "observe" and thread["last_assessed_ms"] and now * 1000 - thread["last_assessed_ms"] < OBSERVE_COOLDOWN_SECONDS * 1000:
            return "observe_cooldown"
        if self._recommendations_sent(now) >= DAILY_PROACTIVE_CAP:
            return "daily_cap"
        return ""

    def _recommendations_sent(self, now: float) -> int:
        start = iso(now - 86400)
        rows = self.store.fetchall("SELECT sent_at FROM outbox WHERE kind='recommendation' AND status='sent' AND sent_at >= ?", (start,))
        return sum(1 for row in rows if (row["sent_at"] or "")[:10] == day_key(now))

    def _queue_assessment(self, connection: Any, thread_key: str, thread: dict[str, Any], policy: Policy, now: float) -> None:
        messages, nearby = self._discussion_window(thread_key)
        query = " ".join(message["text"] for message in messages[-6:])
        hits = self.index.search(query, ASSESS_CANDIDATES)
        payload: dict[str, Any] = {
            "messages": messages,
            "nearby": nearby,
            "rules": [{"id": rule_id, **RULES[rule_id]} for rule_id in policy.enabled_rules()],
            "candidates": [_candidate(hit["doc"], hit["score"]) for hit in hits],
        }
        if thread["anchor_idea_id"]:
            payload["anchored_idea"] = _candidate(self.index.get(f"idea:{thread['anchor_idea_id']}") or {"id": "", "kind": "idea", "title": ""})
        tasks.create(
            connection, self.state_dir, kind="assess", thread_key=thread_key, policy_version=policy.version, now=now, payload=payload,
        )
        connection.execute("UPDATE threads SET last_assessed_ms=?, updated_at=? WHERE thread_key=?", (int(now * 1000), iso(now), thread_key))

    def _discussion_window(self, thread_key: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """The latest messages of a discussion with senders replaced by labels."""

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

        return [shape(row, True) for row in rows], [shape(row, False) for row in nearby]

    def _auto_pause(self, policy: Policy, now: float) -> int:
        if policy.proactive != "off" and self._recommendations_sent(now) >= DAILY_PROACTIVE_CAP:
            self._pause(policy, "daily_cap", now)
            return 1
        return 0

    def _pause(self, policy: Policy, reason: str, now: float) -> None:
        policy.proactive = "off"
        with self.store.transaction() as connection:
            policy.save(self.store, connection)
            connection.execute("INSERT INTO pause_log(reason, created_at) VALUES(?, ?)", (reason, iso(now)))

    # ---- semantic tasks ---------------------------------------------------------

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
        if task["policy_version"] != policy.version:
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
        known = {candidate["id"] for candidate in payload.get("candidates") or []}
        if task["kind"] == "refine":
            for selection in output.get("selected") or []:
                if selection["doc_id"] not in known:
                    errors.append(f"doc_id is not one of the candidates: {selection['doc_id']}")
                if selection["quote"] not in payload.get("question", ""):
                    errors.append(f"quote is not verbatim from the question: {selection['quote']!r}")
            if output.get("none_relevant") and output.get("selected"):
                errors.append("none_relevant cannot be combined with a selection")
        elif task["kind"] == "assess":
            expected = sorted(rule["id"] for rule in payload.get("rules") or [])
            if sorted(rule["rule_id"] for rule in output.get("rules") or []) != expected:
                errors.append(f"rules must cover exactly: {', '.join(expected)}")
            texts = [message["text"] for message in (payload.get("messages") or []) + (payload.get("nearby") or [])]
            for rule in output.get("rules") or []:
                if rule["matches"] and not any(rule["evidence_quote"] and rule["evidence_quote"] in text for text in texts):
                    errors.append(f"evidence_quote is not verbatim for rule {rule['rule_id']}")
            if output.get("doc_id") and output["doc_id"] not in known:
                errors.append(f"doc_id is not one of the candidates: {output['doc_id']}")
        elif task["kind"] == "card_copy":
            for field in ("headline", "summary", "why_it_matters"):
                if INTERNAL_FIELD.search(output.get(field) or ""):
                    errors.append(f"{field} contains an internal field name")
        return errors

    def _foreign_urls(self, value: Any) -> list[str]:
        """Links in a host session's output that the published corpus does not carry."""

        if isinstance(value, str):
            return [
                url for url in URL.findall(value) if not any(url.startswith(known) for known in self.known_urls)
            ]
        if isinstance(value, dict):
            return [url for item in value.values() for url in self._foreign_urls(item)]
        if isinstance(value, list):
            return [url for item in value for url in self._foreign_urls(item)]
        return []

    def _reject(self, task: dict[str, Any], policy: Policy, now: float) -> None:
        """Invalid output is final: fall back or stay silent, never ask again."""

        self._close(task, policy, now, "invalid")

    def _accept(self, task: dict[str, Any], output: dict[str, Any], payload: dict[str, Any], policy: Policy, now: float) -> dict[str, Any]:
        outcome: dict[str, Any] = {}
        with self.store.transaction() as connection:
            if task["kind"] == "refine":
                scores = {candidate["id"]: candidate["score"] for candidate in payload.get("candidates") or []}
                selected = [self.index.get(selection["doc_id"]) for selection in output.get("selected") or []]
                text = compose_answer([{"doc": doc} for doc in selected if doc], refined=True) if selected else NO_MATCH_TEXT
                self._queue_refined_answer(connection, task, text, now)
                reason = "refined" if selected else "none_relevant"
                self._move(connection, "trigger_id=?", (task["trigger_id"],), "refine", "answered", reason, now)
                self._record_decision(
                    connection, "refine", task["trigger_id"], task["thread_key"], policy, reason, now,
                    [(doc["id"], scores.get(doc["id"], 0.0)) for doc in selected if doc],
                )
                outcome = {"outcome": reason}
            elif task["kind"] == "assess":
                outcome = self._apply_assessment(connection, task, output, payload, policy, now)
            else:
                drafts = self.store.get_meta("card_drafts", {})
                idea_id = payload.get("idea", {}).get("idea_id", "")
                drafts[idea_id] = {**output, "task_id": task["task_id"]}
                self.store.set_meta("card_drafts", drafts, connection)
                outcome = {"outcome": "card_draft_stored", "idea_id": idea_id}
        tasks.mark(self.store, task["task_id"], "applied", now, result_json=json.dumps(outcome, ensure_ascii=False))
        return outcome

    def _apply_assessment(
        self, connection: Any, task: dict[str, Any], output: dict[str, Any], payload: dict[str, Any], policy: Policy, now: float
    ) -> dict[str, Any]:
        matched = [rule["rule_id"] for rule in output["rules"] if rule["matches"]]
        doc = self.index.get(output["doc_id"]) if output.get("doc_id") else None
        eligible = bool(matched) and doc is not None and output["relevance"] == "high"
        draft = compose_recommendation(doc) if eligible else None
        if not matched:
            outcome = "silent_no_rule"
        elif not eligible:
            outcome = "silent_no_hit"
        elif policy.proactive == "observe":
            outcome = "observe_would_accept"
        else:
            thread_key = task["thread_key"]
            outbox.enqueue(
                self.store, connection, key=f"recommendation:{thread_key}:{int(now)}", kind="recommendation",
                chat_id=thread_key.split(":", 1)[0], reply_to=thread_key.split(":", 1)[1], text=draft or "",
                thread_key=thread_key, now=now,
            )
            connection.execute(
                "UPDATE threads SET last_recommended_ms=?, updated_at=? WHERE thread_key=?", (int(now * 1000), iso(now), thread_key)
            )
            outcome = "recommended"
        decision = {
            "id": stable_hash("assess", task["thread_key"], task["policy_version"], task["created_ms"])[:16],
            "kind": "assess", "thread_key": task["thread_key"], "trigger_id": None, "policy_version": task["policy_version"],
            "mode": policy.proactive, "outcome": outcome, "rules_json": json.dumps(output["rules"], ensure_ascii=False),
            "doc_ids_json": json.dumps([doc["id"]] if doc else []),
            "scores_json": _scores((item["id"], item["score"]) for item in payload.get("candidates") or []),
            "draft": draft, "created_at": iso(now),
        }
        connection.execute(
            """
            INSERT OR IGNORE INTO decisions(id, kind, thread_key, trigger_id, policy_version, mode, outcome,
                                           rules_json, doc_ids_json, scores_json, draft, created_at)
            VALUES(:id, :kind, :thread_key, :trigger_id, :policy_version, :mode, :outcome, :rules_json,
                   :doc_ids_json, :scores_json, :draft, :created_at)
            """,
            decision,
        )
        target = "recommended" if outcome == "recommended" else "silent"
        self._move(connection, "thread_key=?", (task["thread_key"],), "evaluating", target, outcome, now)
        return {"outcome": outcome}

    def _record_decision(
        self, connection: Any, kind: str, trigger_id: str | None, thread_key: str | None, policy: Policy,
        outcome: str, now: float, hits: Iterable[tuple[str, float]],
    ) -> None:
        hits = list(hits)
        connection.execute(
            """
            INSERT OR IGNORE INTO decisions(id, kind, thread_key, trigger_id, policy_version, mode, outcome,
                                           rules_json, doc_ids_json, scores_json, draft, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, NULL, ?)
            """,
            (
                stable_hash(kind, trigger_id or thread_key, policy.version, int(now * 1000))[:16], kind, thread_key,
                trigger_id, policy.version, "explicit" if kind != "assess" else policy.proactive, outcome,
                json.dumps([doc_id for doc_id, _ in hits]), _scores(hits), iso(now),
            ),
        )

    # ---- feedback ---------------------------------------------------------------

    def on_reaction(self, reaction: dict[str, Any], now: float | None = None) -> dict[str, Any]:
        """Record a 👍 / 👎 on an assistant message. A 👎 also opts its discussion out."""

        now = self.clock() if now is None else now
        emoji = reaction.get("emoji") or ""
        choice = {EMOJI_THUMBS_UP: "up", EMOJI_THUMBS_DOWN: "down"}.get(emoji)
        message_id = reaction.get("message_id") or ""
        if choice is None or reaction.get("operator_is_bot"):
            return {"recorded": False}
        # Outbox and registry have different columns, so look them up in turn.
        message = self.store.fetchone("SELECT * FROM outbox WHERE message_id=?", (message_id,)) or self.store.fetchone(
            "SELECT * FROM registry WHERE message_id=?", (message_id,)
        )
        if message is None:
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
            if choice == "down" and message.get("thread_key"):
                connection.execute(
                    "UPDATE threads SET muted_at=? WHERE thread_key=? AND muted_at IS NULL", (iso(now), message["thread_key"])
                )
        paused = self._pause_on_dislikes(now)
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
        self._pause(policy, "dislike_ratio", now)
        return 1
