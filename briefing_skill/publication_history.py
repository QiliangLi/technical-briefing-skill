from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .utils import canonicalize_url, normalize_text, now_iso, read_json, source_identity_key


@dataclass(frozen=True)
class PublishedSource:
    identity_key: str
    version_key: str
    canonical_url: str
    normalized_title: str
    section: str


def ensure_schema(db) -> None:
    """Create the canonical publication-history tables on existing databases."""

    with db.connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS published_sources (
                issue_id TEXT NOT NULL,
                identity_key TEXT NOT NULL,
                version_key TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                section TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                message_id TEXT,
                PRIMARY KEY(issue_id, canonical_url)
            );
            CREATE INDEX IF NOT EXISTS idx_published_identity
              ON published_sources(identity_key, sent_at DESC);
            CREATE INDEX IF NOT EXISTS idx_published_version
              ON published_sources(version_key, sent_at DESC);
            CREATE INDEX IF NOT EXISTS idx_published_url
              ON published_sources(canonical_url, sent_at DESC);
            CREATE TABLE IF NOT EXISTS publication_sync_state (
                sync_key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT NOT NULL
            );
            """
        )


def _reader_role(node) -> str:
    current = node
    while current is not None:
        attrs = getattr(current, "attrs", {}) or {}
        role = str(attrs.get("data-reader-role") or "").strip()
        if role:
            return role
        current = getattr(current, "parent", None)
    return "publication"


def _published_source(url: str, title: str = "", section: str = "publication") -> PublishedSource | None:
    canonical = canonicalize_url(url)
    if not canonical:
        return None
    parsed = urlparse(canonical)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    # Image assets are publication transport, not technical sources.
    if parsed.netloc.lower() == "raw.githubusercontent.com":
        return None
    host = parsed.netloc.lower()
    if host == "github.com" and "/releases/download/" in parsed.path:
        return None
    identity = source_identity_key(canonical)
    if not identity:
        return None
    return PublishedSource(
        identity_key=identity,
        # canonical_url intentionally retains arXiv v1/v2 and exact release/commit URLs.
        version_key=canonical,
        canonical_url=canonical,
        normalized_title=normalize_text(title),
        section=section or "publication",
    )


def sources_from_final_html(root: Path, issue: dict[str, Any]) -> list[PublishedSource]:
    """Read the actual sent artifact. If it has source links, it is the truth."""

    email_path = str(issue.get("email_path") or "").strip()
    if not email_path:
        return []
    path = (root / email_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return []
    if not path.is_file():
        return []

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    result: dict[str, PublishedSource] = {}
    for link in soup.find_all("a", href=True):
        source = _published_source(
            str(link.get("href") or ""),
            link.get_text(" ", strip=True),
            _reader_role(link),
        )
        if source:
            result.setdefault(source.canonical_url, source)
    return list(result.values())


def _structured_sources(root: Path, db, issue: dict[str, Any]) -> list[PublishedSource]:
    """Fallback for historical SENT issues whose final HTML is unavailable."""

    result: dict[str, PublishedSource] = {}

    def add(url: str | None, title: str = "", section: str = "publication") -> None:
        source = _published_source(str(url or ""), title, section)
        if source:
            result.setdefault(source.canonical_url, source)

    issue_path = str(issue.get("issue_json_path") or "").strip()
    if issue_path and (root / issue_path).is_file():
        data = read_json(root / issue_path, {})
        for item in data.get("items") or []:
            title = str(item.get("title") or "")
            role = str(item.get("item_role") or "core")
            for source in item.get("sources") or []:
                add(source.get("url"), title, role)
        synthesis = data.get("synthesis") or {}
        for signal in synthesis.get("radar_signals") or []:
            for url in signal.get("source_urls") or []:
                add(url, str(signal.get("signal") or ""), "radar-item")

    for row in db.fetchall(
        "SELECT canonical_url,title,category FROM issue_radar_items WHERE issue_id=? ORDER BY position",
        (issue["id"],),
    ):
        category = str(row.get("category") or "")
        section = "appendix" if category.startswith("TOPIC_APPENDIX:") else "radar-item"
        add(row.get("canonical_url"), str(row.get("title") or ""), section)

    # Last-resort database reconstruction for older issues after run artifacts were cleaned.
    if not result:
        rows = db.fetchall(
            """
            SELECT DISTINCT r.original_url,r.canonical_url,r.title
            FROM issue_items ii
            JOIN brief_items bi ON bi.id=ii.brief_item_id
            JOIN event_members em ON em.event_id=bi.event_id
            JOIN candidates c ON c.id=em.candidate_id
            JOIN raw_items r ON r.id=c.raw_item_id
            WHERE ii.issue_id=?
            ORDER BY r.created_at
            """,
            (issue["id"],),
        )
        for row in rows:
            add(row.get("original_url") or row.get("canonical_url"), str(row.get("title") or ""), "core")
    return list(result.values())


def collect_published_sources(root: Path, db, issue: dict[str, Any]) -> list[PublishedSource]:
    """Prefer the actual final HTML; structured state is fallback only.

    This deliberately does not union both representations. If an Agent or operator
    altered the final body before sending, the recipient-visible artifact decides
    what was actually published.
    """

    html_sources = sources_from_final_html(root, issue)
    return html_sources if html_sources else _structured_sources(root, db, issue)


def _insert_sources(conn, issue_id: str, sources: Iterable[PublishedSource], sent_at: str, message_id: str) -> int:
    rows = list(sources)
    for source in rows:
        conn.execute(
            """
            INSERT INTO published_sources(
              issue_id,identity_key,version_key,canonical_url,normalized_title,
              section,sent_at,message_id
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(issue_id,canonical_url) DO UPDATE SET
              identity_key=excluded.identity_key,
              version_key=excluded.version_key,
              normalized_title=excluded.normalized_title,
              section=excluded.section,
              sent_at=excluded.sent_at,
              message_id=excluded.message_id
            """,
            (
                issue_id,
                source.identity_key,
                source.version_key,
                source.canonical_url,
                source.normalized_title,
                source.section,
                sent_at,
                message_id,
            ),
        )
    return len(rows)


def _project_compatibility(conn, issue_id: str, sources: Iterable[PublishedSource], sent_at: str) -> None:
    """Project canonical history into legacy columns while old readers are retired."""

    rows = list(sources)
    identities = sorted({source.identity_key for source in rows if source.identity_key})
    if identities:
        placeholders = ",".join("?" for _ in identities)
        conn.execute(
            f"UPDATE events SET last_pushed_at=? WHERE event_key IN ({placeholders})",
            (sent_at, *identities),
        )
    for source in rows:
        conn.execute(
            """
            INSERT INTO radar_history(canonical_url,normalized_title,last_pushed_at,issue_id)
            VALUES (?,?,?,?)
            ON CONFLICT(canonical_url) DO UPDATE SET
              normalized_title=excluded.normalized_title,
              last_pushed_at=excluded.last_pushed_at,
              issue_id=excluded.issue_id
            """,
            (source.canonical_url, source.normalized_title, sent_at, issue_id),
        )
    # The HTML-derived source rows carry no upstream identity; project the
    # final radar cards' item/story ids so cross-period dedup can block the
    # same event republished under a new report URL and title.
    conn.execute(
        """
        INSERT INTO radar_history(
            canonical_url,normalized_title,last_pushed_at,issue_id,upstream_item_id,story_id
        )
        SELECT canonical_url,normalized_title,?,issue_id,upstream_item_id,story_id
        FROM issue_radar_items WHERE issue_id=?
        ON CONFLICT(canonical_url) DO UPDATE SET
          last_pushed_at=excluded.last_pushed_at,
          issue_id=excluded.issue_id,
          upstream_item_id=COALESCE(excluded.upstream_item_id, radar_history.upstream_item_id),
          story_id=COALESCE(excluded.story_id, radar_history.story_id)
        """,
        (sent_at, issue_id),
    )


def record_delivery(service, issue: dict[str, Any], sent_at: str, recipients: str, message_id: str) -> None:
    """Atomically commit delivery state and the exact reader-visible source history."""

    ensure_schema(service.db)
    sources = collect_published_sources(service.root, service.db, issue)
    if not sources:
        raise RuntimeError("Refusing to record SENT without any reconstructable reader-facing source")

    expected = len({source.canonical_url for source in sources})
    with service.db.transaction() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO send_history(issue_id,sent_at,recipients,message_id,status) VALUES (?,?,?,?,?)",
            (issue["id"], sent_at, recipients, message_id, "SENT"),
        )
        conn.execute(
            "UPDATE issues SET status='SENT',updated_at=? WHERE id=?",
            (sent_at, issue["id"]),
        )
        conn.execute("DELETE FROM published_sources WHERE issue_id=?", (issue["id"],))
        _insert_sources(conn, issue["id"], sources, sent_at, message_id)
        actual = conn.execute(
            "SELECT COUNT(*) FROM published_sources WHERE issue_id=?",
            (issue["id"],),
        ).fetchone()[0]
        if actual != expected:
            raise RuntimeError(
                f"Publication history invariant failed: expected {expected} sources, persisted {actual}"
            )
        _project_compatibility(conn, issue["id"], sources, sent_at)
        conn.execute(
            "UPDATE runs SET updated_at=?,stage='SENT',status='COMPLETED' WHERE id=?",
            (sent_at, issue["run_id"]),
        )


def repair_local_sent_history(root: Path, db) -> int:
    """Backfill canonical history for legacy SENT rows from local artifacts/SQLite."""

    ensure_schema(db)
    repaired = 0
    rows = db.fetchall(
        """
        SELECT s.sent_at,s.message_id,i.*
        FROM send_history s JOIN issues i ON i.id=s.issue_id
        WHERE s.status='SENT'
          AND NOT EXISTS(SELECT 1 FROM published_sources p WHERE p.issue_id=s.issue_id)
        ORDER BY s.sent_at
        """
    )
    for issue in rows:
        sources = collect_published_sources(root, db, issue)
        if not sources:
            continue
        with db.transaction() as conn:
            _insert_sources(
                conn,
                issue["id"],
                sources,
                str(issue.get("sent_at") or now_iso()),
                str(issue.get("message_id") or ""),
            )
            _project_compatibility(
                conn,
                issue["id"],
                sources,
                str(issue.get("sent_at") or now_iso()),
            )
        repaired += 1
    return repaired


def project_all_history(db) -> None:
    """Refresh legacy event/Radar markers from the one canonical history table."""

    ensure_schema(db)
    with db.transaction() as conn:
        conn.execute(
            """
            UPDATE events
            SET last_pushed_at=(
              SELECT MAX(p.sent_at) FROM published_sources p
              WHERE p.identity_key=events.event_key
            )
            WHERE event_key IS NOT NULL AND event_key!=''
              AND EXISTS(
                SELECT 1 FROM published_sources p WHERE p.identity_key=events.event_key
              )
            """
        )
        rows = conn.execute(
            """
            SELECT p.* FROM published_sources p
            JOIN (
              SELECT canonical_url,MAX(sent_at) AS sent_at
              FROM published_sources GROUP BY canonical_url
            ) latest
              ON latest.canonical_url=p.canonical_url AND latest.sent_at=p.sent_at
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT INTO radar_history(canonical_url,normalized_title,last_pushed_at,issue_id)
                VALUES (?,?,?,?)
                ON CONFLICT(canonical_url) DO UPDATE SET
                  normalized_title=excluded.normalized_title,
                  last_pushed_at=excluded.last_pushed_at,
                  issue_id=excluded.issue_id
                """,
                (row["canonical_url"], row["normalized_title"], row["sent_at"], row["issue_id"]),
            )


def reconcile_local_history(root: Path, db) -> int:
    repaired = repair_local_sent_history(root, db)
    project_all_history(db)
    return repaired


def publication_state(db, url: str, external_id: str | None = None) -> dict[str, Any]:
    """Return exact-version and stable-identity publication state for a source."""

    ensure_schema(db)
    canonical = canonicalize_url(url)
    identity = source_identity_key(canonical, external_id)
    exact = db.fetchone(
        "SELECT * FROM published_sources WHERE version_key=? ORDER BY sent_at DESC LIMIT 1",
        (canonical,),
    ) if canonical else None
    identity_row = db.fetchone(
        "SELECT * FROM published_sources WHERE identity_key=? ORDER BY sent_at DESC LIMIT 1",
        (identity,),
    ) if identity else None
    return {
        "identity_key": identity,
        "version_key": canonical,
        "exact_version_published": bool(exact),
        "identity_published": bool(identity_row),
        "last_published_at": (exact or identity_row or {}).get("sent_at"),
    }


def published_urls(db) -> set[str]:
    ensure_schema(db)
    return {
        str(row["canonical_url"])
        for row in db.fetchall("SELECT DISTINCT canonical_url FROM published_sources")
        if row.get("canonical_url")
    }


def published_identities(db) -> set[str]:
    ensure_schema(db)
    return {
        str(row["identity_key"])
        for row in db.fetchall("SELECT DISTINCT identity_key FROM published_sources")
        if row.get("identity_key")
    }


def _walk_payload(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, dict):
        yield payload
        for value in payload.values():
            yield from _walk_payload(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_payload(value)


def _message_id(row: dict[str, Any]) -> str:
    return str(row.get("message_id") or row.get("messageId") or row.get("id") or "").strip()


def _message_body(payload: Any) -> str:
    for row in _walk_payload(payload):
        for key in ("html", "body_html", "bodyHtml", "body", "content"):
            value = row.get(key)
            if isinstance(value, str) and "<" in value and "href" in value:
                return value
    return ""


def sync_agently_sent_mailbox(service, *, full: bool = False) -> int:
    """Reconcile actual Agently Sent HTML into canonical history.

    This is an explicit repair command rather than a hidden network dependency of every
    run. It is intended for recovering history after legacy/manual sends.
    """

    from .emailer import AgentlyConfig

    config = AgentlyConfig(
        executable=os.getenv("AGENTLY_CLI", "agently-cli").strip() or "agently-cli",
        recipients=(),
        cc=(),
        bcc=(),
        timeout_seconds=int(os.getenv("AGENTLY_TIMEOUT_SECONDS", "60")),
    )
    args = [config.executable, "message", "+list", "--dir", "sent", "--limit", "100"]
    if not full:
        state = service.db.fetchone(
            "SELECT value FROM publication_sync_state WHERE sync_key='agently_last_sync'"
        )
        if state and state.get("value"):
            args.extend(["--after", str(state["value"])])
    payload = service._run_agently_cli(args, config)

    candidates: dict[str, dict[str, Any]] = {}
    for row in _walk_payload(payload):
        message_id = _message_id(row)
        if message_id:
            candidates.setdefault(message_id, row)

    synced = 0
    latest = now_iso()
    for message_id, summary in candidates.items():
        subject = str(summary.get("subject") or "")
        # Limit repair to this briefing's own messages.
        if subject and "技术情报" not in subject and "brief" not in subject.lower():
            continue
        detail = service._run_agently_cli(
            [config.executable, "message", "+read", "--id", message_id],
            config,
        )
        html = _message_body(detail)
        if not html:
            continue
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        sources: dict[str, PublishedSource] = {}
        for link in soup.find_all("a", href=True):
            source = _published_source(
                str(link.get("href") or ""),
                link.get_text(" ", strip=True),
                _reader_role(link),
            )
            if source:
                sources.setdefault(source.canonical_url, source)
        if not sources:
            continue

        local = service.db.fetchone(
            "SELECT i.* FROM issues i JOIN send_history s ON s.issue_id=i.id WHERE s.message_id=?",
            (message_id,),
        )
        issue_id = str((local or {}).get("id") or f"agently:{message_id}")
        sent_at = str(summary.get("sent_at") or summary.get("sentAt") or summary.get("date") or latest)
        with service.db.transaction() as conn:
            conn.execute("DELETE FROM published_sources WHERE issue_id=?", (issue_id,))
            _insert_sources(conn, issue_id, sources.values(), sent_at, message_id)
            _project_compatibility(conn, issue_id, sources.values(), sent_at)
        synced += 1

    with service.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO publication_sync_state(sync_key,value,updated_at)
            VALUES ('agently_last_sync',?,?)
            ON CONFLICT(sync_key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at
            """,
            (latest, latest),
        )
    return synced


def install_publication_history() -> None:
    """Install one canonical owner for post-delivery publication history."""

    from . import cli
    from .emailer import EmailService

    if getattr(EmailService, "_publication_history_installed", False):
        return

    EmailService._record_sent = record_delivery

    original_build_parser = cli.build_parser

    def build_parser():
        parser = original_build_parser()
        sub = next(
            action for action in parser._actions
            if isinstance(action, __import__("argparse")._SubParsersAction)
        )
        if "publication-sync" not in sub.choices:
            command = sub.add_parser("publication-sync")
            command.add_argument("--full", action="store_true")

            def run(args):
                root, paths, config, db = cli._context(args)
                local = reconcile_local_history(root, db)
                service = EmailService(root, config, db)
                mailbox = sync_agently_sent_mailbox(service, full=args.full)
                print(f"Publication history repaired locally: {local}; Agently messages synced: {mailbox}")
                return 0

            command.set_defaults(func=run)
        return parser

    cli.build_parser = build_parser
    EmailService._publication_history_installed = True
