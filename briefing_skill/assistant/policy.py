"""Accept modes and the admission table.

The admission table is code, not configuration. It reads only message metadata
(the sender, the mentions and the chat) and never the message body.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..utils import stable_hash
from .events import Trigger
from .store import Store

MODES = ("off", "observe", "auto")


@dataclass
class Policy:
    # The assistant is a member of the group: it answers when addressed and
    # takes part in discussions unless its owner switches that off. In
    # ``observe`` it still decides what it would say and records it, but says
    # nothing, which is how a new prompt is calibrated.
    explicit: bool = True
    proactive: str = "auto"
    muted_until: float = 0.0

    @property
    def version(self) -> str:
        return stable_hash("policy", int(self.explicit), self.proactive)[:16]

    def is_muted(self, now: float) -> bool:
        return self.muted_until > now

    @classmethod
    def load(cls, store: Store) -> "Policy":
        data = store.get_meta("policy", {})
        if not isinstance(data, dict):
            data = {}
        if data.get("proactive") not in MODES:
            data = {**data, "proactive": cls.proactive}
        return cls(
            explicit=bool(data.get("explicit", cls.explicit)),
            proactive=data["proactive"],
            muted_until=float(data.get("muted_until") or 0.0),
        )

    def save(self, store: Store, connection: Any = None) -> None:
        store.set_meta(
            "policy", {"explicit": self.explicit, "proactive": self.proactive, "muted_until": self.muted_until}, connection
        )


def admit(trigger: Trigger, policy: Policy, member_ids: set[str]) -> tuple[str | None, str]:
    """Return ``("explicit" | "inferred" | None, reason)``.

    No person list exists: the group itself is a conversation opened to its
    members, so anyone who addresses the assistant makes an explicit request.
    """

    if trigger.is_bot:
        return None, "bot"
    if trigger.is_direct:
        if trigger.sender_id not in member_ids:
            return None, "direct_non_member"
        return ("explicit", "direct") if policy.explicit else (None, "explicit_off")
    if trigger.is_mention:
        return ("explicit", "mention") if policy.explicit else (None, "explicit_off")
    if policy.proactive == "off":
        return None, "proactive_off"
    return "inferred", "unaddressed"
