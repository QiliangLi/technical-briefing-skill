from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ConfigBundle
from .db import Database
from .freshness import freshness_limits, item_age_days
from .tasks import TaskService, brief_item_validation_errors, synthesis_item_payload
from .utils import complete_sentence_excerpt, now_iso, read_json, source_url_is_resolved


LEGACY_FIELD_BUDGETS = {
    "core_conclusion": 70,
    "mechanism": 50,
    "result": 50,
    "boundary": 35,
    "project_relevance": 45,
}


def normalise_legacy_item(item: dict[str, Any], config: ConfigBundle) -> dict[str, Any]:
    min_chars = int(config.settings.get("brief_item_min_chars", 180))
    max_chars = int(config.settings.get("brief_item_max_chars", 260))
    if not brief_item_validation_errors(item, min_chars=min_chars, max_chars=max_chars):
        return item
    rebuilt = dict(item)
    for field, limit in LEGACY_FIELD_BUDGETS.items():
        rebuilt[field] = complete_sentence_excerpt(str(item.get(field) or ""), limit)
    return rebuilt


def _limits(config: ConfigBundle) -> dict[str, int]:
    defaults = {
        "core_min": 0,
        "core_max": 16,
        "observation_max": 4,
        "total_min": 0,
        "total_max": 20,
        "max_per_topic": 4,
        "core_score": 70,
        "observation_score": 60,
    }
    configured = config.scoring.get("expanded_v2", {})
    return {key: int(configured.get(key, value)) for key, value in defaults.items()}


def select_expanded_rows(
    root: Path,
    config: ConfigBundle,
    rows: list[dict[str, Any]],
    *,
    reference_date: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int], dict[str, int]]:
    """Classify and cap fact-checked rows for both normal runs and rebuilds.

    Within each role, technical value is the primary ordering signal. Freshness is
    deliberately only a secondary tie-breaker so a routine release from today
    cannot outrank a materially stronger paper or architecture result from the
    rolling topic window merely because it is newer.
    """
    limits = _limits(config)
    age_limits = freshness_limits(config)
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in rows:
        score = float(row["score"])
        if row.get("fact_check_status") != "PASS":
            excluded.append({"id": row["id"], "score": score, "reason": "fact check did not pass"})
            continue
        item = read_json(root / row["json_path"])
        age = item_age_days(
            {**item, "source_published_at": row.get("source_published_at")},
            reference=reference_date,
        )
        if age is None:
            excluded.append({"id": row["id"], "score": score, "reason": "unknown original publication date"})
            continue
        if age > age_limits["absolute"]:
            excluded.append({"id": row["id"], "score": score, "reason": f"stale source ({age} days old)"})
            continue
        if row.get("last_pushed_at") and not item.get("incremental_update"):
            excluded.append({"id": row["id"], "score": score, "reason": "previously pushed without incremental update"})
            continue
        has_resolved_a = any(
            source.get("source_level") == "A" and source_url_is_resolved(source.get("url"))
            for source in item.get("sources", [])
        )
        if age <= age_limits["core"] and score >= limits["core_score"] and has_resolved_a:
            role = "core"
        elif age <= age_limits["adjacent"] and score >= limits["observation_score"] and has_resolved_a:
            role = "observation"
        else:
            reason = "no resolved A-level source" if not has_resolved_a else "below expanded-v2 evidence threshold"
            excluded.append({"id": row["id"], "score": score, "reason": reason})
            continue
        eligible.append({**row, "item": item, "item_role": role, "age_days": age})

    eligible.sort(
        key=lambda row: (
            0 if row["item_role"] == "core" else 1,
            -float(row["score"]),
            int(row["age_days"]),
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
               e.topic_id, e.direction_id,
               COALESCE(
                 e.last_pushed_at,
                 (SELECT MAX(e2.last_pushed_at) FROM events e2
                  WHERE e.event_key IS NOT NULL AND e2.event_key=e.event_key)
               ) AS last_pushed_at,
               (SELECT MAX(r.published_at)
                FROM event_members em
                JOIN candidates c ON c.id=em.candidate_id
                JOIN raw_items r ON r.id=c.raw_item_id
                WHERE em.event_id=e.id) AS source_published_at,
               ii.visual_plan_path
        FROM brief_items bi
        JOIN events e ON e.id=bi.event_id
        LEFT JOIN issue_items ii ON ii.brief_item_id=bi.id AND ii.issue_id=?
        WHERE bi.run_id=?
        ORDER BY bi.score DESC, bi.id
        """,
        (issue["id"], run_id),
    )
    selected, excluded, counts, limits = select_expanded_rows(
        root,
        config,
        rows,
        reference_date=issue.get("date_to") or issue.get("date_from"),
    )

    core_items = []
    observations = []
    for position, row in enumerate(selected, 1):
        item = {
            **normalise_legacy_item(row["item"], config),
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
        "synthesis": None,
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

    with db.transaction() as conn:
        conn.execute("DELETE FROM issue_items WHERE issue_id=?", (issue["id"],))
        conn.execute("DELETE FROM issue_radar_items WHERE issue_id=?", (issue["id"],))
        for position, row in enumerate(plan["selected"], 1):
            conn.execute(
                "INSERT INTO issue_items(issue_id, brief_item_id, position, item_role, visual_plan_path) VALUES (?, ?, ?, ?, ?)",
                (issue["id"], row["id"], position, row["item_role"], row.get("visual_plan_path")),
            )
        conn.execute("UPDATE brief_items SET approved=0 WHERE run_id=?", (run_id,))
        conn.execute(
            "UPDATE issues SET status='DRAFT', synthesis_path=NULL, issue_json_path=NULL, email_path=NULL, updated_at=? WHERE id=?",
            (now_iso(), issue["id"]),
        )
        conn.execute(
            "UPDATE runs SET stage='AWAITING_ISSUE_SYNTHESIS', status='ACTIVE', updated_at=? WHERE id=?",
            (now_iso(), run_id),
        )

    synthesis_items = [
        synthesis_item_payload(row, row["item"])
        for row in plan["selected"]
        if row["item_role"] == "core"
    ]
    tasks = TaskService(db, root, root / "workspace" / "runs" / run_id)
    task = tasks.create(
        run_id,
        "issue_synthesis",
        issue["id"],
        {
            "issue_id": issue["id"],
            "items": synthesis_items,
            "max_judgements": 3,
            "audience": "公司内部领导和技术同事",
        },
        prompt="issue-synthesis.md",
        schema="issue-synthesis.schema.json",
        priority=100,
        metadata={
            "required_skills": ["human-writing", "humanizer"],
            "skill_mode": "chinese_technical_rewrite_then_ai_pattern_audit",
        },
        replace_existing=True,
    )
    return {
        "dry_run": False,
        "counts": counts,
        "backup": str(backup),
        "status": "AWAITING_ISSUE_SYNTHESIS",
        "stage": "AWAITING_ISSUE_SYNTHESIS",
        "next_task": tasks.instructions(task),
    }
