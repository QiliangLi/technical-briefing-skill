from __future__ import annotations

from pathlib import Path
from typing import Any

from .archive_reader import (
    existing_original_html,
    render_reader_over_original,
    validate_reader_document,
    write_publication_manifest,
)
from .editorial_intent import decorate_reader_cards
from .reader_blocks_renderer_v2 import render_blocks_native
from .utils import read_json


def _machine_items(issue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = [*(issue.get("core_items") or []), *(issue.get("observations") or [])]
    return {
        str(item.get("brief_item_id") or ""): item
        for item in rows
        if item.get("brief_item_id")
    }


def render_archive_variant(
    issue_dir: Path,
    issue: dict[str, Any],
    reader: dict[str, Any],
    *,
    variant: str,
) -> str:
    """Reproject archive prose while preserving the reader contract that produced it."""

    base = render_reader_over_original(issue_dir, issue, reader, variant=variant)
    readers = {
        str(item_id): dict(row)
        for item_id, row in (reader.get("items") or {}).items()
    }
    v2 = {item_id: row for item_id, row in readers.items() if row.get("blocks")}
    legacy = {item_id: row for item_id, row in readers.items() if not row.get("blocks")}

    if v2:
        base = render_blocks_native(
            base,
            v2,
            issue_date=str(reader.get("issue_date") or issue.get("date_to") or ""),
        )
    # Truly old reader documents have no blocks and keep using the legacy deterministic
    # decorator. V2 archives are rebuilt from persisted blocks instead of re-inferring
    # headings or treating lead/body as the display source of truth.
    if legacy and 'data-reader-section-heading="1"' not in base:
        base = decorate_reader_cards(base, _machine_items(issue), legacy)
    return base


def rerender_issue(root: Path, issue_dir: Path) -> list[Path]:
    issue = read_json(issue_dir / "issue.json", {})
    reader = read_json(issue_dir / "reader.json", {})
    validate_reader_document(root, issue, reader)
    originals = existing_original_html(issue_dir)
    if not originals:
        raise ValueError(f"archive has no immutable original email: {issue_dir}")

    changed: list[Path] = []
    fallback_html = ""
    for variant in ("email.html", "email-illustrated.html"):
        original = issue_dir / "original" / variant
        if original.is_file():
            html = render_archive_variant(issue_dir, issue, reader, variant=variant)
            if variant == "email.html":
                fallback_html = html
        else:
            if not fallback_html:
                fallback_html = render_archive_variant(
                    issue_dir,
                    issue,
                    reader,
                    variant="email.html",
                )
            html = fallback_html
        target = issue_dir / variant
        old = target.read_text(encoding="utf-8") if target.is_file() else ""
        if old != html:
            target.write_text(html, encoding="utf-8")
            changed.append(target)

    manifest_before = (issue_dir / "publication-manifest.json").read_text(encoding="utf-8") if (issue_dir / "publication-manifest.json").is_file() else ""
    write_publication_manifest(issue_dir, reader, originals=originals)
    manifest_path = issue_dir / "publication-manifest.json"
    if manifest_path.read_text(encoding="utf-8") != manifest_before:
        changed.append(manifest_path)
    return changed


def rerender_all(root: Path) -> list[Path]:
    changed: list[Path] = []
    for issue_dir in sorted((root / "archive" / "issues").iterdir()):
        if issue_dir.is_dir() and (issue_dir / "issue.json").is_file() and (issue_dir / "reader.json").is_file():
            changed.extend(rerender_issue(root, issue_dir))
    return changed
