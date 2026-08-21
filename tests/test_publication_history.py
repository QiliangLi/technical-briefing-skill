from pathlib import Path

import pytest

import briefing_skill.publication_history as history
from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database
from briefing_skill.emailer import EmailService
from briefing_skill.publication_history import (
    publication_state,
    reconcile_local_history,
    record_delivery,
)
from briefing_skill.utils import now_iso, source_identity_key


def _service(tmp_path: Path) -> tuple[Database, EmailService]:
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    service = EmailService(
        tmp_path,
        ConfigBundle(topics={}, sources={}, scoring={}, settings={}, email={}),
        db,
    )
    return db, service


def _issue(db: Database, tmp_path: Path, *, run_id: str = "run-1", issue_id: str = "issue-1", html: str = ""):
    db.create_run(run_id, "READY_TO_SEND")
    path = tmp_path / "workspace" / "runs" / run_id / "email-illustrated.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    created = now_iso()
    db.execute(
        """
        INSERT INTO issues(
          id,run_id,status,email_path,created_at,updated_at
        ) VALUES (?,?,?,?,?,?)
        """,
        (
            issue_id,
            run_id,
            "READY_TO_SEND",
            str(path.relative_to(tmp_path)),
            created,
            created,
        ),
    )
    return db.fetchone("SELECT * FROM issues WHERE id=?", (issue_id,))


def _event(db: Database, event_id: str, url: str) -> None:
    stamp = now_iso()
    db.execute(
        """
        INSERT INTO events(
          id,topic_id,direction_id,canonical_title,fingerprint,event_key,score,
          first_seen_at,last_updated_at,last_pushed_at,payload_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            event_id,
            "topic",
            "direction",
            event_id,
            event_id,
            source_identity_key(url),
            90,
            stamp,
            stamp,
            None,
            "{}",
        ),
    )


def _html(urls: list[str]) -> str:
    links = "".join(
        f'<tr data-reader-role="core"><td><a href="{url}">source-{index}</a></td></tr>'
        for index, url in enumerate(urls)
    )
    return f"<!doctype html><html><body><table>{links}</table></body></html>"


def test_final_html_is_publication_truth_not_stale_database_plan(tmp_path: Path):
    db, service = _service(tmp_path)
    urls = {
        "A": "https://arxiv.org/abs/2608.00001v1",
        "B": "https://example.org/b",
        "C": "https://example.org/c",
        "D": "https://example.org/d",
        "E": "https://example.org/e",
        "F": "https://example.org/f",
    }
    issue = _issue(db, tmp_path, html=_html([urls[key] for key in "ABDEF"]))
    _event(db, "event-a", urls["A"])
    _event(db, "event-c", urls["C"])

    record_delivery(service, issue, "2026-08-12T08:00:00+00:00", "reader@example.com", "msg-1")

    published = {
        row["canonical_url"]
        for row in db.fetchall("SELECT canonical_url FROM published_sources WHERE issue_id='issue-1'")
    }
    assert published == {urls[key] for key in "ABDEF"}
    assert urls["C"] not in published
    assert db.fetchone("SELECT status FROM send_history WHERE issue_id='issue-1'")["status"] == "SENT"
    assert db.fetchone("SELECT last_pushed_at FROM events WHERE id='event-a'")["last_pushed_at"]
    assert db.fetchone("SELECT last_pushed_at FROM events WHERE id='event-c'")["last_pushed_at"] is None

    # Every actually published URL is projected into the legacy URL history, making
    # Deep -> Appendix/Radar and Radar -> Deep de-duplication symmetric.
    legacy_urls = {row["canonical_url"] for row in db.fetchall("SELECT canonical_url FROM radar_history")}
    assert published <= legacy_urls


def test_record_delivery_is_atomic_when_history_write_fails(tmp_path: Path, monkeypatch):
    db, service = _service(tmp_path)
    url = "https://example.org/a"
    issue = _issue(db, tmp_path, html=_html([url]))
    original = history._insert_sources

    def fail_after_insert(conn, issue_id, sources, sent_at, message_id):
        original(conn, issue_id, sources, sent_at, message_id)
        raise RuntimeError("simulated history failure")

    monkeypatch.setattr(history, "_insert_sources", fail_after_insert)
    with pytest.raises(RuntimeError, match="simulated history failure"):
        record_delivery(service, issue, "2026-08-12T08:00:00+00:00", "reader@example.com", "msg-1")

    assert db.fetchone("SELECT * FROM send_history WHERE issue_id='issue-1'") is None
    assert db.fetchone("SELECT status FROM issues WHERE id='issue-1'")["status"] == "READY_TO_SEND"
    assert db.fetchall("SELECT * FROM published_sources") == []


def test_stable_identity_and_exact_version_are_distinct(tmp_path: Path):
    db, service = _service(tmp_path)
    v1 = "https://arxiv.org/abs/2608.05886v1"
    v2 = "https://arxiv.org/abs/2608.05886v2"
    issue = _issue(db, tmp_path, html=_html([v1]))
    record_delivery(service, issue, "2026-08-12T08:00:00+00:00", "reader@example.com", "msg-1")

    state_v1 = publication_state(db, v1)
    state_v2 = publication_state(db, v2)
    assert state_v1["exact_version_published"] is True
    assert state_v1["identity_published"] is True
    assert state_v2["exact_version_published"] is False
    assert state_v2["identity_published"] is True
    assert state_v1["identity_key"] == state_v2["identity_key"] == "arxiv:2608.05886"


def test_legacy_sent_rows_are_repaired_before_next_cli_run(tmp_path: Path):
    db, _ = _service(tmp_path)
    url = "https://example.org/already-sent"
    issue = _issue(db, tmp_path, html=_html([url]))
    _event(db, "event-sent", url)
    db.execute(
        "INSERT INTO send_history(issue_id,sent_at,recipients,message_id,status) VALUES (?,?,?,?,?)",
        (issue["id"], "2026-08-09T08:00:00+00:00", "reader@example.com", "old-msg", "SENT"),
    )

    repaired = reconcile_local_history(tmp_path, db)

    assert repaired == 1
    assert db.fetchone("SELECT 1 AS ok FROM published_sources WHERE canonical_url=?", (url,))["ok"] == 1
    assert db.fetchone("SELECT last_pushed_at FROM events WHERE id='event-sent'")["last_pushed_at"] == "2026-08-09T08:00:00+00:00"
    assert db.fetchone("SELECT 1 AS ok FROM radar_history WHERE canonical_url=?", (url,))["ok"] == 1


def test_local_repair_is_idempotent(tmp_path: Path):
    db, _ = _service(tmp_path)
    url = "https://example.org/idempotent"
    issue = _issue(db, tmp_path, html=_html([url]))
    db.execute(
        "INSERT INTO send_history(issue_id,sent_at,recipients,message_id,status) VALUES (?,?,?,?,?)",
        (issue["id"], "2026-08-09T08:00:00+00:00", "reader@example.com", "old-msg", "SENT"),
    )
    assert reconcile_local_history(tmp_path, db) == 1
    assert reconcile_local_history(tmp_path, db) == 0
    assert db.fetchone("SELECT COUNT(*) AS n FROM published_sources")["n"] == 1


def test_record_delivery_persists_radar_story_identity(tmp_path: Path) -> None:
    """Two-period repro: the canonical SENT owner must write item/story ids.

    After a real record_delivery, the next run's same-story candidate (new
    report URL and title) must be blocked by cross-period identity dedup.
    """
    from briefing_skill.radar_direct import normalized_radar_candidates

    db, service = _service(tmp_path)
    issue = _issue(
        db,
        tmp_path,
        html="""
        <html><body>
        <table>
        <tr data-reader-row="radar-row"><td data-reader-role="radar-card" data-radar-category="AI Infra">
        <div data-reader-role="radar-item">
          <a href="https://example.com/report-a">KVCache 扩容第一报道</a>
          <div>该报道描述 KV cache 分层扩容机制与实测收益，内容完整。</div>
        </div>
        </td></tr>
        </table></body></html>
        """,
    )
    db.execute(
        """
        INSERT INTO issue_radar_items(
          issue_id,canonical_url,normalized_title,category,title,summary,
          source_name,published_at,position,upstream_item_id,story_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            issue["id"], "https://example.com/report-a", "kvcache扩容第一报道", "AI Infra",
            "KVCache 扩容第一报道", "该报道描述 KV cache 分层扩容机制与实测收益，内容完整。",
            "example.com", "2026-08-21", 1, "cmt-story", "story-77",
        ),
    )

    record_delivery(service, issue, now_iso(), "test@example.com", "mid-1")

    row = db.fetchone(
        "SELECT upstream_item_id, story_id FROM radar_history WHERE canonical_url=?",
        ("https://example.com/report-a",),
    )
    assert row["upstream_item_id"] == "cmt-story"
    assert row["story_id"] == "story-77"

    # Second period: the same story returns under a new URL and title.
    run2 = "run-2"
    db.create_run(run2, "COLLECTING")
    from tests.test_radar_direct import insert_raw  # noqa: PLC0415

    insert_raw(
        db, run2, url="https://example.com/report-b", title="同一事件的新报道：KV cache 扩容跟进",
        summary="跟进报道描述同一事件的部署细节与限制条件，内容完整。",
        external_id="cmt-new-report", story_id="story-77",
    )
    candidates = normalized_radar_candidates(
        service,
        run2,
        {"run_id": run2, "items": [], "date_to": now_iso()[:10]},
    )
    assert all(candidate["story_id"] != "story-77" for candidate in candidates)
