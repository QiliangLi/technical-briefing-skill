import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


def _run_node(source: str) -> dict:
    result = subprocess.run(
        ["node", "-e", source], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_public_site_is_a_routed_three_pane_workbench():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    css = (SITE / "styles.css").read_text(encoding="utf-8")

    assert 'class="workbench"' in html
    assert 'class="left-pane"' in html
    assert 'id="mainPane"' in html
    assert 'id="detailPane"' in html
    assert 'data-route="roadmaps"' in html
    assert 'data-route="ideas"' in html
    assert 'data-route="archive"' in html
    assert 'data-route="atlas"' in html
    assert "height:calc(100vh - 62px)" in css
    assert "grid-template-columns:var(--sidebar) minmax(0,1fr) var(--detail)" in css
    assert "平均评分" not in html


def test_roadmap_and_idea_views_only_read_materialized_knowledge():
    app = (SITE / "app.js").read_text(encoding="utf-8")
    views = (SITE / "intelligence-lab.js").read_text(encoding="utf-8")

    assert "./knowledge" in app
    assert "validateKnowledgeIndex" in app
    assert "loadKnowledgeObject(selected.path)" in views
    assert "project_insights" not in views
    assert ".next_action" not in views
    assert "latest.next_action" not in views
    assert "系统不会用日期列表或 next_action 临时拼装替代品" in views
    assert "验证建议 · 尚未执行" in views
    assert "不是仿真或实验结果" in views


def test_reader_projection_and_original_email_contract_are_visible():
    app = (SITE / "app.js").read_text(encoding="utf-8")
    views = (SITE / "intelligence-lab.js").read_text(encoding="utf-8")

    assert "reader.json" in app
    assert "mergeReaderItem" in app
    assert "Machine IDs" in views
    assert "查看实际发送版" in views
    assert "issue.original_href" in views


def test_feedback_mock_is_explicitly_local_and_non_authoritative():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    views = (SITE / "intelligence-lab.js").read_text(encoding="utf-8")

    assert "演示模式，仅保存在当前浏览器" in html
    assert "不会改变真实 Roadmap、Idea 或日报选择" in html
    assert "导出 JSON" in html
    assert "不会自动改变 Idea 状态" in views


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_route_reader_merge_and_radar_dedupe_contracts():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const route = data.parseRoute('#ideas?status=seed&topic=agent');
        const merged = data.mergeReaderItem(
          {{item_id:'a1', title:'机器标题', summary:'机器摘要'}},
          {{brief_item_id:'a1', title:'读者标题', lead:'读者导语'}}
        );
        const rows = data.mergeRadarWithoutDuplicates(
          [{{role:'radar', arxiv_id:'2608.10000', title:'同一信号', url:'https://arxiv.org/abs/2608.10000v2?utm_source=a'}}],
          [{{role:'radar', title:'同一信号', url:'https://arxiv.org/abs/2608.10000v1'}}]
        );
        process.stdout.write(JSON.stringify({{route, merged, count:rows.length}}));
        """
    )

    assert output["route"] == {"name": "ideas", "params": {"status": "seed", "topic": "agent"}}
    assert output["merged"]["title"] == "读者标题"
    assert output["merged"]["summary"] == "读者导语"
    assert output["merged"]["machine_title"] == "机器标题"
    assert output["count"] == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_local_feedback_toggle_switch_export_and_clear():
    output = _run_node(
        f"""
        const {{LocalFeedbackStore}} = require({json.dumps(str(SITE / 'feedback-store.js'))});
        const memory = {{value:null, getItem(){{return this.value}}, setItem(_,v){{this.value=v}}, removeItem(){{this.value=null}}}};
        let n=0;
        const store = new LocalFeedbackStore(memory, {{now:()=>`t${{n}}`, makeId:()=>`e${{++n}}`}});
        store.toggle('brief_item','item-1','interested');
        const afterSet = store.current('brief_item','item-1');
        store.toggle('brief_item','item-1','not_interested');
        const afterSwitch = store.current('brief_item','item-1');
        store.toggle('brief_item','item-1','not_interested');
        const afterCancel = store.current('brief_item','item-1');
        const exported = store.exportData();
        const persisted = new LocalFeedbackStore(memory).listEvents().length;
        store.clear();
        process.stdout.write(JSON.stringify({{afterSet,afterSwitch,afterCancel,exported,persisted,afterClear:store.listEvents().length}}));
        """
    )

    assert output["afterSet"] == "interested"
    assert output["afterSwitch"] == "not_interested"
    assert output["afterCancel"] is None
    assert output["persisted"] == 3
    assert output["exported"]["mode"] == "local_browser_demo"
    assert len(output["exported"]["events"]) == 3
    assert output["afterClear"] == 0


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize(
    "script",
    ["data-contract.js", "feedback-store.js", "app.js", "intelligence-lab.js", "atlas-layout-v2.js", "atlas-interaction-v3.js"],
)
def test_public_javascript_parses(script: str):
    result = subprocess.run(
        ["node", "--check", str(SITE / script)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
