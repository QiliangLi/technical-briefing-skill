from pathlib import Path

from briefing_skill.publication_manifest import publication_provenance_errors
from briefing_skill.utils import write_json


def _manifest(run_id: str) -> dict:
    return {
        "version": 1,
        "issue_id": "issue-1",
        "run_id": run_id,
        "deep": [],
        "appendix": [],
        "radar": [
            {
                "category": "AI Infra",
                "title": "Expected technical signal",
                "urls": ["https://example.org/same-source"],
            }
        ],
        "radar_contract": {
            "raw_eligible": 1,
            "legal_capacity": 1,
            "required_minimum": 1,
            "final_count": 1,
        },
    }


def _write(tmp_path: Path, run_id: str) -> None:
    write_json(
        tmp_path / "workspace" / "runs" / run_id / "publication-manifest.json",
        _manifest(run_id),
    )


def test_same_radar_url_with_changed_title_still_fails_provenance(tmp_path: Path):
    run_id = "title-change"
    _write(tmp_path, run_id)
    html = """
    <table data-reader-role="radar-card" data-radar-category="AI Infra">
      <tr data-reader-role="radar-item"><td>
        <a href="https://example.org/same-source">Manually changed title</a>
      </td></tr>
    </table>
    """
    assert any(
        "Radar HTML provenance mismatch" in error
        for error in publication_provenance_errors(tmp_path, run_id, html)
    )


def test_same_radar_title_and_url_under_changed_category_fails_provenance(tmp_path: Path):
    run_id = "category-change"
    _write(tmp_path, run_id)
    html = """
    <table data-reader-role="radar-card" data-radar-category="Agent生态">
      <tr data-reader-role="radar-item"><td>
        <a href="https://example.org/same-source">Expected technical signal</a>
      </td></tr>
    </table>
    """
    assert any(
        "Radar HTML provenance mismatch" in error
        for error in publication_provenance_errors(tmp_path, run_id, html)
    )
