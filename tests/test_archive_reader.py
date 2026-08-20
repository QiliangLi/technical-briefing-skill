from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from briefing_skill.archive_reader import (
    apply_historical_rewrite,
    issue_hash,
    machine_item_hash,
    prepare_rewrite_payload,
)
from briefing_skill.utils import stable_hash, write_json
from scripts.archive_sent_issue import archive_issue


REPO_ROOT = Path(__file__).resolve().parents[1]


def _install_schema(root: Path) -> None:
    target = root / "schemas" / "archive-reader.schema.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "schemas" / "archive-reader.schema.json", target)


def _machine_item(item_id: str) -> dict:
    return {
        "brief_item_id": item_id,
        "title": "Agent Harness把长任务状态保存为版本对象",
        "type": "论文",
        "topic_id": "agent_acceleration",
        "topic_name": "Agent语义加速",
        "direction_id": "agent_harness",
        "direction_name": "Agent Harness与长任务运行环境",
        "published_at": "2026-08-20T00:00:00Z",
        "score": 88,
        "core_conclusion": "Harness把长任务状态从进程中移出，失败后可以恢复。",
        "mechanism": "系统保存版本对象，并在接受门之后提交新状态。",
        "result": "实验报告任务成功率提高。",
        "boundary": "结果只覆盖代码任务。",
        "project_relevance": "可先验证状态恢复是否减少重复工作。",
        "sources": [
            {
                "publisher": "Example Lab",
                "url": "https://example.org/harness",
                "source_level": "A",
            }
        ],
    }


def _issue(run_id: str, item: dict) -> dict:
    return {
        "id": "issue-1",
        "run_id": run_id,
        "date_from": "2026-08-20",
        "date_to": "2026-08-20",
        "layout_mode": "expanded_v2",
        "core_items": [item],
        "observations": [],
        "items": [item],
        "synthesis": {
            "headline": "Harness开始成为长任务Agent的独立系统层",
            "judgements": [
                {
                    "title": "状态正在离开进程",
                    "body": "外部系统开始显式保存长任务状态。",
                    "evidence_item_ids": [item["brief_item_id"]],
                }
            ],
            "watch_next": ["关注接受门在真实代码任务中的误判。"],
            "radar_signals": [],
        },
    }


def _reader(issue: dict) -> dict:
    item = issue["core_items"][0]
    item_id = item["brief_item_id"]
    blocks = [
        {
            "heading_key": None,
            "text": "这项工作把长任务状态保存为外部版本对象，失败后可以恢复。",
        },
        {
            "heading_key": "mechanism",
            "text": "新状态只有通过接受门才会提交，因此回滚和继续执行都有明确边界。",
        },
        {
            "heading_key": "implication",
            "text": "可先验证状态恢复是否真的减少重复工作。",
        },
    ]
    return {
        "schema_version": 1,
        "reader_contract_version": 1,
        "source_issue_hash": issue_hash(issue),
        "issue_date": "2026-08-20",
        "headline": "Harness正在成为长任务Agent的独立系统层",
        "judgements": [
            {
                "title": "状态不再只留在进程里",
                "body": "外部系统开始显式保存长任务状态。",
                "evidence_item_ids": [item_id],
            }
        ],
        "watch_next": ["接下来要看接受门在真实代码任务中会不会误判。"],
        "items": {
            item_id: {
                "source_item_hash": machine_item_hash(item),
                "role": "core",
                "topic_id": item["topic_id"],
                "direction_id": item["direction_id"],
                "published_at": item["published_at"],
                "score": item["score"],
                "sources": item["sources"],
                "title": "Agent跑得久以后，状态不该只留在进程里",
                "lead": blocks[0]["text"],
                "body": [blocks[1]["text"], blocks[2]["text"]],
                "takeaway": None,
                "blocks": blocks,
            }
        },
        "radar": [],
        "generated_at": "2026-08-20T09:45:00+08:00",
        "rewrite_status": "historical_semantic_rewrite",
    }


def test_historical_rewrite_preserves_only_real_original_and_is_idempotent(tmp_path: Path) -> None:
    _install_schema(tmp_path)
    run_id = "2026-08-20-094500"
    item_id = stable_hash(run_id, "item", "event-1")
    issue = _issue(run_id, _machine_item(item_id))
    issue_dir = tmp_path / "archive" / "issues" / "2026-08-20"
    write_json(issue_dir / "issue.json", issue)
    write_json(issue_dir / "papers.json", [])
    original = b"<html><body>actual legacy artifact</body></html>"
    (issue_dir / "email.html").write_bytes(original)

    reader = _reader(issue)
    first = apply_historical_rewrite(tmp_path, issue_dir, reader)
    first_files = {
        name: (issue_dir / name).read_bytes()
        for name in ("reader.json", "email.html", "email-illustrated.html", "publication-manifest.json")
    }
    second = apply_historical_rewrite(tmp_path, issue_dir, reader)

    assert (issue_dir / "original" / "email.html").read_bytes() == original
    assert not (issue_dir / "original" / "email-illustrated.html").exists()
    assert first == second
    assert first["original_variants"] == ["email.html"]
    assert first_files == {
        name: (issue_dir / name).read_bytes()
        for name in first_files
    }
    assert "Agent跑得久以后" in (issue_dir / "email.html").read_text(encoding="utf-8")


def test_historical_rewrite_rejects_changed_identity_and_invented_number(tmp_path: Path) -> None:
    _install_schema(tmp_path)
    run_id = "2026-08-20-094500"
    item_id = stable_hash(run_id, "item", "event-1")
    issue = _issue(run_id, _machine_item(item_id))
    issue_dir = tmp_path / "archive" / "issues" / "2026-08-20"
    write_json(issue_dir / "issue.json", issue)
    write_json(issue_dir / "papers.json", [])
    (issue_dir / "email.html").write_text("legacy", encoding="utf-8")

    changed_id = _reader(issue)
    changed_id["items"]["another-id"] = changed_id["items"].pop(item_id)
    with pytest.raises(ValueError, match="item IDs changed"):
        apply_historical_rewrite(tmp_path, issue_dir, changed_id)

    invented = _reader(issue)
    invented["items"][item_id]["body"] = ["系统吞吐提高了99%。"]
    with pytest.raises(ValueError, match="introduces numbers"):
        apply_historical_rewrite(tmp_path, issue_dir, invented)
    assert not (issue_dir / "original").exists()


def test_historical_rewrite_preserves_original_layout_and_images(tmp_path: Path) -> None:
    _install_schema(tmp_path)
    run_id = "2026-08-20-094500"
    item_id = stable_hash(run_id, "item", "event-1")
    issue = _issue(run_id, _machine_item(item_id))
    issue_dir = tmp_path / "archive" / "issues" / "2026-08-20"
    write_json(issue_dir / "issue.json", issue)
    write_json(issue_dir / "papers.json", [])
    original = f"""<!doctype html><html><head><title>旧标题</title><style>.mail-shell{{max-width:700px}}</style></head>
    <body class=\"mail-shell\"><h1>旧标题</h1><img src=\"https://example.org/figure.png\">
    <table data-reader-role=\"judgement\"><tr><td><div style=\"font-weight:700\">旧判断</div><div>旧判断正文</div></td></tr></table>
    <table><tr><td id=\"item-{item_id}\"><h2><a href=\"https://example.org/harness\">旧条目</a></h2>
    <p>旧摘要</p><div><b>机制</b>旧机制</div><div><b>证据</b>旧证据</div>
    <div><b>边界</b>旧边界</div><div><b>启发</b>旧启发</div></td></tr></table></body></html>"""
    (issue_dir / "email.html").write_text(original, encoding="utf-8")

    apply_historical_rewrite(tmp_path, issue_dir, _reader(issue))
    html = (issue_dir / "email.html").read_text(encoding="utf-8")

    assert "https://example.org/figure.png" in html
    assert ".mail-shell{max-width:700px}" in html
    assert "Harness正在成为长任务Agent的独立系统层" in html
    assert "Agent跑得久以后，状态不该只留在进程里" in html
    assert "新状态只有通过接受门才会提交" in html
    assert "旧摘要" not in html
    assert "旧机制" not in html
    assert "旧证据" not in html
    assert "旧边界" not in html
    assert "旧启发" not in html
    assert 'href="https://example.org/harness"' in html
    assert html.count("<img") == original.count("<img")
    item_node = BeautifulSoup(html, "html.parser").find(id=f"item-{item_id}")
    assert item_node is not None
    assert not item_node.find("b", string=lambda value: value and value.strip() in {"机制", "证据", "边界", "启发"})


def test_prepare_rewrite_is_one_issue_and_exposes_locked_output(tmp_path: Path) -> None:
    run_id = "2026-08-20-094500"
    item_id = stable_hash(run_id, "item", "event-1")
    issue = _issue(run_id, _machine_item(item_id))
    payload = prepare_rewrite_payload(issue)

    assert payload["constraints"]["one_published_issue_only"] is True
    assert payload["locked_output"]["items"][item_id]["role"] == "core"
    assert payload["locked_output"]["source_issue_hash"] == issue_hash(issue)
    assert payload["locked_output"]["generated_at"] == "2026-08-20T09:45:00+08:00"
    assert payload["issue"]["items"][0]["machine_item"]["sources"][0]["url"] == "https://example.org/harness"


def test_future_archive_keeps_email_variants_separate_and_checks_reader_hash(tmp_path: Path) -> None:
    _install_schema(tmp_path)
    run_id = "2026-08-20-094500"
    event_id = "event-1"
    item_id = stable_hash(run_id, "item", event_id)
    machine = _machine_item(item_id)
    issue = _issue(run_id, machine)
    run_dir = tmp_path / "workspace" / "runs" / run_id
    write_json(run_dir / "issue" / "issue.json", issue)
    write_json(run_dir / "items" / f"{event_id}.json", machine)
    title = "Agent跑得久以后，状态不该只留在进程里"
    write_json(
        run_dir / "reader_items" / f"{item_id}.json",
        {
            "brief_item_id": item_id,
            "reader_version": 1,
            "title": title,
            "lead": "这项工作把长任务状态保存为外部版本对象，失败后可以恢复。",
            "body": ["新状态只有通过接受门才会提交，因此回滚和继续执行都有明确边界。"],
            "takeaway": None,
            "used_fields": ["core_conclusion", "mechanism"],
            "_provenance": {
                "run_id": run_id,
                "source_item_hash": machine_item_hash(machine),
                "reader_contract_version": 1,
            },
        },
    )
    headline = issue["synthesis"]["headline"]
    plain = f"<html><body>{headline} plain {title}</body></html>"
    illustrated = f"<html><body>{headline} illustrated {title}</body></html>"
    (run_dir / "email.html").write_text(plain, encoding="utf-8")
    (run_dir / "email-illustrated.html").write_text(illustrated, encoding="utf-8")

    target = archive_issue(tmp_path, run_id)
    manifest_before = (target / "publication-manifest.json").read_bytes()
    archive_issue(tmp_path, run_id)

    assert (target / "email.html").read_text(encoding="utf-8") == plain
    assert (target / "email-illustrated.html").read_text(encoding="utf-8") == illustrated
    assert (target / "original" / "email.html").read_text(encoding="utf-8") == plain
    assert (target / "original" / "email-illustrated.html").read_text(encoding="utf-8") == illustrated
    assert (target / "publication-manifest.json").read_bytes() == manifest_before
    assert json.loads((target / "reader.json").read_text(encoding="utf-8"))["items"][item_id]["title"] == title

    sidecar = json.loads((run_dir / "reader_items" / f"{item_id}.json").read_text(encoding="utf-8"))
    sidecar["_provenance"]["source_item_hash"] = "stale"
    write_json(run_dir / "reader_items" / f"{item_id}.json", sidecar)
    with pytest.raises(ValueError, match="not bound to a current machine item"):
        archive_issue(tmp_path, run_id)


def test_future_archive_rejects_sidecar_bound_to_another_current_item(tmp_path: Path) -> None:
    _install_schema(tmp_path)
    run_id = "2026-08-20-094500"
    first = _machine_item(stable_hash(run_id, "item", "event-1"))
    second = _machine_item(stable_hash(run_id, "item", "event-2"))
    second["title"] = "另一个当前运行条目"
    issue = _issue(run_id, first)
    issue["observations"] = [second]
    run_dir = tmp_path / "workspace" / "runs" / run_id
    write_json(run_dir / "issue" / "issue.json", issue)
    write_json(run_dir / "items" / "event-1.json", first)
    write_json(run_dir / "items" / "event-2.json", second)
    for item, bound_item in ((first, second), (second, second)):
        write_json(
            run_dir / "reader_items" / f"{item['brief_item_id']}.json",
            {
                "reader_version": 1,
                "title": item["title"],
                "lead": "摘要",
                "body": ["正文"],
                "takeaway": None,
                "_provenance": {
                    "run_id": run_id,
                    "source_item_hash": machine_item_hash(bound_item),
                },
            },
        )

    with pytest.raises(ValueError, match="bound to a different current item"):
        archive_issue(tmp_path, run_id)
