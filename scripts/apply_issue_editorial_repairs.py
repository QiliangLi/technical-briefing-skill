#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from briefing_skill.db import Database
from briefing_skill.paths import Paths, discover_root
from briefing_skill.utils import now_iso, read_json, write_json


def _merge_signals(existing: list[dict[str, Any]], additions: list[dict[str, Any]]):
    seen = {
        str(url)
        for signal in existing
        for url in signal.get("source_urls") or []
        if str(url)
    }
    merged = list(existing)
    for signal in additions:
        urls = {str(url) for url in signal.get("source_urls") or [] if str(url)}
        if not urls or urls & seen:
            continue
        merged.append(signal)
        seen.update(urls)
    return merged


def apply_repairs(root: Path, run_id: str, repair_path: Path) -> dict[str, Any]:
    paths = Paths(root)
    db = Database(paths.db)
    db.init()
    issue_row = db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
    if not issue_row or not issue_row.get("issue_json_path"):
        raise RuntimeError("Target run has no issue JSON")
    issue_path = root / issue_row["issue_json_path"]
    issue = read_json(issue_path, {})
    repairs = read_json(repair_path, {})
    item_repairs = dict(repairs.get("items") or {})

    history = issue_path.parent / "history"
    history.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    shutil.copy2(issue_path, history / f"issue-before-editorial-repair-{stamp}.json")
    synthesis_path = root / str(issue_row.get("synthesis_path") or "")
    if synthesis_path.is_file():
        shutil.copy2(
            synthesis_path,
            history / f"synthesis-before-editorial-repair-{stamp}.json",
        )

    updated_ids: set[str] = set()
    for collection_name in ("core_items", "items"):
        collection = issue.get(collection_name) or []
        for item in collection:
            item_id = str(item.get("brief_item_id") or "")
            patch = item_repairs.get(item_id)
            if not isinstance(patch, dict):
                continue
            item.update(patch)
            updated_ids.add(item_id)

    for item_id in updated_ids:
        row = db.fetchone(
            "SELECT json_path FROM brief_items WHERE id=? AND run_id=?",
            (item_id, run_id),
        )
        if not row or not row.get("json_path"):
            continue
        item_path = root / row["json_path"]
        item = read_json(item_path, {})
        item.update(item_repairs[item_id])
        write_json(item_path, item)

    additions = list(repairs.get("radar_signals") or [])
    synthesis = dict(issue.get("synthesis") or {})
    synthesis["radar_signals"] = _merge_signals(
        list(synthesis.get("radar_signals") or []), additions
    )
    issue["synthesis"] = synthesis
    audit = dict(issue.get("rebuild_audit") or {})
    audit["editorial_repaired_at"] = now_iso()
    audit["editorial_repair_file"] = str(repair_path.relative_to(root))
    issue["rebuild_audit"] = audit
    write_json(issue_path, issue)

    if synthesis_path.is_file():
        persisted = read_json(synthesis_path, {})
        persisted["radar_signals"] = _merge_signals(
            list(persisted.get("radar_signals") or []), additions
        )
        write_json(synthesis_path, persisted)

    with db.transaction() as conn:
        conn.execute(
            "UPDATE issues SET status='READY_FOR_RENDER',email_path=NULL,updated_at=? WHERE id=?",
            (now_iso(), issue_row["id"]),
        )
        conn.execute(
            "UPDATE runs SET stage='READY_FOR_RENDER',status='ACTIVE',updated_at=? WHERE id=?",
            (now_iso(), run_id),
        )
    return {
        "run_id": run_id,
        "updated_items": len(updated_ids),
        "radar_signals": len(synthesis["radar_signals"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--repairs", required=True, type=Path)
    args = parser.parse_args()
    root = discover_root()
    repair_path = args.repairs
    if not repair_path.is_absolute():
        repair_path = root / repair_path
    print(apply_repairs(root, args.run, repair_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
