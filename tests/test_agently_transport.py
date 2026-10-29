from pathlib import Path

import pytest

from briefing_skill.agently_transport import (
    agently_send,
    publication_illustration_input,
    render_publication_html,
    resolve_agently_only_backend,
    validate_send_html,
)
from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database
from briefing_skill.emailer import AgentlyConfirmationRequired, EmailService


PINNED_URL = (
    "https://raw.githubusercontent.com/QiliangLi/technical-briefing-skill/"
    + "a" * 40
    + "/published-assets/run-1/diagram.png"
)


def test_transport_is_agently_only():
    assert resolve_agently_only_backend({}) == "agently"
    assert resolve_agently_only_backend({"EMAIL_BACKEND": "AGENTLY"}) == "agently"
    with pytest.raises(RuntimeError, match="direct SMTP delivery is retired"):
        resolve_agently_only_backend({"EMAIL_BACKEND": "smtp"})


def test_generated_illustration_requires_commit_pinned_public_url(tmp_path):
    captured = {}

    def original(root, base_html, manifest):
        captured["manifest"] = manifest
        return base_html

    manifest = {
        "illustrations": [
            {
                "status": "generated",
                "generated_asset_path": "published-assets/run-1/diagram.png",
                "published_asset_url": PINNED_URL,
            }
        ]
    }
    assert render_publication_html(original, tmp_path, "<html></html>", manifest) == "<html></html>"
    assert captured["manifest"]["illustrations"][0]["generated_asset_path"] == PINNED_URL

    manifest["illustrations"][0]["published_asset_url"] = (
        "https://raw.githubusercontent.com/QiliangLi/technical-briefing-skill/main/diagram.png"
    )
    with pytest.raises(RuntimeError, match="commit-SHA-pinned"):
        render_publication_html(original, tmp_path, "<html></html>", manifest)


def test_generated_illustration_accepts_release_download_url(tmp_path):
    captured = {}

    def original(root, base_html, manifest):
        captured["manifest"] = manifest
        return base_html

    release_url = (
        "https://github.com/QiliangLi/technical-briefing-skill/releases/download/"
        "illustrations-run-1/diagram.png"
    )
    manifest = {
        "illustrations": [
            {
                "status": "generated",
                "generated_asset_path": "published-assets/run-1/diagram.png",
                "published_asset_url": release_url,
            }
        ]
    }
    assert render_publication_html(original, tmp_path, "<html></html>", manifest) == "<html></html>"
    assert captured["manifest"]["illustrations"][0]["generated_asset_path"] == release_url

    manifest["illustrations"][0]["published_asset_url"] = (
        "https://github.com/QiliangLi/technical-briefing-skill/releases/download/tag/readme.md"
    )
    with pytest.raises(RuntimeError, match="immutable public URL"):
        render_publication_html(original, tmp_path, "<html></html>", manifest)


def test_send_html_rejects_local_or_relative_images(tmp_path):
    good = tmp_path / "good.html"
    good.write_text(f'<html><img src="{PINNED_URL}"></html>', encoding="utf-8")
    validate_send_html(good)

    for value in ("illustrations/a.png", "/home/user/a.png", "file:///tmp/a.png"):
        bad = tmp_path / "bad.html"
        bad.write_text(f'<html><img src="{value}"></html>', encoding="utf-8")
        with pytest.raises(RuntimeError, match="non-public image src"):
            validate_send_html(bad)


def test_agently_send_uses_same_final_html_as_body_and_attachment(tmp_path, monkeypatch):
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    service = EmailService(
        tmp_path,
        ConfigBundle(topics={}, sources={}, scoring={}, settings={}, email={}),
        db,
    )
    run_id = "run-1"
    body = tmp_path / "workspace" / "runs" / run_id / "email-illustrated.html"
    body.parent.mkdir(parents=True)
    body.write_text(f'<html><body><img src="{PINNED_URL}"></body></html>', encoding="utf-8")
    issue = {
        "id": "issue-1",
        "run_id": run_id,
        "subject": "Brief",
        "email_path": str(body.relative_to(tmp_path)),
    }
    monkeypatch.setenv("EMAIL_TO", "one@example.com")
    calls = []
    recorded = []
    monkeypatch.setattr(
        service,
        "_run_agently_cli",
        lambda args, config: calls.append(args) or {"data": {"message_id": "msg-1"}},
    )
    monkeypatch.setattr(
        service,
        "_record_sent",
        lambda issue, sent_at, recipients, message_id: recorded.append(
            (issue["id"], recipients, message_id)
        ),
    )

    agently_send(service, issue, run_id)

    args = calls[0]
    body_rel = str(body.relative_to(tmp_path)).replace("\\", "/")
    assert args[args.index("--body-file") + 1] == body_rel
    assert args[args.index("--attachment") + 1] == body_rel
    assert recorded == [("issue-1", "one@example.com", "msg-1")]


def test_publication_input_moves_assets_to_tracked_publication_directory():
    class Pipeline:
        run_id = "run-42"

    payload = publication_illustration_input(
        lambda pipeline, issue: {"constraints": {"output_directory": "workspace/runs/run-42/illustrations"}},
        Pipeline(),
        {"id": "issue-42"},
    )
    assert payload["constraints"]["output_directory"] == "published-assets/run-42"
    policy = payload["constraints"]["asset_publication_policy"]
    assert policy["required"] is True
    assert "<40-char-commit-sha>" in policy["preferred_url_format"]
    assert "<release-tag>" in policy["backup_url_format"]


def _autocompletion_fixture(tmp_path, settings=None):
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    service = EmailService(
        tmp_path,
        ConfigBundle(topics={}, sources={}, scoring={}, settings=settings or {}, email={}),
        db,
    )
    run_id = "run-1"
    body = tmp_path / "workspace" / "runs" / run_id / "email-illustrated.html"
    body.parent.mkdir(parents=True)
    body.write_text("<html><body>ok</body></html>", encoding="utf-8")
    issue = {
        "id": "issue-1",
        "run_id": run_id,
        "subject": "Brief",
        "email_path": str(body.relative_to(tmp_path)),
    }
    return service, issue, run_id


def test_agently_send_autocompletes_when_envelope_matches(tmp_path, monkeypatch):
    service, issue, run_id = _autocompletion_fixture(tmp_path)
    monkeypatch.setenv("EMAIL_TO", "one@example.com")
    calls = []
    recorded = []

    def fake_cli(args, config):
        calls.append(args)
        if len(calls) == 1:
            return {
                "data": {
                    "confirmation_required": True,
                    "confirmation_token": "ctk_ok",
                    "summary": {
                        "subject": "Brief",
                        "to": ["one@example.com"],
                        "attachment_count": 1,
                    },
                }
            }
        return {"data": {"message_id": "msg-ok"}}

    monkeypatch.setattr(service, "_run_agently_cli", fake_cli)
    monkeypatch.setattr(
        service,
        "_record_sent",
        lambda issue, sent_at, recipients, message_id: recorded.append(
            (issue["id"], recipients, message_id)
        ),
    )

    agently_send(service, issue, run_id)

    assert len(calls) == 2
    assert "--confirmation-token" not in calls[0]
    assert calls[1][calls[1].index("--confirmation-token") + 1] == "ctk_ok"
    assert recorded == [("issue-1", "one@example.com", "msg-ok")]
    verified = tmp_path / "workspace" / "runs" / run_id / "agently-send-verified.json"
    assert verified.exists()
    assert not (tmp_path / "workspace" / "runs" / run_id / "agently-send-pending.json").exists()


def test_agently_send_autocompletes_exit8_path(tmp_path, monkeypatch):
    from briefing_skill.emailer import AgentlyCLIError

    service, issue, run_id = _autocompletion_fixture(tmp_path)
    monkeypatch.setenv("EMAIL_TO", "one@example.com")
    calls = []

    def fake_cli(args, config):
        calls.append(args)
        if len(calls) == 1:
            raise AgentlyCLIError(
                8,
                "confirmation required",
                {
                    "data": {
                        "confirmation_token": "ctk_exit8",
                        "summary": {"subject": "Brief", "to": ["one@example.com"]},
                    }
                },
            )
        return {"data": {"message_id": "msg-exit8"}}

    monkeypatch.setattr(service, "_run_agently_cli", fake_cli)
    monkeypatch.setattr(service, "_record_sent", lambda *a, **k: None)

    agently_send(service, issue, run_id)

    assert len(calls) == 2
    assert calls[1][calls[1].index("--confirmation-token") + 1] == "ctk_exit8"


def test_agently_send_stops_when_recipients_drift_from_last_sent(tmp_path, monkeypatch):
    service, issue, run_id = _autocompletion_fixture(tmp_path)
    monkeypatch.setenv("EMAIL_TO", "one@example.com")
    service.db.execute(
        "INSERT INTO send_history(issue_id, sent_at, recipients, message_id, status) "
        "VALUES ('issue-0', '2026-10-27T00:00:00', 'someone-else@example.com', 'm', 'SENT')"
    )
    calls = []

    def fake_cli(args, config):
        calls.append(args)
        return {
            "data": {
                "confirmation_required": True,
                "confirmation_token": "ctk_drift",
                "summary": {"subject": "Brief", "to": ["one@example.com"], "attachment_count": 1},
            }
        }

    monkeypatch.setattr(service, "_run_agently_cli", fake_cli)

    with pytest.raises(AgentlyConfirmationRequired) as excinfo:
        agently_send(service, issue, run_id)

    assert len(calls) == 1
    assert any("differ from last SENT" in line for line in excinfo.value.verification_errors)


def test_agently_send_stops_on_envelope_mismatch(tmp_path, monkeypatch):
    service, issue, run_id = _autocompletion_fixture(tmp_path)
    monkeypatch.setenv("EMAIL_TO", "one@example.com")
    calls = []

    def fake_cli(args, config):
        calls.append(args)
        return {
            "data": {
                "confirmation_required": True,
                "confirmation_token": "ctk_bad",
                "summary": {"subject": "Brief", "to": ["one@example.com"], "attachment_count": 2},
            }
        }

    monkeypatch.setattr(service, "_run_agently_cli", fake_cli)

    with pytest.raises(AgentlyConfirmationRequired) as excinfo:
        agently_send(service, issue, run_id)

    assert len(calls) == 1
    assert any("attachment_count" in line for line in excinfo.value.verification_errors)
    # A stopped send keeps the pending token file for the manual second call.
    pending = tmp_path / "workspace" / "runs" / run_id / "agently-send-pending.json"
    assert pending.exists()


def test_agently_send_respects_disabled_auto_confirm(tmp_path, monkeypatch):
    service, issue, run_id = _autocompletion_fixture(
        tmp_path, settings={"send": {"auto_confirm_envelope": False}}
    )
    monkeypatch.setenv("EMAIL_TO", "one@example.com")
    calls = []

    def fake_cli(args, config):
        calls.append(args)
        return {
            "data": {
                "confirmation_required": True,
                "confirmation_token": "ctk_off",
                "summary": {"subject": "Brief", "to": ["one@example.com"], "attachment_count": 1},
            }
        }

    monkeypatch.setattr(service, "_run_agently_cli", fake_cli)

    with pytest.raises(AgentlyConfirmationRequired) as excinfo:
        agently_send(service, issue, run_id)

    assert len(calls) == 1
    assert excinfo.value.verification_errors == []
