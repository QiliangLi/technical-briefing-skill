#!/usr/bin/env python3
"""Restore immutable pre-v2 archive provenance from Git history.

This script does not change the public Reader v2 projection. It restores the last
pre-v2 reader document and illustrated publication snapshot under ``original/``
and records which legacy prose segments are represented verbatim in current v2
blocks. Restored artifacts are copied byte-for-byte from the locked source commit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from briefing_skill.archive_reader import existing_original_html, write_publication_manifest
from briefing_skill.utils import read_json, write_json


LEGACY_READER_COMMIT = "8ae3e0ee90f377ddae74b4032298a23480eeaeaa"
ARCHIVE_DATES = (
    "2026-08-02",
    "2026-08-06",
    "2026-08-10",
    "2026-08-11",
    "2026-08-15",
    "2026-08-17",
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git_show(root: Path, commit: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise ValueError(
            f"historical artifact missing at {commit}:{path}: "
            f"{result.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return result.stdout


def _write_immutable(path: Path, content: bytes) -> None:
    if path.is_file():
        if path.read_bytes() != content:
            raise ValueError(f"refusing to replace immutable provenance artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _legacy_segments(item: dict[str, Any]) -> list[tuple[str, int, str]]:
    result: list[tuple[str, int, str]] = []
    lead = str(item.get("lead") or "").strip()
    if lead:
        result.append(("lead", 0, lead))
    for index, value in enumerate(item.get("body") or []):
        text = str(value or "").strip()
        if text:
            result.append(("body", index, text))
    takeaway = str(item.get("takeaway") or "").strip()
    if takeaway:
        result.append(("takeaway", 0, takeaway))
    return result


def _traceability(legacy: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    current_items = current.get("items") or {}
    totals = {"lead": 0, "body": 0, "takeaway": 0}
    preserved = {"lead": 0, "body": 0, "takeaway": 0}
    missing: list[dict[str, Any]] = []

    for item_id, legacy_item in (legacy.get("items") or {}).items():
        current_item = current_items.get(item_id) or {}
        block_texts = {
            str(block.get("text") or "").strip()
            for block in current_item.get("blocks") or []
            if str(block.get("text") or "").strip()
        }
        for field, index, text in _legacy_segments(legacy_item):
            totals[field] += 1
            if text in block_texts:
                preserved[field] += 1
            else:
                missing.append({"item_id": item_id, "field": field, "index": index})

    total = sum(totals.values())
    preserved_total = sum(preserved.values())
    return {
        "legacy_segment_total": total,
        "legacy_segment_exactly_preserved_in_v2_blocks": preserved_total,
        "legacy_segment_not_verbatim_in_v2_blocks": total - preserved_total,
        "by_field": {
            field: {
                "total": totals[field],
                "exactly_preserved_in_v2_blocks": preserved[field],
                "not_verbatim_in_v2_blocks": totals[field] - preserved[field],
            }
            for field in ("lead", "body", "takeaway")
        },
        "not_verbatim_segments": missing,
    }


def _illustrated_metadata(issue_dir: Path, source_commit: str) -> dict[str, Any]:
    path = issue_dir / "original" / "email-illustrated.html"
    data = path.read_bytes()
    plain = issue_dir / "original" / "email.html"
    return {
        "kind": "pre_v2_published_snapshot",
        "source_commit": source_commit,
        "path": "original/email-illustrated.html",
        "sha256": _sha256(data),
        "distinct_from_plain_original": plain.is_file() and plain.read_bytes() != data,
        "img_tag_count": len(re.findall(rb"<img\b", data, flags=re.IGNORECASE)),
    }


def _build_provenance(issue_dir: Path, source_commit: str) -> dict[str, Any]:
    legacy_path = issue_dir / "original" / "reader.json"
    legacy_bytes = legacy_path.read_bytes()
    legacy = json.loads(legacy_bytes.decode("utf-8"))
    current = read_json(issue_dir / "reader.json", {})
    traceability = _traceability(legacy, current)
    return {
        "schema_version": 1,
        "issue_date": issue_dir.name,
        "legacy_reader": {
            "kind": "pre_v2_reader_snapshot",
            "source_commit": source_commit,
            "path": "original/reader.json",
            "sha256": _sha256(legacy_bytes),
            "reader_contract_version": legacy.get("reader_contract_version"),
            "item_count": len(legacy.get("items") or {}),
            "traceability": traceability,
        },
        "illustrated_html": _illustrated_metadata(issue_dir, source_commit),
    }


def backfill_issue(root: Path, issue_date: str) -> Path:
    issue_dir = root / "archive" / "issues" / issue_date
    legacy_reader_rel = f"archive/issues/{issue_date}/reader.json"
    illustrated_rel = f"archive/issues/{issue_date}/email-illustrated.html"
    legacy_reader = _git_show(root, LEGACY_READER_COMMIT, legacy_reader_rel)
    illustrated = _git_show(root, LEGACY_READER_COMMIT, illustrated_rel)

    _write_immutable(issue_dir / "original" / "reader.json", legacy_reader)
    _write_immutable(issue_dir / "original" / "email-illustrated.html", illustrated)

    provenance = _build_provenance(issue_dir, LEGACY_READER_COMMIT)
    write_json(issue_dir / "original" / "provenance.json", provenance)

    reader = read_json(issue_dir / "reader.json", {})
    write_publication_manifest(
        issue_dir,
        reader,
        originals=existing_original_html(issue_dir),
    )
    return issue_dir


def validate_issue(issue_dir: Path) -> list[str]:
    errors: list[str] = []
    legacy_path = issue_dir / "original" / "reader.json"
    illustrated_path = issue_dir / "original" / "email-illustrated.html"
    provenance_path = issue_dir / "original" / "provenance.json"
    if not legacy_path.is_file():
        errors.append(f"{issue_dir.name}: missing original/reader.json")
        return errors
    if not illustrated_path.is_file():
        errors.append(f"{issue_dir.name}: missing original/email-illustrated.html")
        return errors
    if not provenance_path.is_file():
        errors.append(f"{issue_dir.name}: missing original/provenance.json")
        return errors

    provenance = read_json(provenance_path, {})
    expected = _build_provenance(issue_dir, LEGACY_READER_COMMIT)
    if provenance != expected:
        errors.append(f"{issue_dir.name}: provenance.json is stale")

    legacy = read_json(legacy_path, {})
    current = read_json(issue_dir / "reader.json", {})
    if set(legacy.get("items") or {}) != set(current.get("items") or {}):
        errors.append(f"{issue_dir.name}: legacy/current item IDs differ")
    if any(not (item.get("blocks") or []) for item in (current.get("items") or {}).values()):
        errors.append(f"{issue_dir.name}: current Reader v2 item is missing blocks")

    manifest = read_json(issue_dir / "publication-manifest.json", {})
    files = manifest.get("files") or {}
    for relative in ("original/reader.json", "original/email-illustrated.html", "original/provenance.json"):
        path = issue_dir / relative
        if files.get(relative) != _sha256(path.read_bytes()):
            errors.append(f"{issue_dir.name}: manifest hash missing/stale for {relative}")
    return errors


def validate_archives(root: Path) -> list[str]:
    errors: list[str] = []
    for issue_date in ARCHIVE_DATES:
        errors.extend(validate_issue(root / "archive" / "issues" / issue_date))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not args.check:
        for issue_date in ARCHIVE_DATES:
            backfill_issue(root, issue_date)
    errors = validate_archives(root)
    if errors:
        for error in errors:
            print(error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
