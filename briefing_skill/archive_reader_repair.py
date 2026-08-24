"""Repair current-run reader sidecars from the immutable sent HTML.

The expanded issue can be rebuilt after the reader task was completed (for
example when a topic floor promotes historical supplements). In that case the
sent HTML is still the polished artifact recipients saw, while the sidecar
set may lag behind the final issue selection. This module only fills or
replaces sidecars for the final issue IDs and binds every result to the
canonical machine-item hash; it never changes the sent HTML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from .archive_reader import _items
from .reader_projection import CONTRACT_VERSION, machine_item_hash
from .utils import read_json, write_json


class ReaderSidecarRepairError(RuntimeError):
    """Raised when a sent item cannot be projected safely into a sidecar."""


_HEADING_KEYS = {
    "机制": "mechanism",
    "证据": "result",
    "结果": "result",
    "边界": "boundary",
    "启发": "implication",
    "关键结果": "result",
    "实际改了什么": "engineering",
}


def _text(node: Tag | None) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _labeled_divs(node: Tag) -> list[tuple[str | None, str]]:
    rows: list[tuple[str | None, str]] = []
    for div in node.find_all("div", recursive=False):
        label = div.find("b", recursive=False)
        if not label:
            continue
        label_text = _text(label).rstrip("：:")
        full = _text(div)
        label_value = _text(label)
        body = full[len(label_value) :].lstrip(" ：:") if full.startswith(label_value) else full
        if body:
            rows.append((_HEADING_KEYS.get(label_text), body))
    return rows


def _item_prose(node: Tag, item_id: str) -> dict[str, Any]:
    title = _text(node.find(["h1", "h2", "h3"]))
    if not title:
        raise ReaderSidecarRepairError(f"{item_id}: sent HTML item has no title")

    # Current reader projection markup carries explicit block markers. Prefer
    # them because they preserve the already-polished wording and section
    # semantics exactly.
    marked = node.find_all("p", attrs={"data-reader-block": "1"})
    blocks: list[dict[str, str | None]] = []
    if marked:
        for paragraph in marked:
            text = _text(paragraph)
            if not text:
                continue
            heading: str | None = None
            section = paragraph.find_previous(
                attrs={"data-reader-section-heading": "1"}
            )
            if section is not None and section.parent is node:
                heading = str(section.get("data-reader-section-role") or "").strip() or None
            blocks.append({"heading_key": heading, "text": text})
    else:
        lead_node = node.find("p", recursive=False)
        lead = _text(lead_node)
        if lead:
            blocks.append({"heading_key": None, "text": lead})
        for heading, text in _labeled_divs(node):
            blocks.append({"heading_key": heading, "text": text})

    if not blocks:
        raise ReaderSidecarRepairError(f"{item_id}: sent HTML item has no reader prose")

    lead = str(blocks[0]["text"])
    body_blocks = blocks[1:]
    # The archive contract intentionally keeps a compact body. If a legacy
    # email has four labeled slots, retain every sentence by folding the tail
    # into the final body/block rather than dropping evidence or boundaries.
    if len(body_blocks) > 3:
        tail = body_blocks[2:]
        body_blocks = body_blocks[:2] + [
            {
                "heading_key": body_blocks[2].get("heading_key"),
                "text": "；".join(str(row["text"]) for row in tail),
            }
        ]
    body = [str(row["text"]) for row in body_blocks]
    compact_blocks = [{"heading_key": row.get("heading_key"), "text": str(row["text"])} for row in body_blocks]
    compact_blocks.insert(0, {"heading_key": None, "text": lead})
    return {
        "reader_version": CONTRACT_VERSION,
        "reader_shape": "blocks_v2",
        "title": title,
        "blocks": compact_blocks[:3],
        "lead": lead,
        "body": body[:3],
        "takeaway": None,
        "used_fields": ["core_conclusion", "mechanism", "result"],
    }


def _sidecar_is_current(sidecar: dict[str, Any], run_id: str, expected_hash: str) -> bool:
    provenance = sidecar.get("_provenance") or {}
    return (
        int(sidecar.get("reader_version") or 0) == CONTRACT_VERSION
        and str(provenance.get("run_id") or "") == run_id
        and str(provenance.get("source_item_hash") or "") == expected_hash
    )


def repair_reader_sidecars_from_sent_html(root: Path, run_id: str) -> list[str]:
    """Ensure every final issue item has a valid current-run sidecar.

    Existing hash-valid sidecars are left byte-for-byte untouched. Missing or
    stale sidecars are reconstructed from the exact sent ``email.html`` and
    receive a fresh provenance binding to the final issue item.
    """

    run_dir = root / "workspace" / "runs" / run_id
    issue = read_json(run_dir / "issue" / "issue.json", {})
    html_path = run_dir / "email.html"
    if not issue or not html_path.is_file():
        raise ReaderSidecarRepairError(f"{run_id}: issue.json and email.html are required")
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    repaired: list[str] = []
    for _, item in _items(issue):
        item_id = str(item.get("brief_item_id") or "").strip()
        if not item_id:
            raise ReaderSidecarRepairError(f"{run_id}: issue item is missing brief_item_id")
        expected_hash = machine_item_hash(item)
        sidecar_path = run_dir / "reader_items" / f"{item_id}.json"
        existing = read_json(sidecar_path, {})
        if _sidecar_is_current(existing, run_id, expected_hash):
            continue
        node = soup.find(id=f"item-{item_id}")
        if not isinstance(node, Tag):
            raise ReaderSidecarRepairError(f"{item_id}: sent HTML has no matching item anchor")
        sidecar = _item_prose(node, item_id)
        sidecar["brief_item_id"] = item_id
        sidecar["_provenance"] = {
            "run_id": run_id,
            "source_item_hash": expected_hash,
            "reader_contract_version": CONTRACT_VERSION,
            "cache_scope": "current_run_only",
            "repair_source": "sent_html",
        }
        write_json(sidecar_path, sidecar)
        repaired.append(item_id)
    return repaired
