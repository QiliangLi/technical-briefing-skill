from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from .paths import Paths


class ConfigError(RuntimeError):
    pass


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Missing config file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping: {path}")
    return data


@dataclass
class ConfigBundle:
    topics: dict[str, Any]
    sources: dict[str, Any]
    scoring: dict[str, Any]
    settings: dict[str, Any]
    email: dict[str, Any]

    @classmethod
    def load(cls, paths: Paths) -> "ConfigBundle":
        return cls(
            topics=_load_yaml(paths.config / "topics.yaml"),
            sources=_load_yaml(paths.config / "sources.yaml"),
            scoring=_load_yaml(paths.config / "scoring.yaml"),
            settings=_load_yaml(paths.config / "settings.yaml"),
            email=_load_yaml(paths.config / "email.yaml"),
        )

    def topic_list(self) -> list[dict[str, Any]]:
        return list(self.topics.get("topics", []))

    def source_list(self) -> list[dict[str, Any]]:
        return list(self.sources.get("sources", []))

    def topic(self, topic_id: str) -> dict[str, Any]:
        for topic in self.topic_list():
            if topic.get("id") == topic_id:
                return topic
        raise ConfigError(f"Unknown topic: {topic_id}")

    def direction(self, topic_id: str, direction_id: str) -> dict[str, Any]:
        for direction in self.topic(topic_id).get("directions", []):
            if direction.get("id") == direction_id:
                return direction
        raise ConfigError(f"Unknown direction: {topic_id}/{direction_id}")

    def context_path(self, paths: Paths, topic_id: str) -> Path:
        mapping = {
            "tpn": "tpn.md",
            "memory_dsa": "memory-dsa.md",
            "dpu_inline": "dpu.md",
            "agent_acceleration": "agent-acceleration.md",
            "cross_region": "cross-region.md",
            "optical_network": "optical-network.md",
        }
        return paths.config / "project-context" / mapping[topic_id]

    def iter_directions(self) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
        for topic in self.topic_list():
            for direction in topic.get("directions", []):
                yield topic, direction
