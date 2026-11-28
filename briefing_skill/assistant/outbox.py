"""Record first, send later.

Every outbound message is committed to the outbox in the same transaction as
the decision behind it, and only then handed to the transport. The idempotency
key is the outbox row ID, so a retry after a crash cannot post twice. Only
answers, recommendations and idea cards may ever be queued: the assistant has
no progress or acknowledgement message. The same checks run again at the door,
so a row that should not exist can never reach the group.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .constants import OUTBOX_MAX_ATTEMPTS
from .policy import Policy
from .replies import count_words, within_limit
from .store import Store
from .timeutil import iso

ALLOWED_KINDS = ("answer", "recommendation", "card")

# A card push records its idea before the message ID is known. The placeholder
# is replaced with the real ID once the card has been sent.
PENDING_CARD = "pending:"


class Transport(Protocol):
    """Sends one queued message. An empty ``reply_to`` opens a new message in the chat."""

    def send(self, chat_id: str, reply_to: str, text: str, idempotency_key: str, kind: str) -> "SendResult": ...


@dataclass(frozen=True)
class SendResult:
    status: str  # sent | retry | gone
    message_id: str = ""
    error: str = ""


class OutboxError(ValueError):
    pass


def enqueue(
    store: Store,
    connection: Any,
    *,
    key: str,
    kind: str,
    chat_id: str,
    reply_to: str,
    text: str,
    thread_key: str | None,
    now: float,
) -> None:
    """Queue one message inside the caller's open transaction.

    A reply that could not be shortened to the IM word limit is kept as
    ``refused`` with the reason, so the ledger shows what was dropped instead
    of failing the message that asked for it. Cards follow a template and are
    not counted.
    """

    if kind not in ALLOWED_KINDS:
        raise OutboxError(f"Reply kind is not allowed: {kind}")
    words = count_words(text)
    refused = kind != "card" and not within_limit(text)
    connection.execute(
        """
        INSERT OR IGNORE INTO outbox(id, kind, chat_id, reply_to, thread_key, text, status, attempts, created_at, last_error)
        VALUES(?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            key, kind, chat_id, reply_to, thread_key, text, "refused" if refused else "pending", iso(now),
            f"Exceeds the IM word limit: {words} words" if refused else None,
        ),
    )


def blocked_reason(store: Store, row: dict[str, Any]) -> str:
    """Why a queued message must not leave the machine; empty when it may go.

    The engine queues only what passed these checks while it ran. Repeating
    them here means a bad row cannot reach the group even if a writer misbehaves.
    """

    if row["kind"] == "answer":
        event = store.fetchone(
            "SELECT is_bot, is_mention, is_direct FROM events WHERE message_id=?", (row["reply_to"],)
        )
        if event is None or event["is_bot"] or not (event["is_mention"] or event["is_direct"]):
            return "The message being answered did not come from a person addressing the assistant"
    elif row["kind"] == "recommendation":
        decision = store.fetchone(
            "SELECT 1 FROM decisions WHERE kind='assess' AND thread_key=? AND outcome='recommended'", (row["thread_key"],)
        )
        if decision is None:
            return "No accepted assessment with a matching rule covers this recommendation"
        if Policy.load(store).proactive != "auto":
            return "Proactive mode is no longer auto"
    elif row["kind"] == "card":
        if store.fetchone("SELECT 1 FROM registry WHERE message_id=?", (PENDING_CARD + row["id"],)) is None:
            return "No confirmed card push covers this message"
    return ""


def _claim_card(store: Store, row: dict[str, Any], message_id: str, now: float) -> None:
    """A sent card is known to the group by its message ID; the registry follows."""

    with store.transaction() as connection:
        connection.execute(
            "UPDATE registry SET message_id=?, pushed_at=? WHERE message_id=?", (message_id, iso(now), PENDING_CARD + row["id"])
        )


def flush(store: Store, transport: Transport, now: float) -> dict[str, int]:
    """Send what is ready. Each row is checked again right before it leaves."""

    summary = {"sent": 0, "retry": 0, "gone": 0, "failed": 0, "refused": 0}
    rows = store.fetchall("SELECT * FROM outbox WHERE status IN ('pending', 'retry') ORDER BY created_at, id")
    for row in rows:
        reason = blocked_reason(store, row)
        if reason:
            store.execute("UPDATE outbox SET status='refused', last_error=? WHERE id=?", (reason, row["id"]))
            summary["refused"] += 1
            continue
        result = transport.send(row["chat_id"], row["reply_to"], row["text"], row["id"], row["kind"])
        attempts = int(row["attempts"]) + 1
        sent_at, message_id, error = row["sent_at"], row["message_id"], row["last_error"]
        if result.status == "sent":
            status, sent_at, message_id = "sent", iso(now), result.message_id
            if row["kind"] == "card" and result.message_id:
                _claim_card(store, row, result.message_id, now)
        elif result.status == "gone":
            status, error = "gone", result.error
        elif attempts >= OUTBOX_MAX_ATTEMPTS:
            status, error = "failed", result.error
        else:
            status, error = "retry", result.error
        store.execute(
            "UPDATE outbox SET status=?, attempts=?, sent_at=?, message_id=?, last_error=? WHERE id=?",
            (status, attempts, sent_at, message_id, error, row["id"]),
        )
        summary[status] += 1
    return summary
