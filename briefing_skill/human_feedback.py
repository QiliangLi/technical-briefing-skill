from __future__ import annotations

from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Mapping

from .utils import now_iso, read_json, write_json


EDITABLE_FIELDS = (
    "title",
    "core_conclusion",
    "mechanism",
    "result",
    "boundary",
    "project_relevance",
)
FIELD_LABELS = {
    "title": "标题",
    "core_conclusion": "核心结论",
    "mechanism": "机制",
    "result": "结果/证据",
    "boundary": "边界",
    "project_relevance": "项目启发",
}
FIELD_LIMITS = {
    "title": 300,
    "core_conclusion": 2400,
    "mechanism": 2400,
    "result": 2400,
    "boundary": 2400,
    "project_relevance": 2400,
}
SYNTHETIC_RUN_PREFIXES = ("demo-", "ci-", "test-", "pytest-")


def ensure_human_feedback_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS human_review_items (
            issue_id TEXT NOT NULL,
            brief_item_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            topic_id TEXT NOT NULL,
            direction_id TEXT,
            decision TEXT NOT NULL,
            changed_field_count INTEGER NOT NULL DEFAULT 0,
            reviewed_item_path TEXT,
            reviewed_at TEXT NOT NULL,
            PRIMARY KEY(issue_id, brief_item_id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS human_review_edits (
            issue_id TEXT NOT NULL,
            brief_item_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            original_text TEXT NOT NULL,
            reviewed_text TEXT NOT NULL,
            similarity REAL NOT NULL,
            char_delta INTEGER NOT NULL,
            reviewed_at TEXT NOT NULL,
            PRIMARY KEY(issue_id, brief_item_id, field_name)
        )
        """
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_human_review_run ON human_review_items(run_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_human_edit_run ON human_review_edits(run_id)")


def _text(value: Any) -> str:
    return str(value or "").replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _field_value(item: Mapping[str, Any], field: str) -> str:
    if field == "result":
        return _text(item.get("result") or item.get("evidence_summary"))
    return _text(item.get(field))


def _validate_field(field: str, value: Any) -> str:
    if field not in EDITABLE_FIELDS:
        raise ValueError(f"Unsupported editable field: {field}")
    if not isinstance(value, str):
        raise ValueError(f"Review field {field} must be a string")
    cleaned = _text(value)
    if not cleaned:
        raise ValueError(f"Review field {field} cannot be empty")
    limit = FIELD_LIMITS[field]
    if len(cleaned) > limit:
        raise ValueError(f"Review field {field} exceeds {limit} characters")
    return cleaned


def _issue_and_rows(db, run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    issue = db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
    if not issue or not issue.get("issue_json_path"):
        raise RuntimeError("Issue not ready")
    rows = db.fetchall(
        """
        SELECT ii.position, ii.visual_plan_path, ii.item_role, bi.id, bi.json_path,
               bi.approved, e.topic_id, e.direction_id
        FROM issue_items ii
        JOIN brief_items bi ON bi.id=ii.brief_item_id
        JOIN events e ON e.id=bi.event_id
        WHERE ii.issue_id=? AND bi.fact_check_status='PASS'
        ORDER BY ii.position
        """,
        (issue["id"],),
    )
    return issue, rows


def _sidecar_path(root: Path, run_id: str, item_id: str) -> Path:
    return root / "workspace" / "runs" / run_id / "reviewed_items" / f"{item_id}.json"


def prepare_reviewed_items(
    root: Path,
    db,
    run_id: str,
    edits: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Validate human edits and persist reviewed sidecars without mutating Agent JSON.

    Sidecars are intentionally written before approval validation so a failed email
    validation does not make the reviewer retype work. Feedback tables are updated
    only after the approved deliverable validates successfully.
    """

    issue, rows = _issue_and_rows(db, run_id)
    del issue
    edits = edits or {}
    valid_ids = {str(row["id"]) for row in rows}
    unknown_ids = sorted(set(str(value) for value in edits) - valid_ids)
    if unknown_ids:
        raise ValueError(f"Review edits reference unknown item IDs: {', '.join(unknown_ids)}")

    prepared: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_id = str(row["id"])
        original = read_json(root / row["json_path"], {})
        sidecar = _sidecar_path(root, run_id, item_id)
        existing = read_json(sidecar, {}) if sidecar.exists() else {}
        submitted = edits.get(item_id) or {}
        if not isinstance(submitted, Mapping):
            raise ValueError(f"Review edits for {item_id} must be an object")
        unknown_fields = sorted(set(str(value) for value in submitted) - set(EDITABLE_FIELDS))
        if unknown_fields:
            raise ValueError(
                f"Review edits for {item_id} contain unsupported fields: {', '.join(unknown_fields)}"
            )

        reviewed = dict(original)
        reviewed_values: dict[str, str] = {}
        diffs: dict[str, dict[str, Any]] = {}
        for field in EDITABLE_FIELDS:
            original_text = _field_value(original, field)
            current_text = _field_value(existing, field) if existing else original_text
            if field in submitted:
                current_text = _validate_field(field, submitted[field])
            elif not current_text:
                current_text = original_text
            if current_text:
                reviewed[field] = current_text
            reviewed_values[field] = current_text
            if current_text != original_text:
                similarity = round(SequenceMatcher(None, original_text, current_text).ratio(), 4)
                diffs[field] = {
                    "original_text": original_text,
                    "reviewed_text": current_text,
                    "similarity": similarity,
                    "char_delta": len(current_text) - len(original_text),
                }

        sidecar_rel: str | None = None
        if diffs:
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            write_json(sidecar, reviewed)
            sidecar_rel = str(sidecar.relative_to(root))
        elif sidecar.exists():
            sidecar.unlink()

        prepared[item_id] = {
            "item": reviewed,
            "original": original,
            "reviewed_values": reviewed_values,
            "diffs": diffs,
            "reviewed_item_path": sidecar_rel,
            "topic_id": str(row.get("topic_id") or ""),
            "direction_id": str(row.get("direction_id") or ""),
        }
    return prepared


def record_human_review(
    db,
    run_id: str,
    approved_ids: set[str],
    prepared: Mapping[str, Mapping[str, Any]],
) -> None:
    """Persist the latest validated human decision and final field-level differences."""

    ensure_human_feedback_schema(db)
    issue, rows = _issue_and_rows(db, run_id)
    now = now_iso()
    with db.transaction() as conn:
        for row in rows:
            item_id = str(row["id"])
            entry = prepared[item_id]
            decision = "approved" if item_id in approved_ids else "rejected"
            diffs = entry.get("diffs") or {}
            conn.execute(
                """
                INSERT INTO human_review_items(
                    issue_id, brief_item_id, run_id, topic_id, direction_id,
                    decision, changed_field_count, reviewed_item_path, reviewed_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(issue_id, brief_item_id) DO UPDATE SET
                    run_id=excluded.run_id,
                    topic_id=excluded.topic_id,
                    direction_id=excluded.direction_id,
                    decision=excluded.decision,
                    changed_field_count=excluded.changed_field_count,
                    reviewed_item_path=excluded.reviewed_item_path,
                    reviewed_at=excluded.reviewed_at
                """,
                (
                    issue["id"],
                    item_id,
                    run_id,
                    str(entry.get("topic_id") or row.get("topic_id") or ""),
                    str(entry.get("direction_id") or row.get("direction_id") or ""),
                    decision,
                    len(diffs),
                    entry.get("reviewed_item_path"),
                    now,
                ),
            )
            conn.execute(
                "DELETE FROM human_review_edits WHERE issue_id=? AND brief_item_id=?",
                (issue["id"], item_id),
            )
            for field, diff in diffs.items():
                conn.execute(
                    """
                    INSERT INTO human_review_edits(
                        issue_id, brief_item_id, run_id, field_name, original_text,
                        reviewed_text, similarity, char_delta, reviewed_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        issue["id"],
                        item_id,
                        run_id,
                        field,
                        diff["original_text"],
                        diff["reviewed_text"],
                        float(diff["similarity"]),
                        int(diff["char_delta"]),
                        now,
                    ),
                )


def build_review_payload(root: Path, db, run_id: str) -> dict[str, Any]:
    """Rebuild the review page from immutable candidates plus latest sidecars.

    This deliberately does not trust the filtered approved issue JSON for its item
    list, so a reviewer can reopen the page and re-approve a previously rejected item.
    """

    ensure_human_feedback_schema(db)
    issue, rows = _issue_and_rows(db, run_id)
    current_issue = read_json(root / issue["issue_json_path"], {})
    decisions = {
        str(row["brief_item_id"]): row
        for row in db.fetchall(
            "SELECT * FROM human_review_items WHERE issue_id=?",
            (issue["id"],),
        )
    }
    items: list[dict[str, Any]] = []
    for row in rows:
        item_id = str(row["id"])
        original = read_json(root / row["json_path"], {})
        sidecar = _sidecar_path(root, run_id, item_id)
        reviewed = read_json(sidecar, {}) if sidecar.exists() else dict(original)
        for field in EDITABLE_FIELDS:
            value = _field_value(reviewed, field) or _field_value(original, field)
            reviewed[field] = value
        decision = decisions.get(item_id)
        reviewed.update(
            {
                "brief_item_id": item_id,
                "topic_id": row.get("topic_id"),
                "direction_id": row.get("direction_id"),
                "item_role": row.get("item_role") or "core",
                "review_checked": decision is None or decision.get("decision") == "approved",
                "human_changed_fields": [
                    field
                    for field in EDITABLE_FIELDS
                    if _field_value(reviewed, field) != _field_value(original, field)
                ],
                "_review_original": {
                    field: _field_value(original, field) for field in EDITABLE_FIELDS
                },
            }
        )
        items.append(reviewed)

    return {
        **current_issue,
        "id": issue["id"],
        "run_id": run_id,
        "items": items,
        "reviewed_count": len(decisions),
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _summarize_feedback(rows: list[dict[str, Any]], edits: list[dict[str, Any]]) -> dict[str, Any]:
    reviewed = len(rows)
    approved_rows = [row for row in rows if row.get("decision") == "approved"]
    rejected = reviewed - len(approved_rows)
    approved_ids = {(str(row["issue_id"]), str(row["brief_item_id"])) for row in approved_rows}
    approved_edits = [
        edit
        for edit in edits
        if (str(edit["issue_id"]), str(edit["brief_item_id"])) in approved_ids
    ]
    edited_item_ids = {
        (str(edit["issue_id"]), str(edit["brief_item_id"])) for edit in approved_edits
    }
    total_fields = len(approved_rows) * len(EDITABLE_FIELDS)
    retention_numerator = total_fields - len(approved_edits) + sum(
        float(edit.get("similarity") or 0.0) for edit in approved_edits
    )

    per_field: dict[str, dict[str, Any]] = {}
    for field in EDITABLE_FIELDS:
        field_edits = [edit for edit in approved_edits if edit.get("field_name") == field]
        net_delta = sum(int(edit.get("char_delta") or 0) for edit in field_edits)
        per_field[field] = {
            "label": FIELD_LABELS[field],
            "changed": len(field_edits),
            "edit_rate": _ratio(len(field_edits), len(approved_rows)),
            "mean_similarity_when_changed": (
                round(sum(float(edit.get("similarity") or 0.0) for edit in field_edits) / len(field_edits), 4)
                if field_edits
                else None
            ),
            "net_char_delta": net_delta,
            "shortened": sum(1 for edit in field_edits if int(edit.get("char_delta") or 0) < 0),
            "lengthened": sum(1 for edit in field_edits if int(edit.get("char_delta") or 0) > 0),
        }

    topic_rows: dict[str, dict[str, int]] = defaultdict(lambda: {"reviewed": 0, "approved": 0, "rejected": 0, "edited_approved": 0})
    for row in rows:
        topic = str(row.get("topic_id") or "unknown")
        topic_rows[topic]["reviewed"] += 1
        topic_rows[topic][str(row.get("decision") or "rejected")] += 1
    edited_by_topic = Counter(
        str(row.get("topic_id") or "unknown")
        for row in approved_rows
        if (str(row["issue_id"]), str(row["brief_item_id"])) in edited_item_ids
    )
    for topic, count in edited_by_topic.items():
        topic_rows[topic]["edited_approved"] = count

    return {
        "reviewed_items": reviewed,
        "approved_items": len(approved_rows),
        "rejected_items": rejected,
        "approval_rate": _ratio(len(approved_rows), reviewed),
        "approved_items_with_edits": len(edited_item_ids),
        "approved_item_edit_rate": _ratio(len(edited_item_ids), len(approved_rows)),
        "approved_fields_total": total_fields,
        "approved_fields_changed": len(approved_edits),
        "approved_field_edit_rate": _ratio(len(approved_edits), total_fields),
        "mean_field_text_retention": (
            round(retention_numerator / total_fields, 4) if total_fields else None
        ),
        "by_field": per_field,
        "by_topic": dict(sorted(topic_rows.items())),
    }


def _production_feedback_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep synthetic Demo/CI/test decisions observable but out of learning history."""

    return [
        row
        for row in rows
        if not str(row.get("run_id") or "").lower().startswith(SYNTHETIC_RUN_PREFIXES)
    ]


def human_feedback_stats(db, run_id: str) -> dict[str, Any]:
    ensure_human_feedback_schema(db)
    current_rows = db.fetchall(
        "SELECT * FROM human_review_items WHERE run_id=? ORDER BY reviewed_at, brief_item_id",
        (run_id,),
    )
    current_edits = db.fetchall(
        "SELECT * FROM human_review_edits WHERE run_id=? ORDER BY reviewed_at, brief_item_id, field_name",
        (run_id,),
    )
    all_rows = db.fetchall("SELECT * FROM human_review_items ORDER BY reviewed_at, brief_item_id")
    all_edits = db.fetchall("SELECT * FROM human_review_edits ORDER BY reviewed_at, brief_item_id, field_name")
    history_rows = _production_feedback_rows(all_rows)
    history_keys = {
        (str(row["issue_id"]), str(row["brief_item_id"])) for row in history_rows
    }
    history_edits = [
        edit
        for edit in all_edits
        if (str(edit["issue_id"]), str(edit["brief_item_id"])) in history_keys
    ]
    synthetic_rows = len(all_rows) - len(history_rows)
    return {
        "current_run": _summarize_feedback(current_rows, current_edits),
        "history": _summarize_feedback(history_rows, history_edits),
        "synthetic_reviews_excluded_from_history": synthetic_rows,
        "synthetic_run_prefixes": list(SYNTHETIC_RUN_PREFIXES),
        "note": (
            "Human edit telemetry records only validated review decisions and final field-level diffs. "
            "Long-term history excludes synthetic Demo/CI/test runs and is not automatically injected into generation prompts."
        ),
    }


def install_human_feedback_telemetry() -> None:
    """Append human-review signals to the existing stats command without new Agent work."""

    from . import telemetry

    if getattr(telemetry, "_human_feedback_installed", False):
        return
    original_run_stats = telemetry.run_stats

    def run_stats(db, root: Path, run_id: str):
        payload = original_run_stats(db, root, run_id)
        payload["human_edit_feedback"] = human_feedback_stats(db, run_id)
        return payload

    telemetry.run_stats = run_stats
    telemetry._human_feedback_installed = True
