"""Archive a sent run and publish its public projection to GitHub Pages.

The email transport and the Pages publication are deliberately separate
systems.  This module is the small, idempotent bridge between them: archive the
sent run, commit only the generated archive paths, and push the current main
branch so the existing Pages workflow can assemble and deploy the site.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .archive_reader_repair import ReaderSidecarRepairError, repair_reader_sidecars_from_sent_html
from .utils import read_json


class ArchivePublishError(RuntimeError):
    """Raised when a sent run cannot be safely archived or published."""


@dataclass(frozen=True)
class ArchivePublication:
    run_id: str
    issue_date: str
    archive_path: Path
    commit: str


def _run(root: Path, command: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=root,
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except FileNotFoundError as exc:
        raise ArchivePublishError(f"Required command is unavailable: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise ArchivePublishError(
            f"Command failed ({' '.join(command)}){suffix}"
        ) from exc


def _issue_date(root: Path, run_id: str) -> str:
    issue_path = root / "workspace" / "runs" / run_id / "issue" / "issue.json"
    issue = read_json(issue_path, {})
    issue_date = str(issue.get("date_to") or "").strip()
    if not issue_date:
        raise ArchivePublishError(f"Sent run {run_id} has no issue date")
    return issue_date


def archive_sent_run(root: Path, run_id: str) -> tuple[str, Path]:
    """Materialize one sent run under ``archive/issues`` and rebuild its index."""

    script = root / "scripts" / "archive_sent_issue.py"
    if not script.is_file():
        raise ArchivePublishError(f"Archive script is missing: {script}")
    issue_date = _issue_date(root, run_id)
    try:
        repair_reader_sidecars_from_sent_html(root, run_id)
    except ReaderSidecarRepairError as exc:
        raise ArchivePublishError(f"reader sidecar repair failed: {exc}") from exc
    _run(
        root,
        [
            sys.executable,
            str(script),
            "archive",
            "--root",
            str(root),
            "--run",
            run_id,
        ],
    )
    archive_path = root / "archive" / "issues" / issue_date
    if not (archive_path / "reader.json").is_file():
        raise ArchivePublishError(f"Archive did not produce reader.json: {archive_path}")
    return issue_date, archive_path


def _git_output(root: Path, command: list[str]) -> str:
    result = _run(root, command, capture_output=True)
    return (result.stdout or "").strip()


def publish_archive(root: Path, run_id: str, issue_date: str, archive_path: Path) -> ArchivePublication:
    """Commit only the generated issue and index, then push ``main``.

    The path-limited commit prevents a user's unrelated worktree changes from
    being included in an automatic publication commit.  A pre-existing staged
    change under either generated path is rejected because it is impossible to
    distinguish it safely from this run's output.
    """

    branch = _git_output(root, ["git", "branch", "--show-current"])
    if branch != "main":
        raise ArchivePublishError(
            f"Automatic Pages publication requires the main branch; current branch is {branch or 'detached'}"
        )

    relative_paths = [
        Path("archive/index.json"),
        Path("archive/issues") / issue_date,
    ]
    staged = _git_output(root, ["git", "diff", "--cached", "--name-only", "--", *map(str, relative_paths)])
    if staged:
        raise ArchivePublishError(
            "Generated archive paths already contain staged changes; publish them manually after review"
        )

    _run(root, ["git", "add", "--", *map(str, relative_paths)])
    cached = _git_output(root, ["git", "diff", "--cached", "--name-only", "--", *map(str, relative_paths)])
    if cached:
        _run(
            root,
            [
                "git",
                "commit",
                "-m",
                f"archive: publish {issue_date} briefing",
                "--",
                *map(str, relative_paths),
            ],
        )

    _run(root, ["git", "push", "origin", "HEAD:main"])
    commit = _git_output(root, ["git", "rev-parse", "HEAD"])
    return ArchivePublication(run_id, issue_date, archive_path, commit)


def archive_and_publish_sent_run(root: Path, run_id: str) -> ArchivePublication:
    """Archive and publish a run; safe to repeat after a failed push."""

    issue_date, archive_path = archive_sent_run(root, run_id)
    return publish_archive(root, run_id, issue_date, archive_path)
