from __future__ import annotations

import os
import re
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

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
        topic_groups = self._topic_groups(data)
        judgement_refs = self._judgement_refs(data)
        aihot_groups = self._aihot_groups(data.get("date_to"))
        html_text = template.render(
            issue=data,
            subject=subject,
            footer=self.config.email.get("footer", ""),
            topic_names=topic_names,
            topic_groups=topic_groups,
            judgement_refs=judgement_refs,
            aihot_groups=aihot_groups,
            aihot_count=sum(len(group["items"]) for group in aihot_groups),
        )
        path = self.root / "workspace" / "runs" / run_id / "email.html"
        path.write_text(html_text, encoding="utf-8")
        self.db.execute("UPDATE issues SET subject=?, email_path=?, status=?, updated_at=? WHERE id=?", (subject, str(path.relative_to(self.root)), status_after, now_iso(), issue["id"]))
        self.db.update_run(run_id, stage=status_after)
        return path

    @staticmethod
    def _shorten(text: str | None, limit: int = 110) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip()
        return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"

    def _topic_groups(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        core_items = data.get("core_items")
        if core_items is None:
            core_items = [item for item in data.get("items", []) if item.get("item_role", "core") == "core"]
        observations = data.get("observations", [])
        by_topic: dict[str, list[dict[str, Any]]] = {}
        observations_by_topic: dict[str, list[dict[str, Any]]] = {}
        for item in core_items:
            item.setdefault("anchor_id", f"item-{item.get('brief_item_id', '')}")
            item["compact_conclusion"] = self._shorten(item.get("core_conclusion"), 150)
            item["compact_mechanism"] = self._shorten(item.get("mechanism"), 105)
            item["compact_result"] = self._shorten(item.get("result") or item.get("evidence_summary"), 105)
            item["compact_boundary"] = self._shorten(item.get("boundary"), 90)
            item["compact_relevance"] = self._shorten(item.get("project_relevance"), 105)
            by_topic.setdefault(item.get("topic_id", "unknown"), []).append(item)
        for item in observations:
            item.setdefault("anchor_id", f"item-{item.get('brief_item_id', '')}")
            observations_by_topic.setdefault(item.get("topic_id", "unknown"), []).append(item)
        groups = []
        seen = set()
        for topic in self.config.topic_list():
            items = by_topic.get(topic["id"], [])
            topic_observations = observations_by_topic.get(topic["id"], [])
            if items or topic_observations:
                groups.append({"id": topic["id"], "name": topic["name"], "description": topic.get("description", ""), "items": items, "observations": topic_observations, "total_count": len(items) + len(topic_observations)})
                seen.add(topic["id"])
        for topic_id in set(by_topic) | set(observations_by_topic):
            if topic_id not in seen:
                items = by_topic.get(topic_id, [])
                topic_observations = observations_by_topic.get(topic_id, [])
                sample = (items or topic_observations)[0]
                groups.append({"id": topic_id, "name": sample.get("topic_name") or topic_id, "description": "", "items": items, "observations": topic_observations, "total_count": len(items) + len(topic_observations)})
        return groups

    @staticmethod
    def _normalise_reference(value: str) -> str:
        return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff²]+", "", value).lower()

    def _judgement_refs(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        core_items = data.get("core_items") or [item for item in data.get("items", []) if item.get("item_role", "core") == "core"]
        result = []
        for judgement in data.get("synthesis", {}).get("judgements", []):
            normalised_judgement = self._normalise_reference(str(judgement))
            refs = []
            for item in core_items:
                title = str(item.get("title", ""))
                alias = re.split(r"[：:]", title, maxsplit=1)[0]
                leading_identifier = re.match(r"^[A-Za-z0-9²]+", title)
                if leading_identifier and leading_identifier.group(0).lower() not in {"agent", "ai", "llm"}:
                    alias = leading_identifier.group(0)
                normalised_alias = self._normalise_reference(alias)
                if len(normalised_alias) >= 2 and normalised_alias in normalised_judgement:
                    refs.append({"anchor_id": item.get("anchor_id") or f"item-{item.get('brief_item_id', '')}", "title": title})
            if not refs and core_items:
                # Syntheses from older runs did not persist item IDs. Resolve a
                # deterministic best match from technical tokens and topic cues.
                topic_cues = {
                    "tpn": ("tpn", "kvcache", "kv cache", "token", "网络", "带宽", "通信"),
                    "memory_dsa": ("dsa", "cxl", "内存", "memory", "numa"),
                    "dpu_inline": ("dpu", "doca", "dpdk", "卸载", "随路"),
                    "agent_acceleration": ("agent", "code", "read", "grep", "工具", "代码"),
                    "cross_region": ("跨域", "跨区", "crossregion", "迁移", "kvcache"),
                    "optical_network": ("光交换", "ocs", "optical", "光路"),
                }
                judgement_lower = str(judgement).lower()
                tokens = {
                    token.lower()
                    for token in re.findall(r"[A-Za-z][A-Za-z0-9²-]{2,}", str(judgement))
                    if token.lower() not in {"the", "and", "with", "from", "llm"}
                }
                ranked = []
                for item in core_items:
                    searchable = " ".join(
                        str(item.get(key, ""))
                        for key in ("title", "core_conclusion", "mechanism", "result", "project_relevance")
                    ).lower()
                    score = sum(2 for token in tokens if token in searchable)
                    score += sum(1 for cue in topic_cues.get(str(item.get("topic_id")), ()) if cue in judgement_lower)
                    ranked.append((score, float(item.get("score") or 0), item))
                best_score, _, best = max(ranked, key=lambda entry: (entry[0], entry[1], str(entry[2].get("brief_item_id", ""))))
                if best_score > 0:
                    refs.append({"anchor_id": best.get("anchor_id") or f"item-{best.get('brief_item_id', '')}", "title": str(best.get("title", ""))})
            result.append({"text": judgement, "refs": refs})
        return result

    @staticmethod
    def _parse_source_time(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _aihot_category(title: str, summary: str) -> str:
        text = f"{title} {summary}".lower()
        if any(term in text for term in ("版权", "法院", "copyright", "suno", "政策")):
            return "政策与产业"
        if any(term in text for term in ("agent", "智能体", "office", "办公")):
            return "Agent与生产力"
        if any(term in text for term in ("记忆", "memory", "架构演进")):
            return "模型与架构"
        return "模型与科学前沿"

    def _aihot_groups(self, issue_date: str | None) -> list[dict[str, Any]]:
        configured_timezone = ZoneInfo(str(self.config.settings.get("timezone", "Asia/Shanghai")))
        end = (
            datetime.fromisoformat(f"{issue_date}T23:59:59").replace(tzinfo=configured_timezone).astimezone(timezone.utc)
            if issue_date
            else datetime.now(timezone.utc)
        )
        start = end - timedelta(days=7)
        rows = self.db.fetchall(
            "SELECT title, summary, original_url, aihot_url, canonical_url, published_at, discovered_at FROM raw_items WHERE source_id='aihot' ORDER BY priority DESC, LENGTH(COALESCE(summary,'')) DESC, COALESCE(published_at, discovered_at) DESC, title"
        )
        categories = {name: [] for name in ("模型与科学前沿", "Agent与生产力", "模型与架构", "政策与产业")}
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        for row in rows:
            published = self._parse_source_time(row.get("published_at") or row.get("discovered_at"))
            if not published or not (start <= published <= end):
                continue
            key = row.get("canonical_url") or row.get("original_url") or row.get("aihot_url") or row["title"]
            title_key = self._normalise_reference(row["title"])
            if key in seen_urls or title_key in seen_titles:
                continue
            seen_urls.add(key)
            seen_titles.add(title_key)
            category = self._aihot_category(row["title"], row.get("summary") or "")
            categories[category].append(
                {
                    "title": row["title"],
                    "summary": self._shorten(row.get("summary"), 105),
                    "url": row.get("original_url") or row.get("aihot_url"),
                    "aihot_url": row.get("aihot_url"),
                    "published_at": published.date().isoformat(),
                }
            )
            if len(seen_urls) >= 12:
                break
        return [{"name": name, "items": items} for name, items in categories.items() if items]

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
            "UPDATE events SET last_pushed_at=? WHERE id IN (SELECT bi.event_id FROM issue_items ii JOIN brief_items bi ON bi.id=ii.brief_item_id WHERE ii.issue_id=? AND bi.approved=1)",
            (sent_at, issue["id"]),
        )
        self.db.update_run(run_id, stage="SENT", status="COMPLETED")
        return sent_at
