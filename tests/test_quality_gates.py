from __future__ import annotations

import json
from pathlib import Path

from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database
from briefing_skill.dedup import EventClusterer
from briefing_skill.emailer import EmailService
from briefing_skill.expanded import select_expanded_rows
from briefing_skill.tasks import brief_item_validation_errors
from briefing_skill.utils import now_iso, source_identity_key, write_json


def _config() -> ConfigBundle:
    return ConfigBundle(
        topics={"topics": [{"id": "tpn", "name": "TPN"}]},
        sources={},
        scoring={
            "expanded_v2": {
                "core_max": 14,
                "observation_max": 8,
                "total_max": 18,
                "max_per_topic": 8,
                "core_score": 70,
                "observation_score": 60,
            },
            "freshness_gates": {
                "core_max_age_days": 3,
                "adjacent_max_age_days": 7,
                "absolute_max_age_days": 14,
            },
            "radar": {"max_age_days": 7, "total_max": 6, "max_per_category": 2},
        },
        settings={"timezone": "Asia/Shanghai"},
        email={},
    )


def test_freshness_is_a_hard_gate_and_never_fills_with_old_or_unknown_items(tmp_path: Path) -> None:
    rows = []
    for item_id, published in (
        ("today", "2026-08-05T00:00:00Z"),
        ("adjacent", "2026-08-01T00:00:00Z"),
        ("old", "2026-07-20T00:00:00Z"),
        ("unknown", None),
    ):
        path = tmp_path / f"{item_id}.json"
        write_json(path, {"title": item_id, "published_at": published, "sources": [{"source_level": "A"}]})
        rows.append(
            {
                "id": item_id,
                "score": 90,
                "json_path": path.name,
                "fact_check_status": "PASS",
                "topic_id": "tpn",
                "source_published_at": published,
                "last_pushed_at": None,
            }
        )

    selected, excluded, counts, _ = select_expanded_rows(
        tmp_path,
        _config(),
        rows,
        reference_date="2026-08-05",
    )

    assert [(row["id"], row["item_role"]) for row in selected] == [
        ("today", "core"),
        ("adjacent", "observation"),
    ]
    assert counts["total"] == 2
    assert {row["id"] for row in excluded} == {"old", "unknown"}


def _insert_fact(db: Database, run_id: str, candidate_id: str, url: str, hint: str) -> None:
    identity = source_identity_key(url)
    now = now_iso()
    db.execute(
        """
        INSERT INTO raw_items(
            id, run_id, source_id, discovery_source, source_level, discovery_only,
            title, canonical_url, original_url, identity_key, published_at,
            priority, payload_json, created_at
        ) VALUES (?, ?, 'arxiv', 'arXiv', 'A', 0, ?, ?, ?, ?, ?, 20, '{}', ?)
        """,
        (f"raw-{candidate_id}", run_id, hint, url, url, identity, now, now),
    )
    db.execute(
        """
        INSERT INTO candidates(id, run_id, raw_item_id, topic_id, direction_id, rule_score, status, created_at)
        VALUES (?, ?, ?, 'tpn', 'd', 90, 'FACTS_READY', ?)
        """,
        (candidate_id, run_id, f"raw-{candidate_id}", now),
    )
    db.execute(
        """
        INSERT INTO facts(id, run_id, candidate_id, json_path, quality_score, event_hint, created_at)
        VALUES (?, ?, ?, ?, 90, ?, ?)
        """,
        (f"facts-{candidate_id}", run_id, candidate_id, f"{candidate_id}.json", hint, now),
    )


def test_arxiv_identity_reuses_sent_event_across_versions_and_languages(tmp_path: Path) -> None:
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    db.create_run("r1")
    db.create_run("r2")
    _insert_fact(db, "r1", "c1", "https://arxiv.org/abs/2607.25431v1", "CodeNib repository index")
    first = EventClusterer(db).persist("r1", EventClusterer(db).cluster_run("r1"))[0]
    db.execute("UPDATE events SET last_pushed_at=? WHERE id=?", (now_iso(), first["event_id"]))

    _insert_fact(db, "r2", "c2", "https://arxiv.org/abs/2607.25431v2", "CodeNib代码仓库索引")
    second = EventClusterer(db).persist("r2", EventClusterer(db).cluster_run("r2"))[0]

    assert source_identity_key("https://arxiv.org/abs/2607.25431v1") == "arxiv:2607.25431"
    assert first["event_id"] == second["event_id"]
    assert db.fetchone("SELECT last_pushed_at FROM events WHERE id=?", (second["event_id"],))["last_pushed_at"]


def test_brief_item_validator_rejects_fragments_and_ellipsis() -> None:
    item = {
        "core_conclusion": "这是完整结论。",
        "mechanism": "系统按稳定标识完成跨期事件去重。",
        "result": "测试确认同一来源不会重复入选。",
        "boundary": "仅适用于有稳定原始链接的事件。",
        "project_relevance": "项目侧应继续核验没有稳定链接的事件。",
    }
    assert brief_item_validation_errors(item, min_chars=10, max_chars=1000) == []
    item["result"] = "测试结果显示…"
    assert any("result must end" in error for error in brief_item_validation_errors(item, min_chars=10, max_chars=1000))


def test_radar_filters_nontechnical_items_caps_categories_and_remembers_sent_urls(tmp_path: Path) -> None:
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    db.create_run("r1")
    now = now_iso()
    db.execute(
        "INSERT INTO issues(id,run_id,status,date_from,date_to,created_at,updated_at) VALUES ('i1','r1','DRAFT','2026-08-05','2026-08-05',?,?)",
        (now, now),
    )
    technical = [
        ("Agent runtime parallel tool calls", "Agent tool call runtime benchmark"),
        ("Repository index for coding agents", "Code search and context retrieval"),
        ("New LLM serving scheduler", "Inference throughput and latency"),
        ("GPU kernel compiler update", "Kernel runtime benchmark"),
        ("CXL memory for AI clusters", "GPU memory and interconnect"),
        ("Optical AI Fabric prototype", "Network topology for GPU cluster"),
    ]
    blocked = [
        ("EA builds playable generative game worlds", "Gaming executive interview"),
        ("Palantir CEO comments after quarterly earnings", "Stock and revenue discussion"),
    ]
    columns = (
        "id", "run_id", "source_id", "discovery_source", "source_level", "title", "summary",
        "original_url", "canonical_url", "published_at", "priority", "payload_json", "created_at",
    )
    rows = []
    for index, (title, summary) in enumerate(technical + blocked):
        url = f"https://example.com/{index}"
        rows.append((str(index), "r1", "aihot", "AI HOT", "B", title, summary, url, url, "2026-08-04T00:00:00Z", 100-index, "{}", now))
    db.executemany(
        f"INSERT INTO raw_items({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
        rows,
    )
    service = EmailService(tmp_path, _config(), db)
    groups = service._aihot_groups("2026-08-05", issue_id="i1", issue_data={"items": []})
    selected = [item for group in groups for item in group["items"]]

    assert len(selected) == 6
    assert all("Palantir" not in item["title"] and not item["title"].startswith("EA ") for item in selected)
    assert all(len(group["items"]) <= 2 for group in groups)

    service._record_sent({"id": "i1", "run_id": "r1"}, now_iso(), "test@example.com", "m1")
    db.create_run("r2")
    db.execute(
        "INSERT INTO issues(id,run_id,status,date_from,date_to,created_at,updated_at) VALUES ('i2','r2','DRAFT','2026-08-05','2026-08-05',?,?)",
        (now, now),
    )
    assert service._aihot_groups("2026-08-05", issue_id="i2", issue_data={"items": []}) == []
