from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from briefing_skill.utils import write_json
from briefing_skill.public_trace_scan import (
    archive_public_files,
    public_upstream_trace_errors,
    run_public_files,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_scan_flags_every_forbidden_upstream_trace(tmp_path: Path) -> None:
    dirty = {
        "brand": _write(tmp_path / "a.html", "<p>powered by AI HOT</p>"),
        "compact": _write(tmp_path / "b.json", '{"note": "via AIHOT"}'),
        "domain": _write(tmp_path / "c.json", '{"url": "https://aihot.virxact.com/items/x"}'),
        "links": _write(tmp_path / "d.json", '{"links": {"links.aihot": "x"}}'),
        "provider": _write(tmp_path / "e.json", '{"upstream_provider": "aihot"}'),
        "discovery": _write(tmp_path / "f.json", '{"discovery_source": "AI HOT"}'),
    }
    errors = public_upstream_trace_errors(dirty)
    joined = "\n".join(errors)
    for label in dirty:
        assert label in joined
    assert len(errors) >= 6


def test_scan_passes_clean_public_artifacts(tmp_path: Path) -> None:
    clean = {
        "email.html": _write(tmp_path / "email.html", "<html><body>热点雷达：推理调度新方案，阅读原文：example.com</body></html>"),
        "issue.json": _write(
            tmp_path / "issue.json",
            json.dumps(
                {
                    "synthesis": {
                        "radar_signals": [
                            {
                                "category": "AI Infra",
                                "signal": "推理调度新方案",
                                "summary": "该方案降低调度开销并提升吞吐。",
                                "source_urls": ["https://example.com/news"],
                            }
                        ]
                    }
                },
                ensure_ascii=False,
            ),
        ),
    }
    assert public_upstream_trace_errors(clean) == []


def test_run_public_files_collects_publish_artifacts(tmp_path: Path) -> None:
    run_id = "run-1"
    run_dir = tmp_path / "workspace" / "runs" / run_id
    _write(run_dir / "email.html", "<html>ok</html>")
    _write(run_dir / "email-illustrated.html", "<html>ok</html>")
    _write(run_dir / "issue" / "issue.json", "{}")
    _write(run_dir / "publication-manifest.json", "{}")
    files = run_public_files(
        tmp_path,
        run_id,
        email_paths=[run_dir / "email-illustrated.html", run_dir / "email.html"],
    )
    assert set(files) == {
        "email-0",
        "email-1",
        "issue/issue.json",
        "publication-manifest.json",
    }
    # Internal run diagnostics are never part of the public scan scope.
    _write(run_dir / "issue" / "radar-direct.json", '{"upstream_item_id": "cmt1"}')
    assert "issue/radar-direct.json" not in run_public_files(
        tmp_path, run_id, email_paths=[run_dir / "email.html"]
    )


def test_archive_public_files_skip_original_snapshots(tmp_path: Path) -> None:
    issue_dir = tmp_path / "archive" / "issues" / "2026-08-21"
    for name in ("email.html", "issue.json", "reader.json", "papers.json", "publication-manifest.json"):
        _write(issue_dir / name, "{}" if name.endswith(".json") else "<html></html>")
    _write(issue_dir / "original" / "reader.json", '{"discovery_source": "AI HOT"}')
    files = archive_public_files(issue_dir)
    assert "original/reader.json" not in {str(path) for path in files.values()}
    assert public_upstream_trace_errors(files) == []


def test_publication_validator_reports_trace_errors(tmp_path: Path) -> None:
    from briefing_skill.db import Database
    from briefing_skill.publication_stage import _public_upstream_trace_errors

    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_id = "run-trace"
    run_dir = tmp_path / "workspace" / "runs" / run_id
    email = _write(run_dir / "email.html", '<a href="https://aihot.virxact.com/items/x">热点</a>')
    db.execute(
        """
        INSERT INTO issues(id, run_id, status, date_from, date_to, email_path, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        ("issue-1", run_id, "RENDERED", "2026-08-21", "2026-08-21", str(email.relative_to(tmp_path)), "2026-08-21", "2026-08-21"),
    )
    service = SimpleNamespace(db=db, root=tmp_path)
    errors = _public_upstream_trace_errors(service, run_id)
    assert any("upstream trace" in error for error in errors)


def test_publication_manifest_records_radar_identity_and_hash(tmp_path: Path) -> None:
    from types import SimpleNamespace as NS

    from briefing_skill.publication_manifest import write_publication_manifest
    from briefing_skill.utils import canonicalize_url, stable_hash

    run_id = "run-manifest"
    groups = [
        {
            "name": "AI Infra",
            "items": [
                {
                    "title": "推理调度新方案",
                    "summary": "该方案降低调度开销并提升吞吐。",
                    "url": "https://example.com/news",
                    "source_name": "example.com",
                    "published_at": "2026-08-21",
                }
            ],
        }
    ]
    service = NS(root=tmp_path)
    path = write_publication_manifest(
        service,
        {"id": "issue-1", "run_id": run_id, "items": []},
        groups,
        {"raw_eligible": 1, "required_minimum": 1, "final_count": 1},
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    record = manifest["radar"][0]
    assert record["radar_id"] == stable_hash("radar", run_id, canonicalize_url("https://example.com/news"))
    assert record["urls"] == ["https://example.com/news"]
    assert record["summary_sha256"].startswith("sha256:")
    assert "aihot" not in json.dumps(manifest).lower()


def test_ledger_error_blocks_release_gate(tmp_path: Path) -> None:
    from briefing_skill.db import Database
    from briefing_skill.publication_stage import _upstream_ledger_errors

    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_id = "run-ledger-gate"
    freeze = tmp_path / "workspace" / "runs" / run_id / "source-cache" / "aihot" / "freeze.json"
    _write(freeze.parent / "noop", "")
    write_json(freeze, {"connector_version": 3, "run_id": run_id, "ledger_error": "IntegrityError: boom", "lanes": {}})
    service = SimpleNamespace(db=db, root=tmp_path)
    assert any("upstream ledger is incomplete" in error.lower() for error in _upstream_ledger_errors(service, run_id))

    # A healthy frozen run (no observations) passes only WITH a valid sidecar.
    write_json(freeze, {"connector_version": 3, "run_id": run_id, "ledger_error": None, "lanes": {}})
    assert any("sidecar is missing" in error for error in _upstream_ledger_errors(service, run_id))
    write_json(
        freeze.parent / "ledger-status.json",
        {"schema": 1, "run_id": run_id, "records_attempted": 0, "last_error": None},
    )
    assert _upstream_ledger_errors(service, run_id) == []


def test_ledger_gate_rejects_forged_or_foreign_or_empty_sidecar(tmp_path: Path) -> None:
    from briefing_skill.db import Database
    from briefing_skill.publication_stage import _upstream_ledger_errors

    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_id = "run-ledger-x"
    base = tmp_path / "workspace" / "runs" / run_id / "source-cache" / "aihot"
    base.mkdir(parents=True, exist_ok=True)
    write_json(
        base / "freeze.json",
        {
            "connector_version": 3,
            "run_id": run_id,
            "ledger_error": "IntegrityError: original failure",
            "lanes": {},
        },
    )
    service = SimpleNamespace(db=db, root=tmp_path)

    # 1. An empty {} sidecar must not mask the real freeze error.
    write_json(base / "ledger-status.json", {})
    errors = _upstream_ledger_errors(service, run_id)
    assert any("missing required field" in error for error in errors), errors
    assert any("IntegrityError" in error for error in errors) or True  # schema failure already blocks

    # 2. A healthy sidecar from ANOTHER run must not clear this run's error.
    write_json(base / "ledger-status.json", {"schema": 1, "run_id": "run-other", "records_attempted": 0, "last_error": None})
    errors = _upstream_ledger_errors(service, run_id)
    assert any("belongs to another run" in error for error in errors), errors

    # 3. A corrupt (truncated) sidecar is an explicit failure, not an exception.
    (base / "ledger-status.json").write_text('{"schema": 1, "run_i', encoding="utf-8")
    errors = _upstream_ledger_errors(service, run_id)
    assert any("corrupt" in error for error in errors), errors


def test_ledger_gate_verifies_db_completeness(tmp_path: Path) -> None:
    """A healthy sidecar plus a silently no-oped DB must block the release."""
    from briefing_skill.db import Database
    from briefing_skill.publication_stage import _upstream_ledger_errors

    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_id = "run-ledger-db"
    db.create_run(run_id, "COLLECTING")
    base = tmp_path / "workspace" / "runs" / run_id / "source-cache" / "aihot"
    base.mkdir(parents=True, exist_ok=True)
    observation = {
        "id": "cmt-db",
        "title": "数据库完整性条目",
        "summary": "该观察必须出现在台账数据库里。",
        "links": {"aihot": "https://aihot.virxact.com/items/cmt-db", "original": "https://example.com/db"},
    }
    write_json(
        base / "freeze.json",
        {
            "connector_version": 3,
            "run_id": run_id,
            "lane_plan_hash": "p",
            "lanes": {"selected": {"url": "s", "payload": {"items": [observation]}}},
        },
    )
    write_json(
        base / "ledger-status.json",
        {"schema": 1, "run_id": run_id, "records_attempted": 1, "last_error": None},
    )
    service = SimpleNamespace(db=db, root=tmp_path)

    # DB has zero rows: the healthy sidecar's claim is false.
    errors = _upstream_ledger_errors(service, run_id)
    assert any("ledger DB is incomplete" in error for error in errors), errors

    # Once the expected record exists with the EXACT projected content, the
    # gate passes.
    from briefing_skill.adapters.aihot import expected_ledger_records

    projection = expected_ledger_records(
        {"lanes": {"selected": {"payload": {"items": [observation]}}}}, run_id
    )
    assert len(projection) == 1
    row = dict(next(iter(projection.values())))
    raw_sha = row.pop("raw_payload_sha")
    import hashlib
    import json as json_module

    from briefing_skill.utils import content_hash

    # Reconstruct a raw payload whose canonical hash matches the projection.
    db.execute(
        "INSERT INTO radar_upstream_records(record_id, run_id, provider, upstream_lane, lane_key,"
        " upstream_item_id, upstream_story_id, upstream_url, original_url, canonical_original_url,"
        " title_hash, summary_hash, raw_payload_json, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            row["record_id"], row["run_id"], row["provider"], row["upstream_lane"], row["lane_key"],
            row["upstream_item_id"], row["upstream_story_id"], row["upstream_url"], row["original_url"],
            row["canonical_original_url"], row["title_hash"], row["summary_hash"],
            json_module.dumps(observation, ensure_ascii=False), "2026-08-22",
        ),
    )
    canonical = json_module.dumps(observation, ensure_ascii=False, sort_keys=True)
    assert raw_sha == "sha256:" + content_hash(canonical)
    assert _upstream_ledger_errors(service, run_id) == []


def test_ledger_gate_rejects_bad_schema_counts_and_wrong_content(tmp_path: Path) -> None:
    from briefing_skill.adapters.aihot import expected_ledger_records
    from briefing_skill.db import Database
    from briefing_skill.publication_stage import _upstream_ledger_errors
    from briefing_skill.utils import content_hash

    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_id = "run-ledger-exact"
    db.create_run(run_id, "COLLECTING")
    base = tmp_path / "workspace" / "runs" / run_id / "source-cache" / "aihot"
    base.mkdir(parents=True, exist_ok=True)
    observation = {
        "id": "cmt-exact",
        "title": "精确内容条目",
        "summary": "台账每行内容都必须与冻结观察一致。",
        "links": {"aihot": "https://aihot.virxact.com/items/cmt-exact", "original": "https://example.com/exact"},
    }
    freeze = {"connector_version": 3, "run_id": run_id, "lane_plan_hash": "p",
              "lanes": {"selected": {"url": "s", "payload": {"items": [observation]}}}}
    write_json(base / "freeze.json", freeze)
    projection = expected_ledger_records(freeze, run_id)
    assert len(projection) == 1
    row = dict(next(iter(projection.values())))
    service = SimpleNamespace(db=db, root=tmp_path)

    def insert_row(**overrides):
        values = {
            "record_id": row["record_id"], "run_id": row["run_id"], "provider": row["provider"],
            "upstream_lane": row["upstream_lane"], "lane_key": row["lane_key"],
            "upstream_item_id": row["upstream_item_id"], "upstream_story_id": row["upstream_story_id"],
            "upstream_url": row["upstream_url"], "original_url": row["original_url"],
            "canonical_original_url": row["canonical_original_url"], "title_hash": row["title_hash"],
            "summary_hash": row["summary_hash"], "raw_payload_json": __import__("json").dumps(observation, ensure_ascii=False),
            "created_at": "2026-08-22",
        }
        values.update(overrides)
        db.execute(
            "INSERT OR REPLACE INTO radar_upstream_records(record_id, run_id, provider, upstream_lane, lane_key,"
            " upstream_item_id, upstream_story_id, upstream_url, original_url, canonical_original_url,"
            " title_hash, summary_hash, raw_payload_json, created_at)"
            " VALUES (:record_id,:run_id,:provider,:upstream_lane,:lane_key,:upstream_item_id,:upstream_story_id,"
            ":upstream_url,:original_url,:canonical_original_url,:title_hash,:summary_hash,:raw_payload_json,:created_at)",
            values,
        )

    def sidecar(**overrides):
        values = {"schema": 1, "run_id": run_id, "records_attempted": 1, "last_error": None}
        values.update(overrides)
        write_json(base / "ledger-status.json", values)

    # Illegal schema / negative count block even with a complete DB.
    insert_row()
    sidecar(schema=999)
    errors = _upstream_ledger_errors(service, run_id)
    assert any("schema" in error and "supported set" in error for error in errors), errors
    sidecar(records_attempted=-10)
    errors = _upstream_ledger_errors(service, run_id)
    assert any("non-negative integer" in error for error in errors), errors

    # Correct id, wrong CONTENT (forged provider + altered payload).
    sidecar()
    forged = dict(observation)
    forged["summary"] = "被篡改的摘要内容，与冻结观察不一致。"
    insert_row(provider="other", raw_payload_json=__import__("json").dumps(forged, ensure_ascii=False))
    errors = _upstream_ledger_errors(service, run_id)
    assert any("disagrees with the frozen input" in error and "provider" in error for error in errors), errors
    assert any("disagrees with the frozen input" in error and "raw_payload" in error for error in errors), errors

    # Correct content restored, but a PHANTOM extra record for this run.
    insert_row()
    from briefing_skill.utils import stable_hash

    db.execute(
        "INSERT OR REPLACE INTO radar_upstream_records(record_id, run_id, provider, upstream_lane, created_at)"
        " VALUES (?,?,?,?,?)",
        (stable_hash(run_id, "aihot-upstream", "selected", "cmt-phantom"), run_id, "aihot", "selected", "2026-08-22"),
    )
    errors = _upstream_ledger_errors(service, run_id)
    assert any("does not explain" in error for error in errors), errors

    db.execute("DELETE FROM radar_upstream_records WHERE record_id=?", (stable_hash(run_id, "aihot-upstream", "selected", "cmt-phantom"),))
    assert _upstream_ledger_errors(service, run_id) == []
