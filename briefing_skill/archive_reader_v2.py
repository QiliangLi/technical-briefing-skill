from __future__ import annotations

from typing import Any


def _normalise_blocks(value: Any) -> list[dict[str, str | None]]:
    blocks: list[dict[str, str | None]] = []
    for row in value or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        raw_key = row.get("heading_key")
        key = str(raw_key).strip() if raw_key is not None else None
        blocks.append({"heading_key": key or None, "text": text})
    return blocks


def install_archive_reader_v2_persistence() -> None:
    """Keep v2 blocks as durable archive data while retaining v1 compatibility fields."""

    from . import archive_reader
    from .pipeline import Pipeline

    if getattr(Pipeline, "_archive_reader_v2_persistence_installed", False):
        return

    original_reader_item = archive_reader._reader_item

    def reader_item(
        role: str,
        item: dict[str, Any],
        prose: dict[str, Any],
    ) -> dict[str, Any]:
        result = original_reader_item(role, item, prose)
        blocks = _normalise_blocks(prose.get("blocks"))
        if blocks:
            result["blocks"] = blocks
        return result

    archive_reader._reader_item = reader_item
    Pipeline._archive_reader_v2_persistence_installed = True
