from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .knowledge_materialization import (
    EVIDENCE_SCOPE,
    FRONTIER_TOPIC_ID,
    IDEA_TYPES,
    SCHEMA_VERSION,
    TASK_BINDING_KEY,
    PublishedArchive,
    _json_digest,
    _validate_schema,
    idea_semantic_errors,
    rebuild_knowledge_index,
    stable_idea_id,
)
from .utils import canonicalize_url, read_json, source_identity_key, stable_hash, write_json, write_json_atomic


CANDIDATE_DISPOSITIONS = {"proposed", "accepted", "duplicate", "deferred", "dismissed"}
CANDIDATE_ORIGINS = {
    "single_evidence",
    "cross_source_synthesis",
    "cross_issue_synthesis",
    "roadmap_gap",
    "legacy_seed",
}
CANDIDATE_TASK_ROOT = "workspace/knowledge/candidate-tasks"
PROMOTION_TASK_ROOT = "workspace/knowledge/promotion-tasks"
CANDIDATE_APPLICATION_ROOT = "knowledge/candidate-applications"
TRANSACTION_RELPATH = "knowledge/.candidate-transaction.json"


def _recover_candidate_transaction(root: Path) -> None:
    """Recover a Candidate write interrupted before its commit marker.

    GitHub Pages only publishes after commands finish, but a durable journal
    also makes the local apply operation recoverable after a process crash.
    """

    journal_path = root / TRANSACTION_RELPATH
    if not journal_path.is_file():
        return
    journal = read_json(journal_path, {})
    if journal.get("state") == "committed":
        journal_path.unlink()
        return
    for row in journal.get("backups") or []:
        path = root / str(row["path"])
        before = row.get("before")
        if before is None:
            if path.is_file():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(f".{path.name}.recover-{os.getpid()}")
            temp.write_text(str(before), encoding="utf-8")
            os.replace(temp, path)
    journal_path.unlink()


def commit_candidate_updates(root: Path, updates: dict[Path, Any]) -> None:
    """Commit Candidate/Idea/application changes with rollback and recovery."""

    _recover_candidate_transaction(root)
    index_path = root / "knowledge" / "index.json"
    tracked = list(dict.fromkeys([*updates, index_path]))
    backups = [
        {
            "path": str(path.relative_to(root)),
            "before": path.read_text(encoding="utf-8") if path.is_file() else None,
        }
        for path in tracked
    ]
    journal_path = root / TRANSACTION_RELPATH
    write_json_atomic(journal_path, {"schema_version": 1, "state": "prepared", "backups": backups})
    try:
        for path, value in updates.items():
            write_json_atomic(path, value)
        rebuild_knowledge_index(root)
        write_json_atomic(journal_path, {"schema_version": 1, "state": "committed", "backups": backups})
        journal_path.unlink()
    except Exception:
        _recover_candidate_transaction(root)
        raise


def stable_candidate_id(identity: dict[str, Any]) -> str:
    idea_id = stable_idea_id(identity)
    return f"candidate_{idea_id.removeprefix('idea_')}"


def _candidate_files(root: Path) -> list[Path]:
    return sorted((root / "knowledge" / "idea-candidates").glob("candidate_*.json"))


def read_candidates(root: Path) -> list[dict[str, Any]]:
    return [read_json(path) for path in _candidate_files(root)]


def _evidence_map(root: Path, issue_date: str | None = None) -> dict[str, dict[str, Any]]:
    archive = PublishedArchive(root)
    dates = archive.issue_dates()
    if not dates:
        return {}
    target = issue_date or dates[-1]
    return {str(row["item_id"]): row for row in archive.evidence_through(target)}


def _candidate_semantic_errors(
    candidate: dict[str, Any],
    *,
    evidence: dict[str, dict[str, Any]],
    previous: dict[str, Any] | None = None,
    known_candidate_ids: set[str] | None = None,
    known_idea_ids: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    try:
        expected = stable_candidate_id(candidate.get("identity") or {})
    except ValueError as exc:
        errors.append(str(exc))
        expected = ""
    if expected and candidate.get("candidate_id") != expected:
        errors.append(f"candidate_id must equal deterministic identity id {expected}")
    if candidate.get("idea_type") not in IDEA_TYPES:
        errors.append("candidate idea_type is invalid")
    if candidate.get("disposition") not in CANDIDATE_DISPOSITIONS:
        errors.append("candidate disposition is invalid")

    refs = candidate.get("evidence") or []
    ref_ids = [str(ref.get("item_id") or "") for ref in refs]
    if ref_ids != list(map(str, candidate.get("evidence_item_ids") or [])):
        errors.append("candidate evidence_item_ids must preserve and exactly match evidence refs")
    if len(ref_ids) != len(set(ref_ids)):
        errors.append("candidate evidence references must not contain duplicates")

    urls: list[str] = []
    groups: list[str] = []
    dates: list[str] = []
    topics: set[str] = set()
    for index, ref in enumerate(refs):
        item_id = str(ref.get("item_id") or "")
        item = evidence.get(item_id)
        if not item:
            errors.append(f"candidate evidence {index} references unpublished item {item_id}")
            continue
        if item.get("evidence_kind") == "discovery_signal" or item.get("claim_strength") == "unverified":
            errors.append(f"candidate evidence {index} cites an unverified discovery signal")
        if str(ref.get("issue_date") or "") != str(item.get("issue_date") or ""):
            errors.append(f"candidate evidence {index} issue_date mismatch for {item_id}")
        allowed_urls = set(map(canonicalize_url, item.get("source_urls") or []))
        ref_urls = [canonicalize_url(str(url)) for url in ref.get("source_urls") or []]
        if not ref_urls or not set(ref_urls).issubset(allowed_urls):
            errors.append(f"candidate evidence {index} source_urls are outside {item_id}")
        urls.extend(ref_urls)
        group = str(ref.get("independence_group") or "")
        groups.append(group)
        source_groups = {source_identity_key(url) for url in ref_urls}
        if len(source_groups) != 1 or group not in source_groups:
            errors.append(f"candidate evidence {index} independence_group must match its canonical source identity")
        dates.append(str(item.get("issue_date") or ""))
        topics.add(str(item.get("topic_id") or ""))

    if list(dict.fromkeys(urls)) != list(map(canonicalize_url, candidate.get("source_urls") or [])):
        errors.append("candidate source_urls must be the ordered union of evidence URLs")
    if list(dict.fromkeys(groups)) != list(map(str, candidate.get("independence_groups") or [])):
        errors.append("candidate independence_groups must be the ordered union of evidence groups")
    if dates and candidate.get("first_seen_issue") != min(dates):
        errors.append("candidate first_seen_issue must equal earliest cited evidence")
    if not set(map(str, candidate.get("topic_ids") or [])).issubset(topics):
        errors.append("candidate topic_ids must be supported by cited evidence")
    if FRONTIER_TOPIC_ID in set(map(str, candidate.get("topic_ids") or [])):
        errors.append("candidate requires a stable Topic; frontier_exploration must be promoted first")

    origin = candidate.get("origin") or {}
    kind = origin.get("kind")
    issue_dates = set(dates)
    if kind not in CANDIDATE_ORIGINS:
        errors.append("candidate origin kind is invalid")
    if kind == "single_evidence" and len(refs) != 1:
        errors.append("single_evidence candidate must cite exactly one item")
    if kind == "cross_source_synthesis" and (len(issue_dates) != 1 or len(set(groups)) < 2):
        errors.append("cross_source_synthesis requires one issue and at least two independence groups")
    if kind == "cross_issue_synthesis" and len(issue_dates) < 2:
        errors.append("cross_issue_synthesis requires at least two issue dates")
    if dates and origin.get("trigger_issue") != max(dates):
        errors.append("candidate trigger_issue must equal latest cited evidence issue")

    related_candidates = set(map(str, candidate.get("related_candidate_ids") or []))
    related_ideas = set(map(str, candidate.get("related_idea_ids") or []))
    if candidate.get("candidate_id") in related_candidates:
        errors.append("candidate cannot relate to itself")
    if known_candidate_ids is not None:
        missing = related_candidates - known_candidate_ids
        if missing:
            errors.append(f"candidate references unknown related candidates: {', '.join(sorted(missing))}")
    if known_idea_ids is not None:
        missing = related_ideas - known_idea_ids
        if missing:
            errors.append(f"candidate references unknown related ideas: {', '.join(sorted(missing))}")
    if candidate.get("disposition") == "duplicate" and not (related_candidates or related_ideas):
        errors.append("duplicate candidate must point to an existing Candidate or Idea")
    if candidate.get("disposition") == "accepted" and not related_ideas:
        errors.append("accepted candidate must point to its formal Idea")
    if candidate.get("disposition") == "accepted" and expected and stable_idea_id(candidate["identity"]) not in related_ideas:
        errors.append("accepted candidate must point to the formal Idea with the same stable identity")

    logs = candidate.get("decision_log") or []
    if not logs:
        errors.append("candidate requires an append-only decision_log")
    event_ids = [str(row.get("event_id") or "") for row in logs]
    if len(event_ids) != len(set(event_ids)):
        errors.append("candidate decision_log event_id values must be unique")
    if logs:
        if logs[-1].get("to_disposition") != candidate.get("disposition"):
            errors.append("candidate disposition must match the last decision")
        if candidate.get("last_updated_issue") != logs[-1].get("issue_date"):
            errors.append("candidate last_updated_issue must match the last decision")
    previous_disposition: str | None = None
    previous_issue = ""
    for index, row in enumerate(logs):
        decision = str(row.get("decision") or "")
        from_disposition = row.get("from_disposition")
        to_disposition = str(row.get("to_disposition") or "")
        event_issue = str(row.get("issue_date") or "")
        if from_disposition != previous_disposition:
            errors.append(f"candidate decision_log {index} from_disposition does not match prior state")
        if event_issue < previous_issue:
            errors.append(f"candidate decision_log {index} issue_date is not append-order monotonic")
        if decision in CANDIDATE_DISPOSITIONS and decision != to_disposition:
            errors.append(f"candidate decision_log {index} decision must match to_disposition")
        if decision == "reopened" and to_disposition != "proposed":
            errors.append(f"candidate decision_log {index} reopened must return to proposed")
        unknown = set(map(str, row.get("evidence_item_ids") or [])) - set(evidence)
        if unknown:
            errors.append(f"candidate decision_log {index} references unknown evidence")
        previous_disposition = to_disposition
        previous_issue = event_issue

    if previous:
        if previous.get("identity") != candidate.get("identity"):
            errors.append("candidate identity is immutable")
        old_logs = previous.get("decision_log") or []
        if logs[: len(old_logs)] != old_logs:
            errors.append("candidate decision_log is append-only")
    return errors


def validate_candidate_store(root: Path) -> list[str]:
    _recover_candidate_transaction(root)
    evidence = _evidence_map(root)
    candidates = read_candidates(root)
    known_candidate_ids = {str(row.get("candidate_id") or "") for row in candidates}
    known_idea_ids = {path.stem for path in (root / "knowledge" / "ideas").glob("idea_*.json")}
    errors: list[str] = []
    for path, candidate in zip(_candidate_files(root), candidates):
        errors.extend(f"{path}: {error}" for error in _validate_schema(root, "idea-candidate.schema.json", candidate))
        errors.extend(
            f"{path}: {error}"
            for error in _candidate_semantic_errors(
                candidate,
                evidence=evidence,
                known_candidate_ids=known_candidate_ids,
                known_idea_ids=known_idea_ids,
            )
        )
    backfill_path = root / "knowledge" / "candidate-backfill.json"
    if backfill_path.is_file():
        report = read_json(backfill_path, {})
        errors.extend(
            f"{backfill_path}: {error}"
            for error in _validate_schema(root, "idea-candidate-backfill.schema.json", report)
        )
        through_issue = str(report.get("through_issue") or "")
        try:
            expected_rows = PublishedArchive(root).evidence_through(through_issue)
        except ValueError as exc:
            errors.append(f"{backfill_path}: invalid through_issue: {exc}")
            expected_rows = []
        expected = [str(row["item_id"]) for row in expected_rows]
        issue_dates = [str(row.get("issue_date") or "") for row in report.get("issues") or []]
        if issue_dates != [date for date in PublishedArchive(root).issue_dates() if date <= through_issue]:
            errors.append(f"{backfill_path}: issues must cover every archive issue through the watermark in order")
        ledger_rows = [row for issue in report.get("issues") or [] for row in issue.get("items") or []]
        actual = [str(row.get("item_id") or "") for row in ledger_rows]
        if actual != expected:
            errors.append(f"{backfill_path}: items must cover every published item exactly once and in archive order")
        candidates_by_id = {str(row.get("candidate_id") or ""): row for row in candidates}
        for row in ledger_rows:
            item_id = str(row.get("item_id") or "")
            candidate_ids = list(map(str, row.get("candidate_ids") or []))
            if row.get("result") == "candidate" and not candidate_ids:
                errors.append(f"{backfill_path}: candidate result for {item_id} requires candidate_ids")
            if row.get("result") == "no_op" and candidate_ids:
                errors.append(f"{backfill_path}: no_op result for {item_id} cannot reference Candidates")
            for candidate_id in candidate_ids:
                candidate = candidates_by_id.get(candidate_id)
                if not candidate or item_id not in set(map(str, candidate.get("evidence_item_ids") or [])):
                    errors.append(f"{backfill_path}: {item_id} does not belong to Candidate {candidate_id}")
    return errors


def _task_row(input_path: Path, root: Path, application_root: str) -> dict[str, Any]:
    value = read_json(input_path, {})
    binding = value.get(TASK_BINDING_KEY) or {}
    output_path = input_path.with_name(input_path.name.replace(".input.json", ".output.json"))
    applied = root / application_root / f"{binding.get('id')}.json"
    return {
        "task_id": binding.get("id"),
        "task_type": binding.get("type"),
        "entity_id": binding.get("entity_id"),
        "issue_date": binding.get("issue_date"),
        "input_path": str(input_path.relative_to(root)),
        "output_path": str(output_path.relative_to(root)),
        "status": "applied" if applied.is_file() else "completed" if output_path.is_file() else "pending",
    }


def prepare_candidate_tasks(
    root: Path,
    *,
    issue_date: str,
) -> list[dict[str, Any]]:
    archive = PublishedArchive(root)
    existing = list_candidate_tasks(root, issue_date=issue_date)
    if existing:
        return existing
    # A later issue may not bind a Candidate/Idea snapshot until every earlier
    # published issue has a complete discovery ledger. Existing task files are
    # returned above so an interrupted issue can always resume idempotently.
    from .knowledge_publication import _candidate_analysis

    analysis = _candidate_analysis(root, archive.issue_dates())
    target_issue = analysis["pending"][0] if analysis["pending"] else None
    if issue_date != target_issue:
        if target_issue is None:
            raise ValueError("Candidate discovery already covers the published archive head")
        raise ValueError(f"Candidate discovery must process the oldest pending issue first: {target_issue}")
    current = PublishedArchive.evidence(archive.load_issue(issue_date))
    all_evidence = archive.evidence_through(issue_date)
    current = [row for row in current if row.get("topic_id") != FRONTIER_TOPIC_ID]
    topics = sorted({str(row.get("topic_id") or "") for row in current if row.get("topic_id")})
    candidates = read_candidates(root)
    ideas = [read_json(path) for path in sorted((root / "knowledge" / "ideas").glob("idea_*.json"))]
    task_root = root / CANDIDATE_TASK_ROOT / issue_date
    tasks: list[dict[str, Any]] = []

    def add_task(mode: str, entity_id: str, payload: dict[str, Any]) -> None:
        digest = _json_digest(payload)
        task_id = f"idea_discovery_{stable_hash(issue_date, mode, entity_id, digest, length=24)}"
        binding = {
            "id": task_id,
            "type": f"idea_candidate_{mode}",
            "entity_id": entity_id,
            "issue_date": issue_date,
            "input_digest": digest,
        }
        input_path = task_root / f"{task_id}.input.json"
        output_path = task_root / f"{task_id}.output.json"
        write_json(input_path, {TASK_BINDING_KEY: binding, **payload})
        tasks.append(
            {
                "task_id": task_id,
                "task_type": binding["type"],
                "entity_id": entity_id,
                "issue_date": issue_date,
                "prompt_path": "prompts/idea-candidate-discovery.md",
                "schema_path": "schemas/idea-candidate-discovery.schema.json",
                "input_path": str(input_path.relative_to(root)),
                "output_path": str(output_path.relative_to(root)),
                "status": "completed" if output_path.is_file() else "pending",
            }
        )

    for item in current:
        topic_id = str(item.get("topic_id") or "")
        add_task(
            "direct",
            str(item["item_id"]),
            {
                "schema_version": SCHEMA_VERSION,
                "evidence_scope": EVIDENCE_SCOPE,
                "mode": "direct",
                "issue_date": issue_date,
                "topic_id": topic_id,
                "trigger_evidence_item_ids": [str(item["item_id"])],
                "published_evidence": [item],
                "previous_candidates": [row for row in candidates if topic_id in (row.get("topic_ids") or [])],
                "existing_ideas": [row for row in ideas if topic_id in (row.get("topic_ids") or [])],
            },
        )

    for topic_id in topics:
        topic_evidence = [row for row in all_evidence if row.get("topic_id") == topic_id]
        trigger_ids = [str(row["item_id"]) for row in current if row.get("topic_id") == topic_id]
        roadmap_path = root / "knowledge" / "roadmaps" / f"{topic_id}.json"
        add_task(
            "synthesis",
            topic_id,
            {
                "schema_version": SCHEMA_VERSION,
                "evidence_scope": EVIDENCE_SCOPE,
                "mode": "synthesis",
                "issue_date": issue_date,
                "topic_id": topic_id,
                "trigger_evidence_item_ids": trigger_ids,
                "published_evidence": topic_evidence,
                "roadmap": read_json(roadmap_path, None) if roadmap_path.is_file() else None,
                "previous_candidates": [row for row in candidates if topic_id in (row.get("topic_ids") or [])],
                "existing_ideas": [row for row in ideas if topic_id in (row.get("topic_ids") or [])],
            },
        )
    return tasks


def list_candidate_tasks(root: Path, *, issue_date: str | None = None) -> list[dict[str, Any]]:
    base = root / CANDIDATE_TASK_ROOT
    pattern = f"{issue_date}/*.input.json" if issue_date else "*/*.input.json"
    return [_task_row(path, root, CANDIDATE_APPLICATION_ROOT) for path in sorted(base.glob(pattern))]


def next_candidate_task(root: Path, *, issue_date: str | None = None) -> dict[str, Any] | None:
    return next((row for row in list_candidate_tasks(root, issue_date=issue_date) if row["status"] == "pending"), None)


def candidate_task_instructions(task: dict[str, Any] | None) -> str:
    if not task:
        return "No pending Idea candidate discovery tasks"
    return (
        f"Task {task['task_id']} ({task['task_type']})\n"
        "1. Read prompts/idea-candidate-discovery.md\n"
        f"2. Read {task['input_path']} only; do not read candidates, full text, Reader prose, or another task input\n"
        "3. Write one bounded result matching schemas/idea-candidate-discovery.schema.json\n"
        "4. Echo the exact input _task object at the output top level\n"
        f"5. Write only {task['output_path']}\n"
        f"6. Run: python3 briefing.py knowledge candidates apply --task {task['task_id']}"
    )


def apply_candidate_task(root: Path, task_id: str) -> dict[str, Any]:
    matches = list((root / CANDIDATE_TASK_ROOT).glob(f"*/{task_id}.input.json"))
    if len(matches) != 1:
        raise ValueError(f"candidate task not found or ambiguous: {task_id}")
    input_path = matches[0]
    output_path = input_path.with_name(input_path.name.replace(".input.json", ".output.json"))
    if not output_path.is_file():
        raise ValueError(f"candidate task output does not exist: {output_path.relative_to(root)}")
    input_data = read_json(input_path)
    output = read_json(output_path)
    binding = input_data.get(TASK_BINDING_KEY)
    if output.pop(TASK_BINDING_KEY, None) != binding:
        raise ValueError("candidate task binding mismatch")
    payload = {key: value for key, value in input_data.items() if key != TASK_BINDING_KEY}
    if _json_digest(payload) != binding.get("input_digest"):
        raise ValueError("candidate task input digest mismatch")
    application_path = root / CANDIDATE_APPLICATION_ROOT / f"{task_id}.json"
    if application_path.is_file():
        return {**read_json(application_path), "idempotent": True}

    errors = _validate_schema(root, "idea-candidate-discovery.schema.json", output)
    trigger_ids = list(map(str, input_data.get("trigger_evidence_item_ids") or []))
    if list(map(str, output.get("covered_trigger_item_ids") or [])) != trigger_ids:
        errors.append("covered_trigger_item_ids must exactly match the task triggers")
    no_op_ids = [str(row.get("item_id") or "") for row in output.get("no_ops") or []]
    if len(no_op_ids) != len(set(no_op_ids)):
        errors.append("no_ops must not contain duplicate item IDs")
    unknown_no_ops = set(no_op_ids) - set(trigger_ids)
    if unknown_no_ops:
        errors.append(f"no_ops may only cover trigger items: {', '.join(sorted(unknown_no_ops))}")
    covered = {
        str(row.get("item_id") or "") for row in output.get("no_ops") or []
    } | {
        str(value)
        for candidate in output.get("candidates") or []
        for value in candidate.get("evidence_item_ids") or []
    }
    missing = set(trigger_ids) - covered
    if input_data.get("mode") == "direct" and missing:
        errors.append(f"direct task lacks a candidate or no-op for {', '.join(sorted(missing))}")

    allowed = {str(row["item_id"]): row for row in input_data.get("published_evidence") or []}
    previous = {str(row["candidate_id"]): row for row in input_data.get("previous_candidates") or []}
    output_candidate_ids = {
        str(candidate.get("candidate_id") or "") for candidate in output.get("candidates") or []
    }
    known_candidates = {path.stem for path in _candidate_files(root)} | set(previous) | output_candidate_ids
    known_ideas = {path.stem for path in (root / "knowledge" / "ideas").glob("idea_*.json")}
    seen: set[str] = set()
    for candidate in output.get("candidates") or []:
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id in seen:
            errors.append(f"duplicate candidate_id in task output: {candidate_id}")
        seen.add(candidate_id)
        if candidate.get("disposition") == "accepted":
            errors.append("discovery tasks cannot accept Candidates; use an exclusive promotion task")
        if input_data.get("mode") == "synthesis" and not (
            set(map(str, candidate.get("evidence_item_ids") or [])) & set(trigger_ids)
        ):
            errors.append(f"synthesis Candidate {candidate_id} must cite at least one trigger item")
        errors.extend(_validate_schema(root, "idea-candidate.schema.json", candidate))
        persisted_path = root / "knowledge" / "idea-candidates" / f"{candidate_id}.json"
        if persisted_path.is_file() and candidate_id not in previous:
            errors.append(f"candidate {candidate_id} exists outside this task snapshot")
        if candidate_id in previous and persisted_path.is_file() and read_json(persisted_path) != previous[candidate_id]:
            errors.append(f"candidate {candidate_id} changed after task preparation")
        errors.extend(
            _candidate_semantic_errors(
                candidate,
                evidence=allowed,
                previous=previous.get(candidate_id),
                known_candidate_ids=known_candidates,
                known_idea_ids=known_ideas,
            )
        )
    if errors:
        raise ValueError("invalid candidate discovery output: " + "; ".join(errors[:16]))

    application = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "task_type": binding["type"],
        "issue_date": binding["issue_date"],
        "entity_id": binding["entity_id"],
        "candidate_ids": [row["candidate_id"] for row in output.get("candidates") or []],
        "no_ops": output.get("no_ops") or [],
        "output_digest": _json_digest(output),
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "idempotent": False,
    }
    updates = {
        root / "knowledge" / "idea-candidates" / f"{candidate['candidate_id']}.json": candidate
        for candidate in output.get("candidates") or []
    }
    updates[application_path] = application
    commit_candidate_updates(root, updates)
    return application


def prepare_promotion_task(root: Path, *, candidate_id: str) -> dict[str, Any]:
    candidate_path = root / "knowledge" / "idea-candidates" / f"{candidate_id}.json"
    if not candidate_path.is_file():
        raise ValueError(f"Idea Candidate does not exist: {candidate_id}")
    candidate = read_json(candidate_path)
    if candidate.get("disposition") != "proposed":
        raise ValueError("only a proposed Candidate can enter promotion review")
    idea_id = stable_idea_id(candidate["identity"])
    idea_path = root / "knowledge" / "ideas" / f"{idea_id}.json"
    existing_idea = read_json(idea_path, None) if idea_path.is_file() else None
    issue_date = PublishedArchive(root).issue_dates()[-1]
    evidence = _evidence_map(root)
    evidence_ids = list(candidate["evidence_item_ids"])
    for field in ("evidence_for", "evidence_against"):
        for ref in (existing_idea or {}).get(field) or []:
            item_id = str(ref.get("item_id") or "")
            if item_id and item_id not in evidence_ids:
                evidence_ids.append(item_id)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "evidence_scope": EVIDENCE_SCOPE,
        "issue_date": issue_date,
        "candidate": candidate,
        "published_evidence": [evidence[item_id] for item_id in evidence_ids],
        "existing_idea": existing_idea,
    }
    digest = _json_digest(payload)
    task_id = f"idea_promotion_{stable_hash(candidate_id, issue_date, digest, length=24)}"
    binding = {
        "id": task_id,
        "type": "idea_promotion",
        "entity_id": candidate_id,
        "issue_date": issue_date,
        "input_digest": digest,
        "candidate_digest": _json_digest(candidate),
        "previous_idea_digest": _json_digest(existing_idea) if existing_idea else None,
    }
    task_root = root / PROMOTION_TASK_ROOT / candidate_id
    input_path = task_root / f"{task_id}.input.json"
    output_path = task_root / f"{task_id}.output.json"
    write_json(input_path, {TASK_BINDING_KEY: binding, **payload})
    return {
        "task_id": task_id,
        "task_type": "idea_promotion",
        "entity_id": candidate_id,
        "issue_date": issue_date,
        "prompt_path": "prompts/idea-promotion.md",
        "schema_path": "schemas/idea-promotion.schema.json",
        "input_path": str(input_path.relative_to(root)),
        "output_path": str(output_path.relative_to(root)),
        "status": "completed" if output_path.is_file() else "pending",
    }


def list_promotion_tasks(root: Path) -> list[dict[str, Any]]:
    return [
        _task_row(path, root, CANDIDATE_APPLICATION_ROOT)
        for path in sorted((root / PROMOTION_TASK_ROOT).glob("*/*.input.json"))
    ]


def promotion_task_instructions(task: dict[str, Any] | None) -> str:
    if not task:
        return "No pending Idea promotion tasks"
    return (
        f"Task {task['task_id']} (idea_promotion)\n"
        "1. Read prompts/idea-promotion.md\n"
        f"2. Read {task['input_path']} only\n"
        "3. Write one result matching schemas/idea-promotion.schema.json and echo the exact _task\n"
        f"4. Write only {task['output_path']}\n"
        f"5. Run: python3 briefing.py knowledge candidates apply-promotion --task {task['task_id']}"
    )


def candidate_to_idea(candidate: dict[str, Any], *, issue_date: str) -> dict[str, Any]:
    idea_id = stable_idea_id(candidate["identity"])
    status = "observing" if len(candidate.get("independence_groups") or []) >= 2 else "seed"
    evidence_for = [
        {key: copy.deepcopy(ref[key]) for key in ("item_id", "issue_date", "source_urls", "reason")}
        for ref in candidate.get("evidence") or []
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "idea_id": idea_id,
        "identity": copy.deepcopy(candidate["identity"]),
        "idea_type": candidate["idea_type"],
        "title": candidate["title"],
        "problem": candidate["problem"],
        "hypothesis": candidate["hypothesis"],
        "mechanism": candidate["mechanism"],
        "expected_effect": candidate["expected_effect"],
        "topic_ids": copy.deepcopy(candidate["topic_ids"]),
        "status": status,
        "evidence_for": evidence_for,
        "evidence_against": [],
        "unknowns": copy.deepcopy(candidate["unknowns"]),
        "validation_plan": copy.deepcopy(candidate["validation_plan"]),
        "first_seen_issue": min(ref["issue_date"] for ref in evidence_for),
        "last_updated_issue": issue_date,
        "decision_log": [
            {
                "event_id": f"idea_decision_{stable_hash(idea_id, issue_date, 'created_from_candidate', length=20)}",
                "issue_date": issue_date,
                "decision": "created",
                "from_status": None,
                "to_status": status,
                "reason": f"Candidate {candidate['candidate_id']} 通过身份、来源独立性和可验证性审阅后进入正式 Idea。",
                "evidence_item_ids": list(candidate["evidence_item_ids"]),
            }
        ],
    }


def apply_promotion_task(root: Path, task_id: str) -> dict[str, Any]:
    matches = list((root / PROMOTION_TASK_ROOT).glob(f"*/{task_id}.input.json"))
    if len(matches) != 1:
        raise ValueError(f"promotion task not found or ambiguous: {task_id}")
    input_path = matches[0]
    output_path = input_path.with_name(input_path.name.replace(".input.json", ".output.json"))
    if not output_path.is_file():
        raise ValueError(f"promotion output does not exist: {output_path.relative_to(root)}")
    input_data = read_json(input_path)
    output = read_json(output_path)
    binding = input_data.get(TASK_BINDING_KEY)
    if output.pop(TASK_BINDING_KEY, None) != binding:
        raise ValueError("promotion task binding mismatch")
    payload = {key: value for key, value in input_data.items() if key != TASK_BINDING_KEY}
    if _json_digest(payload) != binding.get("input_digest"):
        raise ValueError("promotion task input digest mismatch")
    application_path = root / CANDIDATE_APPLICATION_ROOT / f"{task_id}.json"
    if application_path.is_file():
        return {**read_json(application_path), "idempotent": True}

    candidate_id = str(binding["entity_id"])
    candidate_path = root / "knowledge" / "idea-candidates" / f"{candidate_id}.json"
    candidate = read_json(candidate_path, None)
    if not isinstance(candidate, dict) or _json_digest(candidate) != binding.get("candidate_digest"):
        raise ValueError("stale promotion task: Candidate changed after preparation")
    if candidate.get("disposition") != "proposed":
        raise ValueError("stale promotion task: Candidate is no longer proposed")

    errors = _validate_schema(root, "idea-promotion.schema.json", output)
    if output.get("candidate_id") != candidate_id:
        errors.append("promotion candidate_id mismatch")
    idea = output.get("idea") or {}
    errors.extend(_validate_schema(root, "idea.schema.json", idea))
    expected_idea_id = stable_idea_id(candidate["identity"])
    if idea.get("idea_id") != expected_idea_id or idea.get("identity") != candidate.get("identity"):
        errors.append("promoted Idea identity must exactly match the Candidate")
    current_idea_path = root / "knowledge" / "ideas" / f"{expected_idea_id}.json"
    current_idea = read_json(current_idea_path, None) if current_idea_path.is_file() else None
    current_digest = _json_digest(current_idea) if current_idea else None
    if current_digest != binding.get("previous_idea_digest"):
        errors.append("stale promotion task: formal Idea changed after preparation")
    allowed = input_data.get("published_evidence") or []
    errors.extend(
        idea_semantic_errors(
            idea,
            issue_date=str(binding["issue_date"]),
            evidence=allowed,
            previous=input_data.get("existing_idea"),
        )
    )
    candidate_ids = set(map(str, candidate.get("evidence_item_ids") or []))
    previous_ids = {
        str(ref.get("item_id") or "")
        for field in ("evidence_for", "evidence_against")
        for ref in (input_data.get("existing_idea") or {}).get(field) or []
    }
    supporting_ids = {str(ref.get("item_id") or "") for ref in idea.get("evidence_for") or []}
    promoted_ids = {
        str(ref.get("item_id") or "")
        for field in ("evidence_for", "evidence_against")
        for ref in idea.get(field) or []
    }
    if promoted_ids != candidate_ids | previous_ids:
        errors.append("promoted Idea evidence must exactly preserve old evidence and add Candidate evidence")
    if not candidate_ids.issubset(supporting_ids):
        errors.append("Candidate evidence must enter the promoted Idea as supporting evidence")
    if errors:
        raise ValueError("invalid Idea promotion output: " + "; ".join(errors[:16]))

    accepted = copy.deepcopy(candidate)
    issue_date = str(binding["issue_date"])
    accepted["disposition"] = "accepted"
    accepted["disposition_reason"] = f"已创建正式 Idea {expected_idea_id}。"
    accepted["related_idea_ids"] = list(dict.fromkeys([*accepted.get("related_idea_ids", []), expected_idea_id]))
    accepted["last_updated_issue"] = issue_date
    accepted.setdefault("decision_log", []).append(
        {
            "event_id": f"candidate_decision_{stable_hash(candidate_id, issue_date, 'accepted', length=20)}",
            "issue_date": issue_date,
            "decision": "accepted",
            "from_disposition": "proposed",
            "to_disposition": "accepted",
            "reason": accepted["disposition_reason"],
            "evidence_item_ids": list(accepted["evidence_item_ids"]),
            "actor": "human",
        }
    )
    candidate_errors = _validate_schema(root, "idea-candidate.schema.json", accepted)
    candidate_errors.extend(
        _candidate_semantic_errors(
            accepted,
            evidence=_evidence_map(root),
            previous=candidate,
            known_candidate_ids={path.stem for path in _candidate_files(root)},
            known_idea_ids={path.stem for path in (root / "knowledge" / "ideas").glob("idea_*.json")} | {expected_idea_id},
        )
    )
    if candidate_errors:
        raise ValueError("accepted Candidate is invalid: " + "; ".join(candidate_errors[:12]))

    application = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "task_type": "idea_promotion",
        "issue_date": issue_date,
        "candidate_id": candidate_id,
        "idea_id": expected_idea_id,
        "output_digest": _json_digest(output),
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "idempotent": False,
    }
    commit_candidate_updates(
        root,
        {
            current_idea_path: idea,
            candidate_path: accepted,
            application_path: application,
        },
    )
    return application


def install_idea_discovery() -> None:
    from . import cli

    if getattr(cli, "_idea_discovery_installed", False):
        return
    original_build_parser = cli.build_parser

    def cmd_candidates(args: argparse.Namespace) -> int:
        root = Path(args.root).resolve() if getattr(args, "root", None) else cli.discover_root()
        action = args.candidate_action
        if action == "prepare":
            tasks = prepare_candidate_tasks(root, issue_date=args.issue)
            print(json.dumps({"prepared": tasks}, ensure_ascii=False, indent=2))
            pending = next_candidate_task(root, issue_date=args.issue)
            if pending:
                print(candidate_task_instructions(pending))
            return 0
        if action == "next":
            print(candidate_task_instructions(next_candidate_task(root, issue_date=args.issue)))
            return 0
        if action == "apply":
            print(json.dumps(apply_candidate_task(root, args.task), ensure_ascii=False, indent=2))
            return 0
        if action == "promote":
            task = prepare_promotion_task(root, candidate_id=args.candidate)
            print(json.dumps(task, ensure_ascii=False, indent=2))
            print(promotion_task_instructions(task))
            return 0
        if action == "next-promotion":
            pending = next((row for row in list_promotion_tasks(root) if row["status"] == "pending"), None)
            print(promotion_task_instructions(pending))
            return 0
        if action == "apply-promotion":
            print(json.dumps(apply_promotion_task(root, args.task), ensure_ascii=False, indent=2))
            return 0
        if action == "status":
            print(
                json.dumps(
                    {"discovery": list_candidate_tasks(root, issue_date=args.issue), "promotion": list_promotion_tasks(root)},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        raise ValueError(f"unsupported Candidate action: {action}")

    def build_parser():
        parser = original_build_parser()
        top = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        knowledge_parser = top.choices.get("knowledge")
        if knowledge_parser is None:
            return parser
        knowledge_actions = next(
            action for action in knowledge_parser._actions if isinstance(action, argparse._SubParsersAction)
        )
        candidate_parser = knowledge_actions.add_parser("candidates", help="discover and promote Idea Candidates")
        actions = candidate_parser.add_subparsers(dest="candidate_action", required=True)
        prepare = actions.add_parser("prepare")
        prepare.add_argument("--issue", required=True)
        prepare.set_defaults(func=cmd_candidates)
        next_cmd = actions.add_parser("next")
        next_cmd.add_argument("--issue")
        next_cmd.set_defaults(func=cmd_candidates)
        apply = actions.add_parser("apply")
        apply.add_argument("--task", required=True)
        apply.set_defaults(func=cmd_candidates)
        promote = actions.add_parser("promote")
        promote.add_argument("--candidate", required=True)
        promote.set_defaults(func=cmd_candidates)
        next_promotion = actions.add_parser("next-promotion")
        next_promotion.set_defaults(func=cmd_candidates)
        apply_promotion = actions.add_parser("apply-promotion")
        apply_promotion.add_argument("--task", required=True)
        apply_promotion.set_defaults(func=cmd_candidates)
        status = actions.add_parser("status")
        status.add_argument("--issue")
        status.set_defaults(func=cmd_candidates)
        return parser

    cli.build_parser = build_parser
    cli._idea_discovery_installed = True
