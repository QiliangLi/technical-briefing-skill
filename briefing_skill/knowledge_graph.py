"""Deterministic daily-briefing knowledge graph builder.

Reads only the authoritative public inputs (``archive/`` machine records and
materialized ``knowledge/`` objects) and emits the derived publication
``knowledge/graph.json``. The graph is never an authoritative knowledge source:
every node must remain traceable to at least one authoritative object, and the
file can be deleted and regenerated at any time.

Business relations come only from explicit fields (see ``RELATION_ENDPOINTS``);
topic/direction names and keywords are display material and never create edges.
NetworkX provides build-time structure checks only; coordinates come from the
stable layered algorithm in this module, never from a seeded or unseeded spring
layout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .knowledge_materialization import PublishedArchive, validate_knowledge_store
from .utils import normalize_text, read_json, stable_hash, write_json_atomic

SCHEMA_VERSION = 1
GRAPH_SCHEMA_NAME = "knowledge-graph.schema.json"
GRAPH_RELATIVE_PATH = "knowledge/graph.json"
# A build fails when dangling explicit references exceed this budget. Skeleton
# topics/directions are always materialized from their own explicit records, so
# they can never dangle by construction.
MAX_UNRESOLVED = 20

RELATION_LABELS: dict[str, str] = {
    "has_direction": "包含方向",
    "has_item": "收录条目",
    "published_in": "发布于",
    "supports_judgement": "支持判断",
    "tracks": "跟踪",
    "organizes": "组织方向",
    "uses_evidence": "引用证据",
    "relates_to": "关联专题",
    "supports_idea": "支持",
    "challenges_idea": "反对",
}

# relation -> (allowed source kind, allowed target kind). Edges outside these
# pairs fail the build; the direction is part of the data contract.
RELATION_ENDPOINTS: dict[str, tuple[str, str]] = {
    "has_direction": ("topic", "direction"),
    "has_item": ("direction", "item"),
    "published_in": ("item", "issue"),
    "supports_judgement": ("item", "judgement"),
    "tracks": ("roadmap", "topic"),
    "organizes": ("roadmap_branch", "direction"),
    "uses_evidence": ("roadmap_branch", "item"),
    "relates_to": ("idea", "topic"),
    "supports_idea": ("item", "idea"),
    "challenges_idea": ("item", "idea"),
}

KIND_RANK: dict[str, int] = {
    "roadmap": 0,
    "topic": 1,
    "roadmap_branch": 2,
    "direction": 3,
    "item": 4,
    "judgement": 5,
    "issue": 5,
    "idea": 6,
}

# Stable column grid: knowledge (left) -> archive structure (middle) -> audit
# objects (right). Every kind owns a distinct column so overlays never collide;
# roadmap branches stack in the topic column below the topic band.
KIND_COLUMNS: dict[str, float] = {
    "roadmap": 0.0,
    "topic": 280.0,
    "roadmap_branch": 280.0,
    "direction": 540.0,
    "item": 1340.0,
    "judgement": 1560.0,
    "issue": 1780.0,
    "idea": 2000.0,
}
KIND_ROW_HEIGHTS: dict[str, float] = {
    "roadmap": 132.0,
    "topic": 132.0,
    "roadmap_branch": 150.0,
    "direction": 76.0,
    "item": 90.0,
    "judgement": 130.0,
    "issue": 110.0,
    "idea": 160.0,
}
# Directions cluster beside their primary (first-seen) topic in compact
# sub-rows so the default structure lens stays readable after one fit.
DIRECTIONS_PER_ROW = 4
DIRECTION_COLUMN_GAP = 196.0
JUDGEMENTS_PER_COLUMN = 10
JUDGEMENT_COLUMN_GAP = 420.0
# Branch nodes stack in the topic column below the topic band so overlay lanes
# stay readable without a second horizontal column.
BRANCH_BAND_GAP = 360.0

_ID_PREFIX_RE = re.compile(r"^[a-z_]+:[A-Za-z0-9_.:-]+$")


@dataclass
class _GraphDraft:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)

    def add_node(self, node_id: str, kind: str, label: str, provenance: dict[str, str], **data: Any) -> str:
        if node_id in self.nodes:
            existing = self.nodes[node_id]
            if existing["data"]["kind"] != kind:
                raise ValueError(f"node id collision across kinds: {node_id}")
            existing["provenance"] = _merge_provenance(existing["provenance"], [provenance])
            return node_id
        cleaned = {"id": node_id, "kind": kind, "label": str(label or node_id)}
        for key, value in data.items():
            if value is None or value == "" or value == []:
                continue
            cleaned[key] = value
        self.nodes[node_id] = {"data": cleaned, "position": {"x": 0.0, "y": 0.0}, "provenance": [provenance]}
        return node_id

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        provenance: dict[str, str],
    ) -> None:
        key = (source, target, relation)
        label = RELATION_LABELS[relation]
        if key in self.edges:
            # The same explicit fact stated twice stays one edge; provenance
            # records both statements.
            self.edges[key]["provenance"] = _merge_provenance(self.edges[key]["provenance"], [provenance])
            return
        edge_id = f"edge:{relation}:{source}->{target}"
        self.edges[key] = {
            "data": {
                "id": edge_id,
                "source": source,
                "target": target,
                "relation": relation,
                "label": label,
                "confirmation": "explicit",
            },
            "provenance": [provenance],
        }

    def add_unresolved(self, reason: str, **extra: Any) -> None:
        entry = {"reason": reason}
        for key, value in extra.items():
            if value:
                entry[key] = str(value)
        self.unresolved.append(entry)


def _merge_provenance(existing: list[dict[str, str]], additions: list[dict[str, str]]) -> list[dict[str, str]]:
    merged = {(entry.get("path"), entry.get("object_id"), entry.get("field")): entry for entry in existing}
    for entry in additions:
        merged.setdefault((entry.get("path"), entry.get("object_id"), entry.get("field")), entry)
    return [merged[key] for key in sorted(merged, key=lambda key: (key[0], key[1] or "", key[2] or ""))]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _input_digest(inputs: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(inputs).encode("utf-8")).hexdigest()


def _generated_at() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "")
    if epoch.isdigit():
        moment = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    else:
        moment = datetime.now(timezone.utc)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _archive_issue_path(issue_date: str) -> str:
    return f"archive/issues/{issue_date}/issue.json"


def _topic_node_id(topic_id: str) -> str:
    return f"topic:{topic_id}"


def _direction_node_id(direction_id: str) -> str:
    return f"direction:{direction_id}"


def _item_node_id(item_id: str) -> str:
    return f"item:{item_id}"


def _judgement_node_id(issue_date: str, digest: str) -> str:
    return f"judgement:{issue_date}:{digest}"


def _issue_node_id(issue_date: str) -> str:
    return f"issue:{issue_date}"


def _judgement_digest(issue_date: str, title: str, evidence_ids: list[str]) -> str:
    return stable_hash(issue_date, normalize_text(title), "\x1f".join(sorted(evidence_ids)), length=16)


def _collect_archive(draft: _GraphDraft, archive: PublishedArchive, dates: list[str]) -> None:
    source_levels: dict[str, str | None] = {}
    for issue_date in dates:
        published = archive.load_issue(issue_date)
        issue_path = _archive_issue_path(issue_date)
        draft.inputs["issues"][issue_date] = {
            "issue": published.issue,
            "papers": published.papers,
        }
        for row in published.papers:
            if isinstance(row, dict) and row.get("item_id"):
                source_levels[str(row["item_id"])] = row.get("source_level")

        draft.add_node(
            _issue_node_id(issue_date),
            "issue",
            issue_date,
            {"path": issue_path, "object_id": issue_date, "field": "date"},
            issue_date=issue_date,
            href=f"#archive?date={issue_date}",
        )

        for item in PublishedArchive.evidence(published):
            item_id = item["item_id"]
            topic_id = item["topic_id"]
            direction_id = item["direction_id"]
            if not topic_id or not direction_id:
                draft.add_unresolved(
                    "missing_item_direction",
                    source_ref=_item_node_id(item_id),
                    detail=f"{issue_date}:{item_id}",
                )
            else:
                draft.add_node(
                    _topic_node_id(topic_id),
                    "topic",
                    item["topic_name"] or topic_id,
                    {"path": issue_path, "object_id": topic_id, "field": "topic_id"},
                    topic_id=topic_id,
                )
                draft.add_node(
                    _direction_node_id(direction_id),
                    "direction",
                    item["direction_name"] or direction_id,
                    {"path": issue_path, "object_id": direction_id, "field": "direction_id"},
                    direction_id=direction_id,
                )
                draft.add_edge(
                    _topic_node_id(topic_id),
                    _direction_node_id(direction_id),
                    "has_direction",
                    {"path": issue_path, "object_id": item_id, "field": "topic_id/direction_id"},
                )
                draft.add_edge(
                    _direction_node_id(direction_id),
                    _item_node_id(item_id),
                    "has_item",
                    {"path": issue_path, "object_id": item_id, "field": "direction_id"},
                )
            item_node_id = _item_node_id(item_id)
            existing_item = draft.nodes.get(item_node_id)
            if existing_item is not None:
                # Same stable item id republished in a later issue: keep the
                # first classification, extend the coverage window, and keep
                # every provenance statement.
                existing_item["data"]["last_issue_date"] = max(
                    str(existing_item["data"].get("last_issue_date") or issue_date), issue_date
                )
                existing_item["provenance"] = _merge_provenance(
                    existing_item["provenance"],
                    [{"path": issue_path, "object_id": item_id, "field": "brief_item_id"}],
                )
            else:
                draft.add_node(
                    item_node_id,
                    "item",
                    item["title"] or item_id,
                    {"path": issue_path, "object_id": item_id, "field": "brief_item_id"},
                    topic_id=topic_id,
                    direction_id=direction_id,
                    issue_date=issue_date,
                    first_issue_date=issue_date,
                    last_issue_date=issue_date,
                    published_at=item.get("published_at"),
                    role=item["role"],
                    source_level=source_levels.get(item_id),
                    href=f"#archive?date={issue_date}&item={item_id}",
                )
            draft.add_edge(
                _item_node_id(item_id),
                _issue_node_id(issue_date),
                "published_in",
                {"path": issue_path, "object_id": item_id, "field": "items"},
            )

        for judgement in (published.issue.get("synthesis") or {}).get("judgements") or []:
            if not isinstance(judgement, dict):
                continue
            title = str(judgement.get("title") or "")
            evidence_ids = [str(value) for value in judgement.get("evidence_item_ids") or []]
            digest = _judgement_digest(issue_date, title, evidence_ids)
            judgement_id = _judgement_node_id(issue_date, digest)
            draft.add_node(
                judgement_id,
                "judgement",
                title or "未命名编辑判断",
                {"path": issue_path, "object_id": digest, "field": "synthesis.judgements[]"},
                issue_date=issue_date,
                body=str(judgement.get("body") or ""),
                evidence_item_ids=evidence_ids,
                href=f"#archive?date={issue_date}",
            )
            for ref in evidence_ids:
                if _item_node_id(ref) not in draft.nodes:
                    draft.add_unresolved(
                        "dangling_judgement_evidence",
                        source_ref=_item_node_id(ref),
                        target_ref=judgement_id,
                        detail=f"{issue_date}:{ref}",
                    )
                    continue
                draft.add_edge(
                    _item_node_id(ref),
                    judgement_id,
                    "supports_judgement",
                    {"path": issue_path, "field": "synthesis.judgements[].evidence_item_ids", "object_id": ref},
                )


def _load_knowledge_index(root: Path) -> dict[str, Any] | None:
    index = read_json(root / "knowledge" / "index.json", None)
    if not isinstance(index, dict):
        return None
    return index


def _collect_roadmaps(draft: _GraphDraft, root: Path, index: dict[str, Any]) -> None:
    for row in index.get("roadmaps") or []:
        if not isinstance(row, dict):
            continue
        topic_id = str(row.get("topic_id") or "")
        path = str(row.get("path") or f"knowledge/roadmaps/{topic_id}.json")
        roadmap = read_json(root / path, None)
        if not isinstance(roadmap, dict):
            draft.add_unresolved(
                "dangling_roadmap_evidence",
                source_ref=f"roadmap:{topic_id}",
                detail=f"missing roadmap file {path}",
            )
            continue
        draft.inputs["roadmaps"][path] = roadmap
        roadmap_id = f"roadmap:{topic_id}"
        draft.add_node(
            roadmap_id,
            "roadmap",
            str(roadmap.get("topic_name") or row.get("topic_name") or topic_id),
            {"path": path, "object_id": str(roadmap.get("roadmap_id") or topic_id), "field": "roadmap"},
            topic_id=topic_id,
            status=str(roadmap.get("view_mode") or ""),
            summary=str(roadmap.get("summary") or ""),
            issue_date=str(roadmap.get("updated_by_issue") or ""),
            href=f"#roadmaps?topic={topic_id}",
        )
        if topic_id:
            draft.add_node(
                _topic_node_id(topic_id),
                "topic",
                str(roadmap.get("topic_name") or topic_id),
                {"path": path, "object_id": topic_id, "field": "topic_id"},
                topic_id=topic_id,
            )
            draft.add_edge(
                roadmap_id,
                _topic_node_id(topic_id),
                "tracks",
                {"path": path, "object_id": topic_id, "field": "topic_id"},
            )
        for branch in roadmap.get("branches") or []:
            if not isinstance(branch, dict):
                continue
            branch_id = str(branch.get("branch_id") or "")
            if not branch_id:
                draft.add_unresolved(
                    "missing_branch_id",
                    source_ref=roadmap_id,
                    detail=f"{topic_id}:{branch.get('name') or 'unnamed branch'}",
                )
                continue
            branch_node = f"branch:{topic_id}:{branch_id}"
            draft.add_node(
                branch_node,
                "roadmap_branch",
                str(branch.get("name") or branch_id),
                {"path": path, "object_id": branch_id, "field": "branches[]"},
                topic_id=topic_id,
                branch_id=branch_id,
                status=str(branch.get("status") or ""),
                issue_date=str(roadmap.get("updated_by_issue") or ""),
                href=f"#roadmaps?topic={topic_id}&branch={branch_id}",
            )
            for direction_id in branch.get("direction_ids") or []:
                direction_id = str(direction_id or "")
                if not direction_id:
                    continue
                draft.add_node(
                    _direction_node_id(direction_id),
                    "direction",
                    direction_id,
                    {"path": path, "object_id": direction_id, "field": "branches[].direction_ids"},
                    direction_id=direction_id,
                )
                draft.add_edge(
                    branch_node,
                    _direction_node_id(direction_id),
                    "organizes",
                    {"path": path, "object_id": branch_id, "field": "branches[].direction_ids"},
                )
            evidence_refs: list[str] = []
            for ref in branch.get("evidence_item_ids") or []:
                evidence_refs.append(str(ref or ""))
            for event in branch.get("evidence_timeline") or []:
                if isinstance(event, dict):
                    evidence_refs.append(str(event.get("item_id") or ""))
            for ref in _dedupe(evidence_refs):
                if _item_node_id(ref) not in draft.nodes:
                    draft.add_unresolved(
                        "dangling_roadmap_evidence",
                        source_ref=branch_node,
                        target_ref=_item_node_id(ref),
                        detail=ref,
                    )
                    continue
                draft.add_edge(
                    branch_node,
                    _item_node_id(ref),
                    "uses_evidence",
                    {"path": path, "object_id": f"{branch_id}:{ref}", "field": "branches[].evidence_item_ids"},
                )


def _collect_ideas(draft: _GraphDraft, root: Path, index: dict[str, Any]) -> None:
    for row in index.get("ideas") or []:
        if not isinstance(row, dict):
            continue
        idea_id = str(row.get("idea_id") or "")
        if not idea_id:
            continue
        path = str(row.get("path") or f"knowledge/ideas/{idea_id}.json")
        idea = read_json(root / path, None)
        if not isinstance(idea, dict):
            draft.add_unresolved(
                "dangling_idea_evidence",
                source_ref=f"idea:{idea_id}",
                detail=f"missing idea file {path}",
            )
            continue
        draft.inputs["ideas"][path] = idea
        idea_node = f"idea:{idea_id}"
        draft.add_node(
            idea_node,
            "idea",
            str(idea.get("title") or row.get("title") or idea_id),
            {"path": path, "object_id": idea_id, "field": "idea"},
            status=str(idea.get("status") or ""),
            summary=str(idea.get("hypothesis") or idea.get("problem") or ""),
            issue_date=str(idea.get("last_updated_issue") or ""),
            href=f"#ideas?idea={idea_id}&view=overview",
        )
        for topic_id in idea.get("topic_ids") or []:
            topic_id = str(topic_id or "")
            if not topic_id:
                continue
            draft.add_node(
                _topic_node_id(topic_id),
                "topic",
                topic_id,
                {"path": path, "object_id": topic_id, "field": "topic_ids"},
                topic_id=topic_id,
            )
            draft.add_edge(
                idea_node,
                _topic_node_id(topic_id),
                "relates_to",
                {"path": path, "object_id": idea_id, "field": "topic_ids"},
            )
        for field_name, relation in (("evidence_for", "supports_idea"), ("evidence_against", "challenges_idea")):
            for entry in idea.get(field_name) or []:
                if isinstance(entry, str):
                    ref = entry
                else:
                    ref = str((entry or {}).get("item_id") or "")
                if not ref:
                    continue
                if _item_node_id(ref) not in draft.nodes:
                    draft.add_unresolved(
                        "dangling_idea_evidence",
                        source_ref=_item_node_id(ref),
                        target_ref=idea_node,
                        detail=ref,
                    )
                    continue
                draft.add_edge(
                    _item_node_id(ref),
                    idea_node,
                    relation,
                    {"path": path, "object_id": idea_id, "field": field_name},
                )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _assign_positions(draft: _GraphDraft) -> None:
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for node in draft.nodes.values():
        by_kind.setdefault(node["data"]["kind"], []).append(node)

    # Directions grouped beside their primary (first-seen) topic, packed in
    # compact sub-rows so the default structure lens fits readably.
    direction_topic: dict[str, str] = {}
    directions_by_topic: dict[str, list[dict[str, Any]]] = {}
    for (_, target, relation), edge in draft.edges.items():
        if relation == "has_direction":
            direction_topic.setdefault(target, edge["data"]["source"])
    orphans: list[dict[str, Any]] = []
    for node in by_kind.get("direction", []):
        topic = direction_topic.get(node["data"]["id"])
        if topic:
            directions_by_topic.setdefault(topic, []).append(node)
        else:
            orphans.append(node)

    topic_order = sorted(by_kind.get("topic", []), key=lambda node: node["data"]["id"])
    topic_y: dict[str, float] = {}
    cursor_y = 0.0
    for topic in topic_order:
        topic_y[topic["data"]["id"]] = cursor_y
        group = sorted(directions_by_topic.get(topic["data"]["id"], []), key=lambda node: node["data"]["id"])
        rows = max(1, math.ceil(len(group) / DIRECTIONS_PER_ROW)) if group else 0
        group_height = rows * KIND_ROW_HEIGHTS["direction"] + 24 if group else 0
        for index, node in enumerate(group):
            node["position"] = {
                "x": KIND_COLUMNS["direction"] + (index % DIRECTIONS_PER_ROW) * DIRECTION_COLUMN_GAP,
                "y": cursor_y + (index // DIRECTIONS_PER_ROW) * KIND_ROW_HEIGHTS["direction"],
            }
        cursor_y += max(KIND_ROW_HEIGHTS["topic"], group_height)
    orphan_y = cursor_y
    for index, node in enumerate(sorted(orphans, key=lambda node: node["data"]["id"])):
        node["position"] = {
            "x": KIND_COLUMNS["direction"] + (index % DIRECTIONS_PER_ROW) * DIRECTION_COLUMN_GAP,
            "y": orphan_y + (index // DIRECTIONS_PER_ROW) * KIND_ROW_HEIGHTS["direction"],
        }

    roadmap_by_id = {node["data"]["id"]: node for node in by_kind.get("roadmap", [])}
    for node in roadmap_by_id.values():
        topic_id = str(node["data"].get("topic_id") or "")
        node["position"] = {"x": KIND_COLUMNS["roadmap"], "y": topic_y.get(_topic_node_id(topic_id), 0.0)}
    for node in topic_order:
        node["position"] = {"x": KIND_COLUMNS["topic"], "y": topic_y[node["data"]["id"]]}

    items = sorted(
        by_kind.get("item", []),
        key=lambda node: (str(node["data"].get("issue_date") or ""), node["data"]["id"]),
    )
    for index, node in enumerate(items):
        node["position"] = {"x": KIND_COLUMNS["item"], "y": index * KIND_ROW_HEIGHTS["item"]}

    judgements = sorted(
        by_kind.get("judgement", []),
        key=lambda node: (str(node["data"].get("issue_date") or ""), node["data"]["id"]),
    )
    for index, node in enumerate(judgements):
        node["position"] = {
            "x": KIND_COLUMNS["judgement"] + (index // JUDGEMENTS_PER_COLUMN) * JUDGEMENT_COLUMN_GAP,
            "y": (index % JUDGEMENTS_PER_COLUMN) * KIND_ROW_HEIGHTS["judgement"],
        }

    issues = sorted(by_kind.get("issue", []), key=lambda node: node["data"]["id"])
    for index, node in enumerate(issues):
        node["position"] = {"x": KIND_COLUMNS["issue"], "y": index * KIND_ROW_HEIGHTS["issue"]}

    ideas = sorted(by_kind.get("idea", []), key=lambda node: node["data"]["id"])
    for index, node in enumerate(ideas):
        node["position"] = {"x": KIND_COLUMNS["idea"], "y": index * KIND_ROW_HEIGHTS["idea"]}

    branch_offset = cursor_y + BRANCH_BAND_GAP
    branches = sorted(by_kind.get("roadmap_branch", []), key=lambda node: node["data"]["id"])
    for index, node in enumerate(branches):
        node["position"] = {"x": KIND_COLUMNS["roadmap_branch"], "y": branch_offset + index * KIND_ROW_HEIGHTS["roadmap_branch"]}


def _node_sort_key(node: dict[str, Any]) -> tuple[Any, ...]:
    data = node["data"]
    return (
        KIND_RANK[data["kind"]],
        str(data.get("topic_id") or ""),
        str(data.get("direction_id") or ""),
        str(data.get("issue_date") or ""),
        data["id"],
    )


def _analyze_graph(draft: _GraphDraft) -> dict[str, Any]:
    """NetworkX build-time structure analysis: duplicates, dangling endpoints,
    relation endpoint kinds, self loops, and isolated-node reporting."""

    import networkx as nx

    graph = nx.MultiDiGraph()
    for node_id, node in draft.nodes.items():
        graph.add_node(node_id, kind=node["data"]["kind"])
    for (source, target, relation), edge in draft.edges.items():
        graph.add_edge(source, target, key=relation, relation=relation, edge_id=edge["data"]["id"])

    errors: list[str] = []
    if graph.number_of_nodes() != len(draft.nodes):
        errors.append(f"networkx node count mismatch: {graph.number_of_nodes()} != {len(draft.nodes)}")
    if graph.number_of_edges() != len(draft.edges):
        errors.append(f"networkx edge count mismatch: {graph.number_of_edges()} != {len(draft.edges)}")
    for source, target in graph.edges():
        if source == target:
            errors.append(f"self loop edge: {source}")
    for source, target, relation in graph.edges(keys=True):
        if source not in draft.nodes or target not in draft.nodes:
            errors.append(f"dangling edge endpoints: {relation} {source}->{target}")
            continue
        source_kind = draft.nodes[source]["data"]["kind"]
        target_kind = draft.nodes[target]["data"]["kind"]
        expected = RELATION_ENDPOINTS.get(relation)
        if expected and (source_kind, target_kind) != expected:
            errors.append(
                f"relation kind mismatch: {relation} requires {expected[0]}->{expected[1]}, "
                f"found {source_kind}->{target_kind} ({source}->{target})"
            )
        if relation not in RELATION_ENDPOINTS:
            errors.append(f"unknown relation: {relation}")
    isolated = sorted(nx.isolates(graph))
    return {
        "errors": errors,
        "isolated": isolated,
        "components": nx.number_weakly_connected_components(graph),
    }


def build_knowledge_graph(root: Path, *, issue_date: str | None = None) -> dict[str, Any]:
    """Build the full derived graph document deterministically from inputs."""

    root = Path(root)
    archive = PublishedArchive(root)
    dates = archive.issue_dates()
    if issue_date is not None:
        if issue_date not in dates:
            raise ValueError(f"issue is not published in archive/index.json: {issue_date}")
        dates = [date for date in dates if date <= issue_date]

    draft = _GraphDraft()
    draft.inputs = {"archive_index": read_json(root / "archive" / "index.json", {}), "issues": {}, "roadmaps": {}, "ideas": {}}
    _collect_archive(draft, archive, dates)

    knowledge_index = _load_knowledge_index(root)
    knowledge_dates: list[str] = []
    if knowledge_index is not None:
        # A structurally valid graph built from schema-invalid or semantically
        # invalid knowledge inputs would still be a broken publication, so the
        # full store validation runs before any graph node is derived.
        store_errors = validate_knowledge_store(root)
        if store_errors:
            raise ValueError(
                "knowledge store failed validation before graph build:\n  " + "\n  ".join(store_errors)
            )
        draft.inputs["knowledge_index"] = knowledge_index
        for row in knowledge_index.get("roadmaps") or []:
            if isinstance(row, dict) and row.get("updated_by_issue"):
                knowledge_dates.append(str(row["updated_by_issue"]))
        for row in knowledge_index.get("ideas") or []:
            if isinstance(row, dict) and row.get("last_updated_issue"):
                knowledge_dates.append(str(row["last_updated_issue"]))
        _collect_roadmaps(draft, root, knowledge_index)
        _collect_ideas(draft, root, knowledge_index)

    archive_through = dates[-1] if dates else ""
    knowledge_through = max(knowledge_dates) if knowledge_dates else ""

    for node_id in draft.nodes:
        if not _ID_PREFIX_RE.match(node_id):
            raise ValueError(f"node id violates kind-prefixed stable id contract: {node_id}")

    analysis = _analyze_graph(draft)
    if analysis["errors"]:
        raise ValueError("graph structure analysis failed:\n  " + "\n  ".join(analysis["errors"]))
    if len(draft.unresolved) > MAX_UNRESOLVED:
        raise ValueError(
            f"unresolved explicit references exceed the allowed budget: {len(draft.unresolved)} > {MAX_UNRESOLVED}"
        )

    _assign_positions(draft)

    nodes = sorted(draft.nodes.values(), key=_node_sort_key)
    edges = sorted(draft.edges.values(), key=lambda edge: (edge["data"]["relation"], edge["data"]["source"], edge["data"]["target"]))
    unresolved = sorted(draft.unresolved, key=lambda entry: _canonical_json(entry))

    document = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _generated_at(),
        "archive_through_issue": archive_through,
        "knowledge_through_issue": knowledge_through,
        "input_digest": _input_digest(draft.inputs),
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "unresolved_count": len(unresolved),
        },
        "nodes": nodes,
        "edges": edges,
        "unresolved": unresolved,
    }
    _validate_document(root, document)
    return document


def graph_schema_errors(root: Path, document: Any) -> list[str]:
    schema = read_json(Path(root) / "schemas" / GRAPH_SCHEMA_NAME)
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda error: list(error.path))
    return [f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors]


def _validate_document(root: Path, document: dict[str, Any]) -> None:
    errors = graph_schema_errors(root, document)
    if errors:
        raise ValueError("knowledge graph schema validation failed:\n  " + "\n  ".join(errors))
    node_ids = {node["data"]["id"] for node in document["nodes"]}
    if len(node_ids) != len(document["nodes"]):
        raise ValueError("duplicate node ids in graph document")
    edge_ids = {edge["data"]["id"] for edge in document["edges"]}
    if len(edge_ids) != len(document["edges"]):
        raise ValueError("duplicate edge ids in graph document")
    for edge in document["edges"]:
        data = edge["data"]
        if data["source"] not in node_ids or data["target"] not in node_ids:
            raise ValueError(f"edge endpoint missing from node set: {data['id']}")
        if data["label"] != RELATION_LABELS.get(data["relation"]):
            raise ValueError(f"edge label diverges from relation contract: {data['id']}")
    stats = document["stats"]
    if stats["node_count"] != len(document["nodes"]) or stats["edge_count"] != len(document["edges"]):
        raise ValueError("stats counts do not match document arrays")
    if stats["unresolved_count"] != len(document["unresolved"]):
        raise ValueError("unresolved count does not match document array")


def build_knowledge_graph_file(root: Path, *, issue_date: str | None = None) -> dict[str, Any]:
    """Build and atomically replace knowledge/graph.json. A failed build never
    overwrites the previous valid document."""

    root = Path(root)
    document = build_knowledge_graph(root, issue_date=issue_date)
    write_json_atomic(root / GRAPH_RELATIVE_PATH, document)
    return document


def validate_knowledge_graph(root: Path) -> list[str]:
    """Validate the committed graph document against current inputs.

    Freshness is gated by rebuilding from the authoritative inputs and comparing
    every stable field; only ``generated_at`` may differ."""

    root = Path(root)
    path = root / GRAPH_RELATIVE_PATH
    existing = read_json(path, None)
    if not isinstance(existing, dict):
        return [f"{GRAPH_RELATIVE_PATH}: missing or invalid JSON"]
    errors = graph_schema_errors(root, existing)
    if errors:
        return [f"{GRAPH_RELATIVE_PATH}: {error}" for error in errors]
    try:
        fresh = build_knowledge_graph(root)
    except Exception as error:  # noqa: BLE001 - report, do not crash validation
        return [f"rebuild failed: {error}"]
    for key in (
        "schema_version",
        "archive_through_issue",
        "knowledge_through_issue",
        "input_digest",
        "stats",
        "nodes",
        "edges",
        "unresolved",
    ):
        if existing.get(key) != fresh.get(key):
            errors.append(f"{GRAPH_RELATIVE_PATH}: {key} is stale relative to current archive/knowledge inputs")
    return errors


def _install_cli() -> None:
    from . import cli

    if getattr(cli, "_knowledge_graph_installed", False):
        return
    original_build_parser = cli.build_parser

    def cmd_graph(args: argparse.Namespace) -> int:
        root = Path(args.root).resolve() if getattr(args, "root", None) else cli.discover_root()
        if args.graph_action == "build":
            document = build_knowledge_graph_file(root, issue_date=getattr(args, "issue", None))
            print(
                json.dumps(
                    {
                        "written": str((root / GRAPH_RELATIVE_PATH).relative_to(root)),
                        "archive_through_issue": document["archive_through_issue"],
                        "knowledge_through_issue": document["knowledge_through_issue"],
                        "input_digest": document["input_digest"],
                        **document["stats"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if args.graph_action == "validate":
            errors = validate_knowledge_graph(root)
            print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
            return 1 if errors else 0
        raise ValueError(f"unsupported knowledge graph action: {args.graph_action}")

    def build_parser():
        parser = original_build_parser()
        top = next(
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        )
        knowledge_parser = top.choices.get("knowledge")
        if knowledge_parser is None:
            return parser
        knowledge_actions = next(
            action
            for action in knowledge_parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        graph_parser = knowledge_actions.add_parser("graph", help="build or validate the derived knowledge graph")
        graph_sub = graph_parser.add_subparsers(dest="graph_action", required=True)
        build_cmd = graph_sub.add_parser("build", help="regenerate knowledge/graph.json deterministically")
        build_cmd.add_argument("--issue", default=None, help="build only through this published issue date")
        build_cmd.set_defaults(func=cmd_graph)
        validate_cmd = graph_sub.add_parser("validate", help="compare graph.json against current inputs")
        validate_cmd.set_defaults(func=cmd_graph)
        return parser

    cli.build_parser = build_parser
    cli._knowledge_graph_installed = True


def install_knowledge_graph() -> None:
    _install_cli()
