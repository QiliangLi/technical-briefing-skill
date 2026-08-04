from __future__ import annotations

import os
import json
import re
import shutil
import smtplib
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import ConfigBundle
from .db import Database
from .utils import now_iso, read_json, stable_hash, write_json


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    username: str
    sender: str
    recipients: tuple[str, ...]
    security: str
    port: int


@dataclass(frozen=True)
class AgentlyConfig:
    executable: str
    recipients: tuple[str, ...]
    cc: tuple[str, ...]
    bcc: tuple[str, ...]
    timeout_seconds: int


class AgentlyConfirmationRequired(RuntimeError):
    """Raised after agently-cli prepares a send and returns its confirmation token."""

    exit_code = 8

    def __init__(self, summary: object):
        self.summary = summary
        super().__init__(
            "agently-cli requires a second confirmation call. Review this summary, "
            "then rerun `python briefing.py send --confirm-send`: "
            f"{json.dumps(summary, ensure_ascii=False)}"
        )


class AgentlyCLIError(RuntimeError):
    def __init__(self, exit_code: int, message: str, payload: object | None = None):
        self.exit_code = exit_code
        self.payload = payload
        super().__init__(message)


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


def _split_recipients(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in re.split(r"[,;]", value) if part.strip())


def resolve_email_backend(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    backend = env.get("EMAIL_BACKEND", "agently").strip().lower()
    if backend not in {"agently", "smtp"}:
        raise RuntimeError("EMAIL_BACKEND must be one of: agently, smtp")
    return backend


def resolve_agently_config(environ: Mapping[str, str] | None = None) -> AgentlyConfig:
    env = os.environ if environ is None else environ
    recipient_text = _first_nonempty(env, "AGENTLY_TO", "EMAIL_TO", "SMTP_TO")
    recipients = _split_recipients(recipient_text)
    if not recipients:
        raise RuntimeError("AGENTLY_TO/EMAIL_TO/SMTP_TO is required for agently-cli sending")
    raw_timeout = env.get("AGENTLY_TIMEOUT_SECONDS", "60").strip()
    try:
        timeout = int(raw_timeout)
    except ValueError as exc:
        raise RuntimeError("AGENTLY_TIMEOUT_SECONDS must be an integer") from exc
    if timeout < 1 or timeout > 600:
        raise RuntimeError("AGENTLY_TIMEOUT_SECONDS must be between 1 and 600")
    return AgentlyConfig(
        executable=env.get("AGENTLY_CLI", "agently-cli").strip() or "agently-cli",
        recipients=recipients,
        cc=_split_recipients(env.get("AGENTLY_CC", "")),
        bcc=_split_recipients(env.get("AGENTLY_BCC", "")),
        timeout_seconds=timeout,
    )


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
        date_from = str(data.get("date_from") or "")
        date_to = str(data.get("date_to") or date_from)
        date_label = date_to if date_from == date_to else f"{date_from}—{date_to}"
        subject = self.config.email.get("subject_template", "AI语义Fabric技术情报（内测版）").replace("{{ date_range }}", date_label).replace("{{ item_count }}", str(len(data.get("items", []))))
        topic_groups = self._topic_groups(data)
        judgement_refs = self._judgement_refs(data)
        aihot_groups = self._aihot_groups(data.get("date_to"), issue_id=issue["id"], issue_data=data)
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
    def _clean_text(text: str | None) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    @classmethod
    def _complete_excerpt(cls, text: str | None, limit: int = 120) -> str:
        """Keep a complete short sentence; never manufacture an ellipsis."""
        value = cls._clean_text(text)
        if len(value) <= limit:
            return value
        matches = list(re.finditer(r"[。！？.!?](?:[”’\"）)\]]*)", value[: limit + 1]))
        return value[: matches[-1].end()].strip() if matches else ""

    def _topic_groups(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        core_items = data.get("core_items")
        if core_items is None:
            core_items = [item for item in data.get("items", []) if item.get("item_role", "core") == "core"]
        observations = data.get("observations", [])
        by_topic: dict[str, list[dict[str, Any]]] = {}
        observations_by_topic: dict[str, list[dict[str, Any]]] = {}
        for item in core_items:
            item.setdefault("anchor_id", f"item-{item.get('brief_item_id', '')}")
            # Item-writing owns the text budget. Rendering must never cut a
            # technical sentence after fact checking.
            item["compact_conclusion"] = self._clean_text(item.get("core_conclusion"))
            item["compact_mechanism"] = self._clean_text(item.get("mechanism"))
            item["compact_result"] = self._clean_text(item.get("result") or item.get("evidence_summary"))
            item["compact_boundary"] = self._clean_text(item.get("boundary"))
            item["compact_relevance"] = self._clean_text(item.get("project_relevance"))
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
        if any(term in text for term in ("agent", "智能体", "coding", "code", "repository", "tool call", "开发工具")):
            return "Agent与开发工具"
        if any(term in text for term in ("serving", "inference", "runtime", "compiler", "kernel", "quantization", "推理", "运行时", "编译")):
            return "推理与系统"
        if any(term in text for term in ("gpu", "accelerator", "hbm", "cxl", "rdma", "network", "optical", "memory", "chip", "芯片", "内存", "网络", "光互联")):
            return "芯片、内存与网络"
        return "模型与研究前沿"

    @staticmethod
    def _radar_is_technical(title: str, summary: str) -> bool:
        text = f" {title} {summary} ".lower()
        blocked = (
            "palantir", "alex karp", "ceo", "chief strategy officer", "earnings", "quarterly",
            "stock", "shares", "revenue", "valuation", "融资", "财报", "股价", "营收", "高管",
            "marxism", "马克思主义", "ai act", "regulation", "regulator", "government",
            "copyright", "lawsuit", "法院", "法案", "监管", "版权", "政策争议",
            "electronic arts", " ea ", "playable game", "game world", "gaming", "suno",
            "游戏", "影视", "音乐版权", "consumer app", "消费应用",
        )
        if any(term in text for term in blocked):
            return False
        allowed = (
            "agent", "智能体", "coding", "code search", "repository", "tool call", "context",
            "llm", "model", "benchmark", "reasoning", "模型", "大模型", "评测", "推理",
            "serving", "inference", "runtime", "compiler", "kernel", "quantization", "调度", "运行时", "编译器",
            "gpu", "accelerator", "hbm", "cxl", "rdma", "smartnic", "dpu", "npu", "tpu",
            "memory", "cache", "storage", "network", "optical", "interconnect", "fabric",
            "芯片", "加速器", "内存", "缓存", "存储", "网络", "光互联",
            "distributed training", "collective", "cluster", "observability", "failure recovery",
            "分布式训练", "集群", "可观测", "故障恢复", "ai infrastructure", "ai infra",
        )
        return any(term in text for term in allowed)

    def _persisted_radar_groups(self, issue_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM issue_radar_items WHERE issue_id=? ORDER BY position",
            (issue_id,),
        )
        categories: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            categories.setdefault(row["category"], []).append(
                {
                    "title": row["title"],
                    "summary": row.get("summary") or "",
                    "url": row["canonical_url"],
                    "source_name": row["source_name"],
                    "published_at": row["published_at"],
                }
            )
        return [{"name": name, "items": items} for name, items in categories.items()]

    def _backfill_radar_history(self) -> None:
        """Recover radar URLs from sent HTML created before radar_history existed."""
        from bs4 import BeautifulSoup

        sent_issues = self.db.fetchall(
            """
            SELECT i.id, i.email_path, sh.sent_at
            FROM issues i JOIN send_history sh ON sh.issue_id=i.id
            WHERE sh.status='SENT' AND i.email_path IS NOT NULL
            """
        )
        for issue in sent_issues:
            if self.db.fetchone("SELECT 1 FROM radar_history WHERE issue_id=? LIMIT 1", (issue["id"],)):
                continue
            path = self.root / issue["email_path"]
            if not path.exists():
                continue
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
            heading = soup.find(string=lambda value: bool(value) and str(value).strip() == "热点雷达")
            if not heading:
                continue
            best_by_url: dict[str, str] = {}
            for link in heading.find_all_next("a", href=True):
                url = str(link.get("href") or "").strip()
                if not url.startswith(("http://", "https://")):
                    continue
                label = self._clean_text(link.get_text(" ", strip=True))
                if len(label) > len(best_by_url.get(url, "")):
                    best_by_url[url] = label
            for url, title in best_by_url.items():
                self.db.execute(
                    "INSERT OR IGNORE INTO radar_history(canonical_url, normalized_title, last_pushed_at, issue_id) VALUES (?, ?, ?, ?)",
                    (url, self._normalise_reference(title), issue["sent_at"], issue["id"]),
                )

    def _aihot_groups(
        self,
        issue_date: str | None,
        *,
        issue_id: str | None = None,
        issue_data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if issue_id:
            persisted = self._persisted_radar_groups(issue_id)
            if persisted:
                return persisted
        self._backfill_radar_history()
        configured_timezone = ZoneInfo(str(self.config.settings.get("timezone", "Asia/Shanghai")))
        end = (
            datetime.fromisoformat(f"{issue_date}T23:59:59").replace(tzinfo=configured_timezone).astimezone(timezone.utc)
            if issue_date
            else datetime.now(timezone.utc)
        )
        radar_config = self.config.scoring.get("radar", {})
        start = end - timedelta(days=int(radar_config.get("max_age_days", 7)))
        total_max = int(radar_config.get("total_max", 6))
        max_per_category = int(radar_config.get("max_per_category", 2))
        rows = self.db.fetchall(
            "SELECT title, summary, original_url, canonical_url, published_at, priority FROM raw_items WHERE source_id='aihot' ORDER BY priority DESC, published_at DESC, LENGTH(COALESCE(summary,'')) DESC, title"
        )
        category_order = ("Agent与开发工具", "推理与系统", "芯片、内存与网络", "模型与研究前沿")
        categories = {name: [] for name in category_order}
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        history_rows = self.db.fetchall("SELECT canonical_url, normalized_title FROM radar_history")
        seen_urls.update(str(row["canonical_url"]) for row in history_rows)
        seen_titles.update(str(row["normalized_title"]) for row in history_rows)
        for item in (issue_data or {}).get("items", []):
            for source in item.get("sources", []):
                if source.get("url"):
                    seen_urls.add(str(source["url"]))
        for row in rows:
            original_url = str(row.get("original_url") or "").strip()
            parsed_url = urlparse(original_url)
            hostname = (parsed_url.hostname or "").lower().rstrip(".")
            if parsed_url.scheme.lower() not in {"http", "https"} or not hostname:
                continue
            if hostname == "aihot.virxact.com" or hostname.endswith(".aihot.virxact.com"):
                continue
            published = self._parse_source_time(row.get("published_at"))
            if not published or not (start <= published <= end):
                continue
            key = original_url
            title_key = self._normalise_reference(row["title"])
            if key in seen_urls or title_key in seen_titles:
                continue
            if not self._radar_is_technical(row["title"], row.get("summary") or ""):
                continue
            category = self._aihot_category(row["title"], row.get("summary") or "")
            if len(categories[category]) >= max_per_category:
                continue
            summary = self._complete_excerpt(row.get("summary"), 120)
            categories[category].append(
                {
                    "title": row["title"],
                    "summary": summary,
                    "url": original_url,
                    "source_name": hostname.removeprefix("www."),
                    "published_at": published.date().isoformat(),
                }
            )
            seen_urls.add(key)
            seen_titles.add(title_key)
            if sum(len(items) for items in categories.values()) >= total_max:
                break
        groups = [{"name": name, "items": categories[name]} for name in category_order if categories[name]]
        if issue_id:
            position = 0
            for group in groups:
                for item in group["items"]:
                    position += 1
                    self.db.execute(
                        """
                        INSERT OR REPLACE INTO issue_radar_items(
                            issue_id, canonical_url, normalized_title, category, title,
                            summary, source_name, published_at, position
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            issue_id,
                            item["url"],
                            self._normalise_reference(item["title"]),
                            group["name"],
                            item["title"],
                            item["summary"],
                            item["source_name"],
                            item["published_at"],
                            position,
                        ),
                    )
        return groups

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

    @staticmethod
    def _parse_cli_payload(stdout: str) -> dict[str, Any] | None:
        text = (stdout or "").strip()
        if not text:
            return None
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            for line in reversed(text.splitlines()):
                try:
                    payload = json.loads(line)
                    return payload if isinstance(payload, dict) else None
                except json.JSONDecodeError:
                    continue
        return None

    @staticmethod
    def _payload_data(payload: dict[str, Any] | None) -> dict[str, Any]:
        if not payload:
            return {}
        data = payload.get("data")
        return data if isinstance(data, dict) else payload

    @classmethod
    def _payload_value(cls, payload: dict[str, Any] | None, *keys: str) -> Any:
        data = cls._payload_data(payload)
        for key in keys:
            if key in data:
                return data[key]
        if payload:
            for key in keys:
                if key in payload:
                    return payload[key]
        return None

    @classmethod
    def _cli_error_message(cls, payload: dict[str, Any] | None, stdout: str, stderr: str) -> str:
        error = payload.get("error") if payload else None
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if isinstance(error, str) and error:
            return error
        return (stderr or stdout or "agently-cli failed").strip()

    def _run_agently_cli(self, args: list[str], config: AgentlyConfig) -> dict[str, Any] | None:
        if not shutil.which(config.executable) and not Path(config.executable).exists():
            raise RuntimeError(
                f"agently-cli executable not found: {config.executable}. "
                "Install @tencent-qqmail/agently-cli or set AGENTLY_CLI."
            )
        try:
            completed = subprocess.run(
                args,
                cwd=self.root,
                text=True,
                capture_output=True,
                timeout=config.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"agently-cli timed out after {config.timeout_seconds}s") from exc
        except OSError as exc:
            raise RuntimeError(f"Unable to execute agently-cli: {exc}") from exc
        payload = self._parse_cli_payload(completed.stdout)
        if completed.returncode != 0:
            raise AgentlyCLIError(
                completed.returncode,
                self._cli_error_message(payload, completed.stdout, completed.stderr),
                payload,
            )
        return payload

    @classmethod
    def _message_id(cls, payload: dict[str, Any] | None) -> str:
        value = cls._payload_value(payload, "message_id", "messageId", "id")
        if value:
            return str(value)
        data = cls._payload_data(payload)
        message = data.get("message")
        if isinstance(message, dict):
            value = message.get("message_id") or message.get("messageId") or message.get("id")
            if value:
                return str(value)
        return "agently-cli"

    def _agently_send(self, issue: dict[str, Any], run_id: str) -> str:
        config = resolve_agently_config()
        body_path = (self.root / str(issue["email_path"])).resolve()
        try:
            body_path.relative_to(self.root.resolve())
        except ValueError as exc:
            raise RuntimeError("Email body must be inside the Skill root") from exc
        if not body_path.exists():
            raise RuntimeError(f"Email body does not exist: {body_path}")
        if body_path.stat().st_size > 1024 * 1024:
            raise RuntimeError("agently-cli email body exceeds its 1 MB limit")

        subject = issue.get("subject") or "AI语义Fabric技术情报（内测版）"
        body_rel = body_path.relative_to(self.root.resolve()).as_posix()
        request_key = stable_hash(subject, config.recipients, config.cc, config.bcc, body_path.read_bytes())
        pending_path = self.root / "workspace" / "runs" / run_id / "agently-send-pending.json"
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
        args.extend(["--body-file", body_rel])
        if token:
            args.extend(["--confirmation-token", token])

        try:
            payload = self._run_agently_cli(args, config)
        except AgentlyCLIError as exc:
            candidate = self._payload_value(exc.payload, "confirmation_token", "confirmationToken")
            if exc.exit_code == 8 and candidate:
                summary = self._payload_value(exc.payload, "summary") or {
                    "subject": subject,
                    "to": list(config.recipients),
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

        if self._payload_value(payload, "confirmation_required", "confirmationRequired"):
            candidate = self._payload_value(payload, "confirmation_token", "confirmationToken")
            if candidate:
                summary = self._payload_value(payload, "summary") or {}
                write_json(pending_path, {"confirmation_token": str(candidate), "request_key": request_key, "summary": summary, "created_at": now_iso()})
                raise AgentlyConfirmationRequired(summary)

        pending_path.unlink(missing_ok=True)
        sent_at = now_iso()
        self._record_sent(issue, sent_at, ",".join(config.recipients), self._message_id(payload))
        return sent_at

    def _smtp_send(self, issue: dict[str, Any]) -> str:
        smtp = resolve_smtp_config()
        password = os.getenv("SMTP_PASSWORD")
        msg = EmailMessage()
        msg["Subject"] = issue.get("subject") or "AI语义Fabric技术情报（内测版）"
        msg["From"] = smtp.sender
        msg["To"] = ", ".join(smtp.recipients)
        msg.set_content("本邮件包含HTML技术情报，请使用支持HTML的邮件客户端查看。")
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
        self._record_sent(issue, sent_at, ",".join(smtp.recipients), msg.get("Message-ID"))
        return sent_at

    def _record_sent(self, issue: dict[str, Any], sent_at: str, recipients: str, message_id: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO send_history(issue_id, sent_at, recipients, message_id, status) VALUES (?, ?, ?, ?, ?)",
            (issue["id"], sent_at, recipients, message_id, "SENT"),
        )
        self.db.execute("UPDATE issues SET status='SENT', updated_at=? WHERE id=?", (sent_at, issue["id"]))
        self.db.execute(
            "UPDATE events SET last_pushed_at=? WHERE id IN (SELECT bi.event_id FROM issue_items ii JOIN brief_items bi ON bi.id=ii.brief_item_id WHERE ii.issue_id=? AND bi.approved=1)",
            (sent_at, issue["id"]),
        )
        self.db.execute(
            """
            INSERT OR REPLACE INTO radar_history(canonical_url, normalized_title, last_pushed_at, issue_id)
            SELECT canonical_url, normalized_title, ?, issue_id
            FROM issue_radar_items WHERE issue_id=?
            """,
            (sent_at, issue["id"]),
        )
        self.db.update_run(issue["run_id"], stage="SENT", status="COMPLETED")

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
        if resolve_email_backend() == "agently":
            return self._agently_send(issue, run_id)
        return self._smtp_send(issue)
