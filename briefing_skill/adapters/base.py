from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class CollectedItem:
    source_id: str
    discovery_source: str
    source_level: str
    discovery_only: bool
    title: str
    summary: str = ""
    original_url: str = ""
    aihot_url: str = ""
    published_at: str | None = None
    discovered_at: str | None = None
    authors: list[str] = field(default_factory=list)
    external_id: str = ""
    topic_hint: str = ""
    direction_hint: str = ""
    priority: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)


class Collector(Protocol):
    def collect(self) -> list[CollectedItem]: ...
