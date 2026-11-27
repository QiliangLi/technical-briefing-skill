"""Accept modes, proactive rules and the admission table.

The admission table is code, not configuration. It reads only message metadata
(the sender, the mentions and the chat) and never the message body.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utils import stable_hash
from .events import Trigger
from .store import Store

MODES = ("off", "observe", "auto")

# Each rule describes one kind of proactive work in plain language. The host
# session judges every enabled rule exactly once per assessment.
RULES: dict[str, dict[str, str]] = {
    "prior_art": {
        "name": "找先例",
        "instruction": "群里有人在找先例，或者问有没有人做过类似的工作，而日报库或 idea 库里正好有这样的记录。",
    },
    "related_evidence": {
        "name": "相关证据",
        "instruction": "群里正在讨论一个技术方案或现象，而日报库里有直接相关的、已经核实过的结果可以参考。",
    },
}


@dataclass
class Policy:
    explicit: bool = False
    proactive: str = "off"
    rules: dict[str, bool] = field(default_factory=lambda: {rule_id: True for rule_id in RULES})
    muted_until: float = 0.0

    @property
    def version(self) -> str:
        enabled = sorted(rule_id for rule_id, on in self.rules.items() if on)
        return stable_hash("policy", int(self.explicit), self.proactive, *enabled)[:16]

    def enabled_rules(self) -> list[str]:
        return [rule_id for rule_id in RULES if self.rules.get(rule_id)]

    def is_muted(self, now: float) -> bool:
        return self.muted_until > now

    @classmethod
    def load(cls, store: Store) -> "Policy":
        data = store.get_meta("policy", {})
        if not isinstance(data, dict):
            data = {}
        if data.get("proactive") not in MODES:
            data = {**data, "proactive": "off"}
        rules = {rule_id: bool((data.get("rules") or {}).get(rule_id, True)) for rule_id in RULES}
        return cls(
            explicit=bool(data.get("explicit")),
            proactive=data["proactive"],
            rules=rules,
            muted_until=float(data.get("muted_until") or 0.0),
        )

    def save(self, store: Store, connection: Any = None) -> None:
        store.set_meta(
            "policy",
            {
                "explicit": self.explicit,
                "proactive": self.proactive,
                "rules": self.rules,
                "muted_until": self.muted_until,
            },
            connection,
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
