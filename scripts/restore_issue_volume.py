#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database
from briefing_skill.item_freshness import item_is_within_lookback, parse_publication_date
from briefing_skill.paths import Paths, discover_root
from briefing_skill.utils import now_iso, read_json, stable_hash, write_json


def _source_urls(item: dict[str, Any]) -> set[str]:
    return {
        str(source.get("url") or "")
        for source in item.get("sources") or []
        if source.get("url")
    }


def _reference_items(
    db: Database,
    root: Path,
    reference_run: str,
    reference_issue: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return issue-selected items followed by other PASS cards from the run."""

    selected = list(
        reference_issue.get("core_items") or reference_issue.get("items") or []
    )
    seen = {str(item.get("brief_item_id") or "") for item in selected}
    rows = db.fetchall(
        """
        SELECT b.*,e.topic_id,e.direction_id
        FROM brief_items b JOIN events e ON e.id=b.event_id
        WHERE b.run_id=? AND b.fact_check_status='PASS'
        ORDER BY b.score DESC,b.created_at
        """,
        (reference_run,),
    )
    for row in rows:
        if str(row.get("id") or "") in seen:
            continue
        item = read_json(root / row["json_path"], {})
        if not item:
            continue
        selected.append(
            {
                **item,
                "brief_item_id": row["id"],
                "topic_id": row["topic_id"],
                "direction_id": row["direction_id"],
                "fact_check_status": "PASS",
                "score": row.get("score") or item.get("score") or 0,
            }
        )
        seen.add(str(row["id"]))
    return selected


def _parse_topic_targets(values: list[str]) -> dict[str, int]:
    targets: dict[str, int] = {}
    for value in values:
        topic_id, separator, count = value.partition("=")
        if not separator or not topic_id.strip():
            raise ValueError(f"Invalid --topic-min value: {value!r}")
        wanted = int(count)
        if wanted < 0 or wanted > 4:
            raise ValueError(f"Topic target must be between 0 and 4: {value!r}")
        targets[topic_id.strip()] = wanted
    return targets


def _issue_end_date(issue: dict[str, Any], issue_row: dict[str, Any]) -> date:
    value = issue.get("date_to") or issue_row.get("date_to")
    parsed = parse_publication_date(value)
    if not parsed:
        raise RuntimeError("Target issue has no valid date_to for freshness checks")
    return parsed


def _rewrite_issue_items(
    db: Database,
    *,
    issue_id: str,
    run_id: str,
    items: list[dict[str, Any]],
) -> None:
    with db.transaction() as conn:
        conn.execute("DELETE FROM issue_items WHERE issue_id=?", (issue_id,))
        for position, item in enumerate(items, 1):
            conn.execute(
                """
                INSERT INTO issue_items(issue_id,brief_item_id,position,item_role)
                VALUES (?,?,?,?)
                """,
                (issue_id, item["brief_item_id"], position, "core"),
            )
        conn.execute(
            """
            UPDATE issues
            SET status='READY_FOR_RENDER',email_path=NULL,updated_at=?
            WHERE id=?
            """,
            (now_iso(), issue_id),
        )
        conn.execute(
            "UPDATE runs SET stage='READY_FOR_RENDER',status='ACTIVE',updated_at=? WHERE id=?",
            (now_iso(), run_id),
        )


def prune_out_of_window_restores(root: Path, run_id: str) -> dict[str, Any]:
    paths = Paths(root)
    config = ConfigBundle.load(paths)
    db = Database(paths.db)
    db.init()
    issue_row = db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
    if not issue_row or not issue_row.get("issue_json_path"):
        raise RuntimeError("Target run has no issue JSON")
    issue_path = root / issue_row["issue_json_path"]
    issue = read_json(issue_path, {})
    issue_end = _issue_end_date(issue, issue_row)
    lookback_days = max(
        1,
        int(
            (config.settings.get("efficiency") or {}).get(
                "deep_lookback_days", 60
            )
        ),
    )
    items = list(issue.get("core_items") or issue.get("items") or [])
    removed = [
        item
        for item in items
        if (item.get("restored_from_run") or item.get("restored_brief_item_id"))
        and not item_is_within_lookback(
            item, issue_end=issue_end, lookback_days=lookback_days
        )
    ]
    if not removed:
        return {"run_id": run_id, "removed": 0, "removed_items": []}

    history = issue_path.parent / "history"
    history.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    issue_backup = history / f"issue-before-freshness-prune-{stamp}.json"
    shutil.copy2(issue_path, issue_backup)
    email_backup = None
    if issue_row.get("email_path") and (root / issue_row["email_path"]).is_file():
        email_backup = history / f"email-before-freshness-prune-{stamp}.html"
        shutil.copy2(root / issue_row["email_path"], email_backup)

    removed_ids = {str(item.get("brief_item_id") or "") for item in removed}
    retained = [
        item for item in items if str(item.get("brief_item_id") or "") not in removed_ids
    ]
    _rewrite_issue_items(
        db,
        issue_id=issue_row["id"],
        run_id=run_id,
        items=retained,
    )
    with db.transaction() as conn:
        for item_id in sorted(removed_ids):
            conn.execute(
                "DELETE FROM brief_items WHERE id=? AND run_id=?", (item_id, run_id)
            )

    audit = dict(issue.get("rebuild_audit") or {})
    audit.update(
        {
            "freshness_pruned_at": now_iso(),
            "freshness_window_days": lookback_days,
            "freshness_window_end": issue_end.isoformat(),
            "freshness_pruned_item_ids": sorted(removed_ids),
        }
    )
    rebuilt = {
        **issue,
        "core_items": retained,
        "items": retained,
        "rebuild_audit": audit,
    }
    write_json(issue_path, rebuilt)
    return {
        "run_id": run_id,
        "removed": len(removed),
        "removed_items": [item.get("title") for item in removed],
        "detailed_total": len(retained),
        "topic_counts": dict(
            Counter(str(item.get("topic_id") or "") for item in retained)
        ),
        "issue_backup": str(issue_backup),
        "email_backup": str(email_backup) if email_backup else None,
    }


def restore_issue_volume(
    root: Path,
    run_id: str,
    reference_runs: str | list[str],
    *,
    topic_targets: dict[str, int] | None = None,
) -> dict[str, Any]:
    paths = Paths(root)
    config = ConfigBundle.load(paths)
    db = Database(paths.db)
    db.init()

    target_issue = db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
    if isinstance(reference_runs, str):
        reference_runs = [reference_runs]
    reference_runs = [str(value) for value in reference_runs if str(value)]
    if not reference_runs:
        raise RuntimeError("At least one reference run is required")
    reference_issues = [
        db.fetchone("SELECT * FROM issues WHERE run_id=?", (reference_run,))
        for reference_run in reference_runs
    ]
    if not target_issue or not target_issue.get("issue_json_path"):
        raise RuntimeError("Target run has no rendered issue JSON")
    if any(not row or not row.get("issue_json_path") for row in reference_issues):
        raise RuntimeError("One or more reference runs have no issue JSON")

    target = read_json(root / target_issue["issue_json_path"], {})
    issue_end = _issue_end_date(target, target_issue)
    lookback_days = max(
        1,
        int(
            (config.settings.get("efficiency") or {}).get(
                "deep_lookback_days", 60
            )
        ),
    )
    target_items = list(target.get("core_items") or target.get("items") or [])
    references: list[tuple[str, list[dict[str, Any]]]] = []
    for reference_run, reference_issue in zip(reference_runs, reference_issues):
        reference = read_json(root / reference_issue["issue_json_path"], {})
        references.append(
            (
                reference_run,
                _reference_items(db, root, reference_run, reference),
            )
        )
    history = (root / target_issue["issue_json_path"]).parent / "history"
    history.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    issue_backup = history / f"issue-before-volume-restore-{stamp}.json"
    shutil.copy2(root / target_issue["issue_json_path"], issue_backup)
    email_backup = None
    if target_issue.get("email_path") and (root / target_issue["email_path"]).is_file():
        email_backup = history / f"email-before-volume-restore-{stamp}.html"
        shutil.copy2(root / target_issue["email_path"], email_backup)
    desired = Counter(topic_targets or {})
    if not desired:
        desired.update(
            str(item.get("topic_id") or "") for item in references[0][1]
        )
    current = Counter(str(item.get("topic_id") or "") for item in target_items)
    selected_urls = {
        url for item in target_items for url in _source_urls(item)
    }
    reference_by_topic: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for reference_run, reference_items in references:
        for item in reference_items:
            reference_by_topic[str(item.get("topic_id") or "")].append(
                (reference_run, item)
            )

    restored_items: list[dict[str, Any]] = []
    skipped_freshness: list[dict[str, Any]] = []
    run_dir = paths.runs / run_id
    for topic_id, wanted in desired.items():
        deficit = max(0, wanted - current.get(topic_id, 0))
        if not deficit:
            continue
        for reference_run, reference_item in reference_by_topic[topic_id]:
            if deficit <= 0:
                break
            urls = _source_urls(reference_item)
            if not urls or urls & selected_urls:
                continue
            reference_item_id = str(reference_item.get("brief_item_id") or "")
            reference_row = db.fetchone(
                """
                SELECT * FROM brief_items
                WHERE id=? AND run_id=? AND fact_check_status='PASS'
                """,
                (reference_item_id, reference_run),
            )
            if not reference_row:
                continue
            source_item = read_json(root / reference_row["json_path"], {})
            if _source_urls(source_item) != urls:
                continue
            freshness_item = {
                **source_item,
                "published_at": reference_item.get("published_at")
                or source_item.get("published_at"),
            }
            if not item_is_within_lookback(
                freshness_item,
                issue_end=issue_end,
                lookback_days=lookback_days,
            ):
                skipped_freshness.append(
                    {
                        "reference_run": reference_run,
                        "brief_item_id": reference_item_id,
                        "title": reference_item.get("title") or source_item.get("title"),
                        "published_at": freshness_item.get("published_at"),
                    }
                )
                continue

            restored_id = stable_hash(
                run_id, "restored-reference-item", reference_run, reference_item_id
            )
            restored_path = run_dir / "items" / f"{restored_id}.json"
            provenance = dict(source_item.get("_provenance") or {})
            provenance.update(
                {
                    "restored_from_run": reference_run,
                    "restored_brief_item_id": reference_item_id,
                }
            )
            write_json(restored_path, {**source_item, "_provenance": provenance})
            db.execute(
                """
                INSERT OR REPLACE INTO brief_items(
                    id,run_id,event_id,json_path,score,fact_check_status,approved,created_at
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    restored_id,
                    run_id,
                    reference_row["event_id"],
                    str(restored_path.relative_to(root)),
                    reference_row["score"],
                    "PASS",
                    0,
                    now_iso(),
                ),
            )
            restored_items.append(
                {
                    **source_item,
                    "brief_item_id": restored_id,
                    "topic_id": reference_item.get("topic_id"),
                    "direction_id": reference_item.get("direction_id"),
                    "item_role": "core",
                    "fact_check_status": "PASS",
                    "anchor_id": f"item-{restored_id}",
                    "restored_from_run": reference_run,
                    "restored_brief_item_id": reference_item_id,
                }
            )
            selected_urls.update(urls)
            current[topic_id] += 1
            deficit -= 1

    merged = target_items + restored_items
    topic_order = {
        str(topic.get("id") or ""): index
        for index, topic in enumerate(config.topic_list())
    }
    merged.sort(
        key=lambda item: (
            topic_order.get(str(item.get("topic_id") or ""), len(topic_order)),
            -float(item.get("score") or 0),
            str(item.get("brief_item_id") or ""),
        )
    )
    _rewrite_issue_items(
        db,
        issue_id=target_issue["id"],
        run_id=run_id,
        items=merged,
    )

    restored_audit = dict(target.get("rebuild_audit") or {})
    restored_audit.update(
        {
            "volume_restored_at": now_iso(),
            "reference_run": str(
                restored_audit.get("reference_run") or reference_runs[0]
            ),
            "supplemental_reference_runs": reference_runs,
            "restored_detailed_items": int(
                restored_audit.get("restored_detailed_items") or 0
            )
            + len(restored_items),
            "requested_topic_minimums": dict(desired),
            "restore_freshness_window_days": lookback_days,
            "restore_freshness_window_end": issue_end.isoformat(),
            "restore_skipped_freshness": skipped_freshness,
        }
    )
    rebuilt = {
        **target,
        "core_items": merged,
        "observations": [],
        "items": merged,
        "rebuild_audit": restored_audit,
    }
    write_json(root / target_issue["issue_json_path"], rebuilt)
    return {
        "run_id": run_id,
        "reference_runs": reference_runs,
        "restored": len(restored_items),
        "skipped_freshness": skipped_freshness,
        "detailed_total": len(merged),
        "topic_counts": dict(Counter(str(item.get("topic_id") or "") for item in merged)),
        "issue_backup": str(issue_backup),
        "email_backup": str(email_backup) if email_backup else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--reference-run", action="append", default=[])
    parser.add_argument(
        "--prune-out-of-window",
        action="store_true",
        help="remove previously restored detailed cards outside the configured lookback",
    )
    parser.add_argument(
        "--topic-min",
        action="append",
        default=[],
        metavar="TOPIC=COUNT",
        help="minimum detailed-card count for a topic (repeatable, max 4)",
    )
    args = parser.parse_args()
    root = discover_root()
    if args.prune_out_of_window:
        result = prune_out_of_window_restores(root, args.run)
    else:
        if not args.reference_run:
            parser.error("--reference-run is required unless --prune-out-of-window is used")
        result = restore_issue_volume(
            root,
            args.run,
            args.reference_run,
            topic_targets=_parse_topic_targets(args.topic_min),
        )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
