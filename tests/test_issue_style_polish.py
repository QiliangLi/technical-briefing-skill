import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from briefing_skill.issue_style_polish import (
    STYLE_FIELDS,
    _strip_redundant_writing_skills,
)


def test_old_per_batch_writing_skill_chain_is_removed() -> None:
    metadata = {
        "required_skills": ["human-writing", "humanizer"],
        "skill_mode": "old",
        "keep": "value",
    }
    for task_type in ("item_writing", "item_writing_batch", "issue_synthesis"):
        assert _strip_redundant_writing_skills(task_type, metadata) == {"keep": "value"}

    assert _strip_redundant_writing_skills("fact_check_batch", metadata) == metadata


def test_issue_level_polish_prompt_uses_human_writing_not_humanizer() -> None:
    root = Path(__file__).resolve().parents[1]
    prompt = (root / "prompts" / "item-style-polish.md").read_text(encoding="utf-8")
    draft_prompt = (root / "prompts" / "item-writing-batch.md").read_text(encoding="utf-8")
    synthesis_prompt = (root / "prompts" / "issue-synthesis.md").read_text(encoding="utf-8")

    assert "single issue-level Chinese style pass" in prompt
    assert "Call `$human-writing` **once for the entire `items` array**" in prompt
    assert "Do not call `$humanizer`" in prompt
    assert "Do not call `$human-writing` or `$humanizer` here" in draft_prompt
    assert "Do **not** call `$human-writing` or `$humanizer` here" in synthesis_prompt


def test_style_polish_schema_edits_only_reader_facing_fields() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas" / "item-style-polish.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    result = {
        "results": [
            {
                "brief_item_id": "item-1",
                "title": "一个足够具体的技术标题",
                "core_conclusion": "该方案在明确条件下改变了关键数据路径，并把主要收益集中到可验证的系统瓶颈上。",
                "mechanism": "系统通过结构化索引缩短重复探索路径，同时保留原有事实边界。",
                "result": "实验在给定基线与工作负载下获得明确收益，结论不外推到未测试条件。",
                "boundary": "当前结果仍受实验规模和部署条件限制。",
                "project_relevance": "项目侧应优先复现实验条件，再判断该机制是否值得进入现有数据路径。",
            }
        ]
    }
    assert list(validator.iter_errors(result)) == []
    assert tuple(result["results"][0].keys())[1:] == STYLE_FIELDS


def test_fact_check_batching_is_character_bounded_with_high_item_ceiling() -> None:
    root = Path(__file__).resolve().parents[1]
    settings = yaml.safe_load((root / "config" / "settings.yaml").read_text(encoding="utf-8"))
    efficiency = settings["efficiency"]

    assert efficiency["item_writing_batch_size"] == 4
    assert efficiency["fact_check_batch_size"] == 24
    assert efficiency["editorial_batch_max_input_chars"] == 65000
