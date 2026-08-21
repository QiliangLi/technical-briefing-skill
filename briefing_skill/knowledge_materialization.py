from __future__ import annotations

import argparse
import copy
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .utils import canonicalize_url, read_json, stable_hash, write_json


SCHEMA_VERSION = 1
EVIDENCE_SCOPE = "published_archive_only"
FRONTIER_TOPIC_ID = "frontier_exploration"
FRONTIER_TOPIC_NAME = "边界探索"
TASK_BINDING_KEY = "_task"
ROADMAP_STATUSES = {"supported", "emerging", "contested", "inferred"}
IDEA_TYPES = {"research_hypothesis", "solution_concept"}
IDEA_STATUSES = {
    "seed",
    "observing",
    "ready_for_validation",
    "promising",
    "rejected",
    "proposal_candidate",
}
IDENTITY_KEY_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
RADAR_CATEGORY_DIRECTIONS = {
    "AI Infra": "ai_infra",
    "Agent生态": "agent_ecosystem",
    "KVCache生态": "kv_cache_ecosystem",
    "存储与介质": "storage_media",
    "其他技术前沿": "other_frontier",
}


def _json_digest(value: Any) -> str:
    return stable_hash(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        length=32,
    )


def _ordered_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _source_urls(item: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for source in item.get("sources") or []:
        if isinstance(source, dict) and source.get("url"):
            urls.append(canonicalize_url(str(source["url"])))
    if item.get("url"):
        urls.append(canonicalize_url(str(item["url"])))
    return _ordered_unique(urls)


def _frontier_direction_id(category: str) -> str:
    return RADAR_CATEGORY_DIRECTIONS.get(category) or f"radar_{stable_hash(category, length=12)}"


def stable_idea_id(identity: dict[str, Any]) -> str:
    """Derive identity from problem + mechanism + target, never project_question alone."""

    keys = [
        str(identity.get("problem_key") or "").strip(),
        str(identity.get("mechanism_key") or "").strip(),
        str(identity.get("target_key") or "").strip(),
    ]
    if not all(IDENTITY_KEY_RE.fullmatch(value) for value in keys):
        raise ValueError("idea identity keys must be lower_snake_case ASCII tokens")
    return f"idea_{stable_hash(*keys, length=20)}"


@dataclass(frozen=True)
class PublishedIssue:
    date: str
    issue_path: Path
    papers_path: Path
    issue: dict[str, Any]
    papers: list[dict[str, Any]]


class PublishedArchive:
    """Read only publication records listed in archive/index.json.

    Candidate pools, workspace run outputs, full text, and reader projections are
    deliberately outside this loader.
    """

    def __init__(self, root: Path):
        self.root = root
        self.archive_root = root / "archive"

    def issue_dates(self) -> list[str]:
        index = read_json(self.archive_root / "index.json", {})
        dates = [str(row.get("date") or "") for row in index.get("issues") or []]
        dates = [value for value in dates if value]
        if dates != sorted(set(dates)):
            raise ValueError("archive/index.json issue dates must be unique and sorted")
        return dates

    def load_issue(self, issue_date: str) -> PublishedIssue:
        if issue_date not in self.issue_dates():
            raise ValueError(f"issue is not published in archive/index.json: {issue_date}")
        issue_dir = self.archive_root / "issues" / issue_date
        issue_path = issue_dir / "issue.json"
        papers_path = issue_dir / "papers.json"
        if not issue_path.is_file() or not papers_path.is_file():
            raise ValueError(f"published issue is incomplete: {issue_date}")
        issue = read_json(issue_path)
        papers = read_json(papers_path)
        if not isinstance(issue, dict) or not isinstance(papers, list):
            raise ValueError(f"invalid publication records: {issue_date}")
        recorded_date = str(issue.get("date_to") or issue.get("date_from") or "")
        if recorded_date and recorded_date != issue_date:
            raise ValueError(f"archive date mismatch for {issue_date}: {recorded_date}")
        return PublishedIssue(issue_date, issue_path, papers_path, issue, papers)

    def through(self, issue_date: str) -> list[PublishedIssue]:
        dates = self.issue_dates()
        if issue_date not in dates:
            raise ValueError(f"issue is not published in archive/index.json: {issue_date}")
        return [self.load_issue(date) for date in dates if date <= issue_date]

    @staticmethod
    def evidence(issue: PublishedIssue) -> list[dict[str, Any]]:
        role_by_item_id = {
            str(row.get("item_id")): str(row.get("role") or "")
            for row in issue.papers
            if isinstance(row, dict) and row.get("item_id")
        }
        result: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for item in issue.issue.get("items") or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("brief_item_id") or "").strip()
            if not item_id:
                raise ValueError(f"published machine item lacks brief_item_id: {issue.date}")
            if item_id in seen_ids:
                raise ValueError(f"duplicate brief_item_id in published issue {issue.date}: {item_id}")
            seen_ids.add(item_id)
            role = role_by_item_id.get(item_id) or str(item.get("item_role") or "core")
            if role == "observation":
                role = "supplement"
            result.append(
                {
                    "item_id": item_id,
                    "issue_date": issue.date,
                    "role": role,
                    "topic_id": str(item.get("topic_id") or ""),
                    "topic_name": str(item.get("topic_name") or ""),
                    "direction_id": str(item.get("direction_id") or ""),
                    "direction_name": str(item.get("direction_name") or ""),
                    "title": str(item.get("title") or ""),
                    "published_at": item.get("published_at"),
                    "core_conclusion": str(item.get("core_conclusion") or ""),
                    "mechanism": str(item.get("mechanism") or ""),
                    "result": str(item.get("result") or ""),
                    "boundary": str(item.get("boundary") or ""),
                    "project_relevance": str(item.get("project_relevance") or ""),
                    "keywords": [str(value) for value in item.get("keywords") or []],
                    "source_urls": _source_urls(item),
                }
            )

        radar_by_url: dict[str, dict[str, Any]] = {}
        for signal in (issue.issue.get("synthesis") or {}).get("radar_signals") or []:
            if not isinstance(signal, dict):
                continue
            for url in signal.get("source_urls") or []:
                radar_by_url[canonicalize_url(str(url))] = signal
        for row in issue.papers:
            if not isinstance(row, dict) or row.get("role") != "radar":
                continue
            url = canonicalize_url(str(row.get("url") or ""))
            signal = radar_by_url.get(url, {})
            category = str(signal.get("category") or row.get("topic_name") or "其他技术前沿")
            item_id = str(row.get("item_id") or "").strip() or f"radar_{stable_hash(issue.date, url, length=20)}"
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            result.append(
                {
                    "item_id": item_id,
                    "issue_date": issue.date,
                    "role": "radar",
                    "topic_id": FRONTIER_TOPIC_ID,
                    "topic_name": FRONTIER_TOPIC_NAME,
                    "direction_id": _frontier_direction_id(category),
                    "direction_name": category,
                    "frontier_category": category,
                    # Radar cards are unverified discovery signals copied from
                    # an invisible upstream; they may cluster and count, but
                    # never support/retire Roadmap stages or Ideas directly.
                    "evidence_kind": "discovery_signal",
                    "claim_strength": "unverified",
                    "title": str(signal.get("signal") or row.get("title") or ""),
                    "published_at": row.get("published_at"),
                    "core_conclusion": str(signal.get("summary") or ""),
                    "mechanism": "",
                    "result": "",
                    "boundary": "Radar 信号仅用于发现和持续观察，不能视作已验证的技术结论。",
                    "project_relevance": "",
                    "keywords": [],
                    "source_urls": [url] if url else [],
                }
            )
        return result

    def evidence_through(self, issue_date: str) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        identities: set[tuple[str, str]] = set()
        for issue in self.through(issue_date):
            for item in self.evidence(issue):
                identity = (item["issue_date"], item["item_id"])
                if identity in identities:
                    raise ValueError(f"cross-record duplicate evidence identity: {identity}")
                identities.add(identity)
                evidence.append(item)
        return evidence


def affected_topics(root: Path, issue_date: str) -> list[dict[str, str]]:
    archive = PublishedArchive(root)
    issue = archive.load_issue(issue_date)
    topics: dict[str, str] = {}
    for item in archive.evidence(issue):
        topic_id = str(item.get("topic_id") or "")
        if topic_id:
            topics.setdefault(topic_id, str(item.get("topic_name") or topic_id))
    return [{"topic_id": key, "topic_name": topics[key]} for key in sorted(topics)]


def _read_ideas(knowledge_root: Path) -> list[dict[str, Any]]:
    ideas: list[dict[str, Any]] = []
    for path in sorted((knowledge_root / "ideas").glob("*.json")):
        value = read_json(path)
        if isinstance(value, dict):
            ideas.append(value)
    return ideas


def _roadmap_semantic_state(roadmap: dict[str, Any]) -> dict[str, Any]:
    """Ignore evidence accumulation when deciding whether the external judgement changed."""

    branches: list[dict[str, Any]] = []
    for branch in roadmap.get("branches") or []:
        stages = []
        for stage in branch.get("stages") or []:
            stages.append(
                {
                    key: copy.deepcopy(stage.get(key))
                    for key in (
                        "stage_id",
                        "name",
                        "problem",
                        "mechanisms",
                        "status",
                        "transition_reason",
                    )
                }
            )
        branches.append(
            {
                "branch_id": branch.get("branch_id"),
                "name": branch.get("name"),
                "direction_ids": sorted(branch.get("direction_ids") or []),
                "status": branch.get("status"),
                "stages": stages,
                "open_questions": copy.deepcopy(branch.get("open_questions") or []),
            }
        )
    return {
        "view_mode": roadmap.get("view_mode"),
        "branches": branches,
    }


def _current_roadmap(knowledge_root: Path, topic_id: str) -> dict[str, Any] | None:
    path = knowledge_root / "roadmaps" / f"{topic_id}.json"
    return read_json(path) if path.is_file() else None


def _evidence_map(evidence: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["item_id"]): item for item in evidence}


def _validate_evidence_ref(
    ref: dict[str, Any],
    *,
    allowed: dict[str, dict[str, Any]],
    context: str,
) -> list[str]:
    errors: list[str] = []
    item_id = str(ref.get("item_id") or "")
    item = allowed.get(item_id)
    if not item:
        return [f"{context} references unpublished or out-of-scope item_id {item_id}"]
    if str(ref.get("issue_date") or "") != str(item.get("issue_date") or ""):
        errors.append(f"{context} issue_date does not match publication record for {item_id}")
    allowed_urls = set(item.get("source_urls") or [])
    urls = {canonicalize_url(str(url)) for url in ref.get("source_urls") or []}
    if not urls or not urls.issubset(allowed_urls):
        errors.append(f"{context} source_urls must be a non-empty subset of {item_id} sources")
    return errors


def roadmap_semantic_errors(
    roadmap: dict[str, Any],
    *,
    topic_id: str,
    issue_date: str,
    evidence: list[dict[str, Any]],
    promoted_clusters: list[dict[str, Any]] | None = None,
) -> list[str]:
    errors: list[str] = []
    if topic_id == FRONTIER_TOPIC_ID:
        return ["frontier_exploration must remain clusters and cannot own a Roadmap"]
    if roadmap.get("topic_id") != topic_id:
        errors.append("roadmap topic_id must match the bounded task")
    if roadmap.get("updated_by_issue") != issue_date:
        errors.append("roadmap updated_by_issue must match the bounded task")
    if roadmap.get("evidence_scope") != EVIDENCE_SCOPE:
        errors.append("roadmap evidence_scope must be published_archive_only")
    topic_allowed = _evidence_map(item for item in evidence if item.get("topic_id") == topic_id)
    frontier_evidence = _evidence_map(
        item for item in evidence if item.get("topic_id") == FRONTIER_TOPIC_ID
    )
    promoted_by_branch: dict[str, set[str]] = {}
    for cluster in promoted_clusters or []:
        target = cluster.get("promotion_target") or {}
        if cluster.get("status") != "promoted" or target.get("topic_id") != topic_id:
            continue
        promoted_by_branch.setdefault(str(target.get("branch_id") or ""), set()).update(
            map(str, cluster.get("evidence_item_ids") or [])
        )
    branch_ids: set[str] = set()
    all_referenced: set[str] = set()
    for branch_index, branch in enumerate(roadmap.get("branches") or []):
        branch_id = str(branch.get("branch_id") or "")
        allowed = dict(topic_allowed)
        for item_id in promoted_by_branch.get(branch_id, set()):
            if item_id in frontier_evidence:
                allowed[item_id] = frontier_evidence[item_id]
        if branch_id in branch_ids:
            errors.append(f"duplicate roadmap branch_id {branch_id}")
        branch_ids.add(branch_id)
        if branch.get("status") not in ROADMAP_STATUSES:
            errors.append(f"branch {branch_id} has invalid status")
        branch_refs = branch.get("evidence_timeline") or []
        if not branch.get("stages") and not branch_refs:
            errors.append(f"branch {branch_id} needs stages or an evidence_timeline")
        for ref_index, ref in enumerate(branch_refs):
            errors.extend(
                _validate_evidence_ref(
                    ref,
                    allowed=allowed,
                    context=f"branch {branch_id} timeline {ref_index}",
                )
            )
            all_referenced.add(str(ref.get("item_id") or ""))
        timeline_ids = [str(ref.get("item_id") or "") for ref in branch_refs]
        if len(timeline_ids) != len(set(timeline_ids)):
            errors.append(f"branch {branch_id} evidence_timeline contains duplicate items")
        stage_refs: list[dict[str, Any]] = []
        for stage_index, stage in enumerate(branch.get("stages") or []):
            if stage.get("status") not in ROADMAP_STATUSES:
                errors.append(f"branch {branch_id} stage {stage_index} has invalid status")
            if not stage.get("evidence_for"):
                errors.append(f"branch {branch_id} stage {stage_index} requires evidence_for")
            for field in ("evidence_for", "evidence_against"):
                for ref_index, ref in enumerate(stage.get(field) or []):
                    errors.extend(
                        _validate_evidence_ref(
                            ref,
                            allowed=allowed,
                            context=f"branch {branch_id} stage {stage_index} {field} {ref_index}",
                        )
                    )
                    all_referenced.add(str(ref.get("item_id") or ""))
                    stage_refs.append(ref)
        declared_ids = set(map(str, branch.get("evidence_item_ids") or []))
        referenced_ids = {
            str(ref.get("item_id") or "") for ref in [*branch_refs, *stage_refs]
        }
        if declared_ids != referenced_ids:
            errors.append(f"branch {branch_id} evidence_item_ids must exactly match cited refs")
        declared_urls = {canonicalize_url(str(url)) for url in branch.get("source_urls") or []}
        referenced_urls = {
            canonicalize_url(str(url))
            for ref in [*branch_refs, *stage_refs]
            for url in ref.get("source_urls") or []
        }
        if declared_urls != referenced_urls:
            errors.append(f"branch {branch_id} source_urls must exactly match cited refs")
    if roadmap.get("branches") and not all_referenced:
        errors.append("roadmap branches must cite published evidence")
    return errors


def idea_semantic_errors(
    idea: dict[str, Any],
    *,
    issue_date: str,
    evidence: list[dict[str, Any]],
    previous: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if idea.get("idea_type") not in IDEA_TYPES:
        errors.append("idea_type must be research_hypothesis or solution_concept")
    if idea.get("status") not in IDEA_STATUSES:
        errors.append("idea status is invalid")
    try:
        expected_id = stable_idea_id(idea.get("identity") or {})
    except ValueError as exc:
        errors.append(str(exc))
        expected_id = ""
    if expected_id and idea.get("idea_id") != expected_id:
        errors.append(f"idea_id must equal deterministic identity id {expected_id}")
    if idea.get("last_updated_issue") != issue_date:
        errors.append("idea last_updated_issue must match the bounded task")
    if not idea.get("topic_ids"):
        errors.append("idea requires topic_ids")
    allowed = _evidence_map(evidence)
    unverified_ids = {
        item_id
        for item_id, item in allowed.items()
        if str(item.get("claim_strength") or "") == "unverified"
        or str(item.get("evidence_kind") or "") == "discovery_signal"
    }
    referenced: set[str] = set()
    for field in ("evidence_for", "evidence_against"):
        for index, ref in enumerate(idea.get(field) or []):
            errors.extend(
                _validate_evidence_ref(ref, allowed=allowed, context=f"idea {field} {index}")
            )
            if str(ref.get("item_id") or "") in unverified_ids:
                errors.append(
                    f"idea {field} {index} cites an unverified discovery signal; "
                    "radar evidence must re-enter through the original-source fact pipeline first"
                )
            referenced.add(str(ref.get("item_id") or ""))
    all_refs = [*(idea.get("evidence_for") or []), *(idea.get("evidence_against") or [])]
    ref_keys = [(str(ref.get("issue_date") or ""), str(ref.get("item_id") or "")) for ref in all_refs]
    if len(ref_keys) != len(set(ref_keys)):
        errors.append("idea evidence references must not contain duplicates")
    if not idea.get("evidence_for"):
        errors.append("idea requires at least one supporting published evidence item")
    if idea.get("status") == "rejected" and not idea.get("evidence_against"):
        errors.append("an automatically rejected idea requires evidence_against")

    logs = idea.get("decision_log") or []
    event_ids = [str(row.get("event_id") or "") for row in logs]
    if len(event_ids) != len(set(event_ids)):
        errors.append("idea decision_log event_id values must be unique")
    for index, row in enumerate(logs):
        if str(row.get("issue_date") or "") > issue_date:
            errors.append(f"idea decision_log {index} cannot be dated after the task issue")
        unknown = sorted(set(map(str, row.get("evidence_item_ids") or [])) - set(allowed))
        if unknown:
            errors.append(f"idea decision_log {index} references unknown evidence: {', '.join(unknown)}")
        unverified_log = sorted(set(map(str, row.get("evidence_item_ids") or [])) & unverified_ids)
        if unverified_log:
            errors.append(
                f"idea decision_log {index} cites unverified discovery signals: {', '.join(unverified_log)}"
            )
    evidence_dates = [str(ref.get("issue_date") or "") for ref in all_refs]
    if evidence_dates and idea.get("first_seen_issue") != min(evidence_dates):
        errors.append("idea first_seen_issue must equal its earliest supporting or contrary evidence")
    evidence_topics = {
        str(allowed[str(ref.get("item_id"))].get("topic_id") or "")
        for ref in all_refs
        if str(ref.get("item_id") or "") in allowed
    }
    if not set(map(str, idea.get("topic_ids") or [])).issubset(evidence_topics):
        errors.append("idea topic_ids must be supported by its cited evidence")
    if previous:
        if previous.get("identity") != idea.get("identity"):
            errors.append("existing idea identity is immutable")
        if previous.get("idea_type") != idea.get("idea_type"):
            errors.append("existing idea_type is immutable")
        old_logs = previous.get("decision_log") or []
        if logs[: len(old_logs)] != old_logs:
            errors.append("existing decision_log is append-only")
        if previous.get("status") != idea.get("status"):
            appended = logs[len(old_logs) :]
            decisions = {str(row.get("decision") or "") for row in appended}
            if idea.get("status") == "rejected" and "rejected" not in decisions:
                errors.append("rejected status requires an appended rejected decision")
            if previous.get("status") == "rejected" and idea.get("status") != "rejected" and "reopened" not in decisions:
                errors.append("reopening a rejected idea requires an appended reopened decision")
    if not logs:
        errors.append("idea requires an auditable decision_log")
    return errors


def frontier_cluster_semantic_errors(
    clusters: list[dict[str, Any]],
    *,
    topic_id: str,
    evidence: list[dict[str, Any]],
    allowed_idea_ids: set[str] | None = None,
    allowed_target_topic_ids: set[str] | None = None,
) -> list[str]:
    if clusters and topic_id != FRONTIER_TOPIC_ID:
        return ["frontier clusters may only be changed by a frontier_exploration task"]
    allowed = _evidence_map(
        item for item in evidence if item.get("topic_id") == FRONTIER_TOPIC_ID
    )
    known_ideas = allowed_idea_ids or set()
    errors: list[str] = []
    cluster_ids: set[str] = set()
    for index, cluster in enumerate(clusters):
        cluster_id = str(cluster.get("cluster_id") or "")
        if cluster_id in cluster_ids:
            errors.append(f"duplicate frontier cluster_id {cluster_id}")
        cluster_ids.add(cluster_id)
        item_ids = [str(value) for value in cluster.get("evidence_item_ids") or []]
        items = [allowed.get(item_id) for item_id in item_ids]
        unknown = [item_id for item_id, item in zip(item_ids, items) if item is None]
        if unknown:
            errors.append(f"frontier cluster {index} references unpublished items: {', '.join(unknown)}")
        allowed_urls = {url for item in items if item for url in item.get("source_urls") or []}
        urls = {canonicalize_url(str(url)) for url in cluster.get("source_urls") or []}
        if not urls or urls != allowed_urls:
            errors.append(f"frontier cluster {index} source_urls must exactly match its evidence items")
        issue_dates = {str(item.get("issue_date")) for item in items if item}
        if issue_dates and cluster.get("first_seen_issue") != min(issue_dates):
            errors.append(f"frontier cluster {index} first_seen_issue does not match evidence")
        if issue_dates and cluster.get("last_seen_issue") != max(issue_dates):
            errors.append(f"frontier cluster {index} last_seen_issue does not match evidence")
        evidence_categories = {
            str(item.get("frontier_category") or item.get("direction_name") or "")
            for item in items
            if item
        }
        if set(map(str, cluster.get("categories") or [])) != evidence_categories:
            errors.append(f"frontier cluster {index} categories must exactly match evidence")
        unknown_ideas = sorted(set(map(str, cluster.get("idea_ids") or [])) - known_ideas)
        if unknown_ideas:
            errors.append(f"frontier cluster {index} references unknown Ideas: {', '.join(unknown_ideas)}")
        if (
            cluster.get("status") == "promoted"
            and len(issue_dates) < 2
            and not cluster.get("idea_ids")
        ):
            errors.append(
                f"frontier cluster {index} needs recurrence across issues or an Idea before promotion"
            )
        if cluster.get("status") == "promoted" and not cluster.get("promotion_reason"):
            errors.append(f"frontier cluster {index} promotion requires promotion_reason")
        target = cluster.get("promotion_target")
        if cluster.get("status") == "promoted":
            if not isinstance(target, dict):
                errors.append(f"frontier cluster {index} promotion requires a stable target")
            elif target.get("topic_id") == FRONTIER_TOPIC_ID:
                errors.append(f"frontier cluster {index} cannot target frontier_exploration Roadmap")
            elif (
                allowed_target_topic_ids is not None
                and target.get("topic_id") not in allowed_target_topic_ids
            ):
                errors.append(f"frontier cluster {index} target topic is not a stable Roadmap")
        elif target is not None:
            errors.append(f"temporary frontier cluster {index} cannot declare a promotion target")
    return errors


def _validate_schema(root: Path, schema_name: str, value: Any) -> list[str]:
    schema = read_json(root / "schemas" / schema_name)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    return [f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors]


def prepare_knowledge_tasks(
    root: Path,
    *,
    issue_date: str,
    topic_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    archive = PublishedArchive(root)
    all_evidence = archive.evidence_through(issue_date)
    current_evidence = PublishedArchive.evidence(archive.load_issue(issue_date))
    affected = {row["topic_id"]: row["topic_name"] for row in affected_topics(root, issue_date)}
    knowledge_root = root / "knowledge"
    frontier_path = knowledge_root / "frontier-clusters.json"
    frontier_state = read_json(frontier_path, {}) if frontier_path.is_file() else {}
    all_clusters = frontier_state.get("clusters") or []
    promoted_targets: dict[str, str] = {}
    for cluster in all_clusters:
        target = cluster.get("promotion_target") or {}
        target_topic = str(target.get("topic_id") or "")
        if cluster.get("status") != "promoted" or not target_topic:
            continue
        previous_target = _current_roadmap(knowledge_root, target_topic)
        promoted_targets[target_topic] = str(
            (previous_target or {}).get("topic_name") or target.get("topic_name") or target_topic
        )
    allowed_topics = {**promoted_targets, **affected}
    requested = _ordered_unique(topic_ids or affected.keys())
    unknown = sorted(set(requested) - set(allowed_topics))
    if unknown:
        raise ValueError(
            "topics are neither affected by this issue nor targeted by an explicit Frontier promotion: "
            + ", ".join(unknown)
        )

    task_root = root / "workspace" / "knowledge" / "tasks" / issue_date
    ideas = _read_ideas(knowledge_root)
    tasks: list[dict[str, Any]] = []
    for topic_id in requested:
        previous = None if topic_id == FRONTIER_TOPIC_ID else _current_roadmap(knowledge_root, topic_id)
        if previous and any(
            str(row.get("issue_date") or "") == issue_date
            for row in previous.get("change_log") or []
        ):
            continue
        if topic_id == FRONTIER_TOPIC_ID and any(
            str(row.get("issue_date") or "") == issue_date
            for row in frontier_state.get("change_log") or []
        ):
            continue
        relevant_clusters = (
            all_clusters
            if topic_id == FRONTIER_TOPIC_ID
            else [
                cluster
                for cluster in all_clusters
                if cluster.get("status") == "promoted"
                and (cluster.get("promotion_target") or {}).get("topic_id") == topic_id
            ]
        )
        promoted_item_ids = {
            str(item_id)
            for cluster in relevant_clusters
            for item_id in cluster.get("evidence_item_ids") or []
        }
        current_ids = [
            str(row["item_id"])
            for row in current_evidence
            if row.get("topic_id") == topic_id
        ]
        if topic_id != FRONTIER_TOPIC_ID:
            current_ids = _ordered_unique([*current_ids, *sorted(promoted_item_ids)])
        previous_ideas = [idea for idea in ideas if topic_id in (idea.get("topic_ids") or [])]
        previous_idea_item_ids = {
            str(ref.get("item_id") or "")
            for idea in previous_ideas
            for field in ("evidence_for", "evidence_against")
            for ref in idea.get(field) or []
        }
        task_evidence = [
            row
            for row in all_evidence
            if row.get("topic_id") == topic_id
            or row.get("item_id") in previous_idea_item_ids
            or row.get("item_id") in promoted_item_ids
        ]
        payload = {
            "schema_version": SCHEMA_VERSION,
            "evidence_scope": EVIDENCE_SCOPE,
            "issue_date": issue_date,
            "topic": {"topic_id": topic_id, "topic_name": allowed_topics[topic_id]},
            "current_issue_evidence_item_ids": current_ids,
            "published_evidence": task_evidence,
            "previous_roadmap": previous,
            "previous_ideas": previous_ideas,
            "previous_frontier_clusters": relevant_clusters,
            "frontier_policy": {
                "cluster_before_branch": True,
                "promote_only_after_recurrence_stable_mechanism_or_idea": True,
            },
            "validation_policy": {
                "suggestions_only": True,
                "no_simulation_results": True,
                "no_project_question_as_idea_identity": True,
            },
        }
        input_digest = _json_digest(payload)
        task_id = f"knowledge_{stable_hash(issue_date, topic_id, input_digest, length=24)}"
        binding = {
            "id": task_id,
            "type": "knowledge_materialization",
            "entity_id": topic_id,
            "issue_date": issue_date,
            "input_digest": input_digest,
            "previous_roadmap_digest": _json_digest(previous) if previous else None,
            "previous_frontier_digest": _json_digest(frontier_state) if topic_id == FRONTIER_TOPIC_ID else None,
        }
        input_path = task_root / f"{task_id}.input.json"
        output_path = task_root / f"{task_id}.output.json"
        write_json(input_path, {TASK_BINDING_KEY: binding, **payload})
        tasks.append(
            {
                "task_id": task_id,
                "topic_id": topic_id,
                "issue_date": issue_date,
                "prompt_path": "prompts/knowledge-materialization.md",
                "schema_path": "schemas/knowledge-materialization.schema.json",
                "input_path": str(input_path.relative_to(root)),
                "output_path": str(output_path.relative_to(root)),
                "status": "completed" if output_path.is_file() else "pending",
            }
        )
    return tasks


def list_knowledge_tasks(root: Path, *, issue_date: str | None = None) -> list[dict[str, Any]]:
    task_root = root / "workspace" / "knowledge" / "tasks"
    pattern = f"{issue_date}/*.input.json" if issue_date else "*/*.input.json"
    tasks: list[dict[str, Any]] = []
    for input_path in sorted(task_root.glob(pattern)):
        value = read_json(input_path, {})
        binding = value.get(TASK_BINDING_KEY) or {}
        output_path = input_path.with_name(input_path.name.replace(".input.json", ".output.json"))
        applied_path = root / "knowledge" / "applications" / f"{binding.get('id')}.json"
        status = "applied" if applied_path.is_file() else "completed" if output_path.is_file() else "pending"
        tasks.append(
            {
                "task_id": binding.get("id"),
                "topic_id": binding.get("entity_id"),
                "issue_date": binding.get("issue_date"),
                "input_path": str(input_path.relative_to(root)),
                "output_path": str(output_path.relative_to(root)),
                "status": status,
            }
        )
    return tasks


def next_knowledge_task(root: Path, *, issue_date: str | None = None) -> dict[str, Any] | None:
    return next((task for task in list_knowledge_tasks(root, issue_date=issue_date) if task["status"] == "pending"), None)


def knowledge_task_instructions(task: dict[str, Any] | None) -> str:
    if not task:
        return "No pending knowledge tasks"
    return (
        f"Task {task['task_id']} (knowledge_materialization)\n"
        "1. Read prompts/knowledge-materialization.md\n"
        f"2. Read {task['input_path']} only; do not read candidates, full text, reader.json, or another task input\n"
        "3. Produce result fields matching schemas/knowledge-materialization.schema.json\n"
        "4. Echo the input's exact _task object at the output top level\n"
        f"5. Write only this task result to {task['output_path']}\n"
        f"6. Run: python briefing.py knowledge apply --task {task['task_id']}"
    )


def _append_change_log(
    roadmap: dict[str, Any],
    *,
    task_id: str,
    issue_date: str,
    change_type: str,
    version: int,
    evidence_item_ids: list[str],
) -> None:
    roadmap.setdefault("change_log", []).append(
        {
            "event_id": f"roadmap_change_{stable_hash(task_id, change_type, length=20)}",
            "issue_date": issue_date,
            "change_type": change_type,
            "version": version,
            "summary": (
                "本期证据改变了分支、阶段、状态或开放问题。"
                if change_type == "material_change"
                else "本期新增了已发布证据，但没有改变当前外部技术判断。"
            ),
            "evidence_item_ids": sorted(evidence_item_ids),
        }
    )


def _write_roadmap(
    root: Path,
    roadmap_output: dict[str, Any],
    *,
    previous: dict[str, Any] | None,
    task_id: str,
    issue_date: str,
    current_item_ids: list[str],
) -> tuple[dict[str, Any], str]:
    roadmap = copy.deepcopy(roadmap_output)
    history = copy.deepcopy((previous or {}).get("history") or [])
    previous_version = int((previous or {}).get("version") or 0)
    material = previous is None or _roadmap_semantic_state(previous) != _roadmap_semantic_state(roadmap)
    change_type = "material_change" if material else "no_material_change"
    version = previous_version + 1 if material else previous_version
    if not version:
        version = 1
    if material:
        snapshot_path = f"knowledge/history/roadmaps/{roadmap['topic_id']}/v{version}.json"
        history.append(
            {
                "version": version,
                "issue_date": issue_date,
                "change_type": change_type,
                "path": snapshot_path,
            }
        )
    roadmap["schema_version"] = SCHEMA_VERSION
    roadmap["version"] = version
    roadmap["change_type"] = change_type
    roadmap["updated_by_issue"] = issue_date
    roadmap["history"] = history
    roadmap["change_log"] = copy.deepcopy((previous or {}).get("change_log") or [])
    _append_change_log(
        roadmap,
        task_id=task_id,
        issue_date=issue_date,
        change_type=change_type,
        version=version,
        evidence_item_ids=current_item_ids,
    )
    path = root / "knowledge" / "roadmaps" / f"{roadmap['topic_id']}.json"
    write_json(path, roadmap)
    if material:
        snapshot = copy.deepcopy(roadmap)
        write_json(root / history[-1]["path"], snapshot)
    return roadmap, change_type


def _write_ideas(root: Path, ideas: list[dict[str, Any]]) -> list[str]:
    written: list[str] = []
    for idea in ideas:
        path = root / "knowledge" / "ideas" / f"{idea['idea_id']}.json"
        write_json(path, idea)
        written.append(idea["idea_id"])
    return written


def rebuild_knowledge_index(root: Path) -> dict[str, Any]:
    knowledge_root = root / "knowledge"
    roadmaps = []
    for path in sorted((knowledge_root / "roadmaps").glob("*.json")):
        value = read_json(path)
        roadmaps.append(
            {
                "topic_id": value["topic_id"],
                "topic_name": value["topic_name"],
                "path": str(path.relative_to(root)),
                "version": value["version"],
                "change_type": value["change_type"],
                "updated_by_issue": value["updated_by_issue"],
                "summary": value["summary"],
            }
        )
    ideas = []
    for path in sorted((knowledge_root / "ideas").glob("*.json")):
        value = read_json(path)
        ideas.append(
            {
                "idea_id": value["idea_id"],
                "title": value["title"],
                "idea_type": value["idea_type"],
                "status": value["status"],
                "topic_ids": value["topic_ids"],
                "path": str(path.relative_to(root)),
                "last_updated_issue": value["last_updated_issue"],
            }
        )
    frontier_path = knowledge_root / "frontier-clusters.json"
    frontier_value = read_json(frontier_path, {}) if frontier_path.is_file() else {
        "schema_version": SCHEMA_VERSION,
        "evidence_scope": EVIDENCE_SCOPE,
        "clusters": [],
    }
    frontier_clusters = frontier_value.get("clusters", [])
    index = {
        "schema_version": SCHEMA_VERSION,
        "evidence_scope": EVIDENCE_SCOPE,
        "roadmaps": roadmaps,
        "ideas": ideas,
        "frontier_clusters": frontier_clusters,
    }
    errors = _validate_schema(root, "knowledge-index.schema.json", index)
    if errors:
        raise ValueError("invalid knowledge index: " + "; ".join(errors[:8]))
    write_json(knowledge_root / "index.json", index)
    return index


def apply_knowledge_task(root: Path, task_id: str) -> dict[str, Any]:
    matches = list((root / "workspace" / "knowledge" / "tasks").glob(f"*/{task_id}.input.json"))
    if len(matches) != 1:
        raise ValueError(f"knowledge task not found or ambiguous: {task_id}")
    input_path = matches[0]
    output_path = input_path.with_name(input_path.name.replace(".input.json", ".output.json"))
    if not output_path.is_file():
        raise ValueError(f"knowledge task output does not exist: {output_path.relative_to(root)}")
    input_data = read_json(input_path)
    output = read_json(output_path)
    binding = input_data.get(TASK_BINDING_KEY)
    if output.pop(TASK_BINDING_KEY, None) != binding:
        raise ValueError("knowledge task binding mismatch")
    if _json_digest({key: value for key, value in input_data.items() if key != TASK_BINDING_KEY}) != binding.get("input_digest"):
        raise ValueError("knowledge task input digest mismatch")

    application_path = root / "knowledge" / "applications" / f"{task_id}.json"
    if application_path.is_file():
        return {**read_json(application_path), "idempotent": True}

    topic_id = str(binding["entity_id"])
    issue_date = str(binding["issue_date"])
    previous = None if topic_id == FRONTIER_TOPIC_ID else _current_roadmap(root / "knowledge", topic_id)
    current_digest = _json_digest(previous) if previous else None
    if current_digest != binding.get("previous_roadmap_digest"):
        raise ValueError("stale knowledge task: current roadmap differs from prepared input")
    frontier_path = root / "knowledge" / "frontier-clusters.json"
    frontier_state = read_json(frontier_path, {}) if frontier_path.is_file() else {}
    if topic_id == FRONTIER_TOPIC_ID and _json_digest(frontier_state) != binding.get("previous_frontier_digest"):
        raise ValueError("stale knowledge task: current Frontier clusters differ from prepared input")

    schema_errors = _validate_schema(root, "knowledge-materialization.schema.json", output)
    roadmap_output = output.get("roadmap")
    if topic_id == FRONTIER_TOPIC_ID:
        if roadmap_output is not None:
            schema_errors.append(
                "frontier_exploration output roadmap must be null; promote a cluster to a stable target instead"
            )
    elif roadmap_output is None:
        schema_errors.append("a stable Topic knowledge task requires roadmap output")
    else:
        schema_errors.extend(
            _validate_schema(
                root,
                "roadmap.schema.json",
                {
                    **roadmap_output,
                    "schema_version": SCHEMA_VERSION,
                    "version": int((previous or {}).get("version") or 1),
                    "change_type": "material_change",
                    "history": copy.deepcopy((previous or {}).get("history") or []),
                    "change_log": copy.deepcopy((previous or {}).get("change_log") or []),
                },
            )
        )
    for idea in output.get("ideas") or []:
        schema_errors.extend(_validate_schema(root, "idea.schema.json", idea))
    if schema_errors:
        raise ValueError("invalid knowledge output: " + "; ".join(schema_errors[:12]))
    evidence = input_data.get("published_evidence") or []
    errors: list[str] = []
    if roadmap_output is not None:
        errors.extend(
            roadmap_semantic_errors(
                roadmap_output,
                topic_id=topic_id,
                issue_date=issue_date,
                evidence=evidence,
                promoted_clusters=input_data.get("previous_frontier_clusters") or [],
            )
        )
    existing_ideas = {idea["idea_id"]: idea for idea in input_data.get("previous_ideas") or []}
    output_ids: set[str] = set()
    for idea in output.get("ideas") or []:
        idea_id = str(idea.get("idea_id") or "")
        if idea_id in output_ids:
            errors.append(f"duplicate idea_id in task output: {idea_id}")
        output_ids.add(idea_id)
        persisted_path = root / "knowledge" / "ideas" / f"{idea_id}.json"
        if persisted_path.is_file() and idea_id not in existing_ideas:
            errors.append(f"idea {idea_id} exists outside this topic task scope")
        errors.extend(
            idea_semantic_errors(
                idea,
                issue_date=issue_date,
                evidence=evidence,
                previous=existing_ideas.get(idea_id),
            )
        )
    known_idea_ids = {
        path.stem for path in (root / "knowledge" / "ideas").glob("idea_*.json")
    } | output_ids
    stable_topic_ids = {
        path.stem for path in (root / "knowledge" / "roadmaps").glob("*.json")
    }
    errors.extend(
        frontier_cluster_semantic_errors(
            output.get("frontier_clusters") or [],
            topic_id=topic_id,
            evidence=evidence,
            allowed_idea_ids=known_idea_ids,
            allowed_target_topic_ids=stable_topic_ids,
        )
    )
    if errors:
        raise ValueError("knowledge semantic validation failed: " + "; ".join(errors[:16]))

    roadmap = None
    if roadmap_output is not None:
        roadmap, change_type = _write_roadmap(
            root,
            roadmap_output,
            previous=previous,
            task_id=task_id,
            issue_date=issue_date,
            current_item_ids=input_data.get("current_issue_evidence_item_ids") or [],
        )
    else:
        change_type = "clusters_updated"
    idea_ids = _write_ideas(root, output.get("ideas") or [])
    clusters = output.get("frontier_clusters") or []
    if topic_id == FRONTIER_TOPIC_ID:
        old_log = copy.deepcopy(frontier_state.get("change_log") or [])
        old_log.append(
            {
                "event_id": f"frontier_change_{stable_hash(task_id, length=20)}",
                "issue_date": issue_date,
                "change_type": "clusters_updated",
                "cluster_ids": [str(cluster.get("cluster_id") or "") for cluster in clusters],
            }
        )
        write_json(
            frontier_path,
            {
                "schema_version": SCHEMA_VERSION,
                "evidence_scope": EVIDENCE_SCOPE,
                "updated_by_issue": issue_date,
                "clusters": clusters,
                "change_log": old_log,
            },
        )
    rebuild_knowledge_index(root)
    application = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "issue_date": issue_date,
        "topic_id": topic_id,
        "change_type": change_type,
        "roadmap_version": roadmap["version"] if roadmap else None,
        "idea_ids": idea_ids,
        "output_digest": _json_digest(output),
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "idempotent": False,
    }
    write_json(application_path, application)
    return application


def validate_knowledge_store(root: Path) -> list[str]:
    errors: list[str] = []
    archive = PublishedArchive(root)
    dates = archive.issue_dates()
    evidence = archive.evidence_through(dates[-1]) if dates else []
    knowledge_root = root / "knowledge"
    index_path = knowledge_root / "index.json"
    if not index_path.is_file():
        return ["knowledge/index.json is missing"]
    errors.extend(_validate_schema(root, "knowledge-index.schema.json", read_json(index_path)))
    frontier_path = knowledge_root / "frontier-clusters.json"
    if frontier_path.is_file():
        frontier_value = read_json(frontier_path)
        known_idea_ids = {
            path.stem for path in (knowledge_root / "ideas").glob("idea_*.json")
        }
        errors.extend(
            f"{frontier_path}: {error}"
            for error in _validate_schema(root, "frontier-clusters.schema.json", frontier_value)
        )
        errors.extend(
            f"{frontier_path}: {error}"
            for error in frontier_cluster_semantic_errors(
                frontier_value.get("clusters") or [],
                topic_id=FRONTIER_TOPIC_ID,
                evidence=evidence,
                allowed_idea_ids=known_idea_ids,
                allowed_target_topic_ids={
                    path.stem for path in (knowledge_root / "roadmaps").glob("*.json")
                },
            )
        )
    for path in sorted((knowledge_root / "roadmaps").glob("*.json")):
        value = read_json(path)
        errors.extend(f"{path}: {error}" for error in _validate_schema(root, "roadmap.schema.json", value))
        errors.extend(
            f"{path}: {error}"
            for error in roadmap_semantic_errors(
                value,
                topic_id=str(value.get("topic_id") or ""),
                issue_date=str(value.get("updated_by_issue") or ""),
                evidence=evidence,
                promoted_clusters=(frontier_value.get("clusters") or []) if frontier_path.is_file() else [],
            )
        )
    for path in sorted((knowledge_root / "ideas").glob("*.json")):
        value = read_json(path)
        errors.extend(f"{path}: {error}" for error in _validate_schema(root, "idea.schema.json", value))
        errors.extend(
            f"{path}: {error}"
            for error in idea_semantic_errors(
                value,
                issue_date=str(value.get("last_updated_issue") or ""),
                evidence=evidence,
            )
        )
    return errors


def install_knowledge_materialization() -> None:
    from . import cli

    if getattr(cli, "_knowledge_materialization_installed", False):
        return
    original_build_parser = cli.build_parser

    def cmd_knowledge(args: argparse.Namespace) -> int:
        root = Path(args.root).resolve() if getattr(args, "root", None) else cli.discover_root()
        if args.action == "prepare":
            tasks = prepare_knowledge_tasks(
                root,
                issue_date=args.issue,
                topic_ids=args.topic,
            )
            print(json.dumps({"prepared": tasks}, ensure_ascii=False, indent=2))
            pending = next_knowledge_task(root, issue_date=args.issue)
            if pending:
                print(knowledge_task_instructions(pending))
            return 0
        if args.action == "next":
            print(knowledge_task_instructions(next_knowledge_task(root, issue_date=args.issue)))
            return 0
        if args.action == "apply":
            print(json.dumps(apply_knowledge_task(root, args.task), ensure_ascii=False, indent=2))
            return 0
        if args.action == "status":
            print(json.dumps(list_knowledge_tasks(root, issue_date=args.issue), ensure_ascii=False, indent=2))
            return 0
        if args.action == "validate":
            errors = validate_knowledge_store(root)
            print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
            return 1 if errors else 0
        raise ValueError(f"unsupported knowledge action: {args.action}")

    def build_parser():
        parser = original_build_parser()
        sub = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        p = sub.add_parser("knowledge")
        actions = p.add_subparsers(dest="action", required=True)
        q = actions.add_parser("prepare")
        q.add_argument("--issue", required=True)
        q.add_argument("--topic", action="append")
        q.set_defaults(func=cmd_knowledge)
        q = actions.add_parser("next")
        q.add_argument("--issue")
        q.set_defaults(func=cmd_knowledge)
        q = actions.add_parser("apply")
        q.add_argument("--task", required=True)
        q.set_defaults(func=cmd_knowledge)
        q = actions.add_parser("status")
        q.add_argument("--issue")
        q.set_defaults(func=cmd_knowledge)
        q = actions.add_parser("validate")
        q.set_defaults(func=cmd_knowledge)
        return parser

    cli.build_parser = build_parser
    cli._knowledge_materialization_installed = True
