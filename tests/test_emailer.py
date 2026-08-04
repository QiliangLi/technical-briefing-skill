import pytest

from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database
from briefing_skill.emailer import (
    AgentlyCLIError,
    AgentlyConfirmationRequired,
    EmailService,
    resolve_agently_config,
    resolve_email_backend,
    resolve_smtp_config,
)
from briefing_skill.utils import now_iso


BASE = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_USERNAME": "username@example.com",
    "EMAIL_TO": "one@example.com, two@example.com",
}


def test_smtp_sender_and_recipient_alias_precedence():
    config = resolve_smtp_config(
        {
            **BASE,
            "EMAIL_FROM": "email-from@example.com",
            "SMTP_FROM": "smtp-from@example.com",
            "SMTP_TO": "ignored@example.com",
        }
    )
    assert config.sender == "email-from@example.com"
    assert config.recipients == ("one@example.com", "two@example.com")

    aliases = resolve_smtp_config(
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_USERNAME": "username@example.com",
            "EMAIL_FROM": "   ",
            "SMTP_FROM": "smtp-from@example.com",
            "EMAIL_TO": "   ",
            "SMTP_TO": "alias@example.com",
        }
    )
    assert aliases.sender == "smtp-from@example.com"
    assert aliases.recipients == ("alias@example.com",)


@pytest.mark.parametrize(
    ("value", "expected_mode", "expected_port"),
    [("SSL", "ssl", 465), ("startTLS", "starttls", 587), ("TLS", "starttls", 587), ("none", "none", 25)],
)
def test_smtp_security_modes_are_case_insensitive(value, expected_mode, expected_port):
    config = resolve_smtp_config({**BASE, "SMTP_SECURITY": value})
    assert config.security == expected_mode
    assert config.port == expected_port


def test_smtp_security_overrides_legacy_flag_and_legacy_remains_supported():
    preferred = resolve_smtp_config({**BASE, "SMTP_SECURITY": "tls", "SMTP_USE_SSL": "true"})
    legacy = resolve_smtp_config({**BASE, "SMTP_USE_SSL": "false"})
    assert preferred.security == "starttls"
    assert preferred.port == 587
    assert legacy.security == "starttls"


def test_smtp_rejects_unknown_security_and_requires_explicit_recipient():
    with pytest.raises(RuntimeError, match="SMTP_SECURITY must be one of"):
        resolve_smtp_config({**BASE, "SMTP_SECURITY": "opportunistic"})
    without_recipient = {key: value for key, value in BASE.items() if key != "EMAIL_TO"}
    with pytest.raises(RuntimeError, match="explicit EMAIL_TO/SMTP_TO"):
        resolve_smtp_config(without_recipient)


def test_agently_backend_defaults_to_agently_and_resolves_recipients():
    assert resolve_email_backend({}) == "agently"
    assert resolve_email_backend({"EMAIL_BACKEND": "SMTP"}) == "smtp"
    config = resolve_agently_config({"EMAIL_TO": "one@example.com, two@example.com", "AGENTLY_TIMEOUT_SECONDS": "12"})
    assert config.recipients == ("one@example.com", "two@example.com")
    assert config.timeout_seconds == 12


def test_agently_send_persists_confirmation_then_uses_token(tmp_path, monkeypatch):
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    run_id = "run-agently"
    now = now_iso()
    db.create_run(run_id, "APPROVED")
    db.execute(
        "INSERT INTO issues(id, run_id, status, subject, email_path, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("issue-agently", run_id, "APPROVED", "Brief", "workspace/runs/run-agently/email.html", now, now),
    )
    body = tmp_path / "workspace" / "runs" / run_id / "email.html"
    body.parent.mkdir(parents=True)
    body.write_text("<html><body>brief</body></html>", encoding="utf-8")
    service = EmailService(
        tmp_path,
        ConfigBundle(topics={}, sources={}, scoring={}, settings={}, email={}),
        db,
    )
    monkeypatch.setenv("EMAIL_BACKEND", "agently")
    monkeypatch.setenv("EMAIL_TO", "one@example.com")
    calls = []

    def first_call(_args, _config):
        calls.append(_args)
        raise AgentlyCLIError(
            8,
            "confirmation required",
            {"data": {"confirmation_required": True, "confirmation_token": "ctk_test", "summary": {"to": ["one@example.com"]}}},
        )

    monkeypatch.setattr(service, "_run_agently_cli", first_call)
    with pytest.raises(AgentlyConfirmationRequired):
        service._agently_send(db.fetchone("SELECT * FROM issues WHERE id='issue-agently'"), run_id)
    pending = tmp_path / "workspace" / "runs" / run_id / "agently-send-pending.json"
    assert pending.exists()
    assert "--confirmation-token" not in calls[0]

    monkeypatch.setattr(service, "_run_agently_cli", lambda args, config: calls.append(args) or {"data": {"message_id": "msg_test"}})
    service._agently_send(db.fetchone("SELECT * FROM issues WHERE id='issue-agently'"), run_id)
    assert "--confirmation-token" in calls[1]
    assert not pending.exists()
    assert db.fetchone("SELECT message_id, status FROM send_history WHERE issue_id='issue-agently'") == {"message_id": "msg_test", "status": "SENT"}
