import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from briefing_skill.issue_style_polish import (
    FULL_PROMPT,
    FULL_SCHEMA,
    PATCH_PROMPT,
    PATCH_SCHEMA,
    STYLE_FIELDS,
    _reconstruct_sparse_items,
    _strip_redundant_writing_skills,
)


def test_old_per_batch_writing_skill_chain_is_removed() -> None:
    metadata = {
        "required_skills": ["human-writing", "legacy-writing-skill"],
        "skill_mode": "old",
        "keep": "value",
    }
    for task_type in ("item_writing", "item_writing_batch", "issue_synthesis"):
        assert _strip_redundant_writing_skills(task_type, metadata) == {"keep": "value"}

    assert _strip_redundant_writing_skills("fact_check_batch", metadata) == metadata


def test_issue_level_polish_uses_full_fact_locked_rewrite_for_new_runs() -> None:
    root = Path(__file__).resolve().parents[1]
    prompt = (root / "prompts" / FULL_PROMPT).read_text(encoding="utf-8")
    draft_prompt = (root / "prompts" / "item-writing-batch.md").read_text(encoding="utf-8")
    synthesis_prompt = (root / "prompts" / "issue-synthesis.md").read_text(encoding="utf-8")

    assert "single issue-level Chinese editorial pass" in prompt
    assert "Call `$human-writing` **once for the entire `items` array**" in prompt
    assert "Do not default to KEEP" in prompt
    assert "full **language rewrite authority**" in prompt
    assert "Do not call any writing Skill here" in draft_prompt
    assert "Do not call any writing Skill here" in synthesis_prompt

    schema = json.loads((root / "schemas" / FULL_SCHEMA).read_text(encoding="utf-8"))
    result_properties = schema["properties"]["results"]["items"]["properties"]
    assert set(STYLE_FIELDS).issubset(result_properties)
    assert result_properties["mechanism"]["maxLength"] >= 70


def test_sparse_style_schema_remains_available_for_old_run_resume_only() -> None:
    root = Path(__file__).resolve().parents[1]
    prompt = (root / "prompts" / PATCH_PROMPT).read_text(encoding="utf-8")
    schema = json.loads((root / "schemas" / PATCH_SCHEMA).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    assert "default action is **KEEP**" in prompt
    assert list(validator.iter_errors({"patches": []})) == []
    payload = {
        "patches": [
            {
                "brief_item_id": "item-1",
                "field": "mechanism",
                "before": "原机制表述。",
                "after": "更通顺但事实完全相同的机制表述。",
                "reason": "原句主谓关系不清。",
            }
        ]
    }
    assert list(validator.iter_errors(payload)) == []
    assert payload["patches"][0]["field"] in STYLE_FIELDS


def _input_item():
    item = {
        "title": "技术标题",
        "core_conclusion": "核心结论保持不变。",
        "mechanism": "原机制表述。",
        "result": "实验结果保持不变。",
        "boundary": "边界保持不变。",
        "project_relevance": "项目相关性保持不变。",
        "score": 90,
        "sources": [{"url": "https://example.org/source"}],
    }
    return {
        "items": [
            {
                "brief_item_id": "item-1",
                "item": item,
                "length": {"min_chars": 1, "max_chars": 1000},
            }
        ],
        "constraints": {"sparse_patch": True},
    }


def test_good_sparse_resume_noop_is_exactly_identical() -> None:
    input_data = _input_item()
    reconstructed, errors = _reconstruct_sparse_items(input_data, [])
    assert errors == []
    assert reconstructed["item-1"] == input_data["items"][0]["item"]


def test_sparse_resume_patch_leaves_every_other_field_byte_identical() -> None:
    input_data = _input_item()
    before = input_data["items"][0]["item"]
    patches = [
        {
            "brief_item_id": "item-1",
            "field": "mechanism",
            "before": "原机制表述。",
            "after": "机制表述更通顺。",
            "reason": "修复语序。",
        }
    ]
    reconstructed, errors = _reconstruct_sparse_items(input_data, patches)
    assert errors == []
    after = reconstructed["item-1"]
    assert after["mechanism"] == "机制表述更通顺。"
    for field, value in before.items():
        if field != "mechanism":
            assert after[field] == value


def test_stale_before_and_noop_sparse_patch_are_rejected() -> None:
    input_data = _input_item()
    stale = [
        {
            "brief_item_id": "item-1",
            "field": "mechanism",
            "before": "不是当前文本",
            "after": "修改后",
            "reason": "测试 stale patch",
        }
    ]
    _, errors = _reconstruct_sparse_items(input_data, stale)
    assert any("before text does not match" in error for error in errors)

    noop = [
        {
            "brief_item_id": "item-1",
            "field": "mechanism",
            "before": "原机制表述。",
            "after": "原机制表述。",
            "reason": "不应存在的无效 patch",
        }
    ]
    _, errors = _reconstruct_sparse_items(input_data, noop)
    assert any("no-op" in error for error in errors)


def test_fact_check_batching_and_readable_item_budget() -> None:
    root = Path(__file__).resolve().parents[1]
    settings = yaml.safe_load((root / "config" / "settings.yaml").read_text(encoding="utf-8"))
    efficiency = settings["efficiency"]

    assert settings["brief_item_min_chars"] == 230
    assert settings["brief_item_max_chars"] == 330
    assert efficiency["item_writing_batch_size"] == 4
    assert efficiency["fact_check_batch_size"] == 24
    assert efficiency["editorial_batch_max_input_chars"] == 65000
