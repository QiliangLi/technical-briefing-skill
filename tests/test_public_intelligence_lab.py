import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_site_exposes_archive_grounded_roadmap_and_idea_bank():
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "site" / "intelligence-lab.js").read_text(encoding="utf-8")

    assert 'id="roadmap"' in html
    assert 'id="idea-bank-anchor"' in html
    assert 'src="./intelligence-lab.js"' in html
    assert 'href="./intelligence-lab.css"' in html
    assert "state.items.filter(item => item.role !== 'radar'" in js
    assert "issue.issueDoc?.synthesis?.project_insights" in js
    assert "insight.evidence_item_ids" in js
    assert "latest.next_action" in js
    assert "首次进入归档" in js


def test_idea_bank_uses_explicit_project_insights_not_synthetic_paper_relations():
    js = (ROOT / "site" / "intelligence-lab.js").read_text(encoding="utf-8")
    issue = json.loads((ROOT / "archive" / "issues" / "2026-08-17" / "issue.json").read_text(encoding="utf-8"))
    insights = issue["synthesis"]["project_insights"]

    assert insights
    assert all(row.get("next_action") and row.get("evidence_item_ids") for row in insights)
    assert "EXTENDS" not in js
    assert "USES" not in js
    assert "project_insights" in js
    assert "next_action" in js


def test_roadmap_relations_are_chronology_and_explicit_directions_only():
    js = (ROOT / "site" / "intelligence-lab.js").read_text(encoding="utf-8")

    assert "item.issue_date" in js
    assert "item.direction_name || item.direction_id" in js
    assert "firstSeen" in js
    assert "topic_name === topic" in js
