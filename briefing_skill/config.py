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


def _load_topics(paths: Paths) -> dict[str, Any]:
    """Load the base topic list and optional focused-topic extensions."""

    topics = _load_yaml(paths.config / "topics.yaml")
    topic_list = topics.setdefault("topics", [])
    known_ids = {str(topic.get("id") or "") for topic in topic_list}

    # Focused and exploration topics live in small extension files so adding one does
    # not require rewriting the large base taxonomy. Extensions are inserted before
    # the legacy horizontal Radar topic and otherwise behave like normal topics.
    for filename in ("topics-chip.yaml", "topics-media.yaml", "topics-frontier.yaml"):
        extension_path = paths.config / filename
        if not extension_path.exists():
            continue
        extension_data = _load_yaml(extension_path)
        extension = extension_data.get("topic")
        if not isinstance(extension, dict) or not extension.get("id"):
            raise ConfigError(
                f"Topic extension must contain a topic mapping with id: {extension_path}"
            )
        if extension["id"] in known_ids:
            continue
        horizontal_index = next(
            (
                index
                for index, topic in enumerate(topic_list)
                if topic.get("id") == "ai_infra_horizontal"
            ),
            len(topic_list),
        )
        topic_list.insert(horizontal_index, extension)
        known_ids.add(str(extension["id"]))

    for topic in topic_list:
        if topic.get("id") == "ai_infra_horizontal":
            description = str(topic.get("description") or "")
            topic["description"] = (
                description.replace("前六个专题", "八个深度专题")
                .replace("七个深度专题", "八个深度专题")
            )
            break
    return topics


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
            topics=_load_topics(paths),
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
            "ai_chip_accelerator": "ai-chip-accelerator.md",
            "storage_media": "storage-media.md",
            "frontier_exploration": "frontier-exploration.md",
            "ai_infra_horizontal": "ai-infra-horizontal.md",
        }
        try:
            return paths.config / "project-context" / mapping[topic_id]
        except KeyError as exc:
            raise ConfigError(f"Unknown project context: {topic_id}") from exc

    def iter_directions(self) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
        for topic in self.topic_list():
            for direction in topic.get("directions", []):
                yield topic, direction
