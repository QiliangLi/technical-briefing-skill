"""The briefing's topics and directions, as the assistant shows them to a host session.

A session that finds a discussion the briefing does not cover has to say where
it would fit. It is shown the scope as configured, never a summary of its own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_topics(root: Path) -> list[dict[str, Any]]:
    """Every topic with its one-line scope and its directions' search terms."""

    topics: list[dict[str, Any]] = []
    for path in sorted((root / "config").glob("topics*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for topic in data.get("topics") or []:
            topics.append(
                {
                    "id": str(topic.get("id") or ""),
                    "name": str(topic.get("name") or ""),
                    "scope": str(topic.get("description") or "")[:200],
                    "directions": [
                        {
                            "id": str(direction.get("id") or ""),
                            "name": str(direction.get("name") or ""),
                            "terms": [str(term) for term in (direction.get("include_terms") or [])[:12]],
                        }
                        for direction in topic.get("directions") or []
                    ],
                }
            )
    return topics


def known_scope_ids(topics: list[dict[str, Any]]) -> set[str]:
    """Every topic and direction id a report may name as the nearest existing scope."""

    return {topic["id"] for topic in topics} | {
        direction["id"] for topic in topics for direction in topic["directions"]
    }
