from __future__ import annotations

import argparse
from typing import Any

from .utils import now_iso, read_json


READY_TO_SEND = "READY_TO_SEND"
VALIDATION_FAILED = "VALIDATION_FAILED"
RENDERED = "RENDERED"


def _set_release_state(service, run_id: str, report: dict[str, Any]) -> None:
    status = VALIDATION_FAILED if report.get("failures") else READY_TO_SEND
    issue = service.db.fetchone("SELECT id FROM issues WHERE run_id=?", (run_id,))
    if issue:
        service.db.execute(
            "UPDATE issues SET status=?,updated_at=? WHERE id=?",
            (status, now_iso(), issue["id"]),
        )
    service.db.update_run(run_id, stage=status)


def _strip_review_commands(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Remove legacy review/approve commands from the public CLI surface."""

    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name in ("review", "approve"):
            action.choices.pop(name, None)
    return parser


def install_no_human_review_gate() -> None:
    """Make final validation, not an unused review page, the release gate.

    Historical review code/data remain readable for old runs, but new runs have no
    active review/approve step. Building the email validates the final artifact and
    transitions directly to READY_TO_SEND or VALIDATION_FAILED. Sending still requires
    explicit --confirm-send and a clean persisted validation report.
    """

    from .emailer import EmailService, resolve_email_backend
    from .pipeline import Pipeline
    from .rendering import Renderer

    if getattr(Pipeline, "_no_human_review_gate_installed", False):
        return

    original_validate = Renderer.validate

    def validate(self, run_id: str):
        report = original_validate(self, run_id)
        _set_release_state(self, run_id, report)
        return report

    Renderer.validate = validate

    original_build = EmailService.build

    def build(self, run_id: str, *args, **kwargs):
        # Rendering is an intermediate state. Only the final validator may promote
        # the issue to READY_TO_SEND.
        kwargs["status_after"] = RENDERED
        path = original_build(self, run_id, *args, **kwargs)
        Renderer(self.root, self.config, self.db).validate(run_id)
        return path

    EmailService.build = build

    def record_sent(self, issue: dict[str, Any], sent_at: str, recipients: str, message_id: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO send_history(issue_id,sent_at,recipients,message_id,status) VALUES (?,?,?,?,?)",
            (issue["id"], sent_at, recipients, message_id, "SENT"),
        )
        self.db.execute(
            "UPDATE issues SET status='SENT',updated_at=? WHERE id=?",
            (sent_at, issue["id"]),
        )
        # The final issue is the source of truth. Human `approved` flags are legacy
        # metadata and must not control push history once the review gate is removed.
        self.db.execute(
            """
            UPDATE events SET last_pushed_at=?
            WHERE id IN (
              SELECT bi.event_id FROM issue_items ii
              JOIN brief_items bi ON bi.id=ii.brief_item_id
              WHERE ii.issue_id=?
            )
            """,
            (sent_at, issue["id"]),
        )
        self.db.execute(
            """
            INSERT OR REPLACE INTO radar_history(
              canonical_url,normalized_title,last_pushed_at,issue_id
            )
            SELECT canonical_url,normalized_title,?,issue_id
            FROM issue_radar_items WHERE issue_id=?
            """,
            (sent_at, issue["id"]),
        )
        self.db.update_run(issue["run_id"], stage="SENT", status="COMPLETED")

    EmailService._record_sent = record_sent

    def send(self, run_id: str, *, confirm: bool = False) -> str:
        if not confirm:
            raise RuntimeError("Refusing to send without --confirm-send")
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
        if not issue or not issue.get("email_path"):
            raise RuntimeError("Build email first")
        if issue.get("status") != READY_TO_SEND:
            raise RuntimeError(
                f"Email is not ready to send: issue status is {issue.get('status')}; "
                "render and pass final validation first"
            )
        validation_path = self.root / "workspace" / "runs" / run_id / "validation.json"
        validation = read_json(validation_path, {})
        if not validation or validation.get("failures"):
            raise RuntimeError(
                f"Validation must pass before sending: {validation.get('failures') or 'missing validation report'}"
            )
        if resolve_email_backend() == "agently":
            return self._agently_send(issue, run_id)
        return self._smtp_send(issue)

    EmailService.send = send

    # Import CLI only after runtime behavior has been patched. The legacy review
    # implementation remains importable for archived runs, but it is no longer a
    # supported command in new workflows.
    from . import cli

    original_build_parser = cli.build_parser

    def build_parser():
        return _strip_review_commands(original_build_parser())

    cli.build_parser = build_parser
    Pipeline._no_human_review_gate_installed = True
