from __future__ import annotations

import json
from pathlib import Path

from briefing_skill.archive_reader_repair import repair_reader_sidecars_from_sent_html
from briefing_skill.reader_projection import machine_item_hash
from briefing_skill.utils import write_json


def _item(item_id: str) -> dict:
    return {
        "brief_item_id": item_id,
        "title": "跨模型缓存减少重复Prefill",
        "topic_id": "tpn",
        "topic_name": "TPN",
        "direction_id": "kv_transfer",
        "published_at": "2026-08-23T00:00:00Z",
        "score": 88,
        "core_conclusion": "缓存可以跨模型复用。",
        "mechanism": "系统学习一个方向性映射。",
        "result": "实验减少了重复Prefill。",
        "boundary": "只覆盖同家族模型。",
        "project_relevance": "可以先做小规模验证。",
        "sources": [{"publisher": "arXiv", "url": "https://arxiv.org/abs/2608.00001", "source_level": "A"}],
    }


def test_repair_uses_sent_html_and_binds_final_issue_hash(tmp_path: Path) -> None:
    run_id = "2026-08-23-194951"
    item_id = "item-1"
    item = _item(item_id)
    run_dir = tmp_path / "workspace" / "runs" / run_id
    write_json(
        run_dir / "issue" / "issue.json",
        {"core_items": [], "observations": [item]},
    )
    (run_dir / "email.html").write_text(
        f"""<html><body><td id=\"item-{item_id}\">
        <h2><a href=\"https://arxiv.org/abs/2608.00001\">闭式映射复用跨模型缓存</a></h2>
        <p>研究让接收模型复用源模型缓存，跳过重复Prefill。</p>
        <div><b>机制</b>按目标层拟合方向性映射。</div>
        <div><b>证据</b>多组模型保留了独立Prefill准确率。</div>
        <div><b>边界</b>仅评估同家族模型。</div>
        <div><b>启发</b>可以先做小规模验证。</div>
        </td></body></html>""",
        encoding="utf-8",
    )

    assert repair_reader_sidecars_from_sent_html(tmp_path, run_id) == [item_id]
    sidecar = json.loads((run_dir / "reader_items" / f"{item_id}.json").read_text())
    assert sidecar["title"] == "闭式映射复用跨模型缓存"
    assert sidecar["lead"].startswith("研究让接收模型复用")
    assert len(sidecar["body"]) == 3
    assert "同家族模型" in sidecar["body"][-1]
    assert sidecar["_provenance"]["source_item_hash"] == machine_item_hash(item)
    assert sidecar["_provenance"]["repair_source"] == "sent_html"


def test_machine_hash_ignores_issue_render_wrapper_fields() -> None:
    item = _item("item-1")
    wrapped = {
        **item,
        "item_role": "supplement",
        "fact_check_status": "PASS",
        "anchor_id": "item-item-1",
        "visual_plan": {"visual_mode": "text_only"},
        "illustration": {},
    }
    assert machine_item_hash(item) == machine_item_hash(wrapped)
