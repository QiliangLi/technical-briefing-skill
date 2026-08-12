from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup

import briefing_skill.publication_manifest as publication
from briefing_skill.publication_manifest import (
    finalize_radar_groups,
    publication_provenance_errors,
    radar_required_minimum,
)
from briefing_skill.utils import write_json


def _candidate(index: int, category: str) -> dict:
    return {
        "candidate_id": f"raw-{index}",
        "category": category,
        "title": f"signal-{index}",
        "summary": f"technical signal summary {index} with enough detail",
        "url": f"https://example.org/signal-{index}",
        "source_name": "example.org",
        "source_level": "A",
        "published_at": "2026-08-12",
    }


def test_radar_product_minimum_respects_legal_capacity():
    assert radar_required_minimum(8, 8) == 5
    assert radar_required_minimum(8, 4) == 4
    assert radar_required_minimum(7, 8) == 3
    assert radar_required_minimum(3, 8) == 3
    assert radar_required_minimum(0, 8) == 0


def test_current_run_reserve_refills_radar_without_historical_reference(monkeypatch):
    categories = ["AI Infra", "AI Infra", "Agent生态", "Agent生态", "KVCache生态", "KVCache生态", "存储与介质", "存储与介质"]
    candidates = [_candidate(index, category) for index, category in enumerate(categories, 1)]
    monkeypatch.setattr(publication, "build_radar_candidates", lambda service, run_id, issue: candidates)

    service = SimpleNamespace(
        config=SimpleNamespace(scoring={"radar": {"total_max": 8, "max_per_category": 2}}),
        _topic_appendix_cache={},
    )
    initially_selected = [
        {
            "name": "AI Infra",
            "items": [
                {
                    "title": "signal-1",
                    "summary": "selected signal",
                    "url": "https://example.org/signal-1",
                    "source_name": "example.org",
                    "published_at": "2026-08-12",
                }
            ],
        }
    ]

    groups, contract = finalize_radar_groups(
        service,
        initially_selected,
        issue_id=None,
        issue_data={"run_id": "current-run", "items": []},
    )
    items = [item for group in groups for item in group["items"]]

    assert contract["raw_eligible"] == 8
    assert contract["required_minimum"] == 5
    assert contract["final_count"] == 5
    assert len(items) == 5
    assert {item["url"] for item in items} <= {candidate["url"] for candidate in candidates}
    assert sum(bool(item.get("reserve_fill")) for item in items) == 4


def test_manual_radar_html_injection_fails_structured_provenance(tmp_path: Path):
    run_id = "run-1"
    manifest = {
        "version": 1,
        "issue_id": "issue-1",
        "run_id": run_id,
        "deep": [],
        "appendix": [],
        "radar": [
            {
                "category": "AI Infra",
                "title": "expected",
                "urls": ["https://example.org/expected"],
            }
        ],
        "radar_contract": {
            "raw_eligible": 1,
            "legal_capacity": 1,
            "required_minimum": 1,
            "final_count": 1,
        },
    }
    write_json(tmp_path / "workspace" / "runs" / run_id / "publication-manifest.json", manifest)
    html = """
    <html><body>
      <div data-reader-role="radar-item"><a href="https://example.org/expected">expected</a></div>
      <div data-reader-role="radar-item"><a href="https://example.org/manual-extra">manual</a></div>
    </body></html>
    """

    errors = publication_provenance_errors(tmp_path, run_id, html)
    assert any("Radar HTML provenance mismatch" in error for error in errors)


def test_radar_underfill_fails_even_when_html_shape_is_valid(tmp_path: Path):
    run_id = "run-2"
    manifest = {
        "version": 1,
        "issue_id": "issue-2",
        "run_id": run_id,
        "deep": [],
        "appendix": [],
        "radar": [
            {"category": "AI Infra", "title": "one", "urls": ["https://example.org/one"]}
        ],
        "radar_contract": {
            "raw_eligible": 8,
            "legal_capacity": 8,
            "required_minimum": 5,
            "final_count": 1,
        },
    }
    write_json(tmp_path / "workspace" / "runs" / run_id / "publication-manifest.json", manifest)
    html = '<div data-reader-role="radar-item"><a href="https://example.org/one">one</a></div>'

    errors = publication_provenance_errors(tmp_path, run_id, html)
    assert any("Final Radar underfilled: 1 items, required minimum 5" in error for error in errors)


def test_no_two_explanatory_rows_are_adjacent_in_realistic_layout(tmp_path: Path):
    from briefing_skill.illustrated_publication import render_illustrated_html

    base = """<html><body><table>
    <tr><td><table data-reader-role="judgement"><tr><td>judge</td></tr></table></td></tr>
    <tr><td><a id="topic-a"></a>A</td></tr>
    <tr data-reader-row="deep-row"><td>deep1</td></tr>
    <tr data-reader-row="deep-row"><td>deep2</td></tr>
    <tr><td><a id="topic-b"></a>B</td></tr>
    <tr data-reader-row="deep-row"><td>deep3</td></tr>
    <tr data-reader-row="deep-row"><td>deep4</td></tr>
    </table></body></html>"""
    illustrations = []
    for index in range(5):
        image = tmp_path / f"{index}.png"
        image.write_bytes(b"image")
        illustrations.append(
            {
                "concept_name": f"c{index}",
                "status": "generated",
                "placement": "after_judgements",
                "topic_id": None,
                "generated_asset_path": str(image),
                "alt": "x",
                "caption": "x",
                "persona_used": True,
            }
        )

    soup = BeautifulSoup(
        render_illustrated_html(
            tmp_path,
            base,
            {"status": "complete", "illustrations": illustrations, "notes": []},
        ),
        "html.parser",
    )
    rows = soup.select('tr[data-reader-role="explanatory-illustration"]')
    assert len(rows) == 5
    for row in rows:
        previous = row.find_previous_sibling("tr")
        next_row = row.find_next_sibling("tr")
        assert previous is None or previous.get("data-reader-role") != "explanatory-illustration"
        assert next_row is None or next_row.get("data-reader-role") != "explanatory-illustration"
