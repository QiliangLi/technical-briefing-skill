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


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_evidence_routes_are_normalized_and_aliases_preserve_query_state():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        process.stdout.write(JSON.stringify({{
          graph: data.parseRoute('#graph?idea=i1&depth=9&candidates=yes'),
          atlas: data.parseRoute('#atlas?issue=2026-08-29&mode=keyword'),
          path: data.parseRoute('#evidence?idea=i1'),
          gaps: data.parseRoute('#evidence?view=gaps&task=missing')
        }}));
        """
    )

    assert output["graph"] == {
        "name": "evidence",
        "params": {"idea": "i1", "depth": "1", "candidates": "0", "view": "graph"},
    }
    assert output["atlas"] == {
        "name": "evidence",
        "params": {
            "issue": "2026-08-29",
            "mode": "keyword",
            "view": "atlas",
            "scope": "all",
        },
    }
    assert output["path"] == {
        "name": "evidence",
        "params": {"idea": "i1", "view": "path"},
    }
    assert output["gaps"] == {
        "name": "evidence",
        "params": {"view": "gaps", "task": "missing"},
    }


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_graph_projection_is_stable_truthful_and_rejects_dangling_edges():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const graph = require({json.dumps(str(SITE / 'evidence-graph.js'))});
        const input = {{
          ideaRow: {{idea_id:'i1',title:'可验证 Idea',topic_ids:['t1'],status:'observing'}},
          idea: {{idea_id:'i1',title:'可验证 Idea',topic_ids:['t1'],status:'observing',unknowns:['成本边界'],
            evidence_for:[{{item_id:'e1',issue_date:'2026-08-11',reason:'显式支持'}}],
            evidence_against:[{{item_id:'e2',issue_date:'2026-08-12',reason:'显式挑战'}},{{item_id:'missing',issue_date:'2026-08-13',reason:'悬空引用'}}],
            decision_log:[{{event_id:'d1',decision:'created',issue_date:'2026-08-11'}}]}},
          items:[{{item_id:'e1',title:'支持来源',url:'https://example.com/e1',issue_date:'2026-08-11'}},{{item_id:'e2',title:'挑战来源',url:'https://example.com/e2',issue_date:'2026-08-12'}}],
          roadmaps:[{{topic_id:'t1',topic_name:'主题 1'}}],
          roadmapObjects:new Map([['t1',{{roadmap_id:'r1',branches:[{{evidence_item_ids:['e1','missing']}}]}}]]),
          params:{{view:'graph',depth:1,candidates:0,node:'not-there'}},
          candidateRelations:[{{source:'evidence:e1',target:'idea:i1',relation:'pending'}}]
        }};
        const first=data.buildEvidenceGraphModel(input);
        const second=data.buildEvidenceGraphModel(input);
        const layout1=graph.layoutEvidenceGraphModel(first);
        const layout2=graph.layoutEvidenceGraphModel(second);
        process.stdout.write(JSON.stringify({{
          stable:JSON.stringify(first)===JSON.stringify(second),
          stableLayout:JSON.stringify(layout1)===JSON.stringify(layout2),
          nodeKinds:first.nodes.map(n=>n.kind), relations:first.edges.map(e=>e.relation),
          unresolved:first.unresolved, conflict:first.conflict,
          candidates:first.edges.filter(e=>e.confirmation==='candidate').length,
          danglingDrawn:first.edges.some(e=>e.source==='evidence:missing'||e.target==='evidence:missing'),
          focus:first.focusId, requestedFocusMissing:first.requestedFocusMissing
        }}));
        """
    )

    assert output["stable"] is True
    assert output["stableLayout"] is True
    assert "claim" in output["nodeKinds"]
    assert "supports" in output["relations"]
    assert "challenges" in output["relations"]
    assert output["conflict"] is True
    assert output["candidates"] == 0
    assert output["danglingDrawn"] is False
    assert output["focus"] == "idea:i1"
    assert output["requestedFocusMissing"] is True
    assert any(row["reason"] == "missing_archive_item" for row in output["unresolved"])


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_graph_layout_avoids_overlaps_and_routes_edges_from_the_nearest_side():
    output = _run_node(
        f"""
        const graph = require({json.dumps(str(SITE / 'evidence-graph.js'))});
        const nodes = [
          {{id:'s',kind:'source',title:'S'}},{{id:'e',kind:'evidence',title:'E'}},
          {{id:'c',kind:'claim',title:'C'}},{{id:'i',kind:'idea',title:'I'}},
          {{id:'a1',kind:'assumption',title:'A1'}},{{id:'a2',kind:'assumption',title:'A2'}},
          {{id:'r',kind:'roadmap',title:'R'}},{{id:'d',kind:'decision',title:'D'}}
        ];
        const layout = graph.layoutEvidenceGraphModel({{nodes,edges:[],focusId:'i'}});
        const overlaps = [];
        for (let i=0;i<layout.nodes.length;i++) for (let j=i+1;j<layout.nodes.length;j++) {{
          const a=layout.nodes[i], b=layout.nodes[j];
          if (a.x < b.x+b.width && a.x+a.width > b.x && a.y < b.y+b.height && a.y+a.height > b.y) overlaps.push([a.id,b.id]);
        }}
        const right = graph.routeEvidenceEdge({{x:0,y:20,width:100,height:50}},{{x:180,y:50,width:90,height:50}});
        const left = graph.routeEvidenceEdge({{x:180,y:50,width:90,height:50}},{{x:0,y:20,width:100,height:50}});
        const up = graph.routeEvidenceEdge({{x:40,y:180,width:100,height:60}},{{x:40,y:20,width:100,height:60}});
        process.stdout.write(JSON.stringify({{
          overlaps,
          right:{{axis:right.axis,source:right.sourceAnchor,target:right.targetAnchor}},
          left:{{axis:left.axis,source:left.sourceAnchor,target:left.targetAnchor}},
          up:{{axis:up.axis,source:up.sourceAnchor,target:up.targetAnchor}}
        }}));
        """
    )

    assert output["overlaps"] == []
    assert output["right"]["axis"] == "horizontal"
    assert output["right"]["source"]["x"] == 100
    assert output["right"]["target"]["x"] == 180
    assert output["left"]["axis"] == "horizontal"
    assert output["left"]["source"]["x"] == 180
    assert output["left"]["target"]["x"] == 100
    assert output["up"]["axis"] == "vertical"
    assert output["up"]["source"]["y"] == 180
    assert output["up"]["target"]["y"] == 80


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_second_hop_expands_only_explicit_roadmap_evidence_and_honors_limits():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const refs=Array.from({{length:55}},(_,i)=>`r${{i}}`);
        const items=refs.map((id,i)=>({{item_id:id,title:`来源 ${{i}}`,url:`https://example.com/${{id}}`,issue_date:'2026-08-29'}}));
        const base={{ideaRow:{{idea_id:'i',title:'I',topic_ids:['t']}},idea:{{idea_id:'i',title:'I',topic_ids:['t'],evidence_for:[{{item_id:'r0'}}]}},items,
          roadmaps:[{{topic_id:'t',topic_name:'T'}}],roadmapObjects:new Map([['t',{{roadmap_id:'rm',branches:[{{evidence_item_ids:refs}}]}}]])}};
        const one=data.buildEvidenceGraphModel({{...base,params:{{view:'graph',depth:1}}}});
        const two=data.buildEvidenceGraphModel({{...base,params:{{view:'graph',depth:2}}}});
        process.stdout.write(JSON.stringify({{one:one.limits,two:two.limits,focusPresent:two.nodes.some(n=>n.id===two.focusId),relations:[...new Set(two.edges.map(e=>e.relation))]}}));
        """
    )

    assert output["one"]["nodeCount"] < output["two"]["nodeCount"]
    assert output["two"]["nodeCount"] <= 40
    assert output["two"]["edgeCount"] <= 80
    assert output["two"]["truncated"] is True
    assert output["focusPresent"] is True
    assert set(output["relations"]) <= {"declares", "supports", "leads_to"}


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_archive_atlas_uses_contains_edges_and_stable_aggregation_only():
    output = _run_node(
        f"""
        const data = require({json.dumps(str(SITE / 'data-contract.js'))});
        const graph = require({json.dumps(str(SITE / 'evidence-graph.js'))});
        const issues=[{{date:'2026-08-29',papers:Array.from({{length:7}},(_,i)=>({{item_id:`i${{i}}`,title:`条目 ${{i}}`,topic_id:'t',topic_name:'主题',url:`https://example.com/${{i}}`}}))}}];
        const first=data.buildArchiveAtlasModel({{issues,params:{{view:'atlas',scope:'all',mode:'topic'}}}});
        const second=data.buildArchiveAtlasModel({{issues,params:{{view:'atlas',scope:'all',mode:'topic'}}}});
        const layout=graph.layoutArchiveAtlasModel(first);
        process.stdout.write(JSON.stringify({{stable:JSON.stringify(first)===JSON.stringify(second),relations:[...new Set(first.edges.map(e=>e.relation))],kinds:first.nodes.map(n=>n.kind),layoutKinds:layout.nodes.map(n=>n.kind)}}));
        """
    )

    assert output["stable"] is True
    assert output["relations"] == ["contains"]
    assert "aggregate" in output["kinds"]
    assert set(output["layoutKinds"]) == {"issue", "topic", "archive_entry", "aggregate"}
