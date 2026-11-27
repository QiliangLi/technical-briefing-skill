"""History backfill: recover messages the live event stream missed.

The cursor only moves after a whole round succeeds, and every round re-reads
the last few seconds, so a crash or a dropped event cannot lose a message. A
duplicate is harmless because all ingress paths share one trigger ID.
"""

from __future__ import annotations

from typing import Any, Callable

from .constants import BACKFILL_REWIND_SECONDS, BACKFILL_MAX_ROUNDS_PER_TICK
from .timeutil import iso


def backfill(
    store: Any,
    ingest: Callable[[Any], dict[str, str]],
    reader: Callable[[str, int], list[Any]],
    *,
    chat_id: str,
    now: float,
    max_rounds: int = BACKFILL_MAX_ROUNDS_PER_TICK,
) -> dict[str, Any]:
    """Pull one chat's history up to the stored cursor.

    The first round only sets the cursor: a new state directory must not replay
    the whole history of the group. ``reader`` may raise; the cursor then stays
    where it was and the next round reads the same window again.
    """

    row = store.fetchone("SELECT cursor_ms FROM cursors WHERE chat_id=?", (chat_id,))
    if row is None:
        with store.transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO cursors(chat_id, cursor_ms, updated_at) VALUES(?, ?, ?)",
                (chat_id, int(now * 1000), iso(now)),
            )
        return {"first_round": True, "ingested": 0, "rounds": 0, "failed": False}

    cursor = int(row["cursor_ms"])
    ingested = 0
    rounds = 0
    try:
        while rounds < max_rounds:
            triggers = reader(chat_id, cursor - BACKFILL_REWIND_SECONDS * 1000)
            rounds += 1
            newest = max((trigger.created_ms for trigger in triggers), default=cursor)
            for trigger in triggers:
                ingested += ingest(trigger).get("decision") != "duplicate"
            if newest <= cursor:
                break
            cursor = newest
            with store.transaction() as connection:
                connection.execute(
                    "UPDATE cursors SET cursor_ms=?, updated_at=? WHERE chat_id=?", (cursor, iso(now), chat_id)
                )
    except Exception as exc:  # the cursor keeps its last committed value
        return {"first_round": False, "ingested": ingested, "rounds": rounds, "failed": True, "error": str(exc)}
    return {"first_round": False, "ingested": ingested, "rounds": rounds, "failed": False}
