"""Normalize Feishu events and history records into one Trigger shape.

Three ingress paths feed the same Trigger: live events from
``lark-cli event consume``, history records from ``GET /im/v1/messages`` and
thread pages. They share one trigger ID per message, so a message that arrives
through more than one path is processed once.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

AT_TAG = re.compile(r"<at[^>]*>.*?</at>", re.S)
CONTROL_CHARS = re.compile("[\u200b\u200c\u200d\ufeff\x00]")
RECEIVE_EVENT = "im.message.receive_v1"


@dataclass(frozen=True)
class Trigger:
    message_id: str
    chat_id: str
    sender_id: str
    created_ms: int
    text: str
    via: str
    root_id: str = ""
    thread_id: str = ""
    is_bot: bool = False
    is_direct: bool = False
    is_mention: bool = False

    @property
    def trigger_id(self) -> str:
        return f"feishu:{self.message_id}"

    @property
    def thread_key(self) -> str:
        """A thread is named by its root message; a root names itself."""

        return f"{self.chat_id}:{self.root_id or self.message_id}"

    @property
    def is_reply(self) -> bool:
        return bool(self.root_id)


def _clean(text: str, placeholders: list[str] = ()) -> str:
    cleaned = CONTROL_CHARS.sub("", text or "")
    for placeholder in placeholders:
        cleaned = cleaned.replace(placeholder, " ")
    return AT_TAG.sub(" ", cleaned).strip()


def _content_text(payload: Any, msg_type: str) -> str:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return payload
    if msg_type == "post" and isinstance(payload, dict):
        lines = []
        for locale in payload.values():
            for line in (locale or {}).get("content") or []:
                lines.append(" ".join(str(node.get("text") or "") for node in line if isinstance(node, dict)))
        return "\n".join(lines)
    if isinstance(payload, dict):
        return str(payload.get("text") or "")
    return ""


def from_event(raw: dict[str, Any], *, via: str, bot_ids: set[str]) -> Trigger | None:
    """A flattened ``im.message.receive_v1`` event as printed by lark-cli."""

    if raw.get("type") != RECEIVE_EVENT or not raw.get("message_id") or not raw.get("create_time"):
        return None
    mentions = [mention for mention in raw.get("mentions") or [] if isinstance(mention, dict)]
    sender_id = str(raw.get("sender_id") or "")
    return Trigger(
        message_id=str(raw["message_id"]),
        chat_id=str(raw.get("chat_id") or ""),
        sender_id=sender_id,
        created_ms=int(str(raw["create_time"])),
        text=_clean(str(raw.get("content") or ""), ["@" + str(m.get("name") or "") for m in mentions]),
        via=via,
        root_id=str(raw.get("root_id") or ""),
        thread_id=str(raw.get("thread_id") or ""),
        is_bot=raw.get("sender_type") != "user" or sender_id in bot_ids,
        is_direct=raw.get("chat_type") == "p2p",
        is_mention=any(mention.get("id") in bot_ids for mention in mentions),
    )


def from_record(item: dict[str, Any], *, via: str, bot_ids: set[str], chat_id: str = "") -> Trigger | None:
    """A message record from the history or thread API."""

    if not item.get("message_id") or item.get("deleted"):
        return None
    mentions = [mention for mention in item.get("mentions") or [] if isinstance(mention, dict)]
    sender = item.get("sender") or {}
    sender_id = str(sender.get("id") or "")
    content = _content_text((item.get("body") or {}).get("content"), str(item.get("msg_type") or ""))
    return Trigger(
        message_id=str(item["message_id"]),
        chat_id=chat_id or str(item.get("chat_id") or ""),
        sender_id=sender_id,
        created_ms=int(str(item.get("create_time") or 0)[:13]),
        text=_clean(content, [str(mention.get("key") or "") for mention in mentions]),
        via=via,
        root_id=str(item.get("root_id") or ""),
        thread_id=str(item.get("thread_id") or ""),
        is_bot=sender.get("sender_type") != "user" or sender_id in bot_ids,
        is_direct=item.get("chat_type") == "p2p",
        is_mention=any(mention.get("id") in bot_ids for mention in mentions),
    )


def reaction(raw: dict[str, Any]) -> dict[str, Any] | None:
    """A reaction event. lark-cli passes these through in their V2 envelope."""

    event = raw.get("event") if isinstance(raw.get("event"), dict) else raw
    message_id = event.get("message_id")
    emoji = (event.get("reaction_type") or {}).get("emoji_type")
    if not message_id or not emoji:
        return None
    event_type = (raw.get("header") or {}).get("event_type") or raw.get("type") or ""
    operator = event.get("user_id") or {}
    operator_id = operator.get("open_id") if isinstance(operator, dict) else operator
    return {
        "message_id": message_id,
        "emoji": emoji,
        "operator_id": operator_id or event.get("operator_id") or "",
        "operator_is_bot": event.get("operator_type") not in ("user", None),
        "removed": "deleted" in event_type,
    }


def card_action(raw: dict[str, Any]) -> dict[str, Any] | None:
    """A ``card.action.trigger`` callback from a button on an idea card."""

    if not raw.get("message_id") or raw.get("action_tag") != "button":
        return None
    try:
        value = json.loads(raw.get("action_value") or "{}")
    except ValueError:
        return None
    return {
        "message_id": str(raw["message_id"]),
        "chat_id": str(raw.get("chat_id") or ""),
        "operator_id": str(raw.get("operator_id") or ""),
        "choice": str(value.get("choice") or ""),
        "idea_id": str(value.get("idea_id") or ""),
    }
