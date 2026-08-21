#!/usr/bin/env python3
"""Archive one sent briefing issue or migrate one historical reader layer.

Each archived issue keeps immutable generated/sent HTML snapshots under
``original/``. The stable root names are the current public reader projection:
``email.html`` and ``email-illustrated.html``. Re-running with unchanged inputs is
idempotent; this command never overwrites an existing original snapshot.

    papers.json: [{paper_key, title, url, arxiv_id, topic_id, topic_name,
                   direction_id, role, score, published_at, revisit,
                   item_id, issue_date, source_level}]

role is one of: core | supplement | radar. Rebuild archive/index.json after
every archival so the folder stays a complete, ordered history.

Usage:
    python scripts/archive_sent_issue.py archive --run 2026-08-17-092529
    python scripts/archive_sent_issue.py prepare-rewrite --date 2026-08-17 --output rewrite-input.json
    python scripts/archive_sent_issue.py apply-rewrite --date 2026-08-17 --input reader-output.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from bs4 import BeautifulSoup

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from briefing_skill.archive_reader import (
    apply_historical_rewrite,
    build_reader_from_run,
    prepare_rewrite_payload,
    validate_reader_document,
    write_publication_manifest,
)
from briefing_skill.public_trace_scan import archive_public_files, public_upstream_trace_errors
from briefing_skill.utils import read_json, write_json


def _paper_key(url: str) -> str:
    """Stable cross-issue identity for the same source URL."""
    return re.sub(r"[^0-9a-z]+", "-", url.lower()).strip("-")


def _arxiv_id(url: str) -> str | None:
    match = re.search(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})", url)
    return match.group(1) if match else None


def _paper_rows(issue_date: str, issue: dict) -> list[dict]:
    rows: list[dict] = []
    for item in issue.get("core_items") or []:
        rows.append(_row(issue_date, item, "core"))
    for item in issue.get("observations") or []:
        rows.append(_row(issue_date, item, "supplement"))
    for signal in (issue.get("synthesis") or {}).get("radar_signals") or []:
        for url in signal.get("source_urls") or []:
            rows.append({
                "paper_key": _paper_key(url),
                "title": signal.get("signal") or "",
                "url": url,
                "arxiv_id": _arxiv_id(url),
                "topic_id": None,
                "topic_name": signal.get("category"),
                "direction_id": None,
                "role": "radar",
                "score": None,
                "published_at": None,
                "revisit": False,
                "item_id": None,
                "issue_date": issue_date,
                "source_level": None,
            })
    return rows


def _row(issue_date: str, item: dict, role: str) -> dict:
    source = (item.get("sources") or [{}])[0]
    url = str(source.get("url") or "")
    return {
        "paper_key": _paper_key(url),
        "title": item.get("title") or "",
        "url": url,
        "arxiv_id": _arxiv_id(url),
        "topic_id": item.get("topic_id"),
        "topic_name": item.get("topic_name"),
        "direction_id": item.get("direction_id"),
        "role": role,
        "score": item.get("score"),
        "published_at": item.get("published_at"),
        "revisit": bool(item.get("revisit")),
        "item_id": item.get("brief_item_id"),
        "issue_date": issue_date,
        "source_level": source.get("source_level"),
    }


def _require_reader_html(path: Path, reader: dict) -> None:
    if not path.is_file():
        raise ValueError(f"missing required public variant: {path}")
    text = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser").get_text(" ", strip=True)
    required_text = [str(reader.get("headline") or "")]
    required_text.extend(
        str(item.get("title") or "") for item in (reader.get("items") or {}).values()
    )
    missing = [
        item_id
        for item_id, item in (reader.get("items") or {}).items()
        if str(item.get("title") or "") not in text
    ]
    if required_text[0] and required_text[0] not in text:
        missing.insert(0, "headline")
    if missing:
        raise ValueError(f"{path.name} is not rendered from current reader sidecars: {missing}")


def _copy_original_variants(run_dir: Path, target: Path) -> dict[str, str]:
    original_dir = target / "original"
    result: dict[str, str] = {}
    for name in ("email.html", "email-illustrated.html"):
        source = run_dir / name
        if not source.is_file():
            raise ValueError(f"new archive requires both email variants; missing {source}")
        destination = original_dir / name
        if destination.exists():
            if destination.read_bytes() != source.read_bytes():
                raise ValueError(f"refusing to replace immutable original variant: {destination}")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        import hashlib

        result[name] = hashlib.sha256(destination.read_bytes()).hexdigest()
    return result


def _assemble_archive(root: Path, run_id: str, target: Path, temp_dir: Path) -> None:
    """Assemble the complete public archive inside temp_dir (target untouched)."""
    from briefing_skill.archive_reader import _atomic_swap_directory
    from briefing_skill.public_trace_scan import public_text_trace_errors, public_upstream_trace_errors

    run_dir = root / "workspace" / "runs" / run_id
    issue_path = run_dir / "issue" / "issue.json"
    issue = json.loads(issue_path.read_text(encoding="utf-8"))
    issue_date = target.name

    reader = build_reader_from_run(root, run_id, issue)
    validate_reader_document(root, issue, reader, require_current_sidecar=True)
    for name in ("email.html", "email-illustrated.html"):
        _require_reader_html(run_dir / name, reader)

    temp_dir.mkdir(parents=True, exist_ok=True)
    # Carry over immutable original/ snapshots from an existing archive;
    # a legacy archive (no manifest yet) snapshots its current public emails
    # first. Both preserve the pre-existing bytes exactly.
    if (target / "original").is_dir():
        shutil.copytree(target / "original", temp_dir / "original")
    if not (target / "publication-manifest.json").exists() and not (temp_dir / "original").is_dir():
        for name in ("email.html", "email-illustrated.html"):
            legacy = target / name
            if legacy.is_file():
                (temp_dir / "original").mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy, temp_dir / "original" / name)
    originals = {}
    import hashlib

    for name in ("email.html", "email-illustrated.html"):
        source = run_dir / name
        if not source.is_file():
            raise ValueError(f"new archive requires both email variants; missing {source}")
        destination = temp_dir / "original" / name
        if destination.exists():
            if destination.read_bytes() != source.read_bytes():
                raise ValueError(f"refusing to replace immutable original variant: {destination}")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        originals[name] = hashlib.sha256(destination.read_bytes()).hexdigest()

    shutil.copy2(issue_path, temp_dir / "issue.json")
    write_json(temp_dir / "reader.json", reader)
    for name in ("email.html", "email-illustrated.html"):
        shutil.copy2(run_dir / name, temp_dir / name)

    papers = _paper_rows(issue_date, issue)
    pre_errors = public_text_trace_errors(
        {
            "papers.json": json.dumps(papers, ensure_ascii=False),
            "reader.json": json.dumps(reader, ensure_ascii=False),
        }
    )
    if pre_errors:
        raise SystemExit("upstream trace scan failed before archive write:\n" + "\n".join(pre_errors))
    (temp_dir / "papers.json").write_text(
        json.dumps(papers, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    write_publication_manifest(temp_dir, reader, originals=originals)
    trace_errors = public_upstream_trace_errors(archive_public_files(temp_dir))
    if trace_errors:
        raise SystemExit("upstream trace scan failed:\n" + "\n".join(trace_errors))
    _atomic_swap_directory(temp_dir, target)


def archive_issue(root: Path, run_id: str) -> Path:
    run_dir = root / "workspace" / "runs" / run_id
    issue_path = run_dir / "issue" / "issue.json"
    if not issue_path.is_file():
        raise SystemExit(f"no structured issue for run {run_id}")
    issue = json.loads(issue_path.read_text(encoding="utf-8"))
    issue_date = str(issue.get("date_to") or run_id[:10])

    target = root / "archive" / "issues" / issue_date
    from briefing_skill.archive_reader import _recover_stale_backup

    _recover_stale_backup(target)
    temp_dir = target.with_name(f".{issue_date}.tmp")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    try:
        _assemble_archive(root, run_id, target, temp_dir)
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
    _rebuild_index(root)
    return target


def _rebuild_index(root: Path) -> None:
    archive = root / "archive"
    entries = []
    for papers_path in sorted((archive / "issues").glob("*/papers.json")):
        papers = json.loads(papers_path.read_text(encoding="utf-8"))
        issue = json.loads((papers_path.parent / "issue.json").read_text(encoding="utf-8"))
        roles: dict[str, int] = {}
        for row in papers:
            roles[row["role"]] = roles.get(row["role"], 0) + 1
        reader = read_json(papers_path.parent / "reader.json", {})
        entries.append({
            "date": papers_path.parent.name,
            "run_id": issue.get("run_id"),
            "headline": reader.get("headline") or (issue.get("synthesis") or {}).get("headline"),
            "layout_mode": issue.get("layout_mode"),
            "counts": roles,
            "papers_file": f"issues/{papers_path.parent.name}/papers.json",
        })
    (archive / "index.json").write_text(
        json.dumps({"issues": entries}, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> None:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    commands = {"archive", "prepare-rewrite", "apply-rewrite"}
    if "--run" in raw_args and not any(value in commands for value in raw_args):
        raw_args.insert(0, "archive")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    archive_parser = subparsers.add_parser("archive", help="archive a completed current run")
    archive_parser.add_argument("--root", dest="root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    archive_parser.add_argument("--run", required=True, help="sent run id, e.g. 2026-08-17-092529")
    prepare_parser = subparsers.add_parser("prepare-rewrite", help="prepare one bounded legacy rewrite input")
    prepare_parser.add_argument("--root", dest="root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    prepare_parser.add_argument("--date", required=True, help="archive issue date")
    prepare_parser.add_argument("--output", required=True, help="exact JSON output path")
    apply_parser = subparsers.add_parser("apply-rewrite", help="validate and apply one legacy reader output")
    apply_parser.add_argument("--root", dest="root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    apply_parser.add_argument("--date", required=True, help="archive issue date")
    apply_parser.add_argument("--input", required=True, help="completed reader JSON")
    args = parser.parse_args(raw_args)
    root = Path(args.root).resolve()
    if args.command == "archive":
        target = archive_issue(root, args.run)
        print(f"archived to {target}")
        return
    issue_dir = root / "archive" / "issues" / args.date
    issue_path = issue_dir / "issue.json"
    if not issue_path.is_file():
        raise SystemExit(f"archived issue not found: {args.date}")
    issue = read_json(issue_path, {})
    if args.command == "prepare-rewrite":
        payload = prepare_rewrite_payload(issue)
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        write_json(output, payload)
        print(f"rewrite input written to {output}")
        return
    reader = read_json(Path(args.input) if Path(args.input).is_absolute() else root / args.input, {})
    apply_historical_rewrite(root, issue_dir, reader)
    _rebuild_index(root)
    print(f"reader rewrite applied to {issue_dir}")


if __name__ == "__main__":
    main()
