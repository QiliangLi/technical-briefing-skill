from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from briefing_skill.illustrated_publication import render_illustrated_html


def _base_email() -> str:
    return """<!doctype html><html><body><table>
<tr id="judgement-row"><td><table data-reader-role="judgement"><tr><td>本期判断</td></tr></table></td></tr>
<tr id="tpn-row"><td><a id="topic-tpn"></a>TPN</td></tr>
<tr id="agent-row"><td><a id="topic-agent_acceleration"></a>Agent</td></tr>
</table></body></html>"""


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
                "persona_used": False,
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
    assert illustrations[0]["data-persona-used"] == "1"
    assert "比较传输、重算与就地计算" in illustrations[0].get_text(" ", strip=True)
    assert str(first.resolve()) == illustrations[0].find("img")["src"]
    assert rendered.index("全局取数决策") < rendered.index('id="topic-tpn"')
    assert rendered.index("Agent检索路径") < rendered.index('id="topic-agent_acceleration"')


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
