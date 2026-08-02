from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Mapping

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import ConfigBundle
from .db import Database
from .utils import now_iso, read_json


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    username: str
    sender: str
    recipients: tuple[str, ...]
    security: str
    port: int


def _smtp_security(environ: Mapping[str, str]) -> str:
    if "SMTP_SECURITY" in environ:
        raw = environ.get("SMTP_SECURITY", "").strip().lower()
        modes = {"ssl": "ssl", "starttls": "starttls", "tls": "starttls", "none": "none"}
        if raw not in modes:
            raise RuntimeError("SMTP_SECURITY must be one of: ssl, starttls, tls, none")
        return modes[raw]
    if "SMTP_USE_SSL" in environ:
        raw = environ.get("SMTP_USE_SSL", "").strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return "ssl"
        if raw in {"0", "false", "no", "off"}:
            return "starttls"
        raise RuntimeError("SMTP_USE_SSL must be a boolean value")
    return "ssl"


def _first_nonempty(environ: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = environ.get(name, "").strip()
        if value:
            return value
    return ""


def resolve_smtp_config(environ: Mapping[str, str] | None = None) -> SMTPConfig:
    env = os.environ if environ is None else environ
    host = env.get("SMTP_HOST", "").strip()
    username = env.get("SMTP_USERNAME", "").strip()
    sender = _first_nonempty(env, "EMAIL_FROM", "SMTP_FROM", "SMTP_USERNAME")
    recipient_text = _first_nonempty(env, "EMAIL_TO", "SMTP_TO")
    recipients = tuple(value.strip() for value in recipient_text.split(",") if value.strip())
    if not host or not sender or not recipients:
        raise RuntimeError(
            "SMTP_HOST, EMAIL_FROM/SMTP_FROM/SMTP_USERNAME and explicit EMAIL_TO/SMTP_TO are required"
        )
    security = _smtp_security(env)
    default_ports = {"ssl": 465, "starttls": 587, "none": 25}
    raw_port = env.get("SMTP_PORT", "").strip()
    try:
        port = int(raw_port) if raw_port else default_ports[security]
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("SMTP_PORT must be between 1 and 65535")
    return SMTPConfig(host, username, sender, recipients, security, port)


class EmailService:
    def __init__(self, root: Path, config: ConfigBundle, db: Database):
        self.root = root
        self.config = config
        self.db = db
        self.env = Environment(loader=FileSystemLoader(root / "templates"), autoescape=select_autoescape(["html", "xml"]))

    def build(self, run_id: str, *, status_after: str = "AWAITING_APPROVAL") -> Path:
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
        if not issue or not issue.get("issue_json_path"):
            raise RuntimeError("Issue not ready")
        data = read_json(self.root / issue["issue_json_path"])
        # Keep the archived HTML directly previewable from its run directory.
        # The send path later rewrites these absolute local files to CID parts,
        # so no filesystem path is transmitted in the final message body.
        for item in data.get("items", []):
            asset = (item.get("illustration") or {}).get("generated_asset_path") or (item.get("visual_plan") or {}).get("asset_path")
            if asset and not str(asset).startswith(("http://", "https://", "data:", "cid:")):
                path = Path(asset)
                if not path.is_absolute():
                    path = self.root / path
                item["email_asset_path"] = str(path)
        template = self.env.get_template("email.html")
        topic_names = []
        for item in data.get("items", []):
            name = item.get("topic_name") or item.get("topic_id")
            if name and name not in topic_names:
                topic_names.append(name)
        subject = self.config.email.get("subject_template", "技术情报简报").replace("{{ date_range }}", f"{data.get('date_from')}—{data.get('date_to')}").replace("{{ item_count }}", str(len(data.get("items", []))))
        html_text = template.render(issue=data, subject=subject, footer=self.config.email.get("footer", ""), topic_names=topic_names)
        path = self.root / "workspace" / "runs" / run_id / "email.html"
        path.write_text(html_text, encoding="utf-8")
        self.db.execute("UPDATE issues SET subject=?, email_path=?, status=?, updated_at=? WHERE id=?", (subject, str(path.relative_to(self.root)), status_after, now_iso(), issue["id"]))
        self.db.update_run(run_id, stage=status_after)
        return path

    def _prepare_inline_images(self, html_text: str):
        from bs4 import BeautifulSoup
        import mimetypes
        from .utils import stable_hash

        soup = BeautifulSoup(html_text, "html.parser")
        related = []
        for img in soup.find_all("img"):
            src = str(img.get("src") or "")
            if not src or src.startswith(("http://", "https://", "data:", "cid:")):
                continue
            path = Path(src)
            if not path.is_absolute():
                path = self.root / src
            if not path.exists():
                continue
            mime, _ = mimetypes.guess_type(path.name)
            if not mime or not mime.startswith("image/"):
                continue
            maintype, subtype = mime.split("/", 1)
            cid = stable_hash("email-image", path.resolve())
            img["src"] = f"cid:{cid}"
            related.append((cid, path, maintype, subtype))
        return str(soup), related

    def send(self, run_id: str, *, confirm: bool = False) -> str:
        if not confirm:
            raise RuntimeError("Refusing to send without --confirm-send")
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
        if not issue or not issue.get("email_path"):
            raise RuntimeError("Build email first")
        if self.config.settings.get("require_human_approval", True) and issue.get("status") != "APPROVED":
            raise RuntimeError("Human approval is required before sending")
        validation_path = self.root / "workspace" / "runs" / run_id / "validation.json"
        validation = read_json(validation_path, {})
        if validation.get("failures"):
            raise RuntimeError(f"Validation failures must be fixed: {validation['failures']}")
        smtp = resolve_smtp_config()
        password = os.getenv("SMTP_PASSWORD")
        msg = EmailMessage()
        msg["Subject"] = issue.get("subject") or "技术情报简报"
        msg["From"] = smtp.sender
        msg["To"] = ", ".join(smtp.recipients)
        msg.set_content("本邮件包含HTML技术情报简报，请使用支持HTML的邮件客户端查看。")
        html_text = (self.root / issue["email_path"]).read_text(encoding="utf-8")
        html_text, related = self._prepare_inline_images(html_text)
        msg.add_alternative(html_text, subtype="html")
        html_part = msg.get_payload()[-1]
        for cid, path, maintype, subtype in related:
            html_part.add_related(path.read_bytes(), maintype=maintype, subtype=subtype, cid=f"<{cid}>", filename=path.name)
        if smtp.security == "ssl":
            client = smtplib.SMTP_SSL(smtp.host, smtp.port, timeout=30)
        else:
            client = smtplib.SMTP(smtp.host, smtp.port, timeout=30)
        try:
            if smtp.security == "starttls":
                client.starttls()
            if smtp.username:
                client.login(smtp.username, password or "")
            client.send_message(msg)
        finally:
            client.quit()
        sent_at = now_iso()
        self.db.execute(
            "INSERT OR REPLACE INTO send_history(issue_id, sent_at, recipients, message_id, status) VALUES (?, ?, ?, ?, ?)",
            (issue["id"], sent_at, ",".join(smtp.recipients), msg.get("Message-ID"), "SENT"),
        )
        self.db.execute("UPDATE issues SET status='SENT', updated_at=? WHERE id=?", (sent_at, issue["id"]))
        self.db.execute(
            "UPDATE events SET last_pushed_at=? WHERE id IN (SELECT bi.event_id FROM issue_items ii JOIN brief_items bi ON bi.id=ii.brief_item_id WHERE ii.issue_id=?)",
            (sent_at, issue["id"]),
        )
        self.db.update_run(run_id, stage="SENT", status="COMPLETED")
        return sent_at
