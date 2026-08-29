from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import ConfigBundle
from .db import Database
from .freshness import freshness_limits, item_age_days
from .tasks import TaskService, brief_item_validation_errors, synthesis_item_payload
from .utils import complete_sentence_excerpt, now_iso, read_json, source_url_is_resolved


LEGACY_FIELD_BUDGETS = {
    "core_conclusion": 100,
    "mechanism": 75,
    "result": 75,
    "boundary": 55,
    "project_relevance": 65,
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


def historical_brief_upgrade_min_chars(config: ConfigBundle) -> int:
    """Compatibility floor for fact-checked brief-only cards from older runs."""

    current_min = int(config.settings.get("brief_item_min_chars", 180))
    configured = int(
        config.settings.get("historical_brief_upgrade_min_chars", min(180, current_min))
    )
    return max(1, min(configured, current_min))


def _limits(config: ConfigBundle) -> dict[str, int]:
    defaults = {
        "core_min": 0,
        "core_max": 16,
        "observation_max": 4,
        "total_min": 0,
        "total_max": 20,
        "max_per_topic": 4,
        "topic_target": 4,
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
    expanded_config = config.scoring.get("expanded_v2", {})
    allow_brief_upgrade = bool(
        expanded_config.get(
            "topic_floor_allow_brief_upgrade",
            expanded_config.get("topic_floor_allow_revisit", True),
        )
    )
    policy = dict(config.settings.get("efficiency") or {})
    # Materialized topic-floor upgrades publish at the appendix admission bar.
    upgrade_min_score = float(
        policy.get(
            "topic_floor_upgrade_min_score",
            policy.get("topic_appendix_min_relevance_score", 45),
        )
    )
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    brief_upgrade_pool: dict[str, list[dict[str, Any]]] = {}
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
            previously_brief = bool(row.get("previously_brief"))
            previously_detailed = bool(row.get("previously_detailed"))
            if (
                allow_brief_upgrade
                and previously_brief
                and not previously_detailed
                and score >= limits["observation_score"]
            ):
                brief_upgrade_pool.setdefault(row["topic_id"], []).append(
                    {
                        **row,
                        "item": item,
                        "age_days": age,
                        "item_role": "observation",
                        "brief_upgrade": True,
                    }
                )
            else:
                reason = (
                    "previously published as detailed without incremental update"
                    if previously_detailed
                    else "previously published without brief-only upgrade provenance"
                )
                excluded.append({"id": row["id"], "score": score, "reason": reason})
            continue
        has_resolved_a = any(
            source.get("source_level") == "A" and source_url_is_resolved(source.get("url"))
            for source in item.get("sources", [])
        )
        is_floor_upgrade = bool(row.get("floor_upgrade"))
        min_observation = upgrade_min_score if is_floor_upgrade else limits["observation_score"]
        if not is_floor_upgrade and age <= age_limits["core"] and score >= limits["core_score"] and has_resolved_a:
            role = "core"
        elif age <= age_limits["adjacent"] and score >= min_observation and has_resolved_a:
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
    # Per-topic conversion pass: core-eligible rows first, then upgrade only
    # available short-form rows until the topic reaches topic_target. This is a
    # ceiling on promotion, not a cardinality requirement: if fewer short rows
    # exist, select fewer; never refill with a previously detailed publication.
    topic_floor_candidates: dict[str, list[dict[str, Any]]] = {}
    for row in eligible:
        if row["item_role"] != "core":
            topic_floor_candidates.setdefault(row["topic_id"], []).append(row)
    for row in eligible:
        if row["item_role"] == "core":
            if len(selected) >= limits["total_max"] or topic_counts.get(row["topic_id"], 0) >= limits["max_per_topic"]:
                excluded.append({"id": row["id"], "score": row["score"], "reason": "expanded-v2 capacity"})
                continue
            if core_count >= limits["core_max"]:
                excluded.append({"id": row["id"], "score": row["score"], "reason": "core capacity"})
                continue
            core_count += 1
            topic_counts[row["topic_id"]] = topic_counts.get(row["topic_id"], 0) + 1
            selected.append(row)
    for topic_id in sorted(set(topic_floor_candidates) | set(brief_upgrade_pool)):
        shortfall = limits["topic_target"] - topic_counts.get(topic_id, 0)
        fill = list(topic_floor_candidates.get(topic_id, [])) + sorted(
            brief_upgrade_pool.get(topic_id, []),
            key=lambda row: (
                1 if row.get("historical_brief_candidate") else 0,
                -float(row["score"]),
                row["id"],
            ),
        )
        for row in fill[:max(0, shortfall)]:
            if len(selected) >= limits["total_max"] or observation_count >= limits["observation_max"]:
                break
            if topic_counts.get(topic_id, 0) >= limits["max_per_topic"]:
                break
            observation_count += 1
            topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1
            if row.get("brief_upgrade"):
                # Historical brief-only Machine Item filling this topic's floor.
                row["brief_upgrade_origin"] = "historical"
            elif not row.get("last_pushed_at"):
                # Current-issue brief materialized into a detailed card.
                row["brief_upgrade"] = True
                row["brief_upgrade_origin"] = "current"
            selected.append(row)
        for row in fill[max(0, shortfall):]:
            reason = "brief upgrade capacity" if row.get("brief_upgrade") else "expanded-v2 capacity"
            excluded.append({"id": row["id"], "score": row["score"], "reason": reason})
    for topic_id, rows in topic_floor_candidates.items():
        if topic_id in brief_upgrade_pool:
            continue
        for row in rows:
            if row not in selected:
                excluded.append({"id": row["id"], "score": row["score"], "reason": "expanded-v2 capacity"})
    selected.sort(
        key=lambda row: (
            0 if row["item_role"] == "core" else 1,
            -float(row["score"]),
            int(row["age_days"]),
            row["id"],
        )
    )
    counts = {"core": core_count, "observations": observation_count, "total": len(selected), "topics": topic_counts}
    return selected, excluded, counts, limits


def collect_historical_brief_rows(
    root: Path,
    config: ConfigBundle,
    db: Database,
    run_id: str,
    current_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return prior brief-only Machine Items that can fill current topic gaps.

    Historical refill is deliberately separate from current-run materialisation.
    A prior brief does not need to have been rediscovered in this run, but it must
    still have a fact-checked Machine Item, a stable event identity, and recipient-
    visible brief provenance. Any identity ever published in a detailed card is
    excluded, even when it also appeared in a brief section at another time.
    """

    from .fact_cache_provenance import SYNTHETIC_MODES, execution_mode

    if execution_mode(db, run_id) in SYNTHETIC_MODES:
        # Demo/fixture/test runs must remain reproducible and must never import
        # recipient-visible history from the production workspace.
        return []

    current_keys = {
        str(row.get("event_key") or "")
        for row in current_rows
        if str(row.get("event_key") or "")
    }
    deep_topics = {
        str(topic_id)
        for topic_id in (config.settings.get("efficiency") or {}).get("deep_topics") or []
    }
    deep_topics.update(
        str(row.get("topic_id") or "")
        for row in current_rows
        if str(row.get("topic_id") or "")
    )
    from .fact_cache_provenance import (
        ensure_fact_cache_provenance_schema,
        production_source_run_condition,
    )

    ensure_fact_cache_provenance_schema(db)
    rows = db.fetchall(
        f"""
        SELECT bi.id, bi.run_id AS source_run_id, bi.score, bi.json_path,
               bi.fact_check_status, e.topic_id, e.direction_id, e.event_key,
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
               NULL AS visual_plan_path
        FROM brief_items bi
        JOIN events e ON e.id=bi.event_id
        WHERE bi.run_id<>? AND bi.fact_check_status='PASS'
          AND e.event_key IS NOT NULL AND e.event_key!=''
          AND {production_source_run_condition('bi')}
        ORDER BY bi.score DESC, bi.created_at DESC, bi.id
        """,
        (run_id,),
    )
    from .publication_history import annotate_rows_with_publication_roles

    rows = annotate_rows_with_publication_roles(root, db, rows)
    selected: list[dict[str, Any]] = []
    seen = set(current_keys)
    for row in rows:
        event_key = str(row.get("event_key") or "")
        if not event_key or event_key in seen:
            continue
        if deep_topics and str(row.get("topic_id") or "") not in deep_topics:
            continue
        if not row.get("previously_brief") or row.get("previously_detailed"):
            continue
        item_path = root / str(row.get("json_path") or "")
        if not item_path.is_file():
            continue
        item = read_json(item_path, {})
        hosts = {
            (urlparse(str(source.get("url") or "")).hostname or "").lower().removeprefix("www.")
            for source in item.get("sources") or []
        }
        if hosts & {"example.com", "example.org", "example.net"}:
            continue
        normalised = normalise_legacy_item(item, config)
        min_chars = historical_brief_upgrade_min_chars(config)
        max_chars = int(config.settings.get("brief_item_max_chars", 260))
        if brief_item_validation_errors(normalised, min_chars=min_chars, max_chars=max_chars):
            # Historical brief-only cards retain their legacy length floor, but
            # still need all five complete fields, fact checking and A-level
            # provenance. Never invent filler solely to meet a newer word budget.
            continue
        selected.append({**row, "historical_brief_candidate": True})
        seen.add(event_key)
    return selected


def plan_expanded_issue(root: Path, config: ConfigBundle, db: Database, run_id: str) -> dict[str, Any]:
    issue = db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
    run = db.fetchone("SELECT * FROM runs WHERE id=?", (run_id,))
    if not issue or not run:
        raise RuntimeError("Run does not have a rebuildable issue")
    if issue.get("status") == "SENT" or run.get("status") == "COMPLETED":
        raise RuntimeError("Refusing to rebuild a sent or completed run")

    rows = db.fetchall(
        """
        SELECT bi.id, bi.run_id AS source_run_id, bi.score, bi.json_path, bi.fact_check_status,
               bi.event_id, e.topic_id, e.direction_id, e.event_key,
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
    from .issue_stage import _mark_floor_upgrades
    from .publication_history import annotate_rows_with_publication_roles

    rows = annotate_rows_with_publication_roles(root, db, rows)
    rows.extend(collect_historical_brief_rows(root, config, db, run_id, rows))
    _mark_floor_upgrades(db, run_id, rows)
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
        if row.get("brief_upgrade"):
            item["brief_upgrade"] = True
            item["brief_upgrade_origin"] = (
                "historical" if row.get("historical_brief_candidate") else "current"
            )
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
    issue_path = root / issue["issue_json_path"] if issue.get("issue_json_path") else None
    issue_dir = issue_path.parent if issue_path else root / "workspace" / "runs" / run_id / "issue"
    issue_dir.mkdir(parents=True, exist_ok=True)
    history = issue_dir / "history"
    history.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = None
    if issue_path and issue_path.is_file():
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
        replace_existing=True,
    )
    return {
        "dry_run": False,
        "counts": counts,
        "backup": str(backup) if backup else None,
        "status": "AWAITING_ISSUE_SYNTHESIS",
        "stage": "AWAITING_ISSUE_SYNTHESIS",
        "next_task": tasks.instructions(task),
    }
