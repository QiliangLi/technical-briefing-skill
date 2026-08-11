from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from briefing_skill.illustrated_publication import _host_execution_policy, render_illustrated_html


def _base_email() -> str:
    return """<!doctype html><html><body><table>
<tr id="judgement-row"><td><table data-reader-role="judgement"><tr><td>本期判断</td></tr></table></td></tr>
<tr id="tpn-row"><td><a id="topic-tpn"></a>TPN</td></tr>
<tr id="agent-row"><td><a id="topic-agent_acceleration"></a>Agent</td></tr>
</table></body></html>"""


def _generated(index: int, path: Path, *, placement: str = "after_judgements", topic_id: str | None = None, persona_used: bool = True) -> dict:
    return {
        "concept_name": f"解释图{index}",
        "status": "generated",
        "placement": placement,
        "topic_id": topic_id,
        "generated_asset_path": str(path),
        "alt": f"解释图{index}",
        "caption": f"解释第{index}个独立技术概念。",
        "persona_used": persona_used,
        "qa_notes": [],
    }


def test_issue_level_illustrations_use_stable_publication_placements(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_text("fixture", encoding="utf-8")
    second.write_text("fixture", encoding="utf-8")
    manifest = {
        "status": "complete",
        "illustrations": [
            {
                "concept_name": "全局取数决策",
                "status": "generated",
                "placement": "after_judgements",
                "topic_id": None,
                "generated_asset_path": str(first),
                "alt": "全局取数决策图",
                "caption": "比较传输、重算与就地计算。",
                "persona_used": True,
                "qa_notes": [],
            },
            {
                "concept_name": "Agent检索路径",
                "status": "generated",
                "placement": "before_topic",
                "topic_id": "agent_acceleration",
                "generated_asset_path": str(second),
                "alt": "Agent检索路径图",
                "caption": "结构索引压缩重复探索。",
                "persona_used": True,
                "qa_notes": [],
            },
            {
                "concept_name": "失败图不进入邮件",
                "status": "failed",
                "placement": "before_topic",
                "topic_id": "tpn",
                "generated_asset_path": None,
                "alt": "",
                "caption": "",
                "persona_used": False,
                "qa_notes": ["failed"],
            },
        ],
        "notes": [],
    }

    rendered = render_illustrated_html(tmp_path, _base_email(), manifest)
    soup = BeautifulSoup(rendered, "html.parser")
    illustrations = soup.select('tr[data-reader-role="explanatory-illustration"]')

    assert len(illustrations) == 2
    assert all(node["data-persona-used"] == "1" for node in illustrations)
    assert "比较传输、重算与就地计算" in illustrations[0].get_text(" ", strip=True)
    assert str(first.resolve()) == illustrations[0].find("img")["src"]
    assert rendered.index("全局取数决策") < rendered.index('id="topic-tpn"')
    assert rendered.index("Agent检索路径") < rendered.index('id="topic-agent_acceleration"')


def test_renderer_accepts_more_than_three_generated_persona_images(tmp_path: Path) -> None:
    entries = []
    for index in range(1, 6):
        path = tmp_path / f"image-{index}.png"
        path.write_text("fixture", encoding="utf-8")
        entries.append(_generated(index, path))

    rendered = render_illustrated_html(
        tmp_path,
        _base_email(),
        {"status": "complete", "illustrations": entries, "notes": []},
    )
    soup = BeautifulSoup(rendered, "html.parser")
    illustrations = soup.select('tr[data-reader-role="explanatory-illustration"]')

    assert len(illustrations) == 5
    assert all(node["data-persona-used"] == "1" for node in illustrations)


def test_schema_has_no_image_count_cap_and_requires_persona_for_generated_images() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas" / "illustrated-publication.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    five_generated = {
        "status": "complete",
        "illustrations": [
            {
                "concept_name": f"concept-{index}",
                "status": "generated",
                "placement": "after_judgements",
                "topic_id": None,
                "generated_asset_path": f"workspace/runs/demo/illustrations/{index}.png",
                "alt": "技术解释图",
                "caption": "解释独立技术机制。",
                "persona_used": True,
                "qa_notes": [],
            }
            for index in range(5)
        ],
        "notes": [],
    }
    assert list(validator.iter_errors(five_generated)) == []

    invalid = json.loads(json.dumps(five_generated, ensure_ascii=False))
    invalid["illustrations"][0]["persona_used"] = False
    assert list(validator.iter_errors(invalid))


def test_renderer_skips_generated_image_without_required_persona(tmp_path: Path) -> None:
    image = tmp_path / "missing-persona.png"
    image.write_text("fixture", encoding="utf-8")
    rendered = render_illustrated_html(
        tmp_path,
        _base_email(),
        {"status": "partial", "illustrations": [_generated(1, image, persona_used=False)], "notes": []},
    )
    soup = BeautifulSoup(rendered, "html.parser")

    assert not soup.select('tr[data-reader-role="explanatory-illustration"]')
    assert "本期判断" in soup.get_text(" ", strip=True)


def test_empty_manifest_keeps_readable_baseline_without_images(tmp_path: Path) -> None:
    rendered = render_illustrated_html(
        tmp_path,
        _base_email(),
        {"status": "fallback_to_text", "illustrations": [], "notes": []},
    )
    soup = BeautifulSoup(rendered, "html.parser")

    assert not soup.select('tr[data-reader-role="explanatory-illustration"]')
    assert soup.find("a", id="topic-tpn") is not None
    assert "本期判断" in soup.get_text(" ", strip=True)


def test_host_execution_policy_routes_claude_code_through_codex_plugin() -> None:
    policy = _host_execution_policy()

    assert policy["codex"]["mode"] == "direct"
    assert policy["claude_code"] == {
        "mode": "delegate_via_codex_plugin_cc",
        "plugin_repository": "openai/codex-plugin-cc",
        "subagent_type": "codex:codex-rescue",
        "routing_flags": ["--fresh", "--wait"],
        "delegate_entire_task": True,
        "same_checkout": True,
        "fallback_only_after_bridge_failure": True,
    }


def test_prompt_does_not_treat_missing_native_claude_image_generation_as_fallback() -> None:
    root = Path(__file__).resolve().parents[1]
    prompt = (root / "prompts" / "illustrated-publication.md").read_text(encoding="utf-8")

    assert "codex:codex-rescue" in prompt
    assert "--fresh --wait" in prompt
    assert "not** a reason to return `fallback_to_text`" in prompt
    assert "Delegate the **entire current `illustrated_publication` task once**" in prompt
