from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from briefing_skill.fact_check_minimal_patch import (
    _patch_contract_errors,
    apply_minimal_corrections,
)


def _item() -> dict:
    return {
        "title": "KVCache状态进入网络调度",
        "type": "论文",
        "topic_name": "TPN",
        "direction_name": "KVCache调度",
        "published_at": "2026-08-11",
        "importance": "重点关注",
        "core_conclusion": "该方案在明确实验条件下利用KVCache位置状态改善请求调度，并保持结论边界。",
        "mechanism": "调度器联合缓存位置和请求紧迫度安排传输与执行顺序。",
        "result": "实验在指定基线与工作负载下显示端到端性能得到改善。",
        "boundary": "收益依赖论文给定的负载与系统配置。",
        "project_relevance": "该结果支持继续评估状态感知网络是否能减少跨域KVCache搬移等待。",
        "keywords": ["KVCache", "网络调度", "状态感知"],
        "sources": [
            {
                "publisher": "arXiv",
                "url": "https://arxiv.org/abs/2608.12345",
                "source_level": "A",
                "primary": True,
                "published_at": "2026-08-11",
            }
        ],
        "discovered_via": None,
        "incremental_update": False,
        "incremental_change": None,
        "score": 88.0,
        "_provenance": {"task_id": "writer-1"},
    }


def test_minimal_patch_changes_only_named_field_and_preserves_provenance() -> None:
    item = _item()
    patched = apply_minimal_corrections(
        item,
        [
            {
                "field": "result",
                "before": item["result"],
                "after": "实验仅在指定基线与工作负载下显示端到端性能改善，不能外推到其他配置。",
                "reason": "补回实验条件和外推边界",
            }
        ],
    )

    assert patched["result"] != item["result"]
    assert patched["mechanism"] == item["mechanism"]
    assert patched["score"] == item["score"]
    assert patched["sources"] == item["sources"]
    assert patched["_provenance"] == item["_provenance"]


def test_minimal_patch_rejects_stale_before_text() -> None:
    with pytest.raises(ValueError, match="stale"):
        apply_minimal_corrections(
            _item(),
            [{"field": "result", "before": "旧文本", "after": "新文本", "reason": "test"}],
        )


def test_minimal_patch_rejects_immutable_or_duplicate_fields() -> None:
    item = _item()
    with pytest.raises(ValueError, match="cannot patch field score"):
        apply_minimal_corrections(
            item,
            [{"field": "score", "before": "88.0", "after": "90", "reason": "test"}],
        )
    with pytest.raises(ValueError, match="multiple patches"):
        apply_minimal_corrections(
            item,
            [
                {"field": "result", "before": item["result"], "after": "第一次修正后的结果描述完整保留实验条件。", "reason": "one"},
                {"field": "result", "before": "第一次修正后的结果描述完整保留实验条件。", "after": "第二次修正。", "reason": "two"},
            ],
        )


def test_patch_contract_accepts_provenance_sidecar_and_valid_local_patch(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    item = _item()
    result = {
        "brief_item_id": "item-1",
        "pass": True,
        "issues": ["结果句需要保留外推边界"],
        "corrections": [
            {
                "field": "result",
                "before": item["result"],
                "after": "实验仅在指定基线与工作负载下显示端到端性能改善，不能外推到其他系统配置。",
                "reason": "保留实验条件和边界",
            }
        ],
    }
    errors = _patch_contract_errors(
        root,
        result,
        {"brief_item": item, "length": {"min_chars": 120, "max_chars": 360}},
    )
    assert errors == []


def test_failed_fact_check_cannot_apply_patch() -> None:
    errors = _patch_contract_errors(
        Path(__file__).resolve().parents[1],
        {
            "brief_item_id": "item-1",
            "pass": False,
            "issues": ["证据不足"],
            "corrections": [
                {"field": "result", "before": _item()["result"], "after": "修改。", "reason": "test"}
            ],
        },
        {"brief_item": _item(), "length": {"min_chars": 120, "max_chars": 360}},
    )
    assert errors == ["failed fact check must not apply corrections"]


def test_new_schema_rejects_whole_item_rewrite() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas" / "fact-check-patch-batch.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    valid = {
        "results": [
            {"brief_item_id": "item-1", "pass": True, "issues": [], "corrections": []}
        ]
    }
    assert list(validator.iter_errors(valid)) == []

    invalid = {
        "results": [
            {
                "brief_item_id": "item-1",
                "pass": True,
                "issues": [],
                "corrections": [],
                "corrected_item": _item(),
            }
        ]
    }
    assert list(validator.iter_errors(invalid))


def test_prompt_explicitly_forbids_second_writer_behavior() -> None:
    root = Path(__file__).resolve().parents[1]
    prompt = (root / "prompts" / "fact-check-patch-batch.md").read_text(encoding="utf-8")
    assert "Fact Check is a verifier, not a second writer" in prompt
    assert "Never return a replacement item" in prompt
    assert "Do not rewrite an unaffected field" in prompt
