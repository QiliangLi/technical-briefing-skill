"""The only code that calls lark-cli, and always as the bot.

Nothing else in the assistant builds a lark-cli command line. The wrapper
fixes the identity to the bot and refuses any other, so the user's own
authorisation on this machine cannot be reached from the assistant. Output is
parsed here once; the rest of the assistant works with plain dictionaries.
"""

from __future__ import annotations

import collections
import json
import os
import queue
import signal
import subprocess
import threading
from typing import Any, Callable, Iterator

from ..utils import stable_hash
from .config import AssistantConfig
from .events import Trigger, from_record
from .outbox import SendResult

BOT = "bot"
MESSAGE_EVENT = "im.message.receive_v1"
REACTION_EVENTS = ("im.message.reaction.created_v1", "im.message.reaction.deleted_v1")
CARD_EVENT = "card.action.trigger"
EVENT_KEYS = (MESSAGE_EVENT, *REACTION_EVENTS, CARD_EVENT)

READY_MARKER = "[event] ready"
# The one command that acts on the local event bus daemon rather than on Feishu.
# It takes no identity, and lark-cli rejects ``--as`` for it.
LOCAL_COMMANDS = (("event", "stop"),)
CALL_TIMEOUT_SECONDS = 30
HISTORY_PAGE_SIZE = 50
HISTORY_MAX_PAGES = 4
MEMBERS_PAGE_SIZE = 100
REACTIONS_PAGE_SIZE = 50
STOP_GRACE_SECONDS = 10
# lark-cli accepts an idempotency key of at most 50 characters.
WIRE_KEY_LENGTH = 46
# The destination will never accept the message, so retrying is pointless.
GONE_CODES = frozenset({99992354})
GONE_MARKERS = ("not exists", "NOT be out of the chat")


class LarkError(RuntimeError):
    def __init__(self, message: str, error: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error = error or {}


def _parse(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def undeliverable(error: LarkError) -> bool:
    code = error.error.get("code")
    message = str(error.error.get("message") or "")
    return code in GONE_CODES or any(marker in message for marker in GONE_MARKERS)


def wire_key(outbox_id: str) -> str:
    """A retry-stable idempotency key that fits lark-cli's length limit."""

    return "ast-" + stable_hash("idempotency", outbox_id, length=WIRE_KEY_LENGTH)


def run(
    config: AssistantConfig, *args: str, stdin: str | None = None, timeout: float = CALL_TIMEOUT_SECONDS
) -> dict[str, Any]:
    """Run one lark-cli command as the bot and return its JSON envelope."""

    if any(arg == "--as" or arg.startswith("--as=") for arg in args):
        raise LarkError("The identity is fixed to the bot; never pass --as")
    command = [config.lark_cli, *args] if args[:2] in LOCAL_COMMANDS else [config.lark_cli, *args, "--as", BOT]
    try:
        completed = subprocess.run(command, input=stdin, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise LarkError(f"lark-cli timed out after {timeout:g}s: {' '.join(args[:3])}") from exc
    except OSError as exc:
        raise LarkError(f"lark-cli could not be run: {exc}") from exc
    envelope = _parse(completed.stdout) or _parse(completed.stderr)
    if completed.returncode != 0 or not envelope.get("ok", False):
        error = envelope.get("error") or {}
        detail = error.get("message") or completed.stderr.strip()[:300] or f"exit code {completed.returncode}"
        raise LarkError(f"lark-cli failed: {' '.join(args[:3])}: {detail}", error)
    return envelope


def _paged(
    config: AssistantConfig, path: str, params: dict[str, Any], until: Callable[[list[dict[str, Any]]], bool] | None = None
) -> list[dict[str, Any]]:
    """Follow ``page_token`` while there are more pages, or until ``until(items)`` says stop."""

    items: list[dict[str, Any]] = []
    for _ in range(HISTORY_MAX_PAGES):
        data = run(config, "api", "GET", path, "--params", json.dumps(params)).get("data") or {}
        items.extend(item for item in data.get("items") or [] if isinstance(item, dict))
        if not data.get("has_more") or not data.get("page_token") or (until and until(items)):
            break
        params = {**params, "page_token": data["page_token"]}
    return items


def _created(item: dict[str, Any]) -> int:
    return int(item.get("create_time") or 0)


def records(config: AssistantConfig, *, container_type: str, container_id: str, start_ms: int) -> list[dict[str, Any]]:
    """Messages of one chat or one thread since ``start_ms``, oldest first.

    A chat's history lists a thread's root message but never its replies, so a
    thread is read with a container of its own. The API returns nothing for a
    chat given a time window, so pages are read newest first and cut at
    ``start_ms`` here instead.
    """

    items = _paged(
        config,
        "/open-apis/im/v1/messages",
        {
            "container_id_type": container_type, "container_id": container_id,
            "sort_type": "ByCreateTimeDesc", "page_size": HISTORY_PAGE_SIZE,
        },
        until=lambda items: min(map(_created, items)) < start_ms,
    )
    return sorted((item for item in items if _created(item) >= start_ms), key=_created)


def to_triggers(records: list[dict[str, Any]], *, via: str, bot_ids: set[str], chat_id: str = "") -> list[Trigger]:
    found = (from_record(item, via=via, bot_ids=bot_ids, chat_id=chat_id) for item in records)
    return [trigger for trigger in found if trigger]


def thread_roots(records: list[dict[str, Any]]) -> list[tuple[str, str, str, int]]:
    """``(chat_id, root message_id, thread_id, created_ms)`` for every root in a chat page that has a thread."""

    found = []
    for record in records:
        if record.get("thread_id") and record.get("message_id") and record.get("chat_id"):
            root = str(record.get("root_id") or record["message_id"])
            found.append((str(record["chat_id"]), root, str(record["thread_id"]), int(record.get("create_time") or 0)))
    return found


def members(config: AssistantConfig, chat_id: str) -> dict[str, str]:
    """The human members of a chat by open ID, with the names the owner knows them by."""
    items = _paged(
        config, f"/open-apis/im/v1/chats/{chat_id}/members", {"member_id_type": "open_id", "page_size": MEMBERS_PAGE_SIZE}
    )
    return {str(item["member_id"]): str(item.get("name") or "") for item in items if item.get("member_id")}


def direct_chat(config: AssistantConfig, open_id: str, text: str) -> dict[str, Any]:
    """Message a person directly and return what the platform says about it.

    The reply carries the ID of the private chat between the bot and that
    person, which later reports are sent to.
    """

    return run(
        config, "im", "+messages-send", "--user-id", open_id, "--text", text, "--idempotency-key", wire_key(f"direct:{open_id}")
    ).get("data") or {}


def bot(config: AssistantConfig) -> dict[str, str]:
    """The bot's own identity; its messages are the assistant's and are never processed."""

    data = run(config, "api", "GET", "/open-apis/bot/v3/info").get("data") or {}
    return {"open_id": str(data.get("open_id") or ""), "app_name": str(data.get("app_name") or "")}


def reactions(config: AssistantConfig, message_id: str) -> list[dict[str, Any]]:
    """Who reacted to a message and how; the source of truth when the ledger is reconciled."""

    return _paged(config, f"/open-apis/im/v1/messages/{message_id}/reactions", {"user_id_type": "open_id", "page_size": REACTIONS_PAGE_SIZE})


class LarkTransport:
    """Hands queued messages to lark-cli and maps failures to the outbox's statuses."""

    def __init__(self, config: AssistantConfig) -> None:
        self.config = config

    def send(self, chat_id: str, reply_to: str, text: str, idempotency_key: str, kind: str) -> SendResult:
        key = wire_key(idempotency_key)
        try:
            if kind == "card":
                envelope = run(
                    self.config, "im", "+messages-send", "--chat-id", chat_id, "--msg-type", "interactive",
                    "--content", "-", "--idempotency-key", key, stdin=text,
                )
            elif reply_to:
                envelope = run(
                    self.config, "im", "+messages-reply", "--message-id", reply_to, "--markdown", "-",
                    "--reply-in-thread", "--idempotency-key", key, stdin=text,
                )
            else:
                envelope = run(
                    self.config, "im", "+messages-send", "--chat-id", chat_id, "--markdown", "-",
                    "--idempotency-key", key, stdin=text,
                )
        except LarkError as exc:
            return SendResult("gone" if undeliverable(exc) else "retry", error=str(exc))
        return SendResult("sent", message_id=str((envelope.get("data") or {}).get("message_id") or ""))


def _descendants(pid: int) -> list[int]:
    table: dict[int, list[int]] = {}
    for line in subprocess.run(["ps", "-axo", "pid=,ppid="], capture_output=True, text=True).stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            table.setdefault(int(parts[1]), []).append(int(parts[0]))
    order: list[int] = []
    stack = [pid]
    while stack:
        for child in table.get(stack.pop(), []):
            order.append(child)
            stack.append(child)
    return order


def _terminate(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


class Consumer:
    """One ``lark-cli event consume`` child process for one EventKey.

    stdin stays open because an unbounded consume exits on EOF; closing it is
    also the graceful stop. Both output pipes are drained on threads so the
    child never blocks on a full pipe.
    """

    def __init__(self, config: AssistantConfig, event_key: str) -> None:
        self.config = config
        self.event_key = event_key
        self.process: subprocess.Popen[str] | None = None
        self.log: collections.deque[str] = collections.deque(maxlen=30)
        self.error: dict[str, Any] = {}
        self._ready = threading.Event()
        self._lines: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._stderr_thread: threading.Thread | None = None

    def start(self) -> None:
        self._ready.clear()
        self.error = {}
        self.log.clear()
        self.process = subprocess.Popen(
            [self.config.lark_cli, "event", "consume", self.event_key, "--as", BOT],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        process = self.process
        for stream, is_stdout in ((process.stderr, False), (process.stdout, True)):
            thread = threading.Thread(target=self._drain, args=(stream, is_stdout), daemon=True)
            thread.start()
            if not is_stdout:
                self._stderr_thread = thread

    def _drain(self, stream: Any, is_stdout: bool) -> None:
        for line in stream:
            if is_stdout:
                self._lines.put(line)
                continue
            self.log.append(line.rstrip())
            if READY_MARKER in line:
                self._ready.set()
            error = _parse(line).get("error")
            if error:
                self.error = error
        stream.close()

    def wait_ready(self, timeout: float) -> bool:
        return self._ready.wait(timeout)

    def exit_code(self) -> int | None:
        """``None`` while the child runs; otherwise its exit code once stderr is drained."""

        if self.process is None:
            return 0
        code = self.process.poll()
        if code is not None and self._stderr_thread is not None:
            self._stderr_thread.join(timeout=2)
            self._stderr_thread = None
        return code

    def events(self) -> Iterator[dict[str, Any]]:
        """Events received since the last call."""

        while True:
            try:
                line = self._lines.get_nowait()
            except queue.Empty:
                return
            event = _parse(line)
            if event:
                yield event

    def stop(self, grace: float = STOP_GRACE_SECONDS) -> None:
        """Close stdin first, which is the graceful stop; signal only if the child lingers."""

        process, self.process = self.process, None
        if process is None:
            return
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            pass
        # The launcher is a thin script around the real consumer, so signal both.
        for pid in [*_descendants(process.pid), process.pid]:
            _terminate(pid)
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            self.log.append("consumer did not exit after SIGTERM and was left running")


class LarkClient:
    """What the resident process needs from lark-cli, behind one object."""

    def __init__(self, config: AssistantConfig) -> None:
        self.config = config

    def bot(self) -> dict[str, str]:
        return bot(self.config)

    def members(self, chat_id: str) -> dict[str, str]:
        return members(self.config, chat_id)

    def records(self, *, container_type: str, container_id: str, start_ms: int) -> list[dict[str, Any]]:
        return records(self.config, container_type=container_type, container_id=container_id, start_ms=start_ms)

    def reactions(self, message_id: str) -> list[dict[str, Any]]:
        return reactions(self.config, message_id)

    def open_direct_chat(self, open_id: str, text: str) -> dict[str, Any]:
        return direct_chat(self.config, open_id, text)

    def transport(self) -> LarkTransport:
        return LarkTransport(self.config)

    def consumer(self, event_key: str) -> Consumer:
        return Consumer(self.config, event_key)

    def stop_bus(self) -> None:
        """Stop the local event bus daemon; it does not exit by itself once the consumers are gone."""

        run(self.config, "event", "stop")
