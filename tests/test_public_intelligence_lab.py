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
    finesse_css = (SITE / "workbench-overrides.css").read_text(encoding="utf-8")
    compact_css = "".join(css.split())

    assert 'class="workbench"' in html
    assert 'class="left-pane"' in html
    assert 'id="mainPane"' in html
    assert 'id="detailPane"' in html
    assert 'data-route="roadmaps"' in html
    assert 'data-route="ideas"' in html
    assert 'data-route="archive"' in html
    assert 'data-route="atlas"' in html
    assert 'data-route="features"' in html
    assert html.index('data-route="features"') > html.index('data-route="atlas"')
    assert "height:calc(100vh-62px)" in compact_css
    assert "grid-template-columns:var(--sidebar)minmax(0,1fr)var(--detail)" in compact_css
    assert ".compact-list{grid-template-columns:minmax(0,1fr);min-width:0;}" in compact_css
    assert ".compact-row{min-width:0;}" in compact_css
    assert "shell=floating-triptych" in finesse_css
    assert "overflow-x: clip" in finesse_css
    assert "prefers-reduced-motion: reduce" in finesse_css
    assert "平均评分" not in html


def test_roadmap_and_idea_views_only_read_materialized_knowledge():
    app = (SITE / "app.js").read_text(encoding="utf-8")
    views = (SITE / "intelligence-lab.js").read_text(encoding="utf-8")
    compact_views = "".join(views.split())

    assert "./knowledge" in app
    assert "validateKnowledgeIndex" in app
    assert "loadKnowledgeObject(selected.path)" in views
    assert "project_insights" not in views
    assert ".next_action" not in views
    assert "latest.next_action" not in views
    assert "系统不会用日期列表或 next_action 临时拼装替代品" in views
    assert "验证建议 · 尚未执行" in views
    assert "不是仿真或实验结果" in views
    assert "row.item_id?[row]" in compact_views
    assert "row.reason" in views
    assert "row.mechanisms" in views
    assert "边界观察 · 尚未进入 Roadmap" in views
    assert "state.knowledge?.frontier_clusters" in views
    assert "renderFrontierDetail" in views


def test_reader_projection_and_original_email_contract_are_visible():
    app = (SITE / "app.js").read_text(encoding="utf-8")
    views = (SITE / "intelligence-lab.js").read_text(encoding="utf-8")

    assert "reader.json" in app
    assert "mergeReaderItem" in app
    assert "reader?.radar" in app
    assert "Machine IDs" in views
    assert "查看实际发送版" in views
    assert "issue.original_href" in views


def test_feedback_mock_is_explicitly_local_and_non_authoritative():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    views = (SITE / "intelligence-lab.js").read_text(encoding="utf-8")
    compact_html = "".join(html.split())

    assert "演示模式，仅保存在当前浏览器" in html
    assert "不会改变真实Roadmap、Idea或日报选择" in compact_html
    assert "导出 JSON" in html
    assert "不会自动改变 Idea 状态" in views


def test_idea_filters_are_all_visible_and_feature_plan_is_public():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    views = (SITE / "intelligence-lab.js").read_text(encoding="utf-8")
    feature_plan = json.loads((SITE / "feature-plan.json").read_text(encoding="utf-8"))
    canonical_views = "".join(views.split()).replace('"', "'")

    assert 'id="ideaFilters"' in html
    assert "filterOptions('topic'" in canonical_views
    assert "filterOptions('type'" in canonical_views
    assert "filterOptions('status'" in canonical_views
    assert "<select" not in views
    assert "aria-pressed" in views
    assert "feature-plan-group" in views
    assert "正在迭代" in views
    assert "接下来" in views
    assert feature_plan["schema_version"] == 1
    assert {row["status"] for row in feature_plan["items"]} == {"iterating", "planned"}


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_route_reader_merge_and_radar_dedupe_contracts():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const route = data.parseRoute('#ideas?status=seed&topic=agent');
        const featureRoute = data.parseRoute('#features?feature=team-feedback-loop');
        const merged = data.mergeReaderItem(
          {{item_id:'a1', title:'机器标题', summary:'机器摘要'}},
          {{brief_item_id:'a1', title:'读者标题', lead:'读者导语'}}
        );
        const bodyMerged = data.mergeReaderItem(
          {{item_id:'a2', title:'机器标题'}},
          {{title:'读者标题', body:['第一段','第二段']}}
        );
        const rows = data.mergeRadarWithoutDuplicates(
          [{{role:'radar', arxiv_id:'2608.10000', title:'同一信号', url:'https://arxiv.org/abs/2608.10000v2?utm_source=a'}}],
          [{{role:'radar', title:'同一信号', url:'https://arxiv.org/abs/2608.10000v1'}}]
        );
        const inferredArxiv = data.canonicalIdentity({{url:'https://arxiv.org/abs/2608.10000v3'}});
        process.stdout.write(JSON.stringify({{route, featureRoute, merged, bodyMerged, inferredArxiv, count:rows.length}}));
        """
    )

    assert output["route"] == {"name": "ideas", "params": {"status": "seed", "topic": "agent"}}
    assert output["featureRoute"] == {"name": "features", "params": {"feature": "team-feedback-loop"}}
    assert output["merged"]["title"] == "读者标题"
    assert output["merged"]["summary"] == "读者导语"
    assert output["merged"]["machine_title"] == "机器标题"
    assert output["bodyMerged"]["summary"] == "第一段\n\n第二段"
    assert output["inferredArxiv"] == "arxiv:2608.10000"
    assert output["count"] == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_original_email_path_uses_publication_manifest_contract():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const manifest = {{
          original_variants: ['email.html', 'email-illustrated.html'],
          files: {{
            'original/email.html': 'sha256:plain',
            'original/email-illustrated.html': 'sha256:illustrated',
            'email.html': 'sha256:public'
          }}
        }};
        const href = data.originalEmailPath(manifest, '2026-08-17');
        const absent = data.originalEmailPath({{original_variants:[],files:{{'email.html':'sha'}}}}, '2026-08-17');
        process.stdout.write(JSON.stringify({{href,absent}}));
        """
    )

    assert output["href"] == "./archive/issues/2026-08-17/original/email.html"
    assert output["absent"] == ""


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
