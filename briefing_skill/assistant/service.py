"""The resident process behind ``assistant serve``.

It moves events from lark-cli into the engine, sends what the outbox holds,
and keeps its own house: history backfill, member refresh, retention, the
self-check and a heartbeat. Every unit of work is one short step, so a stop
request is honoured within a second.
"""

from __future__ import annotations

import os
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import lark, outbox
from .backfill import backfill
from .config import AssistantConfig
from .corpus import head_issue
from .constants import (
    BACKFILL_INTERVAL_SECONDS,
    CONSUMER_MAX_BACKOFF_SECONDS,
    CONSUMER_MIN_STABLE_SECONDS,
    CONSUMER_READY_TIMEOUT_SECONDS,
    INDEX_CHECK_INTERVAL_SECONDS,
    INDEX_RETRY_SECONDS,
    RETENTION_DAYS,
    SERVICE_TICK_SECONDS,
    STOP_TIMEOUT_SECONDS,
    SWEEP_INTERVAL_SECONDS,
    STARTUP_RETRIES,
    THREAD_POLL_EVERY,
    THREAD_POLL_MAX,
    THREAD_POLL_WINDOW_SECONDS,
    TICK_FAILURE_LIMIT,
)
from . import feedback
from .engine import Engine
from .events import Trigger, card_action, from_event, reaction
from .retrieval import LexicalIndex, assess, ensure_index, is_stale
from .store import Store
from .timeutil import day_key, day_start, iso

# A fixed question the lexical layer must keep answering with confidence.
PROBE_QUESTION = "KV cache 分层卸载"
DAY_SECONDS = 86400


class AlreadyRunning(RuntimeError):
    pass


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def self_check(root: Path, config: AssistantConfig, state_dir: Path, index: LexicalIndex | None, now: float) -> dict[str, Any]:
    """Retrieval still answers a fixed question, and the snapshot matches the corpus.

    The check never writes to the group; ``status`` and the daily pass read it.
    """

    problems = []
    stale = is_stale(root, config, state_dir)
    if stale:
        problems.append("The index snapshot no longer matches the published corpus; run `python briefing.py assistant index build`")
    if index is None or index.n == 0:
        problems.append("The index is empty")
        probe_state = "none"
    else:
        probe_state = assess(index, PROBE_QUESTION)["state"]
        if probe_state != "confident":
            problems.append(f"The fixed probe question is no longer answered with confidence (state: {probe_state})")
    return {"ok": not problems, "problems": problems, "documents": index.n if index else 0, "probe_state": probe_state, "checked_at": iso(now)}


class Service:
    def __init__(
        self,
        root: Path,
        config: AssistantConfig,
        state_dir: Path,
        *,
        client: Any,
        store: Store | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.root = root
        self.config = config
        self.state_dir = state_dir
        self.client = client
        self.store = store or Store(state_dir / "assistant.sqlite")
        self.clock = clock
        self.sleep = sleep
        self.transport = client.transport()
        self.index: LexicalIndex | None = None
        self.engine: Engine | None = None
        self.bot_ids: set[str] = set()
        self.consumers: dict[str, Any] = {}
        self.consumer_state: dict[str, dict[str, Any]] = {}
        self.exit_code = 0
        self._stopping = False
        self._next: dict[str, float] = {}
        self._started_at: dict[str, float] = {}
        self._backoff: dict[str, float] = {}
        self._restart_at: dict[str, float] = {}
        self._backfill_rounds = 0

    @property
    def pid_path(self) -> Path:
        return self.state_dir / "service.pid"

    @property
    def stop_path(self) -> Path:
        return self.state_dir / "stop"

    # ---- lifecycle --------------------------------------------------------------

    def run(self) -> int:
        self._claim_pid_file()
        try:
            self._open()
            with _signals(self._request_stop):
                failures = 0
                while not self._stop_requested():
                    try:
                        self._tick()
                    except Exception as exc:
                        # Usually a corpus file caught while a briefing run was rewriting it.
                        failures += 1
                        self._note_tick_error(exc, failures)
                        if failures >= TICK_FAILURE_LIMIT:
                            raise
                    else:
                        failures = 0
                        self._clear_tick_error()
                    self.sleep(SERVICE_TICK_SECONDS)
        except Exception as exc:  # shown by `status`; the process must not linger half-started
            self.exit_code = 1
            message = f"{type(exc).__name__}: {exc}"
            self.store.set_meta("service", {**self.store.get_meta("service", {}), "error": message})
            self._tell_owner(f"进程出错退出了，需要重新启动：{message}")
        finally:
            self._shutdown()
        return self.exit_code

    def _open(self) -> None:
        self._load_index()
        identity = self.client.bot()
        self.bot_ids = {identity["open_id"]} - {""}
        self.engine = Engine(
            self.store, self.index, self.config, self.root, self.state_dir, bot_ids=tuple(self.bot_ids), clock=self.clock
        )
        # The index was just built from the corpus and members are refreshed by the daily pass.
        self._next["index"] = self.clock() + INDEX_CHECK_INTERVAL_SECONDS
        # An issue published while the process was down is still news to the group.
        last = self.store.get_meta("index", {}).get("head_issue", "")
        current = head_issue(self.root)
        if last and last != current:
            self.engine.queue_alert(current, self.clock())
        for event_key in lark.EVENT_KEYS:
            self._start_consumer(event_key)
        self.store.set_meta(
            "service",
            {"pid": os.getpid(), "started_at": iso(self.clock()), "bot": identity, "chats": list(self.config.chat_whitelist)},
        )
        self.store.set_meta(
            "index", {"input_digest": self.index.input_digest, "documents": self.index.n, "head_issue": head_issue(self.root)}
        )

    def _load_index(self) -> None:
        """Build or load the index, waiting out a briefing run that is rewriting the corpus."""

        for attempt in range(1, STARTUP_RETRIES + 1):
            try:
                self.index, _ = ensure_index(self.root, self.config, self.state_dir, created_at=iso(self.clock()))
                return
            except (ValueError, KeyError, OSError):
                if attempt == STARTUP_RETRIES:
                    raise
                self.sleep(INDEX_RETRY_SECONDS)

    def _note_tick_error(self, exc: Exception, failures: int) -> None:
        self._publish_service(tick_error={"at": iso(self.clock()), "count": failures, "message": f"{type(exc).__name__}: {exc}"[:300]})

    def _clear_tick_error(self) -> None:
        if self.store.get_meta("service", {}).get("tick_error") is not None:
            self._publish_service(tick_error=None)

    def _claim_pid_file(self) -> None:
        if self.pid_path.exists():
            pid = int(self.pid_path.read_text().strip() or 0)
            if pid and pid != os.getpid() and process_alive(pid):
                raise AlreadyRunning(f"assistant serve is already running (pid {pid})")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.stop_path.unlink(missing_ok=True)
        self.pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")

    def _request_stop(self, *_: Any) -> None:
        self._stopping = True

    def _stop_requested(self) -> bool:
        return self._stopping or self.stop_path.exists()

    def _shutdown(self) -> None:
        for consumer in self.consumers.values():
            if consumer is not None:
                consumer.stop()
        try:
            self.client.stop_bus()
        except lark.LarkError as exc:  # the process still exits; `status` shows why the bus was left up
            self._publish_service(bus_error=str(exc))
        self._publish_service(pid=None, stopped_at=iso(self.clock()))
        self.pid_path.unlink(missing_ok=True)
        self.stop_path.unlink(missing_ok=True)

    def _publish_service(self, **extra: Any) -> None:
        """Share what only this process knows with ``status``."""
        self.store.set_meta(
            "service",
            {**self.store.get_meta("service", {}), "consumers": self.consumer_state, **extra},
        )

    # ---- one tick ---------------------------------------------------------------

    def _tick(self) -> None:
        now = self.clock()
        if self._ingest():
            # A reply goes out as soon as its message arrives, not at the next sweep.
            outbox.flush(self.store, self.transport, now)
        self._supervise(now)
        if now >= self._next.get("sweep", 0):
            self.engine.sweep()
            outbox.flush(self.store, self.transport, now)
            self.store.set_meta("heartbeat", {"at": iso(now), "pid": os.getpid()})
            self._publish_service()
            self._next["sweep"] = now + SWEEP_INTERVAL_SECONDS
        if now >= self._next.get("backfill", 0):
            self._backfill(now)
            outbox.flush(self.store, self.transport, now)
            self._next["backfill"] = now + BACKFILL_INTERVAL_SECONDS
        if now >= self._next.get("index", 0):
            self._refresh_index(now)
            self._next["index"] = now + INDEX_CHECK_INTERVAL_SECONDS
        if now >= self._next.get("daily", 0):
            self._daily(now)
            self._next["daily"] = now + DAY_SECONDS

    def _ingest(self) -> int:
        """Hand the events received since the last tick to the engine; returns how many."""

        handled = 0
        for event_key, consumer in self.consumers.items():
            if consumer is None:
                continue
            for event in consumer.events():
                self._handle(event_key, event)
                handled += 1
        return handled

    def _handle(self, event_key: str, event: dict[str, Any]) -> None:
        if event_key == lark.MESSAGE_EVENT:
            trigger = from_event(event, via="event", bot_ids=self.bot_ids)
            if trigger is not None:
                self.engine.ingest(trigger)
        elif event_key in lark.REACTION_EVENTS:
            note = reaction(event)
            if note is not None:
                self.engine.on_reaction(note, self.clock())
        else:
            action = card_action(event)
            if action is not None and self.engine.on_card_action(action, self.clock())["recorded"]:
                self._show_on_card(action["message_id"])

    def _show_on_card(self, message_id: str) -> None:
        try:
            feedback.refresh_card(self.store, self.root, self.config, message_id)
        except lark.LarkError:
            pass  # the press is recorded; the card just could not be refreshed

    def _backfill(self, now: float) -> None:
        self._backfill_rounds += 1
        poll_threads = self._backfill_rounds % THREAD_POLL_EVERY == 0
        results = self.store.get_meta("backfill", {})
        for chat_id in self.config.chat_whitelist:
            results[chat_id] = backfill(
                self.store, self.engine.ingest, self._reader(chat_id, poll_threads), chat_id=chat_id, now=now
            )
        self.store.set_meta("backfill", results)

    def _reader(self, chat_id: str, poll_threads: bool) -> Callable[[str, int], list[Trigger]]:
        def reader(chat_id: str, start_ms: int) -> list[Trigger]:
            page = self.client.records(container_type="chat", container_id=chat_id, start_ms=start_ms)
            self._remember_threads(lark.thread_roots(page))
            found = lark.to_triggers(page, via="backfill", bot_ids=self.bot_ids)
            if poll_threads:
                for thread_id in self._threads_to_poll(chat_id):
                    replies = self.client.records(container_type="thread", container_id=thread_id, start_ms=start_ms)
                    found += lark.to_triggers(replies, via="thread", bot_ids=self.bot_ids, chat_id=chat_id)
            return found

        return reader

    def _remember_threads(self, roots: list[tuple[str, str, str, int]]) -> None:
        with self.store.transaction() as connection:
            for chat_id, root_message_id, thread_id, created_ms in roots:
                connection.execute(
                    """
                    INSERT INTO threads(thread_key, chat_id, root_message_id, thread_id, last_activity_ms, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?)
                    ON CONFLICT(thread_key) DO UPDATE SET
                        thread_id=COALESCE(threads.thread_id, excluded.thread_id),
                        last_activity_ms=MAX(COALESCE(threads.last_activity_ms, 0), excluded.last_activity_ms)
                    """,
                    (f"{chat_id}:{root_message_id}", chat_id, root_message_id, thread_id, created_ms, iso(self.clock())),
                )

    def _threads_to_poll(self, chat_id: str) -> list[str]:
        since = (self.clock() - THREAD_POLL_WINDOW_SECONDS) * 1000
        rows = self.store.fetchall(
            """
            SELECT thread_id FROM threads
            WHERE chat_id=? AND thread_id IS NOT NULL AND COALESCE(last_activity_ms, 0) >= ?
            ORDER BY last_activity_ms DESC LIMIT ?
            """,
            (chat_id, since, THREAD_POLL_MAX),
        )
        return [row["thread_id"] for row in rows]

    def _refresh_index(self, now: float) -> None:
        if is_stale(self.root, self.config, self.state_dir):
            # What the previous build was cut from; the files on disk are already the new issue.
            before = self.store.get_meta("index", {}).get("head_issue", "")
            index, _ = ensure_index(self.root, self.config, self.state_dir, created_at=iso(now))
            self.index = index
            self.engine.reindex(index)
            after = head_issue(self.root)
            if before != after:
                self.engine.queue_alert(after, now)
            self.store.set_meta(
                "index", {"input_digest": index.input_digest, "documents": index.n, "head_issue": after, "rebuilt_at": iso(now)}
            )

    def _daily(self, now: float) -> None:
        self.store.purge(RETENTION_DAYS, now, self.engine.tasks_dir)
        self._refresh_members()
        self.store.set_meta("self_check", self_check(self.root, self.config, self.state_dir, self.index, now))
        wakes = self.store.get_meta("wakes", {})
        self.store.set_meta("wakes", {day: count for day, count in wakes.items() if day == day_key(now)})

    def _refresh_members(self) -> None:
        """Who may write to the assistant in a direct message, and the names a report may use."""

        members, names = {}, dict(self.store.get_meta("member_names", {}))
        for chat_id in self.config.chat_whitelist:
            try:
                found = self.client.members(chat_id)
            except lark.LarkError:
                found = dict.fromkeys(self.store.get_meta("members", {}).get(chat_id, []), "")
            members[chat_id] = list(found)
            names.update(found)
        self.store.set_meta("members", members)
        self.store.set_meta("member_names", names)

    def _tell_owner(self, text: str) -> None:
        """A last word to the owner before the process gives up; the outbox will not be flushed."""

        owner = self.store.get_meta("report_to")
        if owner:
            self.transport.send(owner["chat_id"], "", f"群助手：{text}"[:1500], f"report:exit-{int(time.time())}", "report")

    # ---- consumers --------------------------------------------------------------

    def _start_consumer(self, event_key: str) -> None:
        try:
            consumer = self.client.consumer(event_key)
            consumer.start()
        except OSError as exc:
            self.consumers[event_key] = None
            self.consumer_state[event_key] = {"state": "error", "error": {"message": str(exc)}}
            return
        self.consumers[event_key] = consumer
        self._started_at[event_key] = self.clock()
        self.consumer_state[event_key] = {"state": "starting"}

    def _supervise(self, now: float) -> None:
        """Resolve readiness, restart crashed consumers with backoff, and keep errors visible."""
        for event_key, consumer in list(self.consumers.items()):
            if consumer is None:
                continue
            if consumer.wait_ready(0):
                self.consumer_state[event_key] = {"state": "ready"}
                if now - self._started_at.get(event_key, now) >= CONSUMER_MIN_STABLE_SECONDS:
                    self._backoff[event_key] = 1.0
            code = consumer.exit_code()
            if code is None:
                if self.consumer_state[event_key]["state"] == "starting" and now - self._started_at[event_key] > CONSUMER_READY_TIMEOUT_SECONDS:
                    consumer.stop()
                    self.consumers[event_key] = None
                    self._schedule_restart(event_key, now, "was not ready in time")
                continue
            self.consumers[event_key] = None
            if consumer.error:
                self.consumer_state[event_key] = {"state": "error", "error": consumer.error}
            else:
                self._schedule_restart(event_key, now, f"exited with code {code}")
        for event_key, at in list(self._restart_at.items()):
            if now >= at:
                del self._restart_at[event_key]
                self._start_consumer(event_key)

    def _schedule_restart(self, event_key: str, now: float, why: str) -> None:
        wait = self._backoff.get(event_key, 1.0)
        self._backoff[event_key] = min(wait * 2, CONSUMER_MAX_BACKOFF_SECONDS)
        self._restart_at[event_key] = now + wait
        self.consumer_state[event_key] = {"state": "restarting", "why": why, "in_seconds": wait}


class _signals:
    """Run SIGTERM and SIGINT through one handler for the duration of a block."""

    def __init__(self, handler: Callable[..., None]) -> None:
        self.handler = handler
        self.previous: dict[int, Any] = {}

    def __enter__(self) -> "_signals":
        for number in (signal.SIGTERM, signal.SIGINT):
            self.previous[number] = signal.getsignal(number)
            signal.signal(number, self.handler)
        return self

    def __exit__(self, *_: Any) -> None:
        for number, handler in self.previous.items():
            signal.signal(number, handler)


def request_stop(state_dir: Path, timeout: float = STOP_TIMEOUT_SECONDS, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """What ``assistant stop`` does: ask the resident process to stop and wait for it."""

    pid_path, stop_path = state_dir / "service.pid", state_dir / "stop"
    pid = int(pid_path.read_text().strip() or 0) if pid_path.exists() else 0
    if not pid or not process_alive(pid):
        pid_path.unlink(missing_ok=True)
        return {"running": False, "stopped": True}
    state_dir.mkdir(parents=True, exist_ok=True)
    stop_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    deadline = time.time() + timeout
    while process_alive(pid) and time.time() < deadline:
        sleep(SERVICE_TICK_SECONDS)
    return {"running": process_alive(pid), "pid": pid, "stopped": not process_alive(pid)}


def _counts(store: Store, sql: str, key: str, params: tuple[Any, ...] = ()) -> dict[str, int]:
    return {row[key]: row["n"] for row in store.fetchall(sql, params)}


def _age(stamp: str | None, now: float) -> int | None:
    return round(now - datetime.fromisoformat(stamp).timestamp()) if stamp else None


def overview(store: Store, root: Path, config: AssistantConfig, state_dir: Path, now: float) -> dict[str, Any]:
    """Everything ``status`` shows, read without touching the resident process."""

    service = store.get_meta("service", {})
    policy_meta = store.get_meta("policy", {})
    pid = service.get("pid") or 0
    since = iso(day_start(now))
    index, _ = ensure_index(root, config, state_dir, created_at=iso(now))
    return {
        "service": {
            "running": bool(pid) and process_alive(pid),
            "pid": pid or None,
            "started_at": service.get("started_at"),
            "heartbeat_age_seconds": _age(store.get_meta("heartbeat", {}).get("at"), now),
            "consumers": service.get("consumers", {}),
            "chats": service.get("chats", []),
            "backfill": store.get_meta("backfill", {}),
            "error": service.get("error"),
            "tick_error": service.get("tick_error"),
            "bus_error": service.get("bus_error"),
        },
        "policy": {
            "explicit": policy_meta.get("explicit", True),
            "proactive": policy_meta.get("proactive", "auto"),
            "muted_for_seconds": max(0, int((policy_meta.get("muted_until") or 0) - now)),
            "report_to": (service.get("report_to") or {}).get("open_id"),
        },
        "index": {"input_digest": index.input_digest, "documents": index.n},
        "today": {
            "dispositions": _counts(
                store, "SELECT decision, COUNT(*) AS n FROM dispositions WHERE updated_at >= ? GROUP BY decision", "decision", (since,)
            ),
            "sent": _counts(store, "SELECT kind, COUNT(*) AS n FROM outbox WHERE sent_at >= ? GROUP BY kind", "kind", (since,)),
            "decisions": _counts(
                store,
                "SELECT kind || ':' || outcome AS outcome, COUNT(*) AS n FROM decisions WHERE created_at >= ? GROUP BY outcome",
                "outcome",
                (since,),
            ),
        },
        "outbox": _counts(store, "SELECT status, COUNT(*) AS n FROM outbox GROUP BY status", "status"),
        "reports": _counts(store, "SELECT kind, COUNT(*) AS n FROM reports GROUP BY kind", "kind"),
        "tasks": {
            **_counts(store, "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status", "status"),
            "wakes": store.get_meta("wakes", {}).get(day_key(now), 0),
        },
        "self_check": self_check(root, config, state_dir, index, now),
    }
