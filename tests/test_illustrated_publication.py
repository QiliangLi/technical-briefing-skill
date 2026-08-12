from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from briefing_skill.illustrated_publication import (
    IAN_STYLE_SKILL,
    _host_execution_policy,
    _ian_persona_contract,
    _illustration_input,
    render_illustrated_html,
)
from briefing_skill.utils import write_json


def _base_email() -> str:
    return """<!doctype html><html><body><table>
<tr id="judgement-row"><td><table data-reader-role="judgement"><tr><td>本期判断</td></tr></table></td></tr>
<tr id="tpn-row"><td><a id="topic-tpn"></a>TPN</td></tr>
<tr data-reader-row="deep-row" id="deep-1"><td>deep-1</td></tr>
<tr data-reader-row="deep-row" id="deep-2"><td>deep-2</td></tr>
<tr id="agent-row"><td><a id="topic-agent_acceleration"></a>Agent</td></tr>
<tr data-reader-row="deep-row" id="deep-3"><td>deep-3</td></tr>
<tr data-reader-row="deep-row" id="deep-4"><td>deep-4</td></tr>
</table></body></html>"""


def _published_url(index: int) -> str:
    return (
        "https://raw.githubusercontent.com/QiliangLi/technical-briefing-skill/"
        + "a" * 40
        + f"/published-assets/demo/image-{index}.png"
    )


def _generated(index: int, path: Path, *, placement: str = "after_judgements", topic_id: str | None = None, persona_used: bool = True) -> dict:
    return {
        "concept_name": f"解释图{index}",
        "status": "generated",
        "placement": placement,
        "topic_id": topic_id,
        "generated_asset_path": str(path),
        "published_asset_url": _published_url(index),
        "alt": f"解释图{index}",
        "caption": f"解释第{index}个独立技术概念。",
        "persona_used": persona_used,
        "qa_notes": [],
    }


def _write_ian_persona_fixture(root: Path) -> dict[str, str]:
    persona_dir = root / "assets" / "persona" / "ian-qiliang"
    persona_dir.mkdir(parents=True, exist_ok=True)
    (persona_dir / "overlay.md").write_text("# Qiliang overlay\n", encoding="utf-8")

    references = {
        "identity_anchor": "pics/圆框形象/identity.png",
        "action_anchor": "pics/方框形象/action.png",
        "wide_scene_anchor": "pics/圆框形象/wide.png",
    }
    for relative in references.values():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")

    (persona_dir / "reference-manifest.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                f"base_skill: {IAN_STYLE_SKILL}",
                "identity_anchor:",
                f"  path: {references['identity_anchor']}",
                "action_anchor:",
                f"  path: {references['action_anchor']}",
                "wide_scene_anchor:",
                f"  path: {references['wide_scene_anchor']}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return references


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
                "published_asset_url": _published_url(1),
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
                "published_asset_url": _published_url(2),
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
                "published_asset_url": None,
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
    assert all(node.get("data-illustration-slot") for node in illustrations)
    for node in illustrations:
        previous = node.find_previous_sibling("tr")
        next_row = node.find_next_sibling("tr")
        assert previous is None or previous.get("data-reader-role") != "explanatory-illustration"
        assert next_row is None or next_row.get("data-reader-role") != "explanatory-illustration"


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
                "generated_asset_path": f"published-assets/demo/{index}.png",
                "published_asset_url": _published_url(index),
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

    invalid_url = json.loads(json.dumps(five_generated, ensure_ascii=False))
    invalid_url["illustrations"][0]["published_asset_url"] = (
        "https://raw.githubusercontent.com/QiliangLi/technical-briefing-skill/main/image.png"
    )
    assert list(validator.iter_errors(invalid_url))


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


def test_illustration_input_reads_only_finalized_issue_document_and_ian_persona(tmp_path: Path) -> None:
    expected_references = _write_ian_persona_fixture(tmp_path)
    issue_path = tmp_path / "workspace" / "runs" / "demo" / "issue" / "issue.json"
    issue_data = {
        "synthesis": {"headline": "immutable synthesis"},
        "items": [
            {
                "brief_item_id": "item-1",
                "item_role": "core",
                "topic_id": "tpn",
                "direction_id": "kv_transfer",
                "title": "Final title",
                "core_conclusion": "Final conclusion.",
                "mechanism": "Final mechanism.",
                "result": "Final result.",
                "boundary": "Final boundary.",
                "project_relevance": "Final relevance.",
            }
        ],
    }
    write_json(issue_path, issue_data)
    pipeline = SimpleNamespace(
        root=tmp_path,
        run_dir=tmp_path / "workspace" / "runs" / "demo",
        config=SimpleNamespace(settings={"visuals": {}}),
    )

    payload = _illustration_input(
        pipeline,
        {"id": "issue-1", "issue_json_path": str(issue_path.relative_to(tmp_path))},
    )

    assert payload["synthesis"] == {"headline": "immutable synthesis"}
    assert payload["items"][0]["title"] == "Final title"
    constraints = payload["constraints"]
    assert constraints["issue_document_is_immutable"] is True
    assert constraints["illustration_style_skill"] == IAN_STYLE_SKILL
    assert constraints["persona_overlay_path"] == "assets/persona/ian-qiliang/overlay.md"
    assert constraints["persona_reference_manifest_path"] == "assets/persona/ian-qiliang/reference-manifest.yaml"
    assert constraints["persona_reference_paths"] == expected_references
    assert "layout_policy" in constraints
    assert "persona_spec_path" not in constraints
    assert "persona_reference_path" not in constraints


def test_ian_persona_contract_fails_closed_when_required_anchor_is_missing(tmp_path: Path) -> None:
    references = _write_ian_persona_fixture(tmp_path)
    (tmp_path / references["action_anchor"]).unlink()

    with pytest.raises(RuntimeError, match="action_anchor"):
        _ian_persona_contract(tmp_path, {})


def test_committed_ian_reference_manifest_points_to_existing_images() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "assets" / "persona" / "ian-qiliang" / "reference-manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert manifest["base_skill"] == IAN_STYLE_SKILL
    for key in ("identity_anchor", "action_anchor", "wide_scene_anchor"):
        reference = root / manifest[key]["path"]
        assert reference.is_file(), f"missing committed Ian persona reference: {reference}"


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


def test_prompt_uses_ian_only_and_separates_guizang_layout_from_image_generation() -> None:
    root = Path(__file__).resolve().parents[1]
    prompt = (root / "prompts" / "illustrated-publication.md").read_text(encoding="utf-8")

    assert "ian-xiaohei-illustrations" in prompt
    assert "persona_overlay_path" in prompt
    assert "persona_reference_manifest_path" in prompt
    assert "Do **not** use Guizang Material Illustration" in prompt
    assert "Guizang remains relevant only to the existing HTML/card presentation contract" in prompt
    assert "assets/persona/reference.jpg" in prompt
