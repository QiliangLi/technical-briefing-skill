import json
from pathlib import Path

import pytest

import briefing_skill.expanded as expanded_module
from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database
from briefing_skill.emailer import EmailService
from briefing_skill.expanded import rebuild_expanded_issue
from briefing_skill.pipeline import Pipeline
from briefing_skill.rendering import Renderer
from briefing_skill.utils import now_iso, write_json


def _config() -> ConfigBundle:
    return ConfigBundle(
        topics={"topics": [{"id": "tpn", "name": "状态感知网络、TPN"}, {"id": "agent_acceleration", "name": "Agent语义加速"}]},
        sources={},
        scoring={"expanded_v2": {"core_max": 14, "observation_max": 4, "total_max": 18, "max_per_topic": 8, "core_score": 70, "observation_score": 60}},
        settings={"issue_mode": "expanded_v2"},
        email={},
    )


def test_email_v2_groups_topics_and_links_specific_judgements(tmp_path: Path) -> None:
    service = EmailService(tmp_path, _config(), Database(tmp_path / "briefing.sqlite"))
    core = [
        {"brief_item_id": "a1", "topic_id": "tpn", "title": "SmartGen：分阶段传输", "core_conclusion": "结论", "mechanism": "机制", "result": "结果", "boundary": "边界", "project_relevance": "启发"},
        {"brief_item_id": "a2", "topic_id": "tpn", "title": "ZCube以确定路径缓解拥塞", "core_conclusion": "结论", "mechanism": "机制", "result": "结果", "boundary": "边界", "project_relevance": "启发"},
    ]
    observation = {"brief_item_id": "o1", "topic_id": "agent_acceleration", "title": "CodeCompass", "item_role": "observation"}
    data = {"core_items": core, "observations": [observation], "items": core + [observation], "synthesis": {"judgements": ["SmartGen与ZCube分别优化传输和路径。"]}}

    groups = service._topic_groups(data)
    refs = service._judgement_refs(data)

    assert [group["id"] for group in groups] == ["tpn", "agent_acceleration"]
    assert groups[0]["total_count"] == 2
    assert groups[1]["observations"][0]["item_role"] == "observation"
    assert [ref["anchor_id"] for ref in refs[0]["refs"]] == ["item-a1", "item-a2"]


def test_email_v2_uses_structured_evidence_ids_without_guessing(tmp_path: Path) -> None:
    service = EmailService(tmp_path, _config(), Database(tmp_path / "briefing.sqlite"))
    core = [
        {"brief_item_id": "a1", "title": "标题完全不出现在判断里", "item_role": "core"},
        {"brief_item_id": "a2", "title": "另一个条目", "item_role": "core"},
    ]
    data = {
        "core_items": core,
        "items": core,
        "synthesis": {
            "judgements": [
                {"title": "执行链变化", "body": "判断正文无需重复项目名。", "evidence_item_ids": ["a2"]}
            ]
        },
    }

    refs = service._judgement_refs(data)

    assert refs == [{"title": "执行链变化", "text": "判断正文无需重复项目名。", "refs": [{"anchor_id": "item-a2", "title": "另一个条目"}]}]


def test_aihot_radar_uses_only_local_seven_day_window_and_deduplicates(tmp_path: Path) -> None:
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    service = EmailService(tmp_path, _config(), db)
    required = ("id", "run_id", "source_id", "discovery_source", "source_level", "title", "summary", "original_url", "aihot_url", "canonical_url", "published_at", "discovered_at", "priority", "payload_json", "created_at")
    rows = [
        ("1", "old-run", "aihot", "AI HOT", "B", "OmegaUse OfficeVal", "Agent办公基准", "https://example.com/a", "https://aihot/a", "https://example.com/a", "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z", 1, "{}", now_iso()),
        ("2", "other-run", "aihot", "AI HOT", "B", "OmegaUse OfficeVal", "重复", "https://example.com/b", "https://aihot/b", "https://example.com/b", "2026-08-01T01:00:00Z", "2026-08-01T01:00:00Z", 1, "{}", now_iso()),
        ("3", "old-run", "aihot", "AI HOT", "B", "过期消息", "旧", "https://example.com/old", "https://aihot/old", "https://example.com/old", "2026-07-01T00:00:00Z", "2026-07-01T00:00:00Z", 1, "{}", now_iso()),
        ("4", "old-run", "aihot", "AI HOT", "B", "无原始来源", "丢弃", "https://aihot.virxact.com/items/4", "https://aihot.virxact.com/items/4", "https://aihot.virxact.com/items/4", "2026-08-01T02:00:00Z", "2026-08-01T02:00:00Z", 1, "{}", now_iso()),
    ]
    db.executemany(f"INSERT INTO raw_items({','.join(required)}) VALUES ({','.join('?' for _ in required)})", rows)

    groups = service._aihot_groups("2026-08-02")

    assert sum(len(group["items"]) for group in groups) == 1
    assert groups[0]["name"] == "Agent与开发工具"
    assert groups[0]["items"][0]["url"] == "https://example.com/a"
    assert groups[0]["items"][0]["source_name"] == "example.com"


def test_expanded_rebuild_requeues_synthesis_and_blocks_email_build(tmp_path: Path) -> None:
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    db.create_run("run-1", "AWAITING_APPROVAL")
    db.create_run("run-2", "READY_FOR_RENDER")
    issue_dir = tmp_path / "workspace" / "runs" / "run-1" / "issue"
    issue_dir.mkdir(parents=True)
    write_json(issue_dir / "issue.json", {"id": "issue-1", "run_id": "run-1", "items": [], "synthesis": {"judgements": []}})
    now = now_iso()
    db.execute("INSERT INTO issues(id,run_id,status,date_from,date_to,issue_json_path,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", ("issue-1", "run-1", "AWAITING_APPROVAL", "2026-08-02", "2026-08-02", "workspace/runs/run-1/issue/issue.json", now, now))
    for event_id, run_id, item_id, score in (("event-core", "run-1", "core", 82), ("event-obs", "run-1", "obs", 65), ("event-other", "run-2", "other", 90)):
        db.execute("INSERT INTO events(id,topic_id,direction_id,canonical_title,fingerprint,score,first_seen_at,last_updated_at,payload_json) VALUES (?,?,?,?,?,?,?,?,?)", (event_id, "tpn", "d", event_id, event_id, score, now, now, "{}"))
        item_path = tmp_path / "workspace" / "runs" / run_id / "items" / f"{item_id}.json"
        write_json(item_path, {"title": item_id, "score": score, "published_at": "2026-08-01T00:00:00Z", "topic_name": "状态感知网络、TPN", "sources": [{"source_level": "A", "url": f"https://example.com/{item_id}"}]})
        db.execute("INSERT INTO brief_items(id,run_id,event_id,json_path,score,fact_check_status,approved,created_at) VALUES (?,?,?,?,?,?,?,?)", (item_id, run_id, event_id, str(item_path.relative_to(tmp_path)), score, "PASS", 1, now))
    db.execute("INSERT INTO issue_items(issue_id,brief_item_id,position,item_role) VALUES (?,?,?,?)", ("issue-1", "core", 1, "core"))

    dry = rebuild_expanded_issue(tmp_path, _config(), db, "run-1", confirm=False)
    assert dry["counts"] == {"core": 1, "observations": 1, "total": 2, "topics": {"tpn": 2}}
    assert db.fetchone("SELECT COUNT(*) n FROM issue_items WHERE issue_id='issue-1'")["n"] == 1

    rebuilt = rebuild_expanded_issue(tmp_path, _config(), db, "run-1", confirm=True)
    assert rebuilt["status"] == "AWAITING_ISSUE_SYNTHESIS"
    assert db.fetchone("SELECT COUNT(*) n FROM issue_items WHERE issue_id='issue-1'")["n"] == 2
    assert db.fetchone("SELECT SUM(approved) n FROM brief_items WHERE run_id='run-1'")["n"] == 0
    assert db.fetchone("SELECT stage FROM runs WHERE id='run-1'")["stage"] == "AWAITING_ISSUE_SYNTHESIS"
    issue = db.fetchone("SELECT synthesis_path,issue_json_path,email_path FROM issues WHERE id='issue-1'")
    assert issue == {"synthesis_path": None, "issue_json_path": None, "email_path": None}
    task = db.fetchone("SELECT status,input_path FROM tasks WHERE run_id='run-1' AND task_type='issue_synthesis'")
    assert task["status"] == "PENDING"
    task_input = json.loads((tmp_path / task["input_path"]).read_text(encoding="utf-8"))
    assert [item["brief_item_id"] for item in task_input["items"]] == ["core"]
    assert len(list((issue_dir / "history").glob("issue-before-expanded-v2-*.json"))) == 1
    with pytest.raises(RuntimeError, match="Issue not ready"):
        EmailService(tmp_path, _config(), db).build("run-1")


def test_expanded_rebuild_accepts_interrupted_draft_without_issue_json(tmp_path: Path) -> None:
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    db.create_run("run-draft", "AWAITING_ISSUE_SYNTHESIS")
    now = now_iso()
    db.execute(
        "INSERT INTO issues(id,run_id,status,date_from,date_to,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        ("issue-draft", "run-draft", "DRAFT", "2026-08-02", "2026-08-02", now, now),
    )
    db.execute(
        "INSERT INTO events(id,topic_id,direction_id,canonical_title,fingerprint,score,first_seen_at,last_updated_at,payload_json) VALUES (?,?,?,?,?,?,?,?,?)",
        ("event-draft", "tpn", "d", "draft", "draft", 82, now, now, "{}"),
    )
    item_path = tmp_path / "workspace" / "runs" / "run-draft" / "items" / "draft.json"
    write_json(
        item_path,
        {
            "title": "draft",
            "score": 82,
            "published_at": "2026-08-01T00:00:00Z",
            "topic_name": "状态感知网络、TPN",
            "sources": [{"source_level": "A", "url": "https://example.com/draft"}],
        },
    )
    db.execute(
        "INSERT INTO brief_items(id,run_id,event_id,json_path,score,fact_check_status,created_at) VALUES (?,?,?,?,?,?,?)",
        (
            "item-draft",
            "run-draft",
            "event-draft",
            str(item_path.relative_to(tmp_path)),
            82,
            "PASS",
            now,
        ),
    )

    rebuilt = rebuild_expanded_issue(tmp_path, _config(), db, "run-draft", confirm=True)

    assert rebuilt["backup"] is None
    assert rebuilt["counts"]["core"] == 1
    assert db.fetchone(
        "SELECT status FROM tasks WHERE run_id='run-draft' AND task_type='issue_synthesis'"
    )["status"] == "PENDING"


def test_email_template_contains_no_item_images() -> None:
    template = (Path(__file__).resolve().parents[1] / "templates" / "email.html").read_text(encoding="utf-8")
    assert "<img" not in template.lower()
    assert "AI语义Fabric技术情报（公测版）" in template
    assert ">热点雷达<" in template
    assert "阅读原文：" in template
    assert "stack-col" in template
    assert "对应：" not in template
    assert "相关解读：" in template
    assert 'data-public-site-link="1"' in template
    assert 'href="https://qiliangli.github.io/technical-briefing-skill/"' in template


def test_expanded_email_validator_checks_the_deliverable_not_unused_cards(tmp_path: Path) -> None:
    email_path = tmp_path / "email.html"
    email_path.write_text(
        '<header>TECHNICAL BRIEFING AI语义Fabric技术情报（公测版） 2026-08-02</header>'
        '<a data-public-site-link="1" href="https://qiliangli.github.io/technical-briefing-skill/">GitHub Pages</a>'
        '<div>本期判断 <span data-judgement-ref-count="1"><a href="#item-a1">对应</a></span></div>'
        '<section id="topic-tpn"><article id="item-a1">内容 阅读原文：<a href="https://example.com/a">原始来源</a></article></section>'
        '<footer>热点雷达 · 未经本简报深度核验</footer>',
        encoding="utf-8",
    )
    report = {"passes": [], "warnings": [], "failures": []}
    Renderer._validate_expanded_email(
        email_path,
        {"date_to": "2026-08-02", "items": [{"brief_item_id": "a1", "topic_id": "tpn"}], "synthesis": {"judgements": ["判断"]}},
        report,
    )

    assert report["failures"] == []
    assert "Expanded email contains no item images" in report["passes"]
    assert "Expanded email judgements expose concrete item references" in report["passes"]
    assert "Expanded email links to the public GitHub Pages site" in report["passes"]


def test_expanded_selection_excludes_items_without_resolved_a_level_source(tmp_path: Path) -> None:
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    db.create_run("run-expanded", "ACTIVE")
    now = now_iso()
    fixtures = (
        ("core", 82, "A"),
        ("observation", 65, "B"),
        ("high-without-a", 78, "B"),
    )
    for item_id, score, source_level in fixtures:
        event_id = f"event-{item_id}"
        db.execute(
            "INSERT INTO events(id,topic_id,direction_id,canonical_title,fingerprint,score,first_seen_at,last_updated_at,payload_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (event_id, "tpn", "d", item_id, event_id, score, now, now, "{}"),
        )
        item_path = tmp_path / "workspace" / "runs" / "run-expanded" / "items" / f"{item_id}.json"
        write_json(
            item_path,
            {"title": item_id, "score": score, "published_at": now, "sources": [{"source_level": source_level, "url": f"https://example.com/{item_id}"}]},
        )
        db.execute(
            "INSERT INTO brief_items(id,run_id,event_id,json_path,score,fact_check_status,created_at) VALUES (?,?,?,?,?,?,?)",
            (item_id, "run-expanded", event_id, str(item_path.relative_to(tmp_path)), score, "PASS", now),
        )

    Pipeline(tmp_path, _config(), db, "run-expanded")._maybe_prepare_issue()

    rows = db.fetchall(
        "SELECT ii.brief_item_id, ii.item_role FROM issue_items ii JOIN issues i ON i.id=ii.issue_id WHERE i.run_id=? ORDER BY ii.position",
        ("run-expanded",),
    )
    assert [(row["brief_item_id"], row["item_role"]) for row in rows] == [("core", "core")]
    synthesis = db.fetchone("SELECT input_path FROM tasks WHERE run_id=? AND task_type='issue_synthesis'", ("run-expanded",))
    synthesis_input = json.loads((tmp_path / synthesis["input_path"]).read_text(encoding="utf-8"))
    assert [item["title"] for item in synthesis_input["items"]] == ["core"]
    assert not db.fetchone("SELECT 1 FROM tasks WHERE run_id=? AND task_type='visual_routing'", ("run-expanded",))
