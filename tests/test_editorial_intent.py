from __future__ import annotations

from pathlib import Path

from briefing_skill.archive_editorial_layout import render_archive_variant
from briefing_skill.editorial_intent import (
    decorate_reader_cards,
    derive_editorial_intent,
    reader_projection_repetition_errors,
    reader_sections,
)
from briefing_skill.utils import read_json


ROOT = Path(__file__).resolve().parents[1]


def test_editorial_intent_foregrounds_counter_intuitive_work() -> None:
    item = {
        "title": "ZCube去掉Spine后反而更稳",
        "core_conclusion": "去掉Spine后P99 TTFT反而下降。",
        "mechanism": "静态ECMP在结构化流量下可能形成不均衡。",
        "result": "P99 TTFT下降40.6%。",
        "boundary": "只覆盖单一集群。",
        "project_relevance": "",
    }
    intent = derive_editorial_intent(item, item_role="supplement", brief_item_id="zcube")
    assert intent["primary_focus"] == "contradiction"
    assert intent["title_style"] == "question"
    assert intent["reader_depth"] == "normal"
    assert intent["section_plan"] == ["contradiction"]

    reader = {"body": ["静态ECMP在结构化流量下可能形成长期热点，因此更少的路径反而更均衡。"]}
    sections = reader_sections(reader, item, item_role="supplement", brief_item_id="zcube")
    assert sections[0]["heading"] == "为什么会这样"


def test_deep_card_gets_at_most_two_semantic_sections() -> None:
    item = {
        "type": "论文",
        "title": "Kairos",
        "core_conclusion": "预填排队时借用解码节点。",
        "mechanism": "调度器逐请求估算TTFT和解码侧余量，并实现偏转决策。",
        "result": "2P2D集群把SLO维持到9RPS。",
        "boundary": "实验规模较小。",
        "project_relevance": "",
    }
    reader = {
        "body": [
            "调度器逐请求估算TTFT，同时检查解码侧还能承受多少额外负载。",
            "在2P2D实验中，满足SLO的负载上限提高到9RPS。",
            "第三段不应进入读者卡。",
        ]
    }
    intent = derive_editorial_intent(item, item_role="core", brief_item_id="kairos")
    assert intent["primary_focus"] == "mechanism"  # generic “实现” must not mean engineering
    sections = reader_sections(reader, item, item_role="core", brief_item_id="kairos")
    assert [row["heading"] for row in sections] == ["调度怎么判断", "关键结果"]
    assert len(sections) == 2


def test_real_release_keeps_engineering_focus() -> None:
    item = {
        "type": "Release",
        "title": "vLLM v0.27.1正式发布",
        "core_conclusion": "本次版本发布主要包含兼容性和接口更新。",
        "mechanism": "运行时增加新的配置入口。",
        "result": "",
        "boundary": "",
        "project_relevance": "",
    }
    intent = derive_editorial_intent(item, item_role="supplement", brief_item_id="vllm-release")
    assert intent["primary_focus"] == "engineering"
    sections = reader_sections(
        {"body": ["运行时增加新的配置入口。"]},
        item,
        item_role="supplement",
        brief_item_id="vllm-release",
    )
    assert sections[0]["heading"] == "实际改了什么"


def test_issue_wide_repetition_guard_detects_project_verb_rhythm() -> None:
    bad = {
        "results": [
            {"title": "Alpha用调度器减少等待"},
            {"title": "Beta让缓存跨节点共享"},
            {"title": "Gamma通过预取降低时延"},
            {"title": "Delta把状态留在项目里"},
            {"title": "一个不同句式的标题"},
        ]
    }
    assert reader_projection_repetition_errors(bad)
    good = {
        "results": [
            {"title": "为什么少一层Spine反而更稳？"},
            {"title": "Kairos：Prefill堵住时借Decode救急"},
            {"title": "确定性推理未必需要重写内核"},
            {"title": "CommitKV关心的是哪些KV真的可以删"},
            {"title": "ZhuLong让Agent自己验证未文档化API"},
        ]
    }
    assert reader_projection_repetition_errors(good) == []


def test_decorator_adds_headings_without_changing_reader_text() -> None:
    html = '<html><body><div id="item-x"><h2>标题</h2><p>导语。</p><p>调度器逐请求估算余量。</p><p>关键结果保持不变。</p></div></body></html>'
    machine = {
        "x": {
            "type": "论文",
            "mechanism": "调度器逐请求估算余量。",
            "result": "关键结果保持不变。",
            "boundary": "",
            "core_conclusion": "",
            "project_relevance": "",
        }
    }
    readers = {"x": {"role": "core", "body": ["调度器逐请求估算余量。", "关键结果保持不变。"]}}
    out = decorate_reader_cards(html, machine, readers)
    assert "调度怎么判断" in out
    assert "关键结果" in out
    assert "调度器逐请求估算余量。" in out
    assert "关键结果保持不变。" in out
    assert out.count('data-reader-section-heading="1"') == 2


def test_2026_08_17_archive_can_be_reprojected_with_specific_headings() -> None:
    issue_dir = ROOT / "archive" / "issues" / "2026-08-17"
    issue = read_json(issue_dir / "issue.json", {})
    reader = read_json(issue_dir / "reader.json", {})
    html = render_archive_variant(issue_dir, issue, reader, variant="email.html")
    assert 'data-reader-section-heading="1"' in html
    assert "为什么会这样" in html  # ZCube
    assert "调度怎么判断" in html  # Kairos
    assert "缓存怎么处理" in html  # AAFLOW+/PTStore family
    assert "Genesis把长时程开发的记忆留在项目里" in html
    assert (issue_dir / "original" / "email.html").is_file()
