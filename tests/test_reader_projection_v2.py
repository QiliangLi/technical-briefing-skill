from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from briefing_skill.reader_projection_v2 import (
    FIXED_BRIEFING_TITLE,
    decorate_reader_blocks,
    issue_synthesis_validation_errors_v2,
    reader_contract_errors_v2,
)


ROOT = Path(__file__).resolve().parents[1]


def test_reader_schema_is_block_based_and_model_selects_heading_key() -> None:
    schema = json.loads((ROOT / "schemas" / "reader-item-writing.schema.json").read_text(encoding="utf-8"))
    item = schema["properties"]["results"]["items"]
    assert item["required"] == ["brief_item_id", "title", "blocks", "used_fields"]
    assert "lead" not in item["properties"]
    assert "body" not in item["properties"]
    keys = item["properties"]["blocks"]["items"]["properties"]["heading_key"]["enum"]
    assert None in keys
    assert {"scheduling", "cache", "result", "boundary", "contradiction"}.issubset(set(keys))


def test_reader_prompt_has_no_binding_editorial_plan_or_title_rotation() -> None:
    prompt = (ROOT / "prompts" / "reader-item-writing.md").read_text(encoding="utf-8")
    assert "editorial_intent" not in prompt
    assert "title_style" not in prompt
    assert "$human-writing" not in prompt
    assert "heading_key" in prompt
    assert "There is no required title style" in prompt
    assert "There is no required `lead -> mechanism -> result -> boundary -> takeaway` sequence" in prompt


def test_model_selected_heading_beats_keywords_inside_paragraph() -> None:
    text = "KV Cache会参与这组实验，但这一段真正报告的是端到端结果。"
    html = f'<table><tr><td id="item-x"><p>{text}</p></td></tr></table>'
    rendered = decorate_reader_blocks(
        html,
        {"x": {"blocks": [{"heading_key": "result", "text": text}]}},
        issue_date="2026-08-20",
    )
    soup = BeautifulSoup(rendered, "html.parser")
    heading = soup.select_one('[data-reader-section-heading="1"]')
    assert heading is not None
    assert heading.get_text(strip=True) == "关键结果"
    assert heading.get("data-reader-section-role") == "result"
    assert "缓存怎么处理" not in rendered


def test_null_heading_is_a_normal_heading_free_block() -> None:
    text = "这段开场本身就能自然接在标题后面，因此不需要额外的小标题。"
    html = f'<table><tr><td id="item-x"><p>{text}</p></td></tr></table>'
    rendered = decorate_reader_blocks(
        html,
        {"x": {"blocks": [{"heading_key": None, "text": text}]}},
        issue_date="2026-08-20",
    )
    assert 'data-reader-section-heading="1"' not in rendered
    assert text in rendered


def test_reader_contract_does_not_reject_natural_project_verb_title() -> None:
    machine = {
        "title": "Kairos",
        "core_conclusion": "Kairos让空闲解码节点分担突发预填请求。",
        "mechanism": "调度器逐请求估算等待时间和解码侧余量。",
        "result": "实验显示这种调度可以减少预填排队。",
        "boundary": "实验规模有限。",
        "project_relevance": "可用于验证解耦调度策略。",
    }
    result = {
        "title": "Kairos让空闲解码节点分担突发预填",
        "blocks": [
            {
                "heading_key": "scheduling",
                "text": "调度器逐请求估算等待时间和解码侧余量。",
            }
        ],
        "used_fields": ["mechanism"],
    }
    assert reader_contract_errors_v2(result, machine) == []


def test_issue_synthesis_keeps_judgements_but_drops_generated_headline() -> None:
    schema = json.loads((ROOT / "schemas" / "issue-synthesis.schema.json").read_text(encoding="utf-8"))
    assert "headline" not in schema["properties"]
    assert "headline" not in schema["required"]
    judgements = schema["properties"]["judgements"]
    assert judgements["minItems"] == 1
    assert judgements["maxItems"] == 3
    assert judgements["items"]["properties"]["title"]["maxLength"] == 64
    assert judgements["items"]["properties"]["body"]["maxLength"] == 400

    prompt = (ROOT / "prompts" / "issue-synthesis.md").read_text(encoding="utf-8")
    assert "Do **not** generate a `headline`" in prompt
    assert "Return **1-3 judgements; usually 2-3**" in prompt
    assert "Do not call any writing Skill here" in prompt


def test_issue_judgements_may_each_use_one_strong_evidence_item() -> None:
    input_data = {
        "items": [
            {"brief_item_id": "a", "title": "A", "core_conclusion": "A结论。"},
            {"brief_item_id": "b", "title": "B", "core_conclusion": "B结论。"},
        ]
    }
    output = {
        "judgements": [
            {"title": "第一个判断", "body": "这个结果挑战了原来的系统假设。", "evidence_item_ids": ["a"]},
            {"title": "第二个判断", "body": "另一个结果给出了新的工程边界。", "evidence_item_ids": ["b"]},
        ]
    }
    assert issue_synthesis_validation_errors_v2(output, input_data) == []


def test_bootstrap_uses_v2_and_keeps_legacy_editorial_intent_out_of_current_run() -> None:
    source = (ROOT / "briefing_skill" / "bootstrap.py").read_text(encoding="utf-8")
    assert "install_reader_projection_v2()" in source
    assert "install_editorial_intent()" not in source


def test_archive_rerender_preserves_sent_v2_heading_markers() -> None:
    source = (ROOT / "briefing_skill" / "archive_editorial_layout.py").read_text(encoding="utf-8")
    assert "sent original already contains the model-selected headings" in source
    assert "data-reader-section-heading" in source


def test_fixed_publication_title_is_code_owned() -> None:
    assert FIXED_BRIEFING_TITLE == "AI语义Fabric技术情报（公测版）"
