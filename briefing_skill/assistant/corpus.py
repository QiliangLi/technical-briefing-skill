"""Published corpus for the group assistant index.

Only published records are read: archived issues with the reader cards written
for them, their radar records and the materialized Roadmap/Idea files. Candidates, full-text caches and run
directories are never indexed, so anything the assistant can cite is public.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# Bumping this changes the input digest and forces every deployment to rebuild.
INDEXER_VERSION = 3


def _text(value: Any) -> str:
    return str(value or "").replace("\x00", "").replace("\r\n", "\n").strip()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _item_doc(item: dict[str, Any], card: dict[str, Any] | None, date: str, base: str) -> dict[str, Any] | None:
    """A briefing item together with the reader card written for it.

    The machine fields say what was found; the card's ``lead`` says it in the
    words a reader sees. Both are published and checked, so a reply may quote
    either without a model writing anything.
    """

    item_id = _text(item.get("brief_item_id"))
    title = _text(item.get("title"))
    if not item_id or not title:
        return None
    keywords = [_text(keyword) for keyword in item.get("keywords") or []]
    conclusion = _text(item.get("core_conclusion"))
    lead = _text(card.get("lead")) if card else ""
    mechanism, result = _text(item.get("mechanism")), _text(item.get("result"))
    boundary, relevance = _text(item.get("boundary")), _text(item.get("project_relevance"))
    return {
        "id": f"item:{item_id}",
        "kind": "item",
        "title": title,
        "headline": _text(card.get("title")) if card and card.get("title") else title,
        "search": " ".join([title] * 3 + keywords * 3 + [lead, conclusion, mechanism, result, boundary]),
        "summary": conclusion,
        "lead": lead or conclusion,
        "result": result,
        "boundary": boundary,
        "project_relevance": relevance,
        "issue_date": date,
        "url": f"{base}#archive?date={date}&item={item_id}",
        "topic_id": _text(item.get("topic_id")),
        "direction_id": _text(item.get("direction_id")),
    }


def _plain(doc: dict[str, Any]) -> dict[str, Any]:
    """Give a document without a reader card the same citation fields as an item."""

    return {
        **doc,
        "headline": doc["title"],
        "lead": doc.get("summary") or "",
        "result": "",
        "boundary": "",
        "project_relevance": "",
    }


def _radar_doc(record: dict[str, Any], base: str) -> dict[str, Any] | None:
    key = _text(record.get("paper_key"))
    title = _text(record.get("title"))
    if not key or not title:
        return None
    date = _text(record.get("issue_date"))
    return _plain({
        "id": f"radar:{key}",
        "kind": "radar",
        "title": title,
        "search": " ".join([title] * 3 + [_text(record.get("topic_name")), _text(record.get("direction_name"))]),
        "summary": "",
        "issue_date": date,
        "url": f"{base}#archive?date={date}",
        "topic_id": _text(record.get("topic_id")),
        "direction_id": _text(record.get("direction_id")),
    })


def _idea_doc(idea: dict[str, Any], base: str) -> dict[str, Any] | None:
    idea_id = _text(idea.get("idea_id"))
    title = _text(idea.get("title"))
    if not idea_id or not title:
        return None
    return _plain({
        "id": f"idea:{idea_id}",
        "kind": "idea",
        "title": title,
        "search": " ".join(
            [title] * 3
            + [_text(idea.get("problem")), _text(idea.get("hypothesis")), _text(idea.get("mechanism"))]
        ),
        "summary": _text(idea.get("hypothesis")),
        "issue_date": _text(idea.get("first_seen_issue")),
        "url": f"{base}#ideas?idea={idea_id}",
        "topic_id": next(iter(idea.get("topic_ids") or []), ""),
        "direction_id": "",
        "status": _text(idea.get("status")),
    })


def _roadmap_doc(roadmap: dict[str, Any], base: str) -> dict[str, Any] | None:
    topic_id = _text(roadmap.get("topic_id"))
    title = _text(roadmap.get("topic_name"))
    if not topic_id or not title:
        return None
    branches = roadmap.get("branches") or []
    parts = [title] * 3 + [_text(roadmap.get("summary"))]
    for branch in branches:
        parts.append(_text(branch.get("name")))
        parts.extend(_text(question) for question in branch.get("open_questions") or [])
    return _plain({
        "id": f"roadmap:{topic_id}",
        "kind": "roadmap",
        "title": title,
        "search": " ".join(parts),
        "summary": _text(roadmap.get("summary")),
        "issue_date": _text(roadmap.get("updated_by_issue")),
        "url": f"{base}#roadmaps?topic={topic_id}",
        "topic_id": topic_id,
        "direction_id": "",
    })


def _judgement_doc(judgement: dict[str, Any], date: str, base: str, number: int) -> dict[str, Any] | None:
    """One of an issue's judgements: a digest of what changed that a reader can cite."""

    title = _text(judgement.get("title"))
    body = _text(judgement.get("body"))
    if not title or not body:
        return None
    return _plain({
        "id": f"judgement:{date}:{number}",
        "kind": "judgement",
        "title": title,
        "search": " ".join([title] * 3 + [body]),
        "summary": body,
        "issue_date": date,
        "url": f"{base}#archive?date={date}",
        "topic_id": "",
        "direction_id": "",
    })


def load_corpus(root: Path, site_base_url: str) -> tuple[list[dict[str, Any]], list[Path]]:
    """Return indexable documents in a stable order plus every input file read."""

    base = site_base_url.rstrip("/") + "/"
    index_path = root / "archive" / "index.json"
    if not index_path.exists():
        return [], []
    inputs = [index_path]
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(doc: dict[str, Any] | None) -> None:
        if doc and doc["id"] not in seen:
            seen.add(doc["id"])
            docs.append(doc)

    index = _load(index_path)
    for issue in sorted(index.get("issues") or [], key=lambda row: str(row.get("date") or "")):
        date = _text(issue.get("date"))
        issue_dir = root / "archive" / "issues" / date
        reader_path = issue_dir / "reader.json"
        reader = _load(reader_path) if reader_path.exists() else {}
        cards = reader.get("items") or {}
        issue_path = issue_dir / "issue.json"
        if issue_path.exists():
            inputs.append(issue_path)
            for item in _load(issue_path).get("items") or []:
                add(_item_doc(item, cards.get(_text(item.get("brief_item_id"))), date, base))
        if reader_path.exists():
            inputs.append(reader_path)
            for number, judgement in enumerate(reader.get("judgements") or []):
                add(_judgement_doc(judgement, date, base, number))
        papers_rel = _text(issue.get("papers_file"))
        papers_path = (root / "archive" / papers_rel) if papers_rel else None
        if papers_path is not None and papers_path.exists():
            inputs.append(papers_path)
            for record in _load(papers_path):
                if record.get("role") == "radar":
                    add(_radar_doc(record, base))
    for path in sorted((root / "knowledge" / "ideas").glob("*.json")):
        inputs.append(path)
        add(_idea_doc(_load(path), base))
    for path in sorted((root / "knowledge" / "roadmaps").glob("*.json")):
        inputs.append(path)
        add(_roadmap_doc(_load(path), base))
    return docs, inputs


def input_digest(root: Path, inputs: list[Path], site_base_url: str) -> str:
    """Digest of everything that can change the index content."""

    digest = hashlib.sha256()
    digest.update(f"v{INDEXER_VERSION}\n{site_base_url}\n".encode("utf-8"))
    for path in inputs:
        digest.update(f"{path.relative_to(root)}\n{_file_digest(path)}\n".encode("utf-8"))
    return digest.hexdigest()[:32]
