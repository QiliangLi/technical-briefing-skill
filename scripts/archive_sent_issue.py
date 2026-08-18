#!/usr/bin/env python3
"""Archive one sent briefing issue into archive/issues/<date>/.

Each archived issue keeps the as-sent email HTML, the structured IssueDocument,
and a normalized papers.json designed as the substrate for later knowledge-graph
or paper-tree generation:

    papers.json: [{paper_key, title, url, arxiv_id, topic_id, topic_name,
                   direction_id, role, score, published_at, revisit,
                   item_id, issue_date, source_level}]

role is one of: core | supplement | radar. Rebuild archive/index.json after
every archival so the folder stays a complete, ordered history.

Usage:
    python scripts/archive_sent_issue.py --run 2026-08-17-092529 [--root .]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


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


def archive_issue(root: Path, run_id: str, *, email_name: str | None = None) -> Path:
    run_dir = root / "workspace" / "runs" / run_id
    issue_path = run_dir / "issue" / "issue.json"
    if not issue_path.is_file():
        raise SystemExit(f"no structured issue for run {run_id}")
    issue = json.loads(issue_path.read_text(encoding="utf-8"))
    issue_date = str(issue.get("date_to") or run_id[:10])

    target = root / "archive" / "issues" / issue_date
    target.mkdir(parents=True, exist_ok=True)

    email = run_dir / (email_name or "email-illustrated.html")
    if not email.is_file():
        email = run_dir / "email.html"
    if email.is_file():
        shutil.copy2(email, target / "email.html")
    shutil.copy2(issue_path, target / "issue.json")

    papers = _paper_rows(issue_date, issue)
    (target / "papers.json").write_text(
        json.dumps(papers, ensure_ascii=False, indent=1), encoding="utf-8"
    )
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
        entries.append({
            "date": papers_path.parent.name,
            "run_id": issue.get("run_id"),
            "headline": (issue.get("synthesis") or {}).get("headline"),
            "layout_mode": issue.get("layout_mode"),
            "counts": roles,
            "papers_file": f"issues/{papers_path.parent.name}/papers.json",
        })
    (archive / "index.json").write_text(
        json.dumps({"issues": entries}, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="sent run id, e.g. 2026-08-17-092529")
    parser.add_argument("--root", default=".", help="repository root")
    args = parser.parse_args()
    target = archive_issue(Path(args.root), args.run)
    print(f"archived to {target}")


if __name__ == "__main__":
    main()
