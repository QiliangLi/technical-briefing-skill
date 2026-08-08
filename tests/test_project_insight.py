import json
from pathlib import Path

from briefing_skill.config import ConfigBundle
from briefing_skill.paths import Paths
from briefing_skill.project_insight import (
    build_project_context_cards,
    enrich_issue_synthesis_input,
    project_insight_semantic_errors,
    render_project_insight_email_block,
)


ROOT = Path(__file__).resolve().parents[1]


def _input_data():
    return {
        "issue_id": "issue-1",
        "items": [
            {
                "brief_item_id": "item-tpn",
                "topic_id": "tpn",
                "topic_name": "状态感知网络、TPN",
                "title": "KV-aware scheduling",
                "core_conclusion": "KVCache位置开始参与网络调度。",
                "mechanism": "调度器联合考虑KVCache位置与带宽。",
                "result": "端到端指标改善。",
                "boundary": "仅在给定拓扑和负载下验证。",
                "project_relevance": "可用于验证网络是否需要感知KVCache状态。",
            },
            {
                "brief_item_id": "item-dpu",
                "topic_id": "dpu_inline",
                "topic_name": "DPU随路卸载",
                "title": "Inline datapath",
                "core_conclusion": "部分数据路径处理迁移到DPU。",
                "mechanism": "数据经过DPU时完成随路处理。",
                "result": "CPU占用下降。",
                "boundary": "收益取决于卸载覆盖率。",
                "project_relevance": "需要确认端到端收益是否来自真正的数据路径缩短。",
            },
        ],
    }


def test_all_configured_topics_have_project_questions_and_context_cards():
    config = ConfigBundle.load(Paths(ROOT))
    topic_ids = [topic["id"] for topic in config.topic_list()]
    cards = build_project_context_cards(ROOT, config, topic_ids)

    assert [card["topic_id"] for card in cards] == topic_ids
    assert len(cards) == len(topic_ids)
    for card in cards:
        assert card["topic_name"]
        assert card["current_questions"]
        assert card["judgement_card"]


def test_issue_synthesis_input_only_carries_context_for_present_topics():
    enriched = enrich_issue_synthesis_input(ROOT, _input_data())
    assert [card["topic_id"] for card in enriched["project_contexts"]] == ["tpn", "dpu_inline"]
    assert enriched["project_insight_policy"]["require_configured_question"] is True
    assert enriched["project_insight_policy"]["allow_empty_when_no_material_change"] is True


def test_new_issue_task_rejects_invented_project_question():
    enriched = enrich_issue_synthesis_input(ROOT, _input_data())
    task = {
        "task_type": "issue_synthesis",
        "metadata_json": json.dumps({"project_insights_required": True}),
    }
    output = {
        "project_insights": [
            {
                "topic_id": "tpn",
                "topic_name": "状态感知网络、TPN",
                "project_question": "一个配置中不存在的新问题",
                "effect": "supports",
                "confidence": "medium",
                "insight": "这条证据加强了当前项目判断。",
                "next_action": "下一步应补充端到端实验。",
                "evidence_item_ids": ["item-tpn"],
            }
        ]
    }
    errors = project_insight_semantic_errors(task, enriched, output)
    assert any("exact configured project_question" in error for error in errors)


def test_valid_project_insight_is_bound_to_configured_question_and_same_topic_evidence():
    enriched = enrich_issue_synthesis_input(ROOT, _input_data())
    context = next(card for card in enriched["project_contexts"] if card["topic_id"] == "tpn")
    task = {
        "task_type": "issue_synthesis",
        "metadata_json": json.dumps({"project_insights_required": True}),
    }
    output = {
        "project_insights": [
            {
                "topic_id": "tpn",
                "topic_name": context["topic_name"],
                "project_question": context["current_questions"][0],
                "effect": "narrows",
                "confidence": "medium",
                "insight": "本期证据说明该判断需要限定在能够获取KVCache位置状态的调度路径内。",
                "next_action": "下一步应对比无状态网络调度和KVCache感知调度的端到端指标。",
                "evidence_item_ids": ["item-tpn", "item-dpu"],
            }
        ]
    }
    assert project_insight_semantic_errors(task, enriched, output) == []


def test_project_insight_cannot_be_supported_only_by_another_topic():
    enriched = enrich_issue_synthesis_input(ROOT, _input_data())
    context = next(card for card in enriched["project_contexts"] if card["topic_id"] == "tpn")
    task = {
        "task_type": "issue_synthesis",
        "metadata_json": json.dumps({"project_insights_required": True}),
    }
    output = {
        "project_insights": [
            {
                "topic_id": "tpn",
                "topic_name": context["topic_name"],
                "project_question": context["current_questions"][0],
                "effect": "supports",
                "confidence": "low",
                "insight": "本期证据对该项目问题提供了新的支持。",
                "next_action": "下一步应验证这一机制是否能够迁移到目标网络路径。",
                "evidence_item_ids": ["item-dpu"],
            }
        ]
    }
    errors = project_insight_semantic_errors(task, enriched, output)
    assert any("same-topic evidence" in error for error in errors)


def test_legacy_issue_task_without_policy_marker_remains_compatible():
    task = {"task_type": "issue_synthesis", "metadata_json": "{}"}
    assert project_insight_semantic_errors(task, _input_data(), {}) == []


def test_email_block_exposes_project_insight_and_evidence_anchor():
    issue = {
        "core_items": [
            {
                "brief_item_id": "item-tpn",
                "anchor_id": "item-item-tpn",
                "title": "KV-aware scheduling",
                "item_role": "core",
            }
        ],
        "synthesis": {
            "project_insights": [
                {
                    "topic_id": "tpn",
                    "topic_name": "状态感知网络、TPN",
                    "project_question": "网络是否能够感知推理阶段、KVCache位置和Token性能目标",
                    "effect": "supports",
                    "confidence": "high",
                    "insight": "本期证据加强了状态感知网络具有独立价值的项目判断。",
                    "next_action": "下一步应在相同GPU负载下对比网络侧和纯GPU侧调度。",
                    "evidence_item_ids": ["item-tpn"],
                }
            ]
        },
    }
    block = render_project_insight_email_block(issue)
    assert 'data-project-insight-count="1"' in block
    assert 'href="#item-item-tpn"' in block
    assert "项目问题" in block
    assert "下一步" in block
