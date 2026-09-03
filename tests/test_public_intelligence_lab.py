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
        "./feedback-store.js",
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
    # The path/graph mode switch and the mobile layered path render in BOTH
    # evidence modes: the graph view must stay reachable from normal
    # navigation, and the mobile evidence path must never be blank.
    assert "const modeSwitch" in idea_view
    assert 'mode === "graph" ? `<div class="segmented-tabs">' not in idea_view
    assert 'const mobile = mobileMarkup(row, idea, model, "evidence", mode)' in idea_view
    assert "evidencePathMarkup" in idea_view
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
    # Bare #roadmaps renders the browsable overview; unknown topics 404
    # honestly instead of silently falling back to the first entry.
    assert "overview: true" in app
    assert "Roadmap 不存在或尚未物化" in views
    # The native select must no longer be the roadmap navigation.
    assert "object-select" not in views
    assert "onchange=" not in views
    assert "验证建议 · 尚未执行" in views
    assert "不是仿真或实验结果" in views
    assert "Candidate 与正式 Idea 使用独立集合" in views
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

    assert "导出 JSON" not in html
    assert "清空" not in html
    assert "添加证据" not in views
    assert "新建实验" not in views


def test_item_feedback_is_browser_local_demo_only():
    app = (SITE / "app.js").read_text(encoding="utf-8")
    views = (SITE / "workbench-view.js").read_text(encoding="utf-8")
    knowledge_view = (SITE / "knowledge-graph-view.js").read_text(encoding="utf-8")
    idea_view = (SITE / "idea-evidence-view.js").read_text(encoding="utf-8")

    # The store initializes defensively and every surface renders through the
    # shared primitives with the browser-local disclaimer.
    assert "BriefingFeedback.LocalFeedbackStore" in app
    assert "feedbackButtons" in views and "bindFeedbackEvents" in views
    assert "state.feedback.toggle" in views
    assert "仅保存在当前浏览器，不参与真实筛选" in views
    assert 'feedbackButtons("brief_item"' in knowledge_view
    assert 'feedbackButtons("brief_item"' in idea_view
    assert "bindFeedbackEvents(panel)" in knowledge_view
    assert "bindFeedbackEvents(panel)" in idea_view
    # No export, count, or clear console anywhere in the new surfaces.
    for surface in (views, knowledge_view, idea_view):
        assert "exportData" not in surface
        assert "listEvents()" not in surface
        assert "feedbackCount" not in surface


def test_home_is_change_first_and_honest_about_freshness():
    app = (SITE / "app.js").read_text(encoding="utf-8")
    views = (SITE / "workbench-view.js").read_text(encoding="utf-8")

    # The homepage reads the freshness manifest and the Issue Change
    # Projection, and never backfills old Roadmap summaries as this issue's
    # change.
    assert "manifest.json" in app
    assert "issue-diffs" in app
    assert "homeChangesBody" in views
    assert "发布清单缺失" in views
    assert "本期已归档" in views
    assert "本期没有实质变化" in views
    assert "不回填历史 Roadmap 摘要" in views
    # Seed template copy is labeled as baseline instead of shown as judgement.
    assert "isSeedSummary" in views
    assert "基线时间线" in views
    # Column widths must not exceed 100%.
    assert 'width: "16%"' in views and 'width: "30%"' in views and 'width: "32%"' in views
    assert 'width: "45%"' not in views


def test_idea_collections_are_separate_and_feature_plan_remains_public():
    views = (SITE / "workbench-view.js").read_text(encoding="utf-8")
    feature_plan = json.loads((SITE / "feature-plan.json").read_text(encoding="utf-8"))

    # Candidate is now a real, separately counted collection. Validation still
    # has no Run/Result data model and remains honestly disabled.
    assert 'value: "未启用"' in views
    assert "data-hub-tab" not in views
    assert "const candidates = []" not in views
    assert "Candidate Inbox" in views
    assert "Candidate · 尚未成为正式 Idea" in views
    assert "待审 Candidate" in views
    assert "本期候选处置" in views
    assert "实验 Run / Result 对象尚未建立" in views
    assert "已有建议，尚未执行" in views
    assert "为什么在当前状态" in views
    assert "下一道门槛" in views
    assert "正在迭代" in views
    assert "接下来" in views
    assert feature_plan["schema_version"] == 1
    assert {row["status"] for row in feature_plan["items"]} == {"iterating", "planned"}


def test_knowledge_overview_focus_and_tech_info_contract():
    knowledge_view = (SITE / "knowledge-graph-view.js").read_text(encoding="utf-8")
    graph_css = (SITE / "knowledge-graph.css").read_text(encoding="utf-8")
    renderer = (SITE / "graph-renderer.js").read_text(encoding="utf-8")
    index_html = (SITE / "index.html").read_text(encoding="utf-8")

    # Bare structure lens renders the topic-cluster overview; the canvas fits
    # its lens first-screen set, not the whole model and not an unconditional
    # topic one-hop.
    assert "overviewMode" in knowledge_view
    assert "overviewMarkup" in knowledge_view
    assert "进入局部图" in knowledge_view
    assert "全局概览" in knowledge_view
    assert "聚焦当前对象" in knowledge_view
    assert "fitFocus" in knowledge_view and "fitFocus" in renderer
    assert "compactLocal" not in knowledge_view
    # The lens layout layer owns coordinates and the initial viewport.
    assert "knowledge-layout.js" in index_html
    assert "KnowledgeLayout.build" in knowledge_view
    assert "lensStatusText" in knowledge_view
    assert "自动聚焦" in knowledge_view
    # Collapsing the filter rail recalculates canvas size and fit range.
    assert "handle.cy.resize()" in knowledge_view
    # The raw digest is build diagnostics in a collapsed tech-info block.
    assert "kg-tech-info" in knowledge_view
    assert "输入校验码" in knowledge_view
    assert "data-copy-digest" in knowledge_view
    assert "构建输入摘要" not in knowledge_view
    # Relationship list paginates (20 rows per page) but keeps all rows in DOM.
    assert "RELATION_PAGE_SIZE = 20" in knowledge_view
    assert "data-relationship-page" in knowledge_view
    assert "rel-pager" in graph_css
    assert "kg-overview-grid" in graph_css
    # Sub-1280px workspaces drop the detail rail below the canvas.
    assert "grid-template-columns:220pxminmax(0,1fr)" in "".join(graph_css.split())
    # Lens empty states are explicit; the shared skeleton never impersonates a
    # successful lens switch.
    assert "本透镜当前没有专属数据" in knowledge_view
    assert "扩大到全部期次" in knowledge_view
    assert "kg-structure-context" in knowledge_view
    assert "kg-lens-empty" in graph_css


def test_lens_layout_module_is_pure_and_lens_specific():
    layout_js = (SITE / "knowledge-layout.js").read_text(encoding="utf-8")

    # The layout layer reads the display model only; it must never fetch data,
    # mutate the graph document, or compute DOM.
    for forbidden in ("fetch(", "document.", "cytoscape", "window.location"):
        assert forbidden not in layout_js, forbidden
    assert "function build(" in layout_js
    for lens in ("structure", "evolution", "judgements"):
        assert lens in layout_js
    assert "lensEmptyState" in layout_js
    assert "edgeStats" in layout_js


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
        "knowledge-layout.js",
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
