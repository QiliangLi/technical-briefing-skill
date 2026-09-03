"""Publication freshness manifest and the Issue Change Projection.

Both files under ``knowledge/`` are derived, regenerable publication
projections. Neither is an authoritative knowledge source:

- ``knowledge/manifest.json`` states how far materialized knowledge has caught
  up with the published archive, so Pages and the homepage can say "analysis
  pending" instead of repackaging stale Roadmap summaries as current change.
- ``knowledge/issue-diffs/<issue_date>.json`` binds per-topic homepage text
  (current judgement, what changed) to explicit applied tasks and published
  evidence for one issue. The frontend renders this projection as-is and never
  synthesizes judgement text in the browser.

Seed template sentences (the per-topic "N 条专题证据…" baseline copy) must
never surface as a homepage judgement; the semantic validator below rejects
them in judgement-bearing fields.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .knowledge_materialization import (
    FRONTIER_TOPIC_ID,
    PublishedArchive,
    _roadmap_semantic_state,
    _validate_schema,
)
from .utils import read_json, write_json_atomic

SCHEMA_VERSION = 1
MANIFEST_RELPATH = "knowledge/manifest.json"
ISSUE_DIFF_DIR = "knowledge/issue-diffs"

PUBLICATION_STATES = ("archive_only", "analysis_pending", "knowledge_complete", "analysis_failed")

# Seed/baseline boilerplate that must never be presented as an issue judgement.
_TEMPLATE_MARKERS = (
    "现有公开归档为",
    "条专题证据",
    "首版先保留",
    "尚未声称存在明确阶段或转折",
    "首版证据时间线",
    "积累了",
)


def is_template_summary(value: str) -> bool:
    text = str(value or "")
    return any(marker in text for marker in _TEMPLATE_MARKERS)


# ---------------------------------------------------------------------------
# shared watermark helpers
# ---------------------------------------------------------------------------


def _archive_dates(root: Path) -> list[str]:
    return PublishedArchive(root).issue_dates()


def _store_issue_watermark(root: Path) -> str | None:
    """Latest issue that materialized knowledge actually reflects."""

    knowledge_root = root / "knowledge"
    dates: list[str] = []
    for path in (knowledge_root / "roadmaps").glob("*.json"):
        value = read_json(path, {})
        if value.get("updated_by_issue"):
            dates.append(str(value["updated_by_issue"]))
    for path in (knowledge_root / "ideas").glob("idea_*.json"):
        value = read_json(path, {})
        if value.get("last_updated_issue"):
            dates.append(str(value["last_updated_issue"]))
    return max(dates) if dates else None


def _prepared_issue_dates(root: Path) -> set[str]:
    task_root = root / "workspace" / "knowledge" / "tasks"
    if not task_root.is_dir():
        return set()
    return {path.parent.name for path in task_root.glob("*/*.input.json")}


def _application_records(root: Path) -> list[dict[str, Any]]:
    applications: list[dict[str, Any]] = []
    for path in sorted((root / "knowledge" / "applications").glob("*.json")):
        value = read_json(path, {})
        if isinstance(value, dict) and value.get("task_id"):
            applications.append(value)
    return applications


def _candidate_analysis(root: Path, dates: list[str]) -> dict[str, Any]:
    """Derive Candidate freshness independently from Roadmap/Idea freshness."""

    counts = {key: 0 for key in ("proposed", "accepted", "duplicate", "deferred", "dismissed")}
    for path in (root / "knowledge" / "idea-candidates").glob("candidate_*.json"):
        disposition = str(read_json(path, {}).get("disposition") or "")
        if disposition in counts:
            counts[disposition] += 1

    report = read_json(root / "knowledge" / "candidate-backfill.json", {})
    watermark = str(report.get("through_issue") or "") or None
    if watermark not in dates:
        watermark = None
    remaining = [date for date in dates if watermark is None or date > watermark]

    application_ids = {
        str(read_json(path, {}).get("task_id") or "")
        for path in (root / "knowledge" / "candidate-applications").glob("*.json")
    }
    for issue_date in list(remaining):
        current = [
            row
            for row in PublishedArchive.evidence(PublishedArchive(root).load_issue(issue_date))
            if row.get("topic_id") != FRONTIER_TOPIC_ID
        ]
        task_paths = sorted((root / "workspace" / "knowledge" / "candidate-tasks" / issue_date).glob("*.input.json"))
        if not task_paths and current:
            break
        bindings = [read_json(path, {}).get("_task") or {} for path in task_paths]
        expected_direct = {str(row["item_id"]) for row in current}
        expected_synthesis = {str(row["topic_id"]) for row in current if row.get("topic_id")}
        actual_direct = {
            str(row.get("entity_id") or "") for row in bindings if row.get("type") == "idea_candidate_direct"
        }
        actual_synthesis = {
            str(row.get("entity_id") or "") for row in bindings if row.get("type") == "idea_candidate_synthesis"
        }
        task_ids = {str(row.get("id") or "") for row in bindings}
        complete = (
            actual_direct == expected_direct
            and actual_synthesis == expected_synthesis
            and (not expected_direct or bool(task_ids))
            and task_ids.issubset(application_ids)
        )
        if not complete:
            break
        watermark = issue_date

    pending = [date for date in dates if watermark is None or date > watermark]
    first_prepared = bool(
        pending
        and list((root / "workspace" / "knowledge" / "candidate-tasks" / pending[0]).glob("*.input.json"))
    )
    state = "complete" if not pending else "analysis_pending" if first_prepared else "archive_only"
    return {"state": state, "watermark": watermark, "pending": pending, "counts": counts}


def _graph_snapshot(root: Path) -> str | None:
    """``knowledge-<digest16>`` snapshot id derived from the built graph."""

    graph = read_json(root / "knowledge" / "graph.json", None)
    digest = str((graph or {}).get("input_digest") or "")
    if not digest.startswith("sha256:"):
        return None
    return f"knowledge-{digest[len('sha256:'):][:16]}"


def _recomputed_graph_digest(root: Path) -> tuple[str, str | None]:
    """Rebuild the graph in memory so manifest validation cannot be fooled by
    a stale stored digest. Returns (full_digest, error)."""

    try:
        from .knowledge_graph import build_knowledge_graph

        digest = str(build_knowledge_graph(root).get("input_digest") or "")
    except Exception as exc:  # noqa: BLE001 - report any rebuild failure as a gate error
        return "", f"knowledge graph could not be rebuilt during manifest validation: {exc}"
    if not digest.startswith("sha256:"):
        return "", "rebuilt graph lacks an input_digest"
    return digest, None


def _snapshot_id_for_digest(digest: str) -> str:
    return f"knowledge-{digest[len('sha256:'):][:16]}"


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------


def build_manifest(
    root: Path,
    *,
    state: str | None = None,
    candidate_state: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    dates = _archive_dates(root)
    archive_head = dates[-1] if dates else ""
    materialized = _store_issue_watermark(root)
    pending = [date for date in dates if materialized is None or date > materialized]
    prepared = _prepared_issue_dates(root)
    prepared_pending = sorted(set(pending) & prepared)
    applications = _application_records(root)
    candidate = _candidate_analysis(root, dates)
    if candidate_state is not None:
        if candidate_state != "analysis_failed":
            raise ValueError("candidate_state override only supports analysis_failed")
        if not candidate["pending"]:
            raise ValueError("candidate analysis_failed requires pending Candidate issues")
        candidate["state"] = candidate_state

    if state is None:
        if not pending:
            computed = "knowledge_complete"
        elif prepared_pending:
            computed = "analysis_pending"
        else:
            computed = "archive_only"
    else:
        if state not in PUBLICATION_STATES:
            raise ValueError(f"unsupported publication_state: {state}")
        if state != "knowledge_complete" and not pending:
            raise ValueError(f"{state} requires pending issues")
        computed = state

    target = pending[0] if pending else None
    affected = 0
    completed = 0
    if target:
        task_ids = {
            path.stem.replace(".input", "")
            for path in (root / "workspace" / "knowledge" / "tasks" / target).glob("*.input.json")
        }
        affected = len(task_ids)
        completed = len(
            {str(row.get("task_id")) for row in applications if str(row.get("issue_date")) == target}
            & task_ids
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "archive_head_issue": archive_head,
        "analysis_target_issue": target,
        "materialized_through_issue": materialized,
        "publication_state": computed,
        "pending_issues": pending,
        "affected_topics": affected,
        "completed_topics": completed,
        "candidate_analysis_state": candidate["state"],
        "candidate_through_issue": candidate["watermark"],
        "candidate_pending_issues": candidate["pending"],
        "candidate_counts": candidate["counts"],
        "snapshot_id": _graph_snapshot(root),
        "publication_note": str(note or ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_manifest(
    root: Path,
    *,
    state: str | None = None,
    candidate_state: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    manifest = build_manifest(root, state=state, candidate_state=candidate_state, note=note)
    errors = _validate_schema(root, "knowledge-manifest.schema.json", manifest)
    if errors:
        raise ValueError("invalid knowledge manifest: " + "; ".join(errors[:8]))
    write_json_atomic(root / MANIFEST_RELPATH, manifest)
    return manifest


def manifest_semantic_errors(root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    dates = _archive_dates(root)
    head = dates[-1] if dates else ""
    if manifest.get("archive_head_issue") != head:
        errors.append(f"archive_head_issue must be {head or '<empty>'}")
    watermark = _store_issue_watermark(root)
    if manifest.get("materialized_through_issue") != watermark:
        errors.append(f"materialized_through_issue must be {watermark or '<none>'}")
    expected_pending = [date for date in dates if watermark is None or date > watermark]
    if manifest.get("pending_issues") != expected_pending:
        errors.append(f"pending_issues must be {expected_pending}")
    target = expected_pending[0] if expected_pending else None
    if manifest.get("analysis_target_issue") != target:
        errors.append(f"analysis_target_issue must be {target or '<none>'}")
    candidate = _candidate_analysis(root, dates)
    manifest_candidate_state = manifest.get("candidate_analysis_state")
    if manifest_candidate_state == "analysis_failed":
        if not candidate["pending"]:
            errors.append("candidate analysis_failed requires pending Candidate issues")
    elif manifest_candidate_state != candidate["state"]:
        errors.append(f"candidate_analysis_state must be {candidate['state']}")
    if manifest.get("candidate_through_issue") != candidate["watermark"]:
        errors.append(f"candidate_through_issue must be {candidate['watermark'] or '<none>'}")
    if manifest.get("candidate_pending_issues") != candidate["pending"]:
        errors.append(f"candidate_pending_issues must be {candidate['pending']}")
    if manifest.get("candidate_counts") != candidate["counts"]:
        errors.append("candidate_counts do not match persisted Candidate dispositions")

    state = manifest.get("publication_state")
    if state not in PUBLICATION_STATES:
        errors.append(f"unknown publication_state {state}")
        return errors
    if state == "knowledge_complete":
        if expected_pending:
            errors.append("knowledge_complete is not allowed while pending issues remain")
        if watermark != head:
            errors.append("knowledge_complete requires materialized_through_issue == archive_head_issue")
    elif not expected_pending:
        errors.append(f"{state} requires pending issues")

    prepared = _prepared_issue_dates(root)
    prepared_pending = sorted(set(expected_pending) & prepared)
    if state == "analysis_pending" and not prepared_pending:
        errors.append("analysis_pending requires prepared tasks for a pending issue")
    if state == "archive_only" and prepared_pending:
        errors.append("archive_only must not be used once tasks are prepared; use analysis_pending")

    applications = _application_records(root)
    if target:
        task_ids = {
            path.stem.replace(".input", "")
            for path in (root / "workspace" / "knowledge" / "tasks" / target).glob("*.input.json")
        }
        completed = len(
            {str(row.get("task_id")) for row in applications if str(row.get("issue_date")) == target}
            & task_ids
        )
        if manifest.get("affected_topics") != len(task_ids) or manifest.get("completed_topics") != completed:
            errors.append("affected_topics/completed_topics do not match prepared tasks and applications")

    rebuilt_digest, rebuild_error = _recomputed_graph_digest(root)
    snapshot: str | None = None
    if rebuild_error:
        errors.append(rebuild_error)
    else:
        stored_graph = read_json(root / "knowledge" / "graph.json", None)
        stored_digest = str((stored_graph or {}).get("input_digest") or "")
        if stored_digest != rebuilt_digest:
            errors.append("knowledge/graph.json is stale relative to the current knowledge store")
        snapshot = _snapshot_id_for_digest(rebuilt_digest)
        if manifest.get("snapshot_id") != snapshot:
            errors.append(f"snapshot_id must match the current graph build ({snapshot})")
    if snapshot is None:
        return errors

    if state == "knowledge_complete" and head:
        head_diff = read_json(root / ISSUE_DIFF_DIR / f"{head}.json", None)
        if not isinstance(head_diff, dict):
            errors.append(f"knowledge_complete requires {ISSUE_DIFF_DIR}/{head}.json")
        else:
            errors.extend(f"{head}.json: {error}" for error in issue_diff_semantic_errors(root, head_diff))
            if head_diff.get("status") != "complete":
                errors.append(f"{head}.json status must be complete before knowledge_complete")
            if head_diff.get("knowledge_snapshot_id") != snapshot:
                errors.append(f"{head}.json knowledge_snapshot_id must be {snapshot}")
    return errors


def validate_manifest(root: Path) -> list[str]:
    path = root / MANIFEST_RELPATH
    if not path.is_file():
        return [f"{MANIFEST_RELPATH} is missing"]
    manifest = read_json(path, {})
    errors = _validate_schema(root, "knowledge-manifest.schema.json", manifest)
    if errors:
        return errors
    return manifest_semantic_errors(root, manifest)


# ---------------------------------------------------------------------------
# Issue Change Projection
# ---------------------------------------------------------------------------


def _semantic_state_diff_text(previous: dict[str, Any] | None, current: dict[str, Any]) -> tuple[str, list[str]]:
    """Deterministic Chinese summary of branch/stage-level judgement changes."""

    if previous is None:
        return "首版建立：初始分支与证据时间线。", []
    before = _roadmap_semantic_state(previous)
    after = _roadmap_semantic_state(current)
    old_branches = {row["branch_id"]: row for row in before["branches"]}
    new_branches = {row["branch_id"]: row for row in after["branches"]}
    phrases: list[str] = []
    affected: list[str] = []
    for branch_id, row in new_branches.items():
        name = str(row.get("name") or branch_id)
        old = old_branches.get(branch_id)
        if old is None:
            phrases.append(f"新增路线「{name}」")
            affected.append(name)
            continue
        branch_changed = False
        if old.get("status") != row.get("status"):
            phrases.append(f"路线「{name}」状态由 {old.get('status')} 变为 {row.get('status')}")
            branch_changed = True
        old_stages = {stage.get("stage_id"): stage for stage in old.get("stages") or []}
        new_stages = {stage.get("stage_id"): stage for stage in row.get("stages") or []}
        for stage_id, stage in new_stages.items():
            old_stage = old_stages.get(stage_id)
            if old_stage is None:
                phrases.append(f"路线「{name}」新增阶段「{stage.get('name') or stage_id}」")
                branch_changed = True
            elif old_stage.get("status") != stage.get("status"):
                phrases.append(
                    f"路线「{name}」阶段「{stage.get('name') or stage_id}」状态由 "
                    f"{old_stage.get('status')} 变为 {stage.get('status')}"
                )
                branch_changed = True
        for stage_id in sorted(set(old_stages) - set(new_stages)):
            phrases.append(f"路线「{name}」移除阶段 {stage_id}")
            branch_changed = True
        old_questions = list(old.get("open_questions") or [])
        new_questions = list(row.get("open_questions") or [])
        added = [q for q in new_questions if q not in old_questions]
        removed = [q for q in old_questions if q not in new_questions]
        if added:
            phrases.append(f"路线「{name}」新增 {len(added)} 个开放问题")
            branch_changed = True
        if removed:
            phrases.append(f"路线「{name}」关闭 {len(removed)} 个开放问题")
            branch_changed = True
        if branch_changed:
            affected.append(name)
    for branch_id in sorted(set(old_branches) - set(new_branches)):
        phrases.append(f"移除路线「{old_branches[branch_id].get('name') or branch_id}」")
        affected.append(str(old_branches[branch_id].get("name") or branch_id))
    if before.get("view_mode") != after.get("view_mode"):
        phrases.append(f"视图模式由 {before.get('view_mode')} 变为 {after.get('view_mode')}")
    return ("；".join(phrases) if phrases else "分支、阶段与开放问题均未变化。"), sorted(set(affected))


def _evidence_state(roadmap: dict[str, Any]) -> str:
    statuses = {str(branch.get("status") or "") for branch in roadmap.get("branches") or []}
    if "contested" in statuses:
        return "contested"
    if roadmap.get("view_mode") == "evidence_timeline":
        return "evidence_building"
    return "supported_with_limits"


def _history_snapshot_for(root: Path, roadmap: dict[str, Any], *, issue_date: str) -> dict[str, Any] | None:
    for row in roadmap.get("history") or []:
        if str(row.get("issue_date") or "") == issue_date:
            value = read_json(root / str(row.get("path") or ""), None)
            if isinstance(value, dict):
                return value
    return None


def _snapshot_for_version(root: Path, roadmap: dict[str, Any], version: int) -> dict[str, Any] | None:
    for row in roadmap.get("history") or []:
        if int(row.get("version") or 0) == int(version):
            value = read_json(root / str(row.get("path") or ""), None)
            if isinstance(value, dict):
                return value
    return None


def build_issue_diff(root: Path, *, issue_date: str) -> dict[str, Any]:
    archive = PublishedArchive(root)
    if issue_date not in archive.issue_dates():
        raise ValueError(f"issue is not published in archive/index.json: {issue_date}")
    published_ids = {str(item["item_id"]) for item in archive.evidence_through(issue_date)}

    knowledge_root = root / "knowledge"
    applications = {
        str(row.get("topic_id")): row
        for row in _application_records(root)
        if str(row.get("issue_date")) == issue_date and str(row.get("topic_id")) != FRONTIER_TOPIC_ID
    }

    topic_changes: list[dict[str, Any]] = []
    for path in sorted((knowledge_root / "roadmaps").glob("*.json")):
        roadmap = read_json(path, {})
        topic_id = str(roadmap.get("topic_id") or path.stem)
        log_entry = next(
            (
                row
                for row in reversed(roadmap.get("change_log") or [])
                if str(row.get("issue_date") or "") == issue_date
            ),
            None,
        )
        if log_entry is None:
            continue
        application = applications.get(topic_id)
        origin = "applied_task" if application else "seed_baseline"
        version_snapshot = _history_snapshot_for(root, roadmap, issue_date=issue_date)
        operative = version_snapshot or roadmap
        judgement_source = version_snapshot
        if judgement_source is None and roadmap.get("updated_by_issue") == issue_date:
            # No version bump this issue, but the operative summary was still
            # (re)written here; the current file is the judgement in effect.
            judgement_source = roadmap
        if judgement_source is None and log_entry.get("version"):
            judgement_source = _snapshot_for_version(root, roadmap, int(log_entry["version"]))

        change_kind = str(log_entry.get("change_type") or "no_material_change")
        if origin == "seed_baseline":
            change_kind = "baseline_seed"
        if application and application.get("change_type"):
            change_kind = str(application["change_type"])

        diff_text, affected_branches = ("", [])
        if version_snapshot is not None:
            previous_path = next(
                (
                    row
                    for row in reversed(roadmap.get("history") or [])
                    if int(row.get("version") or 0) == int(log_entry.get("version") or 1) - 1
                ),
                None,
            )
            previous = read_json(root / str(previous_path.get("path") or ""), None) if previous_path else None
            diff_text, affected_branches = _semantic_state_diff_text(previous, version_snapshot)
        if not diff_text:
            diff_text = str(log_entry.get("summary") or "本期无已记录的判断变化。")

        record: dict[str, Any] = {
            "topic_id": topic_id,
            "topic_name": str(roadmap.get("topic_name") or topic_id),
            "change_kind": change_kind,
            "origin": origin,
            "task_id": str(application.get("task_id")) if application else None,
            "roadmap_version": int(log_entry.get("version")) if log_entry.get("version") else None,
            "what_changed": diff_text,
            "evidence_state": _evidence_state(operative),
            "affected_branches": affected_branches,
            "evidence_item_ids": sorted(str(value) for value in log_entry.get("evidence_item_ids") or []),
        }
        judgement = str((judgement_source or {}).get("summary") or "")
        if origin == "applied_task" and judgement and not is_template_summary(judgement):
            record["current_judgement"] = judgement
        topic_changes.append(record)

    idea_events: list[dict[str, Any]] = []
    for path in sorted((knowledge_root / "ideas").glob("idea_*.json")):
        idea = read_json(path, {})
        for event in idea.get("decision_log") or []:
            if str(event.get("issue_date") or "") != issue_date:
                continue
            idea_events.append(
                {
                    "idea_id": str(idea.get("idea_id") or path.stem),
                    "title": str(idea.get("title") or ""),
                    "decision": str(event.get("decision") or ""),
                    "from_status": str(event.get("from_status") or "") or None,
                    "to_status": str(event.get("to_status") or "") or None,
                    "reason": str(event.get("reason") or ""),
                    "evidence_item_ids": sorted(str(value) for value in event.get("evidence_item_ids") or []),
                }
            )

    watermark = _store_issue_watermark(root)
    status = "complete" if watermark is not None and watermark >= issue_date else "partial"
    return {
        "schema_version": SCHEMA_VERSION,
        "issue_date": issue_date,
        "knowledge_snapshot_id": _graph_snapshot(root),
        "status": status,
        "topic_changes": sorted(topic_changes, key=lambda row: row["topic_id"]),
        "idea_events": sorted(idea_events, key=lambda row: row["idea_id"]),
    }


def write_issue_diff(root: Path, *, issue_date: str) -> dict[str, Any]:
    diff = build_issue_diff(root, issue_date=issue_date)
    errors = _validate_schema(root, "issue-change-projection.schema.json", diff)
    if errors:
        raise ValueError("invalid issue change projection: " + "; ".join(errors[:8]))
    write_json_atomic(root / ISSUE_DIFF_DIR / f"{issue_date}.json", diff)
    return diff


def issue_diff_semantic_errors(root: Path, diff: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    issue_date = str(diff.get("issue_date") or "")
    try:
        published_ids = {
            str(item["item_id"]) for item in PublishedArchive(root).evidence_through(issue_date)
        }
    except ValueError as exc:
        return [f"issue_date is not published: {exc}"]
    for record in diff.get("topic_changes") or []:
        context = f"topic_changes[{record.get('topic_id')}]"
        for value in record.get("evidence_item_ids") or []:
            if str(value) not in published_ids:
                errors.append(f"{context} cites unpublished evidence {value}")
        for field in ("current_judgement", "what_changed", "why_it_matters"):
            if is_template_summary(str(record.get(field) or "")):
                errors.append(f"{context}.{field} must not reuse seed template copy")
        if record.get("change_kind") == "material_change" and not record.get("current_judgement"):
            errors.append(
                f"{context} material_change requires a non-template current_judgement; "
                "omit the field and keep the topic out of the homepage judgement column instead"
            )
    return errors


def validate_issue_diffs(root: Path, *, issue_date: str | None = None) -> list[str]:
    diff_root = root / ISSUE_DIFF_DIR
    if not diff_root.is_dir():
        return [] if issue_date is None else [f"{ISSUE_DIFF_DIR}/{issue_date}.json is missing"]
    paths = sorted(diff_root.glob("*.json"))
    if issue_date:
        paths = [path for path in paths if path.stem == issue_date]
        if not paths:
            return [f"{ISSUE_DIFF_DIR}/{issue_date}.json is missing"]
    errors: list[str] = []
    for path in paths:
        value = read_json(path, {})
        file_errors = _validate_schema(root, "issue-change-projection.schema.json", value)
        if isinstance(value, dict):
            file_errors.extend(issue_diff_semantic_errors(root, value))
        errors.extend(f"{path.name}: {error}" for error in file_errors)
    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def install_knowledge_publication() -> None:
    from . import cli

    if getattr(cli, "_knowledge_publication_installed", False):
        return
    original_build_parser = cli.build_parser

    def cmd_publication(args: argparse.Namespace) -> int:
        root = Path(args.root).resolve() if getattr(args, "root", None) else cli.discover_root()
        if args.publication == "manifest":
            if args.action == "build":
                manifest = write_manifest(
                    root,
                    state=args.state,
                    candidate_state=args.candidate_state,
                    note=args.note,
                )
                print(json.dumps(manifest, ensure_ascii=False, indent=2))
                return 0
            errors = validate_manifest(root)
            print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
            return 1 if errors else 0
        if args.action == "build":
            diff = write_issue_diff(root, issue_date=args.issue)
            print(json.dumps(diff, ensure_ascii=False, indent=2))
            return 0
        errors = validate_issue_diffs(root, issue_date=args.issue)
        print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    def build_parser():
        parser = original_build_parser()
        sub = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        knowledge = next(
            action
            for action in sub.choices["knowledge"]._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        p = knowledge.add_parser("manifest")
        actions = p.add_subparsers(dest="action", required=True)
        build = actions.add_parser("build")
        build.add_argument("--state", choices=list(PUBLICATION_STATES))
        build.add_argument("--candidate-state", choices=["analysis_failed"])
        build.add_argument("--note", default="")
        build.set_defaults(func=cmd_publication, publication="manifest")
        validate = actions.add_parser("validate")
        validate.set_defaults(func=cmd_publication, publication="manifest")

        p = knowledge.add_parser("diff")
        actions = p.add_subparsers(dest="action", required=True)
        build = actions.add_parser("build")
        build.add_argument("--issue", required=True)
        build.set_defaults(func=cmd_publication, publication="diff")
        validate = actions.add_parser("validate")
        validate.add_argument("--issue")
        validate.set_defaults(func=cmd_publication, publication="diff")
        return parser

    cli.build_parser = build_parser
    cli._knowledge_publication_installed = True
