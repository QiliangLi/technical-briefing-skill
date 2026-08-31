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


def test_public_site_uses_the_editorial_routed_shell():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    tokens = (SITE / "editorial-tokens.css").read_text(encoding="utf-8")
    components = (SITE / "editorial-components.css").read_text(encoding="utf-8")
    pages = (SITE / "editorial-pages.css").read_text(encoding="utf-8")
    compact_components = "".join(components.split())
    compact_pages = "".join(pages.split())

    assert 'class="app-nav"' in html
    assert 'id="appMain"' in html
    assert 'data-route="home"' in html
    assert 'data-route="roadmaps"' in html
    assert 'data-route="ideas"' in html
    assert 'data-route="knowledge"' in html
    assert 'data-route="archive"' in html
    assert 'data-route="evidence"' not in html
    for stylesheet in (
        "editorial-tokens.css",
        "editorial-components.css",
        "editorial-pages.css",
        "knowledge-graph.css",
    ):
        assert stylesheet in html
    for script in (
        "./assets/vendor/cytoscape.min.js",
        "./data-contract.js",
        "./graph-styles.js",
        "./graph-renderer.js",
        "./knowledge-graph-view.js",
        "./idea-evidence-view.js",
        "./app.js",
        "./workbench-view.js",
    ):
        assert script in html
    # The vendor script must load before the renderer adapter.
    assert html.index("./assets/vendor/cytoscape.min.js") < html.index("./graph-renderer.js")
    assert "evidence-graph.css" not in html
    assert "evidence-graph.js" not in html
    assert "https://cdn" not in html and "http://cdn" not in html
    assert "styles.css" not in html
    assert "workbench-overrides.css" not in html
    assert "register=product" in tokens
    assert "overflow-x:clip" in "".join(tokens.split())
    assert "prefers-reduced-motion:reduce" in "".join(tokens.split())
    assert ".app-nav{position:sticky;top:0" in compact_components
    assert ".home-grid{display:grid;grid-template-columns:minmax(0,2.2fr)minmax(280px,1fr)" in compact_pages
    assert "minmax(0,1fr)" in pages
    assert "brand-mark.svg" in html
    assert "icons.svg" in html
    assert "平均评分" not in html


def test_knowledge_graph_page_and_idea_evidence_views_declare_their_contracts():
    app = (SITE / "app.js").read_text(encoding="utf-8")
    knowledge_view = (SITE / "knowledge-graph-view.js").read_text(encoding="utf-8")
    idea_view = (SITE / "idea-evidence-view.js").read_text(encoding="utf-8")
    graph_css = (SITE / "knowledge-graph.css").read_text(encoding="utf-8")

    assert "graph.json" in app
    assert "validateKnowledgeGraph" in app
    assert "loadKnowledgeGraph" in app
    assert "destroyActive" in app
    for phrase in (
        "structure",
        "evolution",
        "judgements",
        "archive_through_issue",
        "knowledge_through_issue",
        "已达",
        "relationshipList",
        "kg-canvas",
        "kg-mobile",
    ):
        assert phrase in knowledge_view, phrase
    for phrase in (
        "evidencePathMarkup",
        "reference?.reason",
        "buildIdeaEvidenceGraphModel",
        "relationshipList",
        "Claim 尚未物化",
    ):
        assert phrase in idea_view, phrase
    compact_css = "".join(graph_css.split())
    assert "grid-template-columns:248pxminmax(0,1fr)344px" in compact_css
    assert "@media(max-width:767px)" in compact_css
    assert ".kg-workspace,.graph-workspace,.evidence-path-view{display:none;}" in compact_css
    assert "prefers-reduced-motion:reduce" in compact_css


def test_roadmap_and_idea_views_only_read_materialized_knowledge():
    app = (SITE / "app.js").read_text(encoding="utf-8")
    views = (SITE / "workbench-view.js").read_text(encoding="utf-8")
    compact_views = "".join(views.split())

    assert "./knowledge" in app
    assert "validateKnowledgeIndex" in app
    assert "loadKnowledgeObject(row.path)" in app
    assert "project_insights" not in views
    assert ".next_action" not in views
    assert "latest.next_action" not in views
    assert "系统不会用日期列表或 next_action 临时拼装替代品" in views
    assert "验证建议 · 尚未执行" in views
    assert "不是仿真或实验结果" in views
    assert "Candidate 与正式 Idea 使用独立集合" in views
    assert "不会把正式 Idea 倒推成候选" in views
    assert "renderEvidencePathForIdea" not in views
    assert "function renderEvidence(" not in views
    assert "EvidenceGraph" not in views
    assert "row.item_id?[row]" not in compact_views


def test_reader_projection_and_original_email_contract_are_visible():
    app = (SITE / "app.js").read_text(encoding="utf-8")
    views = (SITE / "workbench-view.js").read_text(encoding="utf-8")

    assert "reader.json" in app
    assert "mergeReaderItem" in app
    assert "reader?.radar" in app
    assert "当前期次的日报条目" in views
    assert "查看本期 Reader" in views
    assert "issue.original_href" in views


def test_public_shell_does_not_expose_fake_write_controls():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    views = (SITE / "workbench-view.js").read_text(encoding="utf-8")

    assert "feedback-store.js" not in html
    assert "导出 JSON" not in html
    assert "清空" not in html
    assert "添加证据" not in views
    assert "新建实验" not in views


def test_idea_collections_are_separate_and_feature_plan_remains_public():
    views = (SITE / "workbench-view.js").read_text(encoding="utf-8")
    feature_plan = json.loads((SITE / "feature-plan.json").read_text(encoding="utf-8"))

    assert 'data-hub-panel="${key}"' in views
    assert 'data-hub-tab="candidate"' in views
    assert 'data-hub-tab="portfolio"' in views
    assert 'data-hub-tab="validation"' in views
    assert "const candidates = []" in views
    assert "validationStatuses" in views
    assert 'role="tablist"' in views
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
        const evidenceRoute = data.parseRoute('#atlas?idea=idea-1');
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
        process.stdout.write(JSON.stringify({{route, featureRoute, evidenceRoute, merged, bodyMerged, inferredArxiv, count:rows.length}}));
        """
    )

    assert output["route"] == {"name": "ideas", "params": {"status": "seed", "topic": "agent"}, "legacy": False}
    assert output["featureRoute"] == {"name": "features", "params": {"feature": "team-feedback-loop"}, "legacy": False}
    assert output["evidenceRoute"]["name"] == "knowledge"
    assert output["evidenceRoute"]["params"]["lens"] == "evolution"
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
    [
        "data-contract.js",
        "graph-styles.js",
        "graph-renderer.js",
        "knowledge-graph-view.js",
        "idea-evidence-view.js",
        "feedback-store.js",
        "app.js",
        "workbench-view.js",
    ],
)
def test_public_javascript_parses(script: str):
    result = subprocess.run(
        ["node", "--check", str(SITE / script)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
