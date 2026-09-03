"""Graph-surface contracts: route normalization (including legacy Evidence /
Graph / Atlas bookmarks), the two display-model projections
(buildKnowledgeGraphModel, buildIdeaEvidenceGraphModel), the Cytoscape adapter
and style tables, and the vendored Cytoscape.js distribution."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

GRAPH_DOC = """
const graphDoc = {
  schema_version: 1,
  archive_through_issue: '2026-08-08',
  knowledge_through_issue: '2026-08-01',
  input_digest: 'sha256:' + 'a'.repeat(64),
  stats: {node_count: 0, edge_count: 0, unresolved_count: 0},
  nodes: [
    {data:{id:'topic:t1',kind:'topic',label:'专题一',topic_id:'t1'},position:{x:0,y:0},provenance:[{path:'archive/issues/2026-08-01/issue.json'}]},
    {data:{id:'direction:d1',kind:'direction',label:'方向一',direction_id:'d1'},position:{x:1,y:0},provenance:[{path:'archive/issues/2026-08-01/issue.json'}]},
    {data:{id:'item:i1',kind:'item',label:'条目一',topic_id:'t1',direction_id:'d1',issue_date:'2026-08-01'},position:{x:2,y:0},provenance:[{path:'archive/issues/2026-08-01/issue.json'}]},
    {data:{id:'item:i2',kind:'item',label:'条目二',topic_id:'t1',direction_id:'d1',issue_date:'2026-08-08'},position:{x:2,y:1},provenance:[{path:'archive/issues/2026-08-08/issue.json'}]},
    {data:{id:'issue:2026-08-01',kind:'issue',label:'2026-08-01',issue_date:'2026-08-01'},position:{x:3,y:0},provenance:[{path:'archive/index.json'}]},
    {data:{id:'issue:2026-08-08',kind:'issue',label:'2026-08-08',issue_date:'2026-08-08'},position:{x:3,y:1},provenance:[{path:'archive/index.json'}]},
    {data:{id:'judgement:2026-08-01:abc',kind:'judgement',label:'判断一',issue_date:'2026-08-01',body:'正文',evidence_item_ids:['i1']},position:{x:4,y:0},provenance:[{path:'archive/issues/2026-08-01/issue.json'}]},
    {data:{id:'roadmap:t1',kind:'roadmap',label:'Roadmap 专题一',topic_id:'t1'},position:{x:-1,y:0},provenance:[{path:'knowledge/roadmaps/t1.json'}]},
    {data:{id:'branch:t1:b1',kind:'roadmap_branch',label:'分支一',topic_id:'t1',branch_id:'b1'},position:{x:-1,y:1},provenance:[{path:'knowledge/roadmaps/t1.json'}]},
    {data:{id:'idea:x1',kind:'idea',label:'Idea 一',status:'observing'},position:{x:5,y:0},provenance:[{path:'knowledge/ideas/idea_x1.json'}]},
    {data:{id:'topic:t2',kind:'topic',label:'专题二',topic_id:'t2'},position:{x:0,y:9},provenance:[{path:'archive/issues/2026-08-08/issue.json'}]},
    {data:{id:'direction:d2',kind:'direction',label:'方向二',direction_id:'d2'},position:{x:1,y:9},provenance:[{path:'archive/issues/2026-08-08/issue.json'}]},
    {data:{id:'item:i3',kind:'item',label:'条目三',topic_id:'t2',direction_id:'d2',issue_date:'2026-08-08'},position:{x:2,y:9},provenance:[{path:'archive/issues/2026-08-08/issue.json'}]},
    {data:{id:'judgement:2026-08-08:def',kind:'judgement',label:'判断二',issue_date:'2026-08-08',body:'正文二',evidence_item_ids:['i3']},position:{x:4,y:9},provenance:[{path:'archive/issues/2026-08-08/issue.json'}]},
  ],
  edges: [
    {data:{id:'e1',source:'topic:t1',target:'direction:d1',relation:'has_direction',label:'包含方向',confirmation:'explicit'},provenance:[{path:'archive/issues/2026-08-01/issue.json'}]},
    {data:{id:'e2',source:'direction:d1',target:'item:i1',relation:'has_item',label:'收录条目',confirmation:'explicit'},provenance:[{path:'archive/issues/2026-08-01/issue.json'}]},
    {data:{id:'e3',source:'direction:d1',target:'item:i2',relation:'has_item',label:'收录条目',confirmation:'explicit'},provenance:[{path:'archive/issues/2026-08-08/issue.json'}]},
    {data:{id:'e4',source:'item:i1',target:'issue:2026-08-01',relation:'published_in',label:'发布于',confirmation:'explicit'},provenance:[{path:'archive/issues/2026-08-01/issue.json'}]},
    {data:{id:'e5',source:'item:i2',target:'issue:2026-08-08',relation:'published_in',label:'发布于',confirmation:'explicit'},provenance:[{path:'archive/issues/2026-08-08/issue.json'}]},
    {data:{id:'e6',source:'item:i1',target:'judgement:2026-08-01:abc',relation:'supports_judgement',label:'支持判断',confirmation:'explicit'},provenance:[{path:'archive/issues/2026-08-01/issue.json'}]},
    {data:{id:'e7',source:'roadmap:t1',target:'topic:t1',relation:'tracks',label:'跟踪',confirmation:'explicit'},provenance:[{path:'knowledge/roadmaps/t1.json'}]},
    {data:{id:'e8',source:'branch:t1:b1',target:'direction:d1',relation:'organizes',label:'组织方向',confirmation:'explicit'},provenance:[{path:'knowledge/roadmaps/t1.json'}]},
    {data:{id:'e9',source:'branch:t1:b1',target:'item:i1',relation:'uses_evidence',label:'引用证据',confirmation:'explicit'},provenance:[{path:'knowledge/roadmaps/t1.json'}]},
    {data:{id:'e10',source:'idea:x1',target:'topic:t1',relation:'relates_to',label:'关联专题',confirmation:'explicit'},provenance:[{path:'knowledge/ideas/idea_x1.json'}]},
    {data:{id:'e11',source:'item:i1',target:'idea:x1',relation:'supports_idea',label:'支持',confirmation:'explicit'},provenance:[{path:'knowledge/ideas/idea_x1.json'}]},
    {data:{id:'e12',source:'item:i2',target:'idea:x1',relation:'challenges_idea',label:'反对',confirmation:'explicit'},provenance:[{path:'knowledge/ideas/idea_x1.json'}]},
    {data:{id:'e13',source:'topic:t2',target:'direction:d2',relation:'has_direction',label:'包含方向',confirmation:'explicit'},provenance:[{path:'archive/issues/2026-08-08/issue.json'}]},
    {data:{id:'e14',source:'direction:d2',target:'item:i3',relation:'has_item',label:'收录条目',confirmation:'explicit'},provenance:[{path:'archive/issues/2026-08-08/issue.json'}]},
    {data:{id:'e15',source:'item:i3',target:'issue:2026-08-08',relation:'published_in',label:'发布于',confirmation:'explicit'},provenance:[{path:'archive/issues/2026-08-08/issue.json'}]},
    {data:{id:'e16',source:'item:i3',target:'judgement:2026-08-08:def',relation:'supports_judgement',label:'支持判断',confirmation:'explicit'},provenance:[{path:'archive/issues/2026-08-08/issue.json'}]},
  ],
  unresolved: [{reason:'dangling_idea_evidence',source_ref:'item:ghost',target_ref:'idea:x1',detail:'ghost'}],
};
"""


def _run_node(source: str) -> dict:
    result = subprocess.run(
        ["node", "-e", source], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_legacy_routes_normalize_once_into_knowledge_and_idea_surfaces():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        process.stdout.write(JSON.stringify({{
          evidencePath: data.parseRoute('#evidence?idea=i1&view=path'),
          evidenceGraph: data.parseRoute('#evidence?idea=i1&view=graph&depth=9&node=n1'),
          evidenceGaps: data.parseRoute('#evidence?idea=i1&view=gaps'),
          graphAlias: data.parseRoute('#graph?idea=i1&depth=2'),
          graphWithoutIdea: data.parseRoute('#graph'),
          atlasAlias: data.parseRoute('#atlas?issue=2026-08-29&topic=tpn'),
          evidenceAtlas: data.parseRoute('#evidence?idea=i1&view=atlas'),
          knowledgeDefault: data.parseRoute('#knowledge'),
          knowledgeInvalidLens: data.parseRoute('#knowledge?lens=bogus&node=item:i1'),
          unknownRoute: data.parseRoute('#nope?x=1')
        }}));
        """
    )

    assert output["evidencePath"] == {
        "name": "ideas",
        "params": {"idea": "i1", "view": "evidence", "mode": "path"},
        "legacy": True,
    }
    assert output["evidenceGraph"]["name"] == "ideas"
    assert output["evidenceGraph"]["params"] == {
        "idea": "i1", "view": "evidence", "mode": "graph", "depth": "1", "node": "n1",
    }
    assert output["evidenceGaps"]["params"] == {"idea": "i1", "view": "gaps"}
    assert output["graphAlias"]["name"] == "ideas"
    assert output["graphAlias"]["params"]["mode"] == "graph"
    assert output["graphWithoutIdea"] == {
        "name": "knowledge",
        "params": {"lens": "structure", "range": "recent3", "overlay": "", "hide": ""},
        "legacy": True,
    }
    assert output["atlasAlias"]["name"] == "knowledge"
    assert output["atlasAlias"]["params"]["lens"] == "evolution"
    assert output["atlasAlias"]["params"]["from"] == "2026-08-29"
    assert output["atlasAlias"]["params"]["to"] == "2026-08-29"
    assert output["atlasAlias"]["params"]["topic"] == "tpn"
    assert output["evidenceAtlas"]["name"] == "knowledge"
    assert output["evidenceAtlas"]["params"]["lens"] == "evolution"
    assert output["knowledgeDefault"]["params"]["lens"] == "structure"
    assert output["knowledgeInvalidLens"]["params"]["lens"] == "structure"
    assert output["knowledgeInvalidLens"]["params"]["node"] == "item:i1"
    assert output["unknownRoute"]["name"] == "home"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_idea_view_params_normalize_modes_depth_and_drop_unknown_keys():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        process.stdout.write(JSON.stringify({{
          overview: data.normalizeIdeaViewParams({{idea:'i1'}}),
          graph: data.normalizeIdeaViewParams({{idea:'i1', view:'evidence', mode:'graph', depth:'2', node:'item:a'}}),
          invalidMode: data.normalizeIdeaViewParams({{idea:'i1', view:'evidence', mode:'bogus', depth:'9'}}),
          gaps: data.normalizeIdeaViewParams({{idea:'i1', view:'gaps', mode:'graph'}}),
          junk: data.normalizeIdeaViewParams({{idea:'i1', view:'overview', task:'missing', candidates:'1'}})
        }}));
        """
    )
    assert output["overview"] == {"view": "overview", "idea": "i1"}
    assert output["graph"] == {"view": "evidence", "idea": "i1", "mode": "graph", "depth": "2", "node": "item:a"}
    assert output["invalidMode"] == {"view": "evidence", "idea": "i1", "mode": "path"}
    assert output["gaps"] == {"view": "gaps", "idea": "i1"}
    assert output["junk"] == {"view": "overview", "idea": "i1"}


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_knowledge_graph_projection_lenses_overlays_and_determinism():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        {GRAPH_DOC}
        const structure = data.buildKnowledgeGraphModel({{graph: graphDoc, params: {{lens: 'structure'}}}});
        const structureAgain = data.buildKnowledgeGraphModel({{graph: graphDoc, params: {{lens: 'structure'}}}});
        const withOverlays = data.buildKnowledgeGraphModel({{graph: graphDoc, params: {{lens: 'structure', overlay: 'roadmap,idea'}}}});
        const evolutionLatest = data.buildKnowledgeGraphModel({{graph: graphDoc, params: {{lens: 'evolution', range: 'latest'}}}});
        const judgements = data.buildKnowledgeGraphModel({{graph: graphDoc, params: {{lens: 'judgements', range: 'all'}}}});
        const unavailable = data.buildKnowledgeGraphModel({{graph: null, params: {{}}}});
        const kinds = (model) => [...new Set(model.nodes.map((n) => n.data.kind))].sort();
        const relations = (model) => [...new Set(model.edges.map((e) => e.data.relation))].sort();
        process.stdout.write(JSON.stringify({{
          stable: JSON.stringify(structure) === JSON.stringify(structureAgain),
          structureKinds: kinds(structure),
          structureRelations: relations(structure),
          overlayKinds: kinds(withOverlays),
          overlayRelations: relations(withOverlays),
          usesEvidenceWithoutItems: withOverlays.edges.some((e) => e.data.relation === 'uses_evidence'),
          evolutionLatestKinds: kinds(evolutionLatest),
          evolutionLatestItems: evolutionLatest.nodes.filter((n) => n.data.kind === 'item').map((n) => n.data.id),
          judgementRelations: relations(judgements),
          focusFallback: structure.focusId,
          focusRequested: data.buildKnowledgeGraphModel({{graph: graphDoc, params: {{lens: 'structure', node: 'item:i1'}}}}).focusId,
          unavailable: unavailable.unavailable,
          unresolvedPassedThrough: judgements.unresolved.length,
          statsNodeCount: judgements.stats.nodeCount
        }}));
        """
    )

    assert output["stable"] is True
    # Structure lens: only the Topic/Direction skeleton.
    assert output["structureKinds"] == ["direction", "topic"]
    assert output["structureRelations"] == ["has_direction"]
    # Overlays add knowledge objects without items; uses_evidence targets a
    # hidden item so it must disappear instead of drawing a dangling edge.
    assert "roadmap" in output["overlayKinds"] and "roadmap_branch" in output["overlayKinds"] and "idea" in output["overlayKinds"]
    assert "tracks" in output["overlayRelations"] and "organizes" in output["overlayRelations"] and "relates_to" in output["overlayRelations"]
    assert output["usesEvidenceWithoutItems"] is False
    # Evolution latest: only the newest issue's items and that issue node.
    assert output["evolutionLatestItems"] == ["item:i2", "item:i3"]
    assert set(output["evolutionLatestKinds"]) == {"topic", "direction", "item", "issue"}
    # Judgements lens keeps the explicit judgement evidence edges.
    assert "supports_judgement" in output["judgementRelations"]
    assert output["focusFallback"] == "topic:t1"
    assert output["focusRequested"] == "topic:t1"  # item focus not visible in structure lens
    assert output["unavailable"] is True
    assert output["unresolvedPassedThrough"] == 1
    assert output["statsNodeCount"] == 14


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_knowledge_graph_projection_enforces_soft_caps_with_focus_priority():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const nodes = [
          {{data:{{id:'topic:t1',kind:'topic',label:'T',topic_id:'t1'}},position:{{x:0,y:0}},provenance:[{{path:'a'}}]}},
          {{data:{{id:'direction:d1',kind:'direction',label:'D',direction_id:'d1'}},position:{{x:1,y:0}},provenance:[{{path:'a'}}]}},
          {{data:{{id:'issue:2026-08-08',kind:'issue',label:'I',issue_date:'2026-08-08'}},position:{{x:2,y:0}},provenance:[{{path:'a'}}]}}
        ];
        const edges = [
          {{data:{{id:'e1',source:'topic:t1',target:'direction:d1',relation:'has_direction',label:'包含方向',confirmation:'explicit'}},provenance:[{{path:'a'}}]}}
        ];
        for (let i = 0; i < 70; i++) {{
          const id = `item:x${{String(i).padStart(2,'0')}}`;
          nodes.push({{data:{{id,kind:'item',label:`条目 ${{i}}`,issue_date:'2026-08-08'}},position:{{x:3,y:i}},provenance:[{{path:'a'}}]}});
          edges.push({{data:{{id:'ei'+i,source:'direction:d1',target:id,relation:'has_item',label:'收录条目',confirmation:'explicit'}},provenance:[{{path:'a'}}]}});
          edges.push({{data:{{id:'ep'+i,source:id,target:'issue:2026-08-08',relation:'published_in',label:'发布于',confirmation:'explicit'}},provenance:[{{path:'a'}}]}});
        }}
        const graph = {{schema_version:1,archive_through_issue:'2026-08-08',knowledge_through_issue:'',input_digest:'sha256:'+'a'.repeat(64),stats:{{node_count:nodes.length,edge_count:edges.length,unresolved_count:0}},nodes,edges,unresolved:[]}};
        const model = data.buildKnowledgeGraphModel({{graph, params: {{lens: 'evolution', range: 'recent3'}}}});
        process.stdout.write(JSON.stringify({{
          nodeCount: model.limits.nodeCount, edgeCount: model.limits.edgeCount,
          truncated: model.limits.truncated, nodeLimit: model.limits.nodeLimit,
          focusKept: model.nodes.some((n) => n.data.id === model.focusId),
          noDanglingEdges: model.edges.every((e) => model.nodes.some((n) => n.data.id === e.data.source) && model.nodes.some((n) => n.data.id === e.data.target)),
          deterministic: JSON.stringify(model) === JSON.stringify(data.buildKnowledgeGraphModel({{graph, params: {{lens: 'evolution', range: 'recent3'}}}}))
        }}));
        """
    )

    assert output["nodeCount"] <= output["nodeLimit"]
    assert output["nodeLimit"] == 60
    assert output["truncated"] is True
    assert output["focusKept"] is True
    assert output["noDanglingEdges"] is True
    assert output["deterministic"] is True


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_hiding_node_kinds_never_leaves_dangling_edges():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        {GRAPH_DOC}
        const hideable = ['topic', 'direction', 'item', 'judgement', 'issue', 'roadmap', 'roadmap_branch', 'idea'];
        const results = {{}};
        for (const kind of hideable) {{
          const model = data.buildKnowledgeGraphModel({{graph: graphDoc, params: {{lens: 'evolution', range: 'all', hide: kind, overlay: 'roadmap,idea'}}}});
          const ids = new Set(model.nodes.map((n) => n.data.id));
          results[kind] = {{
            nodes: model.nodes.length,
            dangling: model.edges.filter((e) => !ids.has(e.data.source) || !ids.has(e.data.target)).length,
            kindGone: !model.nodes.some((n) => n.data.kind === kind),
          }};
        }}
        // Judgements lens exercises judgement + overlay kinds too.
        const judgementModel = data.buildKnowledgeGraphModel({{graph: graphDoc, params: {{lens: 'judgements', range: 'all', hide: 'topic', overlay: 'roadmap,idea'}}}});
        const judgementIds = new Set(judgementModel.nodes.map((n) => n.data.id));
        results.judgementsLensHideTopic = judgementModel.edges.filter((e) => !judgementIds.has(e.data.source) || !judgementIds.has(e.data.target)).length;
        process.stdout.write(JSON.stringify(results));
        """
    )

    for kind, result in output.items():
        if kind == "judgementsLensHideTopic":
            assert result == 0, "judgements lens keeps dangling edges after hiding a kind"
            continue
        assert result["dangling"] == 0, f"{kind}: dangling edges left after hiding"
        assert result["kindGone"] is True, f"{kind}: kind still present after hiding"
        assert result["nodes"] >= 0


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_topic_filter_constrains_judgements_and_issues_to_visible_items():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        {GRAPH_DOC}
        const filtered = data.buildKnowledgeGraphModel({{graph: graphDoc, params: {{lens: 'judgements', range: 'all', topic: 't1'}}}});
        const evolution = data.buildKnowledgeGraphModel({{graph: graphDoc, params: {{lens: 'evolution', range: 'all', topic: 't2'}}}});
        const ids = (model) => new Set(model.nodes.map((n) => n.data.id));
        const isolated = (model) => model.nodes.filter((n) => !model.edges.some((e) => e.data.source === n.data.id || e.data.target === n.data.id)).map((n) => n.data.id);
        process.stdout.write(JSON.stringify({{
          otherTopicJudgementHidden: !ids(filtered).has('judgement:2026-08-08:def'),
          ownTopicJudgementVisible: ids(filtered).has('judgement:2026-08-01:abc'),
          otherTopicItemsHidden: !ids(filtered).has('item:i3'),
          evolutionIsolated: isolated(evolution),
          evolutionIssues: [...ids(evolution)].filter((id) => id.startsWith('issue:')).sort(),
          deterministic: JSON.stringify(filtered) === JSON.stringify(data.buildKnowledgeGraphModel({{graph: graphDoc, params: {{lens: 'judgements', range: 'all', topic: 't1'}}}}))
        }}));
        """
    )

    assert output["otherTopicJudgementHidden"] is True
    assert output["ownTopicJudgementVisible"] is True
    assert output["otherTopicItemsHidden"] is True
    assert output["evolutionIsolated"] == [], "topic-filtered views must not contain isolated nodes"
    assert output["evolutionIssues"] == ["issue:2026-08-08"]
    assert output["deterministic"] is True


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_idea_evidence_projection_uses_published_graph_and_idea_fields_only():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        {GRAPH_DOC}
        const ideaRow = {{idea_id:'x1', title:'Idea 一', status:'observing'}};
        const idea = {{idea_id:'x1', title:'Idea 一', status:'observing', topic_ids:['t1'], unknowns:['成本边界'], hypothesis:'假设',
          evidence_for:[{{item_id:'i1', issue_date:'2026-08-01', source_urls:['https://example.com/i1'], reason:'显式支持'}}],
          evidence_against:[{{item_id:'i2', issue_date:'2026-08-08', source_urls:['https://example.com/i2'], reason:'显式挑战'}}],
          decision_log:[{{event_id:'d1', decision:'created', issue_date:'2026-08-01', reason:'创建'}}]}};
        const input = {{ideaRow, idea, graph: graphDoc, params: {{view:'evidence', mode:'graph', depth:'2'}}}};
        const one = data.buildIdeaEvidenceGraphModel(input);
        const two = data.buildIdeaEvidenceGraphModel(input);
        const oneHop = data.buildIdeaEvidenceGraphModel({{...input, params: {{view:'evidence', mode:'graph', depth:'1'}}}});
        const kinds = (model) => [...new Set(model.nodes.map((n) => n.data.kind))].sort();
        const relations = (model) => [...new Set(model.edges.map((e) => e.data.relation))].sort();
        process.stdout.write(JSON.stringify({{
          stable: JSON.stringify(one) === JSON.stringify(two),
          kinds: kinds(one), relations: relations(one),
          conflict: one.conflict, focus: one.focusId, usesPublishedGraph: one.usesPublishedGraph,
          secondHopOnly: relations(oneHop),
          assumptionEdges: one.edges.filter((e) => e.data.relation === 'qualifies').length,
          decisionEdges: one.edges.filter((e) => e.data.relation === 'leads_to').length,
          reverseDirections: one.edges.some((e) => (e.data.source === 'idea:x1' && ['supports_idea','challenges_idea'].includes(e.data.relation)))
        }}));
        """
    )

    assert output["stable"] is True
    assert output["usesPublishedGraph"] is True
    assert output["conflict"] is True
    assert output["focus"] == "idea:x1"
    for kind in ("idea", "item", "topic", "judgement", "issue", "roadmap_branch", "assumption", "decision"):
        assert kind in output["kinds"], kind
    for relation in ("supports_idea", "challenges_idea", "relates_to", "supports_judgement", "published_in", "uses_evidence", "qualifies", "leads_to"):
        assert relation in output["relations"], relation
    # One hop stops before issues/judgements/branches.
    assert "published_in" not in output["secondHopOnly"]
    assert "supports_judgement" not in output["secondHopOnly"]
    assert output["assumptionEdges"] == 1
    assert output["decisionEdges"] == 1
    assert output["reverseDirections"] is False


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_idea_evidence_projection_falls_back_to_explicit_idea_fields():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const ideaRow = {{idea_id:'i1', title:'可验证 Idea', status:'observing'}};
        const idea = {{idea_id:'i1', title:'可验证 Idea', status:'observing', topic_ids:['t1'], unknowns:['成本边界'],
          evidence_for:[{{item_id:'e1', issue_date:'2026-08-11', reason:'显式支持'}}],
          evidence_against:[{{item_id:'e2', issue_date:'2026-08-12', reason:'显式挑战'}}, {{item_id:'missing', issue_date:'2026-08-13', reason:'悬空引用'}}],
          decision_log:[{{event_id:'d1', decision:'created', issue_date:'2026-08-11'}}]}};
        const input = {{ideaRow, idea, graph: null, params: {{view:'evidence', mode:'graph', depth:'1'}},
          items:[{{item_id:'e1', title:'支持来源', url:'https://example.com/e1', issue_date:'2026-08-11'}}, {{item_id:'e2', title:'挑战来源', url:'https://example.com/e2', issue_date:'2026-08-12'}}]}};
        const model = data.buildIdeaEvidenceGraphModel(input);
        const again = data.buildIdeaEvidenceGraphModel(input);
        process.stdout.write(JSON.stringify({{
          stable: JSON.stringify(model) === JSON.stringify(again),
          kinds: [...new Set(model.nodes.map((n) => n.data.kind))].sort(),
          relations: [...new Set(model.edges.map((e) => e.data.relation))].sort(),
          unresolved: model.unresolved, conflict: model.conflict, usesPublishedGraph: model.usesPublishedGraph,
          danglingDrawn: model.edges.some((e) => e.data.source === 'item:missing' || e.data.target === 'item:missing'),
          focus: model.focusId,
          focusMissing: data.buildIdeaEvidenceGraphModel({{...input, params: {{view:'evidence', mode:'graph', depth:'1', node:'not-there'}}}}).requestedFocusMissing
        }}));
        """
    )

    assert output["stable"] is True
    assert output["usesPublishedGraph"] is False
    assert output["conflict"] is True
    assert output["danglingDrawn"] is False
    assert output["focus"] == "idea:i1"
    assert output["focusMissing"] is True
    assert any(row["reason"] == "missing_archive_item" and row["source_ref"] == "missing" for row in output["unresolved"])
    for kind in ("idea", "item", "topic", "assumption", "decision"):
        assert kind in output["kinds"], kind
    for relation in ("supports_idea", "challenges_idea", "relates_to", "qualifies", "leads_to"):
        assert relation in output["relations"], relation


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_renderer_adapter_style_tables_and_vendored_cytoscape():
    output = _run_node(
        f"""
        const styles = require({json.dumps(str(SITE / 'graph-styles.js'))});
        const renderer = require({json.dumps(str(SITE / 'graph-renderer.js'))});
        const cytoscape = require({json.dumps(str(SITE / 'assets' / 'vendor' / 'cytoscape.min.js'))});
        const publishedKinds = ['topic','direction','item','judgement','issue','roadmap','roadmap_branch','idea','assumption','decision'];
        const relations = ['has_direction','has_item','published_in','supports_judgement','tracks','organizes','uses_evidence','relates_to','supports_idea','challenges_idea','qualifies','leads_to'];
        const stylesheet = styles.cytoscapeStylesheet();
        const selectorText = stylesheet.map((entry) => entry.selector).join(' ');
        let failureReported = null;
        const beforeAvailable = renderer.available();
        globalThis.cytoscape = cytoscape;
        const afterAvailable = renderer.available();
        const handle = renderer.mountGraph({{}}, {{nodes: [], edges: [], onFailure: (error) => {{ failureReported = error ? String(error).slice(0, 60) : 'x'; }}}});
        renderer.destroyActive();
        delete globalThis.cytoscape;
        process.stdout.write(JSON.stringify({{
          cytoscapeType: typeof cytoscape, cytoscapeVersion: cytoscape.version,
          kindsCovered: publishedKinds.every((kind) => styles.KIND_META[kind] && styles.KIND_META[kind].label),
          relationsCovered: relations.every((relation) => styles.RELATION_META[relation] && styles.RELATION_META[relation].label),
          stylesheetNonEmpty: stylesheet.length > 20,
          selectorsCoverKinds: publishedKinds.every((kind) => selectorText.includes(`node[kind = "${{kind}}"]`)),
          selectorsCoverRelations: relations.every((relation) => selectorText.includes(`edge[relation = "${{relation}}"]`)),
          beforeAvailable, afterAvailable,
          invalidContainerReturnsNull: handle === null,
          failureReported: failureReported !== null
        }}));
        """
    )

    assert output["cytoscapeType"] == "function"
    assert output["cytoscapeVersion"] == "3.34.2"
    assert output["kindsCovered"] is True
    assert output["relationsCovered"] is True
    assert output["stylesheetNonEmpty"] is True
    assert output["selectorsCoverKinds"] is True
    assert output["selectorsCoverRelations"] is True
    assert output["beforeAvailable"] is False
    assert output["afterAvailable"] is True
    assert output["invalidContainerReturnsNull"] is True
    assert output["failureReported"] is True


LENS_REPRO = {
    "topic": "agent_acceleration",
    "counts": {"structure": (5, 4), "evolution": (20, 28), "judgements": (22, 25)},
}


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_lens_layout_gives_each_lens_its_own_focus_and_first_screen():
    """The design's reproduction fixture (agent_acceleration + recent3): each
    lens keeps its own node/edge set, and the initial viewport shows the
    objects the lens exists for instead of the shared Topic one-hop."""
    output = _run_node(
        f"""
        const fs = require('fs');
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const layout = require({json.dumps(str(SITE / 'knowledge-layout.js'))});
        const graph = JSON.parse(fs.readFileSync({json.dumps(str(ROOT / 'knowledge' / 'graph.json'))}, 'utf8'));
        const base = {{ topic: 'agent_acceleration', range: 'recent3' }};
        const lenses = ['structure', 'evolution', 'judgements'].map((lens) => {{
          const params = data.normalizeKnowledgeParams({{ ...base, lens }});
          const model = data.buildKnowledgeGraphModel({{ graph, params }});
          const built = layout.build(model, {{ lens, params }});
          const nodeById = new Map(model.nodes.map((n) => [n.data.id, n]));
          const focus = built.viewport ? nodeById.get(built.viewport.focusId) : null;
          const fitKinds = {{}};
          (built.viewport ? built.viewport.fitIds : []).forEach((id) => {{
            const node = nodeById.get(id);
            if (node) fitKinds[node.data.kind] = (fitKinds[node.data.kind] || 0) + 1;
          }});
          return {{
            lens,
            nodes: model.nodes.length,
            edges: model.edges.length,
            focusKind: focus ? focus.data.kind : null,
            fitKinds,
            automatic: built.viewport ? built.viewport.automatic : null,
            highlightIsFit: built.viewport ? JSON.stringify(built.viewport.highlightIds) === JSON.stringify(built.viewport.fitIds) : null,
            empty: Boolean(built.empty),
          }};
        }});
        process.stdout.write(JSON.stringify(lenses));
        """
    )
    by_lens = {row["lens"]: row for row in output}
    for lens, (nodes, edges) in LENS_REPRO["counts"].items():
        assert by_lens[lens]["nodes"] == nodes, lens
        assert by_lens[lens]["edges"] == edges, lens

    # Structure: focus is the Topic and the first screen is the whole skeleton.
    assert by_lens["structure"]["focusKind"] == "topic"
    assert by_lens["structure"]["fitKinds"] == {"topic": 1, "direction": 4}

    # Evolution: focus is a Direction, and the first screen contains at least
    # one item and one issue (the lens's own objects).
    assert by_lens["evolution"]["focusKind"] == "direction"
    assert by_lens["evolution"]["fitKinds"]["direction"] == 1
    assert by_lens["evolution"]["fitKinds"]["item"] >= 1
    assert by_lens["evolution"]["fitKinds"]["issue"] >= 1
    assert by_lens["evolution"]["automatic"] is True
    assert by_lens["evolution"]["highlightIsFit"] is True

    # Judgements: focus is the latest Judgement and the first screen contains
    # its explicit evidence items.
    assert by_lens["judgements"]["focusKind"] == "judgement"
    assert by_lens["judgements"]["fitKinds"]["judgement"] == 1
    assert by_lens["judgements"]["fitKinds"]["item"] >= 1
    assert by_lens["judgements"]["automatic"] is True


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_lens_layout_is_deterministic_and_has_no_coordinate_voids():
    """All topics × standard ranges: identical builds produce identical
    coordinates; every relation keeps max ≤ 4× median edge length (no filtered
    coordinate voids); coordinates stay bounded instead of retaining 10k-unit
    whole-graph rows."""
    output = _run_node(
        f"""
        const fs = require('fs');
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const layout = require({json.dumps(str(SITE / 'knowledge-layout.js'))});
        const graph = JSON.parse(fs.readFileSync({json.dumps(str(ROOT / 'knowledge' / 'graph.json'))}, 'utf8'));
        const topics = graph.nodes.filter((n) => n.data.kind === 'topic').map((n) => n.data.topic_id).sort();
        const violations = [];
        let maxAbs = 0;
        let deterministic = true;
        let checked = 0;
        for (const topic of topics) {{
          for (const range of ['latest', 'recent3', 'all']) {{
            for (const lens of ['structure', 'evolution', 'judgements']) {{
              const params = data.normalizeKnowledgeParams({{ topic, range, lens }});
              const model = data.buildKnowledgeGraphModel({{ graph, params }});
              const first = layout.build(model, {{ lens, params }});
              const second = layout.build(model, {{ lens, params }});
              if (JSON.stringify(first.positions) !== JSON.stringify(second.positions)) deterministic = false;
              if (!first.available) continue;
              checked += 1;
              for (const [id, pos] of Object.entries(first.positions)) {{
                maxAbs = Math.max(maxAbs, Math.abs(pos.x), Math.abs(pos.y));
                void id;
              }}
              const stats = layout.edgeStats(model, first.positions);
              for (const [relation, row] of Object.entries(stats)) {{
                // Semantic edges (has_item / published_in / supports_judgement)
                // must stay local to their lane or column: max ≤ 4× median.
                // Containment edges (has_direction, tracks, …) may span layout
                // context but are bounded outright.
                const semantic = ['has_item', 'published_in', 'supports_judgement'].includes(relation);
                const violated = semantic
                  ? (row.count >= 3 && row.median > 0 && row.max > row.median * 4)
                  : row.max > 4200;
                if (violated) violations.push({{ topic, range, lens, relation, ...row }});
              }}
            }}
          }}
        }}
        process.stdout.write(JSON.stringify({{ checked, deterministic, maxAbs, violations: violations.slice(0, 8) }}));
        """
    )
    assert output["deterministic"] is True
    assert output["checked"] > 0
    # No coordinate may retain a whole-graph row index (10k-unit voids).
    assert output["maxAbs"] < 10000, output["maxAbs"]
    assert output["violations"] == [], output["violations"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_lens_layout_reports_honest_empty_states():
    """Topics without lens-specific objects must be flagged as empty instead of
    rendering the shared skeleton as a successful lens switch; topics that do
    have objects must not be flagged."""
    output = _run_node(
        f"""
        const fs = require('fs');
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const layout = require({json.dumps(str(SITE / 'knowledge-layout.js'))});
        const graph = JSON.parse(fs.readFileSync({json.dumps(str(ROOT / 'knowledge' / 'graph.json'))}, 'utf8'));
        const probes = [
          ['ai_infra_horizontal', 'recent3', 'evolution'],
          ['ai_infra_horizontal', 'recent3', 'judgements'],
          ['dpu_inline', 'recent3', 'evolution'],
          ['dpu_inline', 'recent3', 'judgements'],
          ['tpn', 'recent3', 'judgements'],
          ['agent_acceleration', 'recent3', 'evolution'],
          ['tpn', 'recent3', 'evolution'],
        ];
        const rows = probes.map(([topic, range, lens]) => {{
          const params = data.normalizeKnowledgeParams({{ topic, range, lens }});
          const model = data.buildKnowledgeGraphModel({{ graph, params }});
          const built = layout.build(model, {{ lens, params }});
          return {{ topic, lens, empty: Boolean(built.empty), reason: built.empty ? built.empty.reason : null, viewport: Boolean(built.viewport) }};
        }});
        process.stdout.write(JSON.stringify(rows));
        """
    )
    rows = {(row["topic"], row["lens"]): row for row in output}
    for key in [
        ("ai_infra_horizontal", "evolution"),
        ("ai_infra_horizontal", "judgements"),
        ("dpu_inline", "evolution"),
        ("dpu_inline", "judgements"),
        ("tpn", "judgements"),
    ]:
        assert rows[key]["empty"] is True, key
        assert rows[key]["viewport"] is False, key
        assert rows[key]["reason"], key
    for key in [("agent_acceleration", "evolution"), ("tpn", "evolution")]:
        assert rows[key]["empty"] is False, key
        assert rows[key]["viewport"] is True, key


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_lens_truncation_keeps_explicit_scope_notice():
    """frontier_exploration reaches the soft cap; the model keeps the explicit
    truncation flag that the lens status line surfaces as a scope warning."""
    output = _run_node(
        f"""
        const fs = require('fs');
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const graph = JSON.parse(fs.readFileSync({json.dumps(str(ROOT / 'knowledge' / 'graph.json'))}, 'utf8'));
        const rows = ['evolution', 'judgements'].map((lens) => {{
          const params = data.normalizeKnowledgeParams({{ topic: 'frontier_exploration', range: 'recent3', lens }});
          const model = data.buildKnowledgeGraphModel({{ graph, params }});
          return {{ lens, nodes: model.nodes.length, truncated: model.limits.truncated, nodeLimit: model.limits.nodeLimit }};
        }});
        process.stdout.write(JSON.stringify(rows));
        """
    )
    for row in output:
        assert row["nodes"] == 60
        assert row["truncated"] is True
        assert row["nodeLimit"] == 60
