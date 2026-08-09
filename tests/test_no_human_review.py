from __future__ import annotations

from types import SimpleNamespace

from briefing_skill.cli import build_parser as legacy_build_parser
from briefing_skill.no_human_review import (
    READY_TO_SEND,
    VALIDATION_FAILED,
    _set_release_state,
    _strip_review_commands,
)


class FakeDB:
    def __init__(self):
        self.issue_status = None
        self.run_stage = None

    def fetchone(self, sql, args):
        if "FROM issues" in sql:
            return {"id": "issue-1"}
        return None

    def execute(self, sql, args):
        if "UPDATE issues" in sql:
            self.issue_status = args[0]

    def update_run(self, run_id, **updates):
        self.run_stage = updates.get("stage")


def test_review_and_approve_commands_are_removed_from_public_parser():
    parser = _strip_review_commands(legacy_build_parser())
    subparsers = next(
        action for action in parser._actions if hasattr(action, "choices") and action.choices
    )

    assert "review" not in subparsers.choices
    assert "approve" not in subparsers.choices
    assert "send" in subparsers.choices


def test_clean_validation_promotes_directly_to_ready_to_send():
    db = FakeDB()
    service = SimpleNamespace(db=db)

    _set_release_state(service, "run-1", {"failures": []})

    assert db.issue_status == READY_TO_SEND
    assert db.run_stage == READY_TO_SEND


def test_failed_validation_blocks_release_without_review_fallback():
    db = FakeDB()
    service = SimpleNamespace(db=db)

    _set_release_state(service, "run-1", {"failures": ["bad email"]})

    assert db.issue_status == VALIDATION_FAILED
    assert db.run_stage == VALIDATION_FAILED
