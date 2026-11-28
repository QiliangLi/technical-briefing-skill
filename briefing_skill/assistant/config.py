"""Static configuration for the Feishu group assistant.

The committed file holds values that are safe to publish. Chat IDs and other
local values live in the ignored state directory and override it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

CHAT_ID_PATTERN = re.compile(r"^oc_[0-9a-f]{32}$")


class AssistantConfigError(RuntimeError):
    pass


def default_state_dir(root: Path) -> Path:
    return root / "workspace" / "assistant"


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise AssistantConfigError(f"Config root must be a mapping: {path}")
    return data


def normalize_chat_id(value: Any) -> str:
    text = str(value or "").strip()
    if not CHAT_ID_PATTERN.match(text):
        raise AssistantConfigError(f"Invalid chat id: {text!r}")
    return text


@dataclass(frozen=True)
class AssistantConfig:
    site_base_url: str = "https://qiliangli.github.io/technical-briefing-skill/"
    chat_whitelist: tuple[str, ...] = ()
    lark_cli: str = "lark-cli"
    # The assistant takes part whenever the group does; a narrower window can be configured.
    working_start_hour: int = 0
    working_end_hour: int = 24
    working_days: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)

    @classmethod
    def load(cls, root: Path, state_dir: Path | None = None) -> "AssistantConfig":
        """Load the committed config, then overlay the ignored local config."""

        local_path = (state_dir or default_state_dir(root)) / "config.local.yaml"
        merged = {
            **_read_mapping(root / "config" / "group-assistant.yaml"),
            **{k: v for k, v in _read_mapping(local_path).items() if v is not None},
        }
        return cls.from_mapping(merged)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AssistantConfig":
        hours = data.get("working_hours") or {}
        if not isinstance(hours, dict):
            raise AssistantConfigError("working_hours must be a mapping")
        start, end = int(hours.get("start", cls.working_start_hour)), int(hours.get("end", cls.working_end_hour))
        if not 0 <= start < end <= 24:
            raise AssistantConfigError("working_hours must satisfy 0 <= start < end <= 24")
        days = tuple(int(day) for day in data.get("working_days", (0, 1, 2, 3, 4)))
        if any(day not in range(7) for day in days):
            raise AssistantConfigError("working_days must be integers from 0 to 6")
        chats = data.get("chat_whitelist") or []
        if not isinstance(chats, list):
            raise AssistantConfigError("chat_whitelist must be a list")
        base = str(data.get("site_base_url") or cls.site_base_url).rstrip("/") + "/"
        return cls(
            site_base_url=base,
            chat_whitelist=tuple(normalize_chat_id(chat) for chat in chats),
            lark_cli=str(data.get("lark_cli") or cls.lark_cli),
            working_start_hour=start,
            working_end_hour=end,
            working_days=days,
        )

    def is_working_time(self, moment: datetime) -> bool:
        return (
            moment.weekday() in self.working_days
            and self.working_start_hour <= moment.hour < self.working_end_hour
        )


def write_local_config(state_dir: Path, **settings: Any) -> None:
    """Merge settings into the ignored local config; the chat whitelist is checked here."""

    path = state_dir / "config.local.yaml"
    data = _read_mapping(path)
    if "chat_whitelist" in settings:
        settings["chat_whitelist"] = [normalize_chat_id(chat) for chat in settings["chat_whitelist"]]
    data.update(settings)
    state_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=True), encoding="utf-8")
