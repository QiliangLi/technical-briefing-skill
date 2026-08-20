from __future__ import annotations

import hashlib
import json
import re
import shutil
from html import escape
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .reader_projection import CONTRACT_VERSION, NUMBER_RE, machine_item_hash
from .utils import read_json, stable_hash, write_json


ARCHIVE_CONTRACT_VERSION = 1
READER_SCHEMA_VERSION = 1


def _canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def issue_hash(issue: dict[str, Any]) -> str:
    """Hash the complete published machine document, not its reader projection."""

    return _sha256_bytes(_canonical_json(issue).encode("utf-8"))


def _generated_at(issue: dict[str, Any]) -> str:
    value = str(issue.get("generated_at") or "").strip()
    if value:
        return value
    run_id = str(issue.get("run_id") or "")
    match = re.match(r"^(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})(\d{2})$", run_id)
    if match:
        return f"{match.group(1)}T{match.group(2)}:{match.group(3)}:{match.group(4)}+08:00"
    issue_date = str(issue.get("date_to") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", issue_date):
        return f"{issue_date}T00:00:00+08:00"
    raise ValueError("issue has neither a valid run timestamp nor report date")


def _items(issue: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for role, key in (("core", "core_items"), ("supplement", "observations")):
        for item in issue.get(key) or []:
            rows.append((role, item))
    return rows


def _sources(item: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(source) for source in item.get("sources") or []]


def _reader_item(role: str, item: dict[str, Any], prose: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_item_hash": str(
            (prose.get("_provenance") or {}).get("source_item_hash")
            or machine_item_hash(item)
        ),
        "role": role,
        "topic_id": item.get("topic_id"),
        "direction_id": item.get("direction_id"),
        "published_at": item.get("published_at"),
        "score": item.get("score"),
        "sources": _sources(item),
        "title": str(prose.get("title") or "").strip(),
        "lead": str(prose.get("lead") or "").strip(),
        "body": [str(value or "").strip() for value in prose.get("body") or []],
        "takeaway": (str(prose.get("takeaway") or "").strip() or None),
    }


def _judgements(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for judgement in value or []:
        if isinstance(judgement, str):
            rows.append({"title": "", "body": judgement, "evidence_item_ids": []})
        elif isinstance(judgement, dict):
            rows.append(
                {
                    "title": str(judgement.get("title") or ""),
                    "body": str(judgement.get("body") or judgement.get("text") or ""),
                    "evidence_item_ids": [
                        str(item_id) for item_id in judgement.get("evidence_item_ids") or []
                    ],
                }
            )
    return rows


def _radar(issue: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, signal in enumerate((issue.get("synthesis") or {}).get("radar_signals") or [], 1):
        source_urls = [str(url) for url in signal.get("source_urls") or []]
        result.append(
            {
                "radar_id": stable_hash("archive-radar", index, *source_urls),
                "source_signal_hash": _sha256_bytes(_canonical_json(signal).encode("utf-8")),
                "category": str(signal.get("category") or ""),
                "signal": str(signal.get("signal") or ""),
                "summary": str(signal.get("summary") or ""),
                "source_urls": source_urls,
            }
        )
    return result


def build_reader_from_run(root: Path, run_id: str, issue: dict[str, Any]) -> dict[str, Any]:
    """Build an archive reader document from current-run, hash-bound sidecars."""

    run_dir = root / "workspace" / "runs" / run_id
    sidecars: dict[str, dict[str, Any]] = {}
    machine_hashes = {
        machine_item_hash(read_json(path, {}))
        for path in (run_dir / "items").glob("*.json")
    }
    for role, item in _items(issue):
        item_id = str(item.get("brief_item_id") or "")
        if not item_id:
            raise ValueError("published item is missing brief_item_id")
        sidecar = read_json(run_dir / "reader_items" / f"{item_id}.json", {})
        provenance = sidecar.get("_provenance") or {}
        source_hash = str(provenance.get("source_item_hash") or "")
        if int(sidecar.get("reader_version") or 0) != CONTRACT_VERSION:
            raise ValueError(f"{item_id}: reader sidecar version is missing or stale")
        if str(provenance.get("run_id") or "") != run_id:
            raise ValueError(f"{item_id}: reader sidecar belongs to another run")
        expected_hash = machine_item_hash(item)
        if not source_hash or source_hash not in machine_hashes:
            raise ValueError(f"{item_id}: reader sidecar is not bound to a current machine item")
        if source_hash != expected_hash:
            raise ValueError(f"{item_id}: reader sidecar is bound to a different machine item")
        sidecars[item_id] = _reader_item(role, item, sidecar)

    synthesis = issue.get("synthesis") or {}
    reader = {
        "schema_version": READER_SCHEMA_VERSION,
        "reader_contract_version": CONTRACT_VERSION,
        "source_issue_hash": issue_hash(issue),
        "issue_date": str(issue.get("date_to") or ""),
        "headline": str(synthesis.get("headline") or ""),
        "judgements": _judgements(synthesis.get("judgements")),
        "watch_next": [str(value) for value in synthesis.get("watch_next") or []],
        "items": sidecars,
        "radar": _radar(issue),
        "generated_at": _generated_at(issue),
        "rewrite_status": "current_run_reader_projection",
    }
    validate_reader_document(root, issue, reader, require_current_sidecar=True)
    return reader


def prepare_rewrite_payload(issue: dict[str, Any]) -> dict[str, Any]:
    """Create one bounded historical rewrite input without claiming it is output."""

    machine_items = []
    locked_items: dict[str, dict[str, Any]] = {}
    for role, item in _items(issue):
        item_id = str(item.get("brief_item_id") or "")
        if not item_id:
            raise ValueError("published item is missing brief_item_id")
        machine_items.append(
            {
                "brief_item_id": item_id,
                "role": role,
                "source_item_hash": machine_item_hash(item),
                "machine_item": item,
            }
        )
        locked_items[item_id] = {
            "source_item_hash": machine_item_hash(item),
            "role": role,
            "topic_id": item.get("topic_id"),
            "direction_id": item.get("direction_id"),
            "published_at": item.get("published_at"),
            "score": item.get("score"),
            "sources": _sources(item),
        }
    synthesis = issue.get("synthesis") or {}
    locked_radar = _radar(issue)
    return {
        "_task": {
            "task_type": "archive_reader_rewrite",
            "reader_contract_version": CONTRACT_VERSION,
            "source_issue_hash": issue_hash(issue),
            "output_schema": "schemas/archive-reader.schema.json",
            "prompt": "prompts/archive-reader-rewrite.md",
        },
        "issue": {
            "run_id": issue.get("run_id"),
            "issue_date": issue.get("date_to"),
            "synthesis": issue.get("synthesis") or {},
            "items": machine_items,
        },
        "locked_output": {
            "schema_version": READER_SCHEMA_VERSION,
            "reader_contract_version": CONTRACT_VERSION,
            "source_issue_hash": issue_hash(issue),
            "issue_date": str(issue.get("date_to") or ""),
            "generated_at": _generated_at(issue),
            "rewrite_status": "historical_semantic_rewrite",
            "judgement_evidence_item_ids": [
                row["evidence_item_ids"] for row in _judgements(synthesis.get("judgements"))
            ],
            "items": locked_items,
            "radar": [
                {
                    key: row[key]
                    for key in ("radar_id", "source_signal_hash", "category", "source_urls")
                }
                for row in locked_radar
            ],
        },
        "constraints": {
            "expression_only": True,
            "do_not_add_or_remove_items": True,
            "preserve_ids_roles_dates_scores_sources_and_urls": True,
            "do_not_introduce_numbers": True,
            "radar_is_unverified_signal": True,
            "one_published_issue_only": True,
        },
    }


def _schema(root: Path) -> dict[str, Any]:
    return read_json(root / "schemas" / "archive-reader.schema.json", {})


def _numbers(value: Any) -> set[str]:
    return set(NUMBER_RE.findall(_canonical_json(value)))


def validate_reader_document(
    root: Path,
    issue: dict[str, Any],
    reader: dict[str, Any],
    *,
    require_current_sidecar: bool = False,
) -> None:
    schema_errors = sorted(
        Draft202012Validator(_schema(root)).iter_errors(reader),
        key=lambda error: tuple(str(value) for value in error.path),
    )
    if schema_errors:
        error = schema_errors[0]
        location = ".".join(str(value) for value in error.path) or "$"
        raise ValueError(f"reader schema error at {location}: {error.message}")
    if int(reader.get("schema_version") or 0) != READER_SCHEMA_VERSION:
        raise ValueError("unsupported reader schema_version")
    if int(reader.get("reader_contract_version") or 0) != CONTRACT_VERSION:
        raise ValueError("reader_contract_version does not match the current contract")
    if str(reader.get("source_issue_hash") or "") != issue_hash(issue):
        raise ValueError("reader source_issue_hash does not match issue.json")
    if str(reader.get("issue_date") or "") != str(issue.get("date_to") or ""):
        raise ValueError("reader issue_date changed")
    if str(reader.get("generated_at") or "") != _generated_at(issue):
        raise ValueError("reader generated_at must use the deterministic locked value")

    machine = {str(item.get("brief_item_id") or ""): (role, item) for role, item in _items(issue)}
    output_items = reader.get("items") or {}
    if set(output_items) != set(machine):
        missing = sorted(set(machine) - set(output_items))
        unknown = sorted(set(output_items) - set(machine))
        raise ValueError(f"reader item IDs changed: missing={missing} unknown={unknown}")
    for item_id, output in output_items.items():
        role, item = machine[item_id]
        if output.get("role") != role:
            raise ValueError(f"{item_id}: role changed")
        for field in ("topic_id", "direction_id", "published_at", "score"):
            if output.get(field) != item.get(field):
                raise ValueError(f"{item_id}: {field} changed")
        if output.get("sources") != _sources(item):
            raise ValueError(f"{item_id}: sources changed")
        expected_hash = machine_item_hash(item)
        if not require_current_sidecar and str(output.get("source_item_hash") or "") != expected_hash:
            raise ValueError(f"{item_id}: source_item_hash changed")
        prose = {
            key: output.get(key)
            for key in ("title", "lead", "body", "takeaway")
        }
        invented = sorted(_numbers(prose) - _numbers(item))
        if invented:
            raise ValueError(f"{item_id}: reader text introduces numbers {invented}")

    synthesis = issue.get("synthesis") or {}
    top_reader = {
        "headline": reader.get("headline"),
        "judgements": reader.get("judgements"),
        "watch_next": reader.get("watch_next"),
    }
    top_machine = {
        "headline": synthesis.get("headline"),
        "judgements": synthesis.get("judgements"),
        "watch_next": synthesis.get("watch_next"),
    }
    invented = sorted(_numbers(top_reader) - _numbers(top_machine))
    if invented:
        raise ValueError(f"reader synthesis introduces numbers {invented}")
    source_judgements = _judgements(synthesis.get("judgements"))
    output_judgements = reader.get("judgements") or []
    if len(source_judgements) != len(output_judgements):
        raise ValueError("reader judgement count changed")
    for index, (source, output) in enumerate(zip(source_judgements, output_judgements), 1):
        if output.get("evidence_item_ids") != source.get("evidence_item_ids"):
            raise ValueError(f"judgement {index}: evidence_item_ids changed")
    if len(reader.get("watch_next") or []) != len(synthesis.get("watch_next") or []):
        raise ValueError("reader watch_next count changed")

    source_radar = _radar(issue)
    if len(reader.get("radar") or []) != len(source_radar):
        raise ValueError("reader radar count changed")
    for source, output in zip(source_radar, reader.get("radar") or []):
        for field in ("radar_id", "source_signal_hash", "category", "source_urls"):
            if output.get(field) != source.get(field):
                raise ValueError(f"{source['radar_id']}: radar {field} changed")
        invented = sorted(
            _numbers({"signal": output.get("signal"), "summary": output.get("summary")})
            - _numbers({"signal": source.get("signal"), "summary": source.get("summary")})
        )
        if invented:
            raise ValueError(f"{source['radar_id']}: radar text introduces numbers {invented}")


def backup_original_html(issue_dir: Path) -> dict[str, str]:
    """Copy every actually present legacy variant once; never infer a missing one."""

    originals: dict[str, str] = {}
    original_dir = issue_dir / "original"
    for name in ("email.html", "email-illustrated.html"):
        source = issue_dir / name
        if not source.is_file():
            continue
        target = original_dir / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        originals[name] = _sha256_file(target)
    return originals


def existing_original_html(issue_dir: Path) -> dict[str, str]:
    return {
        name: _sha256_file(issue_dir / "original" / name)
        for name in ("email.html", "email-illustrated.html")
        if (issue_dir / "original" / name).is_file()
    }


def _render_paragraphs(values: list[str]) -> str:
    return "".join(f"<p>{escape(str(value))}</p>" for value in values if str(value).strip())


def render_public_html(issue: dict[str, Any], reader: dict[str, Any]) -> str:
    """Render a deterministic, email-safe public view from reader.json."""

    item_parts: list[str] = []
    for item_id, item in reader.get("items", {}).items():
        machine = next(
            machine_item
            for _, machine_item in _items(issue)
            if str(machine_item.get("brief_item_id") or "") == item_id
        )
        links = " · ".join(
            f'<a href="{escape(str(source.get("url") or ""), quote=True)}">{escape(str(source.get("publisher") or "原始来源"))}</a>'
            for source in item.get("sources") or []
        )
        takeaway = (
            f'<div class="takeaway"><b>值得看的是</b> {escape(str(item.get("takeaway")))}</div>'
            if item.get("takeaway")
            else ""
        )
        item_parts.append(
            f'<article id="item-{escape(item_id, quote=True)}" data-reader-role="{escape(str(item["role"]), quote=True)}">'
            f'<div class="meta">{escape(str(machine.get("topic_name") or ""))} · {escape(str(item.get("published_at") or "")[:10])}</div>'
            f'<h2>{escape(str(item.get("title") or ""))}</h2>'
            f'<p class="lead">{escape(str(item.get("lead") or ""))}</p>'
            f'{_render_paragraphs(item.get("body") or [])}{takeaway}'
            f'<div class="sources">阅读原文：{links}</div></article>'
        )
    judgement_parts = "".join(
        f'<section class="judgement"><h3>{escape(str(row.get("title") or "本期判断"))}</h3><p>{escape(str(row.get("body") or ""))}</p></section>'
        for row in reader.get("judgements") or []
    )
    radar_parts = "".join(
        f'<article class="radar" data-reader-role="radar-item"><div class="meta">{escape(str(row.get("category") or ""))}</div>'
        f'<h3>{escape(str(row.get("signal") or ""))}</h3><p>{escape(str(row.get("summary") or ""))}</p>'
        + " · ".join(
            f'<a href="{escape(str(url), quote=True)}">原始来源</a>' for url in row.get("source_urls") or []
        )
        + "</article>"
        for row in reader.get("radar") or []
    )
    watch = "".join(f"<li>{escape(str(value))}</li>" for value in reader.get("watch_next") or [])
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(str(reader.get('headline') or '技术情报'))}</title><style>
body{{margin:0;background:#ecece8;color:#171717;font-family:-apple-system,BlinkMacSystemFont,'Microsoft YaHei',sans-serif}}main{{max-width:760px;margin:18px auto;background:#fafaf7;padding:28px;box-sizing:border-box}}h1{{font-size:28px}}article,.judgement{{background:white;border:1px solid #d7d7d0;padding:16px;margin:12px 0}}.meta{{font-size:11px;color:#526aa0}}.lead{{font-size:15px}}p{{line-height:1.65}}.takeaway{{background:#f2f3ef;padding:10px}}.sources{{font-size:12px;color:#666;margin-top:10px}}a{{color:#002fa7}}@media(max-width:620px){{main{{margin:0;padding:18px}}}}
</style></head><body><main data-reader-contract="{CONTRACT_VERSION}"><div class="meta">{escape(str(reader.get('issue_date') or ''))}</div>
<h1>{escape(str(reader.get('headline') or ''))}</h1>{judgement_parts}<h2>专题解读</h2>{''.join(item_parts)}
<h2>热点雷达</h2>{radar_parts}<h2>接下来关注</h2><ul>{watch}</ul></main></body></html>"""


def _write_if_changed(path: Path, text: str) -> None:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def apply_historical_rewrite(root: Path, issue_dir: Path, reader: dict[str, Any]) -> dict[str, Any]:
    issue = read_json(issue_dir / "issue.json", {})
    validate_reader_document(root, issue, reader)
    if reader.get("rewrite_status") != "historical_semantic_rewrite":
        raise ValueError("historical apply requires rewrite_status=historical_semantic_rewrite")
    originals = (
        existing_original_html(issue_dir)
        if (issue_dir / "publication-manifest.json").is_file()
        else backup_original_html(issue_dir)
    )
    html = render_public_html(issue, reader)
    write_json(issue_dir / "reader.json", reader)
    _write_if_changed(issue_dir / "email.html", html)
    # A legacy archive may not preserve enough provenance to recover an illustrated
    # variant. Publish the same complete reader view instead of inventing images.
    _write_if_changed(issue_dir / "email-illustrated.html", html)
    return write_publication_manifest(issue_dir, reader, originals=originals)


def _manifest_files(issue_dir: Path) -> dict[str, str]:
    names = (
        "issue.json",
        "papers.json",
        "reader.json",
        "email.html",
        "email-illustrated.html",
        "original/email.html",
        "original/email-illustrated.html",
    )
    return {name: _sha256_file(issue_dir / name) for name in names if (issue_dir / name).is_file()}


def write_publication_manifest(
    issue_dir: Path,
    reader: dict[str, Any],
    *,
    originals: dict[str, str] | None = None,
) -> dict[str, Any]:
    manifest = {
        "schema_version": 1,
        "archive_contract_version": ARCHIVE_CONTRACT_VERSION,
        "reader_contract_version": int(reader["reader_contract_version"]),
        "source_issue_hash": str(reader["source_issue_hash"]),
        "issue_date": str(reader["issue_date"]),
        "generated_at": str(reader["generated_at"]),
        "original_variants": sorted((originals or {}).keys()),
        "files": _manifest_files(issue_dir),
    }
    write_json(issue_dir / "publication-manifest.json", manifest)
    return manifest
