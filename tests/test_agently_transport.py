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
from briefing_skill.emailer import EmailService


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
    assert "<release-tag>" in policy["preferred_url_format"]
    assert "<40-char-commit-sha>" in policy["accepted_url_format"]
