from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ConfigBundle
from .db import Database
from .utils import now_iso, read_json


def _limits(config: ConfigBundle) -> dict[str, int]:
    defaults = {
        "core_min": 8,
        "core_max": 14,
        "observation_max": 4,
        "total_min": 12,
        "total_max": 18,
        "max_per_topic": 8,
        "core_score": 70,
        "observation_score": 60,
    }
    configured = config.scoring.get("expanded_v2", {})
    return {key: int(configured.get(key, value)) for key, value in defaults.items()}


def select_expanded_rows(
    root: Path,
    config: ConfigBundle,
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int], dict[str, int]]:
    """Classify and cap fact-checked rows for both normal runs and rebuilds."""
    limits = _limits(config)
    topic_order = {topic["id"]: index for index, topic in enumerate(config.topic_list())}
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in rows:
        score = float(row["score"])
        if row.get("fact_check_status") != "PASS":
            excluded.append({"id": row["id"], "score": score, "reason": "fact check did not pass"})
            continue
        item = read_json(root / row["json_path"])
        if row.get("last_pushed_at") and not item.get("incremental_update"):
            excluded.append({"id": row["id"], "score": score, "reason": "previously pushed without incremental update"})
            continue
        source_levels = {str(source.get("source_level", "")) for source in item.get("sources", [])}
        if score >= limits["core_score"] and "A" in source_levels:
            role = "core"
        elif limits["observation_score"] <= score < limits["core_score"]:
            role = "observation"
        else:
            reason = "high score but no A-level source" if score >= limits["core_score"] else "below expanded-v2 evidence threshold"
            excluded.append({"id": row["id"], "score": score, "reason": reason})
            continue
        eligible.append({**row, "item": item, "item_role": role})

    eligible.sort(
        key=lambda row: (
            topic_order.get(row["topic_id"], 999),
            0 if row["item_role"] == "core" else 1,
            -float(row["score"]),
            row["id"],
        )
    )
    selected: list[dict[str, Any]] = []
    topic_counts: dict[str, int] = {}
    core_count = observation_count = 0
    for row in eligible:
        if len(selected) >= limits["total_max"] or topic_counts.get(row["topic_id"], 0) >= limits["max_per_topic"]:
            excluded.append({"id": row["id"], "score": row["score"], "reason": "expanded-v2 capacity"})
            continue
        if row["item_role"] == "core":
            if core_count >= limits["core_max"]:
                excluded.append({"id": row["id"], "score": row["score"], "reason": "core capacity"})
                continue
            core_count += 1
        else:
            if observation_count >= limits["observation_max"]:
                excluded.append({"id": row["id"], "score": row["score"], "reason": "observation capacity"})
                continue
            observation_count += 1
        topic_counts[row["topic_id"]] = topic_counts.get(row["topic_id"], 0) + 1
        selected.append(row)
    counts = {"core": core_count, "observations": observation_count, "total": len(selected), "topics": topic_counts}
    return selected, excluded, counts, limits


def plan_expanded_issue(root: Path, config: ConfigBundle, db: Database, run_id: str) -> dict[str, Any]:
    issue = db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
    run = db.fetchone("SELECT * FROM runs WHERE id=?", (run_id,))
    if not issue or not run or not issue.get("issue_json_path"):
        raise RuntimeError("Run does not have a rebuildable issue")
    if issue.get("status") == "SENT" or run.get("status") == "COMPLETED":
        raise RuntimeError("Refusing to rebuild a sent or completed run")

    rows = db.fetchall(
        """
        SELECT bi.id, bi.score, bi.json_path, bi.fact_check_status,
               e.topic_id, e.direction_id, e.last_pushed_at, ii.visual_plan_path
        FROM brief_items bi
        JOIN events e ON e.id=bi.event_id
        LEFT JOIN issue_items ii ON ii.brief_item_id=bi.id AND ii.issue_id=?
        WHERE bi.run_id=?
        ORDER BY bi.score DESC, bi.id
        """,
        (issue["id"], run_id),
    )
    selected, excluded, counts, limits = select_expanded_rows(root, config, rows)

    previous = read_json(root / issue["issue_json_path"])
    core_items = []
    observations = []
    for position, row in enumerate(selected, 1):
        item = {
            **row["item"],
            "brief_item_id": row["id"],
            "topic_id": row["topic_id"],
            "direction_id": row["direction_id"],
            "item_role": row["item_role"],
            "fact_check_status": row["fact_check_status"],
            "anchor_id": f"item-{row['id']}",
        }
        (core_items if row["item_role"] == "core" else observations).append(item)

    rebuilt = {
        "id": issue["id"],
        "run_id": run_id,
        "date_from": issue.get("date_from"),
        "date_to": issue.get("date_to"),
        "layout_mode": "expanded_v2",
        "synthesis": previous.get("synthesis") or read_json(root / issue.get("synthesis_path", ""), {}),
        "core_items": core_items,
        "observations": observations,
        "items": core_items + observations,
        "rebuild_audit": {"planned_at": now_iso(), "source": "existing fact-checked items", "requires_reapproval": True},
    }
    return {
        "issue": issue,
        "run": run,
        "limits": limits,
        "selected": selected,
        "excluded": excluded,
        "rebuilt": rebuilt,
        "counts": counts,
    }


def rebuild_expanded_issue(root: Path, config: ConfigBundle, db: Database, run_id: str, *, confirm: bool = False) -> dict[str, Any]:
    plan = plan_expanded_issue(root, config, db, run_id)
    if not confirm:
        return {"dry_run": True, "counts": plan["counts"], "selected": [{"id": row["id"], "role": row["item_role"], "score": row["score"]} for row in plan["selected"]], "excluded": plan["excluded"]}

    limits = plan["limits"]
    counts = plan["counts"]
    if counts["total"] > limits["total_max"] or counts["core"] > limits["core_max"] or counts["observations"] > limits["observation_max"]:
        raise RuntimeError("Expanded issue exceeds configured capacity")
    issue = plan["issue"]
    issue_path = root / issue["issue_json_path"]
    issue_dir = issue_path.parent
    issue_dir.mkdir(parents=True, exist_ok=True)
    history = issue_dir / "history"
    history.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = history / f"issue-before-expanded-v2-{stamp}.json"
    shutil.copy2(issue_path, backup)

    fd, temp_name = tempfile.mkstemp(prefix=".issue-expanded-v2-", suffix=".json", dir=issue_dir)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(plan["rebuilt"], handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Confirm the complete temporary document is readable before touching state.
        json.loads(temp_path.read_text(encoding="utf-8"))
        replaced = False
        try:
            with db.transaction() as conn:
                conn.execute("DELETE FROM issue_items WHERE issue_id=?", (issue["id"],))
                for position, row in enumerate(plan["selected"], 1):
                    conn.execute(
                        "INSERT INTO issue_items(issue_id, brief_item_id, position, item_role, visual_plan_path) VALUES (?, ?, ?, ?, ?)",
                        (issue["id"], row["id"], position, row["item_role"], row.get("visual_plan_path")),
                    )
                conn.execute("UPDATE brief_items SET approved=0 WHERE run_id=?", (run_id,))
                conn.execute("UPDATE issues SET status='AWAITING_APPROVAL', updated_at=? WHERE id=?", (now_iso(), issue["id"]))
                conn.execute("UPDATE runs SET stage='AWAITING_APPROVAL', status='ACTIVE', updated_at=? WHERE id=?", (now_iso(), run_id))
                os.replace(temp_path, issue_path)
                replaced = True
        except Exception:
            if replaced:
                restore = issue_dir / f".restore-{stamp}.json"
                shutil.copy2(backup, restore)
                os.replace(restore, issue_path)
            raise
    finally:
        temp_path.unlink(missing_ok=True)
    return {"dry_run": False, "counts": counts, "backup": str(backup), "issue_path": str(issue_path), "status": "AWAITING_APPROVAL"}
