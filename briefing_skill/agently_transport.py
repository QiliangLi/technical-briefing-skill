from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .utils import now_iso, read_json, stable_hash, write_json


_GITHUB_RAW_SHA = re.compile(
    r"^https://raw\.githubusercontent\.com/[^/]+/[^/]+/[0-9a-fA-F]{40}/.+"
)
# Release download URLs are immutable per tag+filename and, unlike
# raw.githubusercontent.com, resolve on mail clients behind restricted
# networks (they are served from github.com/release-assets, not raw).
_GITHUB_RELEASE_ASSET = re.compile(
    r"^https://github\.com/[^/]+/[^/]+/releases/download/[^/\s]+/[^/?#\s]+\.(?i:png|jpe?g|gif|webp|svg)$"
)


def resolve_agently_only_backend(environ: Mapping[str, str] | None = None) -> str:
    """Return the sole supported delivery backend and reject legacy SMTP selection."""

    env = os.environ if environ is None else environ
    backend = str(env.get("EMAIL_BACKEND", "agently") or "agently").strip().lower()
    if backend != "agently":
        raise RuntimeError(
            "EMAIL_BACKEND must be agently; direct SMTP delivery is retired so the "
            "publication path has one transport contract"
        )
    return "agently"


def _is_immutable_github_asset_url(value: str | None) -> bool:
    candidate = str(value or "").strip()
    return bool(_GITHUB_RAW_SHA.match(candidate) or _GITHUB_RELEASE_ASSET.match(candidate))


def validate_send_html(path: Path) -> None:
    """Fail closed when a final mail body still references a local/relative image."""

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    bad: list[str] = []
    for image in soup.find_all("img"):
        src = str(image.get("src") or "").strip()
        if src.startswith("data:"):
            continue
        parsed = urlparse(src)
        if parsed.scheme != "https" or not parsed.netloc:
            bad.append(src or "<empty>")
    if bad:
        preview = ", ".join(bad[:5])
        raise RuntimeError(
            "Final Agently HTML contains non-public image src values. Publish generated "
            f"assets first and use HTTPS URLs; invalid src: {preview}"
        )


def render_publication_html(
    original_render,
    root: Path,
    base_html: str,
    manifest: dict[str, Any],
) -> str:
    """Render generated illustrations only from commit-pinned GitHub URLs."""

    prepared = copy.deepcopy(manifest)
    for item in prepared.get("illustrations") or []:
        if str(item.get("status") or "") != "generated":
            continue
        public_url = str(item.get("published_asset_url") or "").strip()
        if not _is_immutable_github_asset_url(public_url):
            raise RuntimeError(
                "Generated briefing illustrations must provide published_asset_url as an "
                "immutable public URL: a GitHub release download URL or a commit-SHA-pinned "
                "raw.githubusercontent.com URL"
            )
        item["generated_asset_path"] = public_url
    return original_render(root, base_html, prepared)


def publication_illustration_input(original_input, pipeline, issue: dict[str, Any]) -> dict[str, Any]:
    """Move generated assets out of ignored run state and define the publication handoff."""

    payload = original_input(pipeline, issue)
    constraints = payload.setdefault("constraints", {})
    constraints["output_directory"] = f"published-assets/{pipeline.run_id}"
    constraints["asset_publication_policy"] = {
        "required": True,
        "repository": "QiliangLi/technical-briefing-skill",
        "preferred_url_format": (
            "https://github.com/QiliangLi/technical-briefing-skill/releases/download/"
            "<release-tag>/<asset-filename>"
        ),
        "accepted_url_format": (
            "https://raw.githubusercontent.com/QiliangLi/technical-briefing-skill/"
            "<40-char-commit-sha>/<repo-relative-path>"
        ),
        "hosting_note": (
            "Prefer release download URLs: raw.githubusercontent.com is unreachable from "
            "many restricted networks, while github.com release assets resolve for mail "
            "clients there."
        ),
        "rule": (
            "Every generated image must be published (release asset upload or commit+push) "
            "before the task result is written; return the immutable URL in "
            "published_asset_url. Never expose workspace/, /home/, /Users/, file://, or a "
            "relative image path in email HTML."
        ),
    }
    return payload


def agently_send(service, issue: dict[str, Any], run_id: str) -> str:
    """Send the exact final HTML as both body and attachment through agently-cli."""

    # Import lazily so installation can safely replace EmailService methods without
    # creating import-order cycles during bootstrap.
    from .emailer import (
        AgentlyCLIError,
        AgentlyConfirmationRequired,
        resolve_agently_config,
    )

    config = resolve_agently_config()
    body_path = (service.root / str(issue["email_path"])).resolve()
    try:
        body_path.relative_to(service.root.resolve())
    except ValueError as exc:
        raise RuntimeError("Email body must be inside the Skill root") from exc
    if not body_path.exists():
        raise RuntimeError(f"Email body does not exist: {body_path}")
    if body_path.stat().st_size > 1024 * 1024:
        raise RuntimeError("agently-cli email body exceeds its 1 MB limit")

    validate_send_html(body_path)

    subject = issue.get("subject") or "AI语义Fabric技术情报（公测版）"
    body_rel = body_path.relative_to(service.root.resolve()).as_posix()
    body_bytes = body_path.read_bytes()
    request_key = stable_hash(
        subject,
        config.recipients,
        config.cc,
        config.bcc,
        body_bytes,
        "attach-html-v1",
    )
    pending_path = service.root / "workspace" / "runs" / run_id / "agently-send-pending.json"
    pending = read_json(pending_path, {}) if pending_path.exists() else {}
    token = str(pending.get("confirmation_token") or "")
    if token and pending.get("request_key") != request_key:
        pending_path.unlink(missing_ok=True)
        token = ""

    args = [config.executable, "message", "+send", "--subject", str(subject)]
    for recipient in config.recipients:
        args.extend(["--to", recipient])
    for recipient in config.cc:
        args.extend(["--cc", recipient])
    for recipient in config.bcc:
        args.extend(["--bcc", recipient])
    args.extend(["--body-file", body_rel, "--attachment", body_rel])
    if token:
        args.extend(["--confirmation-token", token])

    try:
        payload = service._run_agently_cli(args, config)
    except AgentlyCLIError as exc:
        candidate = service._payload_value(exc.payload, "confirmation_token", "confirmationToken")
        if exc.exit_code == 8 and candidate:
            summary = service._payload_value(exc.payload, "summary") or {
                "subject": subject,
                "to": list(config.recipients),
                "attachment": body_rel,
            }
            write_json(
                pending_path,
                {
                    "confirmation_token": str(candidate),
                    "request_key": request_key,
                    "summary": summary,
                    "created_at": now_iso(),
                },
            )
            try:
                pending_path.chmod(0o600)
            except OSError:
                pass
            raise AgentlyConfirmationRequired(summary) from exc
        raise

    if service._payload_value(payload, "confirmation_required", "confirmationRequired"):
        candidate = service._payload_value(payload, "confirmation_token", "confirmationToken")
        if candidate:
            summary = service._payload_value(payload, "summary") or {}
            write_json(
                pending_path,
                {
                    "confirmation_token": str(candidate),
                    "request_key": request_key,
                    "summary": summary,
                    "created_at": now_iso(),
                },
            )
            raise AgentlyConfirmationRequired(summary)

    pending_path.unlink(missing_ok=True)
    sent_at = now_iso()
    service._record_sent(
        issue,
        sent_at,
        ",".join(config.recipients),
        service._message_id(payload),
    )
    return sent_at


def install_agently_transport() -> None:
    """Install the single production transport and remote-asset publication contract."""

    from . import emailer, illustrated_publication

    if getattr(emailer.EmailService, "_agently_transport_installed", False):
        return

    original_input = illustrated_publication._illustration_input
    original_render = illustrated_publication.render_illustrated_html

    def wrapped_input(pipeline, issue):
        return publication_illustration_input(original_input, pipeline, issue)

    def wrapped_render(root, base_html, manifest):
        return render_publication_html(original_render, root, base_html, manifest)

    def wrapped_send(self, issue, run_id):
        return agently_send(self, issue, run_id)

    def smtp_disabled(self, issue):
        raise RuntimeError("Direct SMTP delivery is retired; use the Agently transport")

    illustrated_publication._illustration_input = wrapped_input
    illustrated_publication.render_illustrated_html = wrapped_render
    emailer.resolve_email_backend = resolve_agently_only_backend
    emailer.EmailService._agently_send = wrapped_send
    emailer.EmailService._smtp_send = smtp_disabled
    emailer.EmailService._agently_transport_installed = True
